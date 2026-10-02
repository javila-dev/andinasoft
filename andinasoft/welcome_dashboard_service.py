"""
Dashboard de inicio (/welcome).

Cada sección está ligada a uno o más grupos de usuario y declara qué
métricas, gráficas y accesos rápidos necesita. Solo se consultan las fuentes
de las secciones que el usuario puede ver, y cada fuente se resuelve con UNA
consulta agregada por proyecto (Count/Sum con ``filter=``) en lugar de un
``count()`` por métrica.

Las secciones de accounting respetan el alcance contable del usuario
(empresas/oficinas, ``accounting.alcance``) y no dependen del proyecto.
"""
import calendar
import datetime
import logging
import re

from django.core.cache import cache
from django.db import DatabaseError
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from accounting.alcance import _apply_empresa_oficina, get_alcance
from accounting.gasto_aprobacion import alegra_sin_aprobacion_q, gasto_aprobacion_atraso_cutoff
from accounting.models import Facturas, GastoAprobador, Pagos, info_facturas, solicitud_anticipos
from crm.models import ActaReunion, CompromisoActa
from finance.models import recibos_internos
from andinasoft.models import Profiles, asesores
from andinasoft.models import empresas as EmpresasModel
from andinasoft.shared_models import (
    Adjudicacion,
    AsignacionComisiones,
    Inmuebles,
    Pqrs,
    PresupuestoCartera,
    Recaudos_general,
    RecaudosNoradicados,
    ventas_nuevas,
)
from andinasoft.presupuesto_cartera_service import proyectos_accesibles
from andinasoft.servicio_cliente_service import build_promesa_rows, clasificar_promesa

logger = logging.getLogger(__name__)

BIRTHDAY_WINDOW_DAYS = 15
CACHE_SECONDS = 120
TREND_MONTHS = 6
MAX_SHORTCUTS = 12

MESES_CORTOS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic')

# Estados de inventario agrupados para la gráfica. Lo que no está aquí (bloqueado,
# sin liberar, sin asignar…) cae en "No disponible"; "eliminado" se descarta.
INVENTARIO_CATEGORIAS = (
    {'key': 'adjudicado', 'label': 'Adjudicado', 'color': '#16855a'},
    {'key': 'reservado', 'label': 'Reservado', 'color': '#2a78d6'},
    {'key': 'libre', 'label': 'Libre', 'color': '#eda100'},
    {'key': 'no_disponible', 'label': 'No disponible', 'color': '#c5ccc9'},
)
INVENTARIO_DESCARTADOS = {'eliminado'}

# Recaudo = dinero efectivamente recibido. Mismo criterio de los SP oficiales
# (recaudos_cartera / recaudos_ventas: sin canjes, sin recibos 'N…' de novación y
# sin adjudicaciones desistidas), más lo que tampoco es dinero: devoluciones por
# desistimiento, anulados, recibos CC-AC-… (novaciones), cualquier forma de pago
# 'NOVACION…' y ajustes al peso. Las CxC sí cuentan (pago que entra por otra empresa).
RECAUDO_EXCLUIDO = ('Desistimiento', 'Anulado')
RECAUDO_FORMAS_NO_DINERO = ('Canje', 'Ajuste al peso', 'Desistimiento')


def recaudos_efectivos(db):
    """Recaudos_general de ``db`` que cuentan como dinero recibido."""
    return (
        Recaudos_general.objects.using(db)
        .filter(idadjudicacion__in=Adjudicacion.objects.using(db).exclude(estado='Desistido').values('pk'))
        .exclude(operacion__in=RECAUDO_EXCLUIDO)
        .exclude(formapago__in=RECAUDO_FORMAS_NO_DINERO)
        .exclude(formapago__istartswith='NOVACION')
        .exclude(numrecibo__startswith='N')
        .exclude(numrecibo__istartswith='CC-AC')
    )

# Cargos de la escala de comisiones que identifican al asesor de una venta.
CARGOS_ASESOR = ('8', '9', '99')  # Generador, Línea, Cerrador


# ─── Secciones ────────────────────────────────────────────────────────────────
# kpis.metric: clave en el dict de métricas. tone 'warn' resalta si > 0.
# fmt 'money' formatea como pesos. charts: claves de CHARTS.
# scope 'accounting': depende del alcance contable, no del proyecto.
# scope 'personal': pendientes propios del usuario, visibles sin importar el grupo.

SECTIONS = (
    {
        'key': 'pendientes',
        'title': 'Mis pendientes',
        'icon': 'fa-user-check',
        'groups': (),
        'scope': 'personal',
        'kpis': (
            {'metric': 'mis_gastos_por_aprobar', 'label': 'Gastos por aprobar', 'tone': 'warn', 'href': '/accounting/gastos-alegra/aprobar/'},
            {'metric': 'mis_gastos_atrasados', 'label': 'Gastos atrasados', 'tone': 'warn', 'href': '/accounting/gastos-alegra/aprobar/'},
            {'metric': 'mis_anticipos_por_aprobar', 'label': 'Anticipos a aprobar', 'tone': 'warn', 'href': '/accounting/solicitaranticipos'},
            {'metric': 'mis_anticipos_por_legalizar', 'label': 'Por legalizar', 'tone': 'warn', 'href': '/accounting/legalizaciones'},
        ),
        'shortcuts': (
            {'label': 'Aprobar gastos', 'icon': 'fa-check-circle', 'href': '/accounting/gastos-alegra/aprobar/'},
            {'label': 'Anticipos', 'icon': 'fa-hand-holding-usd', 'href': '/accounting/solicitaranticipos'},
        ),
    },
    {
        'key': 'comercial',
        'title': 'Gerencia comercial',
        'icon': 'fa-chart-line',
        'groups': ('Gerencia Comercial',),
        'kpis': (
            {'metric': 'ventas_mes', 'label': 'Ventas mes', 'href': '/projectselector/graph_ventas'},
            {'metric': 'ventas_pendientes', 'label': 'Por aprobar', 'tone': 'warn', 'href': '/projectselector/ventas_sin_aprobar'},
            {'metric': 'lotes_libres', 'label': 'Lotes libres', 'href': '/projectselector/inventario_ccial'},
            {'metric': 'asesores_activos', 'label': 'Asesores activos', 'href': '/projectselector/lista_asesores'},
        ),
        'charts': ('inventario',),
        'shortcuts': (
            {'label': 'Ventas sin aprobar', 'icon': 'fa-file-contract', 'href': '/projectselector/ventas_sin_aprobar'},
            {'label': 'GTT', 'icon': 'fa-money-check-alt', 'href': '/projectselector/gtt'},
            {'label': 'Simulador', 'icon': 'fa-calculator', 'href': '/simulador'},
            {'label': 'CRM', 'icon': 'fa-address-book', 'href': '/crm/principal'},
        ),
    },
    {
        'key': 'ventas_asesor',
        'title': 'Ventas por asesor',
        'icon': 'fa-handshake',
        'groups': ('Jefe Ventas', 'Gerencia Comercial'),
        'asesor_filter': True,
        'kpis': (
            {'metric': 'asesor_ventas_mes', 'label': 'Ventas mes', 'href': '/projectselector/graph_ventas'},
            {'metric': 'asesor_valor_mes', 'label': 'Valor vendido mes', 'fmt': 'money', 'href': '/projectselector/graph_ventas'},
            {'metric': 'asesor_ventas_pendientes', 'label': 'Sin aprobar', 'tone': 'warn', 'href': '/projectselector/ventas_sin_aprobar'},
        ),
        'charts': ('asesor_6m', 'inventario'),
        'shortcuts': (
            {'label': 'Nueva venta', 'icon': 'fa-plus-circle', 'href': '/projectselector/inventario_ccial'},
            {'label': 'Simulador', 'icon': 'fa-calculator', 'href': '/simulador'},
            {'label': 'CRM', 'icon': 'fa-address-book', 'href': '/crm/principal'},
        ),
    },
    {
        'key': 'operaciones',
        'title': 'Operaciones',
        'icon': 'fa-file-signature',
        'groups': ('Asistente Operaciones',),
        'kpis': (
            {'metric': 'ventas_por_adjudicar', 'label': 'Por adjudicar', 'tone': 'warn', 'href': '/projectselector/nueva_adjudicacion'},
            {'metric': 'adjudicadas_mes', 'label': 'Adjudicadas mes', 'href': '/projectselector/lista_adj'},
            {'metric': 'anuladas_mes', 'label': 'Anulados mes', 'href': '/projectselector/desistidos'},
            {'metric': 'desistidos_mes', 'label': 'Desistidos mes', 'href': '/projectselector/desistidos'},
        ),
        'shortcuts': (
            {'label': 'Reservas', 'icon': 'fa-bookmark', 'href': '/projectselector/nueva_adjudicacion'},
            {'label': 'Adjudicaciones', 'icon': 'fa-folder-open', 'href': '/projectselector/lista_adj'},
            {'label': 'Estados promesas', 'icon': 'fa-tasks', 'href': '/projectselector/promesas'},
            {'label': 'Buscar cliente', 'icon': 'fa-search', 'href': '/operaciones/buscar_cliente'},
        ),
    },
    {
        'key': 'recaudos',
        'title': 'Recaudos',
        'icon': 'fa-cash-register',
        'groups': ('Tesoreria',),
        'kpis': (
            {'metric': 'recaudo_mes_valor', 'label': 'Recaudo mes', 'fmt': 'money', 'href': '/tesoreria/lista_recaudos'},
            {'metric': 'recibos_mes', 'label': 'Recibos mes', 'href': '/tesoreria/lista_recaudos'},
            {'metric': 'mis_recibos_mes', 'label': 'Mis recibos', 'href': '/tesoreria/lista_recaudos'},
            {'metric': 'recibos_nr', 'label': 'No radicados', 'tone': 'warn', 'href': '/projectselector/recaudos_nr'},
            {'metric': 'solicitudes_pendientes', 'label': 'Solic. pendientes', 'tone': 'warn', 'href': '/finance/requirereceipts'},
            {'metric': 'solicitudes_manuales', 'label': 'Solic. manuales', 'tone': 'warn', 'href': '/finance/requirereceipts'},
        ),
        'charts': ('recaudo_6m',),
        'shortcuts': (
            {'label': 'Nuevo recaudo', 'icon': 'fa-receipt', 'href': '/projectselector/nuevo_recaudo'},
            {'label': 'Recaudos no radicados', 'icon': 'fa-inbox', 'href': '/projectselector/recaudos_nr'},
            {'label': 'Listado recaudos', 'icon': 'fa-list', 'href': '/tesoreria/lista_recaudos'},
        ),
    },
    {
        'key': 'pagos',
        'title': 'Pagos',
        'icon': 'fa-money-bill-wave',
        'groups': ('Tesoreria',),
        'scope': 'accounting',
        'kpis': (
            {'metric': 'facturas_por_pagar', 'label': 'Por pagar', 'tone': 'warn', 'href': '/accounting/pagarfactura'},
            {'metric': 'saldo_por_pagar', 'label': 'Saldo por pagar', 'fmt': 'money', 'href': '/accounting/pagarfactura'},
            {'metric': 'pagado_mes_valor', 'label': 'Pagado mes', 'fmt': 'money', 'href': '/accounting/listapagos'},
            {'metric': 'anticipos_por_girar', 'label': 'Anticipos a girar', 'tone': 'warn', 'href': '/accounting/solicitaranticipos'},
        ),
        'charts': ('pagos_6m',),
        'shortcuts': (
            {'label': 'Pagar facturas', 'icon': 'fa-money-check', 'href': '/accounting/pagarfactura'},
            {'label': 'Listado pagos', 'icon': 'fa-list-alt', 'href': '/accounting/listapagos'},
            {'label': 'Movimiento diario', 'icon': 'fa-exchange-alt', 'href': '/accounting/principal'},
            {'label': 'Caja efectivo', 'icon': 'fa-coins', 'href': '/accounting/cajasefectivo'},
        ),
    },
    {
        'key': 'contabilidad',
        'title': 'Contabilidad',
        'icon': 'fa-calculator',
        'groups': ('Contabilidad',),
        'scope': 'accounting',
        'kpis': (
            {'metric': 'facturas_radicadas_mes', 'label': 'Radicadas mes', 'href': '/accounting/listafacturas'},
            {'metric': 'facturas_por_causar', 'label': 'Por causar', 'tone': 'warn', 'href': '/accounting/causarfactura'},
            {'metric': 'gastos_por_asignar', 'label': 'Por asignar', 'tone': 'warn', 'href': '/accounting/gastos-alegra/asignar/'},
            {'metric': 'gastos_por_aprobar', 'label': 'En aprobación', 'href': '/accounting/gastos-alegra/aprobar/'},
            {'metric': 'gastos_atrasados', 'label': 'Atrasados', 'tone': 'warn', 'href': '/accounting/gastos-alegra/aprobar/'},
        ),
        'charts': ('radicados_6m',),
        'shortcuts': (
            {'label': 'Causar facturas', 'icon': 'fa-file-invoice', 'href': '/accounting/causarfactura'},
            {'label': 'Asignar gastos Alegra', 'icon': 'fa-tasks', 'href': '/accounting/gastos-alegra/asignar/'},
            {'label': 'Interfaces', 'icon': 'fa-file-export', 'href': '/projectselector/interfaces'},
            {'label': 'Informe de gastos', 'icon': 'fa-chart-pie', 'href': '/contabilidad/informes/gastos'},
        ),
    },
    {
        'key': 'cartera',
        'title': 'Cartera',
        'icon': 'fa-wallet',
        'groups': ('Supervisor Cartera', 'Gestor Cartera'),
        'kpis': (
            {'metric': 'clientes_cartera_ccial', 'label': 'Clientes ccial', 'href': '/cartera/dashboard'},
            {'metric': 'clientes_cartera_admin', 'label': 'Clientes admin', 'href': '/cartera/dashboard'},
            {'metric': 'presupuesto_cartera_valor', 'label': 'Presupuesto mes', 'fmt': 'money', 'href': '/projectselector/ver_ppto'},
            {'metric': 'recaudo_mes_valor', 'label': 'Recaudo mes', 'fmt': 'money', 'href': '/tesoreria/lista_recaudos'},
        ),
        'charts': ('recaudo_6m',),
        'shortcuts': (
            {'label': 'Dashboard de cartera', 'icon': 'fa-tachometer-alt', 'href': '/cartera/dashboard'},
            {'label': 'Edades de cartera', 'icon': 'fa-hourglass-half', 'href': '/projectselector/edades_cartera'},
            {'label': 'Solicitar recibo', 'icon': 'fa-file-invoice-dollar', 'href': '/finance/requirereceipts'},
            {'label': 'Buscar cliente', 'icon': 'fa-search', 'href': '/operaciones/buscar_cliente'},
        ),
    },
    {
        'key': 'servicio_cliente',
        'title': 'Servicio al cliente',
        'icon': 'fa-headset',
        'groups': ('Servicio Cliente',),
        'kpis': (
            {'metric': 'compromisos_hoy', 'label': 'Compromisos hoy', 'href': '/servicio_cliente/dashboard'},
            {'metric': 'compromisos_vencidos', 'label': 'Comp. vencidos', 'tone': 'warn', 'href': '/servicio_cliente/dashboard'},
            {'metric': 'reuniones_hoy', 'label': 'Reuniones hoy', 'href': '/crm/actas'},
            {'metric': 'entregas_vencidas', 'label': 'Entregas vencidas', 'tone': 'warn', 'href': '/servicio_cliente/dashboard'},
            {'metric': 'entregas_por_vencer', 'label': 'Entregas próximas', 'href': '/projectselector/promesas'},
            {'metric': 'escrituras_vencidas', 'label': 'Escrituras vencidas', 'tone': 'warn', 'href': '/servicio_cliente/dashboard'},
            {'metric': 'escrituras_tramite', 'label': 'En escrituración', 'href': '/servicio_cliente/dashboard'},
            {'metric': 'pqrs_abiertas', 'label': 'PQRS abiertas', 'href': '/projectselector/pqrs'},
            {'metric': 'pqrs_vencidas', 'label': 'PQRS vencidas', 'tone': 'warn', 'href': '/servicio_cliente/dashboard'},
        ),
        'shortcuts': (
            {'label': 'Dashboard SAC', 'icon': 'fa-tachometer-alt', 'href': '/servicio_cliente/dashboard'},
            {'label': 'PQRS', 'icon': 'fa-comment-dots', 'href': '/projectselector/pqrs'},
            {'label': 'Actas y compromisos', 'icon': 'fa-clipboard-check', 'href': '/crm/actas'},
            {'label': 'Buscar cliente', 'icon': 'fa-search', 'href': '/operaciones/buscar_cliente'},
        ),
    },
)

CHARTS = {
    'asesor_6m': {'title': 'Ventas por mes', 'type': 'columns', 'series': 'asesor_trend', 'field': 'total', 'fmt': 'count'},
    'recaudo_6m': {'title': 'Recaudo por mes', 'type': 'columns', 'series': 'recaudo_trend', 'field': 'valor', 'fmt': 'money'},
    'pagos_6m': {'title': 'Pagos por mes', 'type': 'columns', 'series': 'pagos_trend', 'field': 'valor', 'fmt': 'money', 'global': True},
    'radicados_6m': {'title': 'Facturas radicadas por oficina', 'type': 'stacked_columns', 'series': 'radicados_trend', 'global': True},
    'inventario': {'title': 'Inventario por proyecto', 'type': 'stacked'},
}

# Series de la gráfica de radicados (colores validados como par adyacente).
OFICINAS = (
    {'key': 'MEDELLIN', 'label': 'Medellín', 'color': '#16855a'},
    {'key': 'MONTERIA', 'label': 'Montería', 'color': '#2a78d6'},
)

# ─── Fuentes ──────────────────────────────────────────────────────────────────
# Cada fuente produce varias métricas con una sola consulta. METRIC_SOURCE
# permite saber qué fuentes ejecutar a partir de lo que piden las secciones.

PROJECT_SOURCES = {
    'ventas': ('ventas_mes', 'ventas_pendientes', 'ventas_por_adjudicar', 'anuladas_mes'),
    'ventas_asesor': ('asesor_ventas_mes', 'asesor_valor_mes', 'asesor_ventas_pendientes'),
    'inmuebles': ('lotes_libres',),
    'adjudicaciones': ('adjudicadas_mes', 'desistidos_mes'),
    'recaudos': ('recibos_mes', 'mis_recibos_mes', 'recaudo_mes_valor'),
    'recaudos_nr': ('recibos_nr',),
    'cartera': ('clientes_cartera_ccial', 'clientes_cartera_admin', 'presupuesto_cartera_valor'),
    'pqrs': ('pqrs_abiertas', 'pqrs_vencidas', 'pqrs_radicadas_mes', 'pqrs_cerradas_mes'),
    'promesas': ('entregas_vencidas', 'entregas_por_vencer', 'escrituras_vencidas', 'escrituras_tramite'),
    'asesor_trend': (),
    'recaudo_trend': (),
}

GLOBAL_SOURCES = {
    'asesores': ('asesores_activos',),
    'facturas': ('facturas_radicadas_mes',),
    'info_facturas': ('facturas_por_pagar', 'saldo_por_pagar', 'facturas_por_causar'),
    'gastos': ('gastos_por_asignar', 'gastos_por_aprobar', 'gastos_atrasados'),
    'pagos': ('pagado_mes_valor',),
    'anticipos': ('anticipos_por_girar',),
    'mis_pendientes': ('mis_gastos_por_aprobar', 'mis_gastos_atrasados',
                       'mis_anticipos_por_aprobar', 'mis_anticipos_por_legalizar'),
    'compromisos': ('compromisos_hoy', 'compromisos_vencidos', 'reuniones_hoy'),
    'solicitudes': ('solicitudes_pendientes', 'solicitudes_manuales'),
    'radicados_trend': (),
    'pagos_trend': (),
}

METRIC_SOURCE = {
    metric: source
    for sources in (PROJECT_SOURCES, GLOBAL_SOURCES)
    for source, metrics in sources.items()
    for metric in metrics
}

CHART_SOURCES = {
    'asesor_6m': {'asesor_trend'},
    'recaudo_6m': {'recaudo_trend'},
    'pagos_6m': {'pagos_trend'},
    'radicados_6m': {'radicados_trend'},
    'inventario': {'inmuebles'},
}


def _miles(value):
    return f'{int(round(value)):,}'.replace(',', '.')


def format_kpi(value, fmt=None):
    """(texto corto para la tarjeta, texto completo para el tooltip)."""
    if fmt != 'money':
        return _miles(value), _miles(value)
    full = f'${_miles(value)}'
    if abs(value) >= 1_000_000:
        return f'${_miles(value / 1_000_000)} M', full
    return full, full


def month_bounds(today):
    inicio = today.replace(day=1)
    fin = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return inicio, fin


def trend_months(today, count=TREND_MONTHS):
    """Primer día de los últimos ``count`` meses, del más antiguo al actual."""
    months = []
    year, month = today.year, today.month
    for _ in range(count):
        months.append(datetime.date(year, month, 1))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return months[::-1]


def visible_sections(group_names, is_superuser, has_pendientes=False, has_accounting=True):
    """Secciones que ve el usuario.

    has_pendientes: tiene algo propio que aprobar/legalizar (sección personal).
    has_accounting: tiene alcance contable; sin él se ocultan las secciones de accounting.
    """
    group_names = set(group_names)
    out = []
    for s in SECTIONS:
        scope = s.get('scope')
        if scope == 'personal':
            if has_pendientes:
                out.append(s)
            continue
        if scope == 'accounting' and not has_accounting:
            continue
        if is_superuser or group_names.intersection(s['groups']):
            out.append(s)
    return out


def required_sources(sections):
    metrics = {kpi['metric'] for s in sections for kpi in s['kpis']}
    sources = {METRIC_SOURCE[m] for m in metrics}
    for s in sections:
        for chart in s.get('charts', ()):
            sources |= CHART_SOURCES[chart]
    return sources


def user_project_names(user):
    """Proyectos activos a los que el usuario tiene acceso: el mismo universo que
    usan cartera y servicio al cliente (activos, con BD y sin Sotavento)."""
    return proyectos_accesibles(user)


def user_has_pendientes(user):
    """Es aprobador de gastos o tiene anticipos propios por aprobar/legalizar."""
    if GastoAprobador.objects.filter(user=user, activo=True).exists():
        return True
    return solicitud_anticipos.objects.filter(
        Q(quien_aprueba=user, estado='pendiente') | Q(usuario_solicita=user, estado='pagado')
    ).exists()


def _aware_day_start(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


def _month_key(value):
    if isinstance(value, datetime.datetime):
        value = value.date()
    return value.replace(day=1)


def inventario_categoria(estado):
    estado = (estado or '').strip().lower()
    if estado in INVENTARIO_DESCARTADOS:
        return None
    if estado in ('adjudicado', 'reservado', 'libre'):
        return estado
    return 'no_disponible'


def ventas_de_asesor_q(db, asesor):
    """Q sobre ventas_nuevas con las ventas donde ``asesor`` figura en la escala de
    comisiones como Generador, Línea o Cerrador. La escala se guarda con el id de
    la venta ('368') o con el de la adjudicación ('ADJ781'), según cuándo se cargó."""
    claves = set(
        AsignacionComisiones.objects.using(db)
        .filter(idgestor=asesor, idcargo__in=CARGOS_ASESOR)
        .values_list('idadjudicacion', flat=True)
    )
    ids = [int(c) for c in claves if c and c.isdigit()]
    adjs = [c for c in claves if c and not c.isdigit()]
    if not ids and not adjs:
        return None
    return Q(id_venta__in=ids) | Q(adj_id__in=adjs)


def _project_metrics(db, sources, user, today, asesor=None):
    """Métricas escalares y series de un proyecto: (metrics, series)."""
    inicio, fin = month_bounds(today)
    trend_start = trend_months(today)[0]
    username = user.username
    out = {}
    series = {}

    if 'ventas' in sources:
        mes = Q(fecha_contrato__range=(inicio, fin))
        out.update(ventas_nuevas.objects.using(db).aggregate(
            ventas_mes=Count('pk', filter=mes & ~Q(estado='Anulado')),
            ventas_pendientes=Count('pk', filter=Q(estado='Pendiente')),
            ventas_por_adjudicar=Count('pk', filter=Q(estado='Aprobado')),
            anuladas_mes=Count('pk', filter=mes & Q(estado='Anulado')),
        ))

    if sources & {'ventas_asesor', 'asesor_trend'}:
        # Sin asesor elegido = todas las ventas (incluye las que aún no tienen escala).
        ventas = ventas_nuevas.objects.using(db).exclude(estado='Anulado')
        if asesor:
            filtro = ventas_de_asesor_q(db, asesor)
            ventas = ventas.filter(filtro) if filtro is not None else ventas.none()
        if 'ventas_asesor' in sources:
            mes = Q(fecha_contrato__range=(inicio, fin))
            res = ventas.aggregate(
                asesor_ventas_mes=Count('pk', filter=mes),
                asesor_valor_mes=Sum('valor_venta', filter=mes),
                asesor_ventas_pendientes=Count('pk', filter=Q(estado='Pendiente')),
            )
            res['asesor_valor_mes'] = res['asesor_valor_mes'] or 0
            out.update(res)
        if 'asesor_trend' in sources:
            rows = (
                ventas.filter(fecha_contrato__range=(trend_start, fin))
                .annotate(mes=TruncMonth('fecha_contrato'))
                .values('mes')
                .annotate(total=Count('pk'))
            )
            series['asesor_trend'] = {_month_key(r['mes']): {'total': r['total']} for r in rows}

    if 'inmuebles' in sources:
        inventario = {}
        for row in Inmuebles.objects.using(db).values('estado').annotate(n=Count('pk')):
            categoria = inventario_categoria(row['estado'])
            if categoria:
                inventario[categoria] = inventario.get(categoria, 0) + row['n']
        series['inventario'] = inventario
        out['lotes_libres'] = inventario.get('libre', 0)

    if 'adjudicaciones' in sources:
        out.update(Adjudicacion.objects.using(db).aggregate(
            adjudicadas_mes=Count('pk', filter=Q(
                fecha__gte=_aware_day_start(inicio),
                fecha__lt=_aware_day_start(fin + datetime.timedelta(days=1)),
            )),
            desistidos_mes=Count('pk', filter=Q(fechadesistimiento__range=(inicio, fin))),
        ))

    if 'recaudos' in sources:
        res = recaudos_efectivos(db).filter(fecha__range=(inicio, fin)).aggregate(
            recibos_mes=Count('pk'),
            mis_recibos_mes=Count('pk', filter=Q(usuario=username)),
            recaudo_mes_valor=Sum('valor'),
        )
        res['recaudo_mes_valor'] = res['recaudo_mes_valor'] or 0
        out.update(res)

    if 'recaudo_trend' in sources:
        rows = (
            recaudos_efectivos(db)
            .filter(fecha__range=(trend_start, fin))
            .annotate(mes=TruncMonth('fecha'))
            .values('mes')
            .annotate(valor=Sum('valor'))
        )
        series['recaudo_trend'] = {_month_key(r['mes']): {'valor': r['valor'] or 0} for r in rows}

    if 'recaudos_nr' in sources:
        out['recibos_nr'] = RecaudosNoradicados.objects.using(db).count()

    if 'cartera' in sources:
        res = PresupuestoCartera.objects.using(db).filter(
            periodo=f'{today.year}{today.month:02d}'
        ).aggregate(
            clientes_cartera_ccial=Count('idadjudicacion', distinct=True, filter=Q(tipocartera='Comercial')),
            clientes_cartera_admin=Count('idadjudicacion', distinct=True, filter=Q(tipocartera='Administrativa')),
            presupuesto_cartera_valor=Sum('cuota'),
        )
        res['presupuesto_cartera_valor'] = res['presupuesto_cartera_valor'] or 0
        out.update(res)

    if 'pqrs' in sources:
        abierta = Q(estado='Abierta')
        out.update(Pqrs.objects.using(db).aggregate(
            pqrs_abiertas=Count('pk', filter=abierta),
            pqrs_vencidas=Count('pk', filter=abierta & Q(fecha_vencimiento__lt=today)),
            pqrs_radicadas_mes=Count('pk', filter=Q(fecha_radicado__range=(inicio, fin))),
            pqrs_cerradas_mes=Count('pk', filter=Q(fecha_respuesta__range=(inicio, fin), estado='Cerrado')),
        ))

    if 'promesas' in sources:
        conteo = dict.fromkeys(PROJECT_SOURCES['promesas'], 0)
        for row in build_promesa_rows(db):
            estado = clasificar_promesa(row)
            conteo['entregas_vencidas'] += estado['entrega_vencida']
            conteo['entregas_por_vencer'] += estado['entrega_por_vencer']
            conteo['escrituras_vencidas'] += estado['escritura_vencida']
            conteo['escrituras_tramite'] += estado['escritura_tramite']
        out.update(conteo)

    return out, series


def _facturas_scope(alcance):
    """Facturas vigentes dentro del alcance contable."""
    return _apply_empresa_oficina(Facturas.objects.filter(alegra_bill_deleted=False), alcance)


def _global_metrics(sources, user, projects, today, alcance):
    """Métricas que no son por proyecto: (metrics, series)."""
    inicio, fin = month_bounds(today)
    out = {}
    series = {}

    if 'asesores' in sources:
        out['asesores_activos'] = asesores.objects.filter(estado='Activo', tipo_asesor='Externo').count()

    if 'facturas' in sources:
        out['facturas_radicadas_mes'] = _facturas_scope(alcance).filter(
            fecharadicado__range=(inicio, fin)
        ).count()

    if 'info_facturas' in sources:
        # info_facturas es una vista con el saldo por radicado; misma base que los
        # listados de causar/pagar (sin los Alegra que aún esperan aprobación).
        qs = info_facturas.objects.exclude(
            radicado__in=Facturas.objects.filter(alegra_sin_aprobacion_q()).values('pk')
        )
        if alcance['empresa_ids'] is not None or alcance['oficinas'] is not None:
            qs = qs.filter(radicado__in=_facturas_scope(alcance).values('pk'))
        por_pagar = Q(ubicacion='Tesoreria', saldo__gt=0)
        res = qs.aggregate(
            facturas_por_pagar=Count('pk', filter=por_pagar),
            saldo_por_pagar=Sum('saldo', filter=por_pagar),
            facturas_por_causar=Count('pk', filter=Q(ubicacion='Contabilidad')),
        )
        res['saldo_por_pagar'] = res['saldo_por_pagar'] or 0
        out.update(res)

    if 'gastos' in sources or 'mis_pendientes' in sources:
        atrasado = Q(gasto_asignado_en__isnull=False, gasto_asignado_en__lte=gasto_aprobacion_atraso_cutoff())
        en_aprobacion = Q(gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION)
        alegra = Facturas.objects.filter(origen='Alegra', alegra_bill_deleted=False)
        if 'gastos' in sources:
            out.update(_apply_empresa_oficina(alegra, alcance).aggregate(
                gastos_por_asignar=Count('pk', filter=Q(gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION)),
                gastos_por_aprobar=Count('pk', filter=en_aprobacion),
                gastos_atrasados=Count('pk', filter=en_aprobacion & atrasado),
            ))
        if 'mis_pendientes' in sources:
            # Lo asignado al usuario es suyo, sin importar su alcance contable.
            out.update(alegra.filter(en_aprobacion, gasto_aprobador_asignado=user).aggregate(
                mis_gastos_por_aprobar=Count('pk'),
                mis_gastos_atrasados=Count('pk', filter=atrasado),
            ))
            out.update(solicitud_anticipos.objects.aggregate(
                mis_anticipos_por_aprobar=Count('pk', filter=Q(quien_aprueba=user, estado='pendiente')),
                mis_anticipos_por_legalizar=Count('pk', filter=Q(usuario_solicita=user, estado='pagado')),
            ))

    if 'pagos' in sources or 'pagos_trend' in sources:
        pagos = _apply_empresa_oficina(
            Pagos.objects.all(), alcance, empresa_field='empresa_id', oficina_field='nroradicado__oficina',
        )
        if 'pagos' in sources:
            out['pagado_mes_valor'] = pagos.filter(
                fecha_pago__range=(inicio, fin)
            ).aggregate(v=Sum('valor'))['v'] or 0
        if 'pagos_trend' in sources:
            rows = (
                pagos.filter(fecha_pago__range=(trend_months(today)[0], fin))
                .annotate(mes=TruncMonth('fecha_pago'))
                .values('mes')
                .annotate(valor=Sum('valor'))
            )
            series['pagos_trend'] = {_month_key(r['mes']): {'valor': r['valor'] or 0} for r in rows}

    if 'compromisos' in sources:
        # Las actas sin proyecto no dependen del filtro: se cuentan siempre.
        abiertos = CompromisoActa.objects.exclude(estado__in=['Cumplido', 'Cancelado']).filter(
            Q(acta__proyecto_id__in=projects) | Q(acta__proyecto__isnull=True),
        )
        if not user.is_superuser:
            abiertos = abiertos.filter(responsable=user)
        out.update(abiertos.aggregate(
            compromisos_hoy=Count('pk', filter=Q(fecha_compromiso=today)),
            compromisos_vencidos=Count('pk', filter=Q(fecha_compromiso__lt=today)),
        ))
        out['reuniones_hoy'] = ActaReunion.objects.filter(
            Q(proyecto_id__in=projects) | Q(proyecto__isnull=True), fecha_reunion=today,
        ).exclude(estado='Cancelada').count()

    if 'solicitudes' in sources:
        # Solicitudes de recibo (finance) sin recibo generado; mismos criterios del listado.
        sin_recibo = Q(recibo_asociado__isnull=True) | Q(recibo_asociado='')
        out.update(recibos_internos.objects.filter(anulado=False, proyecto_id__in=projects).aggregate(
            solicitudes_pendientes=Count('pk', filter=sin_recibo & Q(requiere_revision_manual=False)),
            solicitudes_manuales=Count('pk', filter=sin_recibo & Q(requiere_revision_manual=True)),
        ))

    if 'radicados_trend' in sources:
        rows = (
            _facturas_scope(alcance)
            .filter(fecharadicado__range=(trend_months(today)[0], fin), oficina__in=[o['key'] for o in OFICINAS])
            .annotate(mes=TruncMonth('fecharadicado'))
            .values('mes', 'oficina')
            .annotate(n=Count('pk'))
        )
        trend = {}
        for r in rows:
            trend.setdefault(_month_key(r['mes']), {})[r['oficina']] = r['n']
        series['radicados_trend'] = trend

    if 'anticipos' in sources:
        out['anticipos_por_girar'] = _apply_empresa_oficina(
            solicitud_anticipos.objects.filter(estado='aprobado'), alcance,
        ).count()

    return out, series


def collect_metrics(sources, user, projects, today, alcance=None, asesor=None):
    """Devuelve (totales, series_por_proyecto, series_globales, proyectos_con_error)."""
    project_sources = sources.intersection(PROJECT_SOURCES)
    totals = {}
    series = {}
    failed = []

    if project_sources:
        for db in projects:
            try:
                metrics, project_series = _project_metrics(db, project_sources, user, today, asesor)
            except DatabaseError:
                logger.exception('welcome: no se pudieron leer métricas de %s', db)
                failed.append(db)
                continue
            series[db] = project_series
            for key, value in metrics.items():
                totals[key] = totals.get(key, 0) + (value or 0)

    if alcance is None:
        alcance = {'empresa_ids': None, 'oficinas': None} if user.is_superuser else get_alcance(user)
    global_metrics, global_series = _global_metrics(
        sources, user, projects, today, alcance or {'empresa_ids': [], 'oficinas': []},
    )
    totals.update(global_metrics)
    return totals, series, global_series, failed


# ─── Gráficas ─────────────────────────────────────────────────────────────────

def _columns_chart(spec, series, today, global_series=None):
    months = trend_months(today)
    sources = [global_series or {}] if spec.get('global') else list(series.values())
    points = []
    for month in months:
        value = sum(
            (source.get(spec['series'], {}).get(month) or {}).get(spec['field'], 0) or 0
            for source in sources
        )
        points.append({
            'label': MESES_CORTOS[month.month - 1],
            'full': f'{MESES_CORTOS[month.month - 1]} {month.year}',
            'value': float(value),
            'partial': month == months[-1],
        })
    return {'title': spec['title'], 'type': 'columns', 'fmt': spec['fmt'], 'points': points}


def _stacked_columns_chart(spec, global_series, today):
    months = trend_months(today)
    data = (global_series or {}).get(spec['series'], {})
    points = []
    for month in months:
        values = {o['key']: (data.get(month) or {}).get(o['key'], 0) for o in OFICINAS}
        points.append({
            'label': MESES_CORTOS[month.month - 1],
            'full': f'{MESES_CORTOS[month.month - 1]} {month.year}',
            'values': values,
            'total': sum(values.values()),
            'partial': month == months[-1],
        })
    return {'title': spec['title'], 'type': 'stacked_columns', 'categories': list(OFICINAS), 'points': points}


def _inventory_chart(spec, series):
    rows = []
    for project, data in series.items():
        inventario = data.get('inventario')
        if not inventario:
            continue
        values = {c['key']: inventario.get(c['key'], 0) for c in INVENTARIO_CATEGORIAS}
        rows.append({'label': project, 'values': values, 'total': sum(values.values())})
    if not rows:
        return None
    return {
        'title': spec['title'],
        'type': 'stacked',
        'categories': list(INVENTARIO_CATEGORIAS),
        'rows': rows,
    }


def build_charts(sections, series, today, global_series=None):
    charts = {}
    for section in sections:
        for key in section.get('charts', ()):
            if key in charts:
                continue
            spec = CHARTS[key]
            if spec['type'] == 'columns':
                charts[key] = _columns_chart(spec, series, today, global_series)
            elif spec['type'] == 'stacked_columns':
                charts[key] = _stacked_columns_chart(spec, global_series, today)
            else:
                chart = _inventory_chart(spec, series)
                if chart:
                    charts[key] = chart
    return charts


# ─── Armado ───────────────────────────────────────────────────────────────────

def upcoming_birthdays(today, days=BIRTHDAY_WINDOW_DAYS):
    """Cumpleaños de usuarios activos en los próximos ``days`` días."""
    window = [today + datetime.timedelta(days=i) for i in range(days + 1)]
    month_days = {(d.month, d.day): d for d in window}
    # 29-feb se celebra el 28-feb en años no bisiestos.
    if (2, 28) in month_days and not calendar.isleap(today.year):
        month_days.setdefault((2, 29), month_days[(2, 28)])

    profiles = (
        Profiles.objects.filter(
            user__is_active=True,
            fecha_nacimiento__isnull=False,
            fecha_nacimiento__month__in={m for m, _ in month_days},
        )
        .select_related('user', 'avatar')
    )
    rows = []
    for profile in profiles:
        fn = profile.fecha_nacimiento
        fecha = month_days.get((fn.month, fn.day))
        if fecha is None:
            continue
        rows.append({
            'nombre': f'{profile.user.first_name} {profile.user.last_name}'.strip(),
            'fecha': fecha,
            'dias': (fecha - today).days,
            'avatar_url': profile.avatar.image.url if profile.avatar_id and profile.avatar.image else '',
        })
    rows.sort(key=lambda r: r['dias'])
    return rows


def _build_sections(sections, totals, charts):
    built = []
    seen_charts = set()
    for section in sections:
        kpis = []
        for kpi in section['kpis']:
            value = totals.get(kpi['metric'], 0) or 0
            display, full = format_kpi(value, kpi.get('fmt'))
            kpis.append({
                **kpi,
                'value': value,
                'display': display,
                'full': full,
                'alert': kpi.get('tone') == 'warn' and value > 0,
            })
        # La sección personal solo aparece si hay algo pendiente.
        if section.get('scope') == 'personal' and not any(k['value'] for k in kpis):
            continue
        # Una gráfica compartida (p. ej. inventario) se muestra solo la primera vez.
        section_charts = [k for k in section.get('charts', ()) if k in charts and k not in seen_charts]
        seen_charts.update(section_charts)
        built.append({
            **section, 'kpis': kpis, 'charts': section_charts,
            'size': section_size(section_charts, kpis),
            # "Flaca": sin gráfica y con una sola fila de KPIs; se apila con otra igual.
            'slim': not section_charts and len(kpis) <= 4,
        })
    return built


# Ancho (columnas de 12) preferido y mínimo de cada tamaño de bloque.
SPANS = {
    'full': (12, 12),     # 2+ gráficas: KPIs arriba y gráficas lado a lado
    'wide': (8, 6),       # 1 gráfica: KPIs y gráfica en paralelo
    'large': (8, 6),      # 7+ KPIs sin gráfica
    'half': (6, 6),       # 4+ KPIs
    'compact': (4, 3),    # pocos KPIs
}


def section_size(charts, kpis):
    if len(charts) >= 2:
        return 'full'
    if charts:
        return 'wide'
    if len(kpis) >= 7:
        return 'large'
    return 'half' if len(kpis) >= 4 else 'compact'


def pack_layout(items, cols=12):
    """Reparte los bloques en filas de ``cols`` columnas sin huecos.

    Recorre los bloques en orden; si el siguiente no cabe en lo que queda de la
    fila busca uno posterior que sí quepa, o encoge los ya puestos hasta su
    mínimo para hacerle espacio. Lo que sobra al cerrar la fila se reparte
    hasta el ancho preferido y el resto lo toma el último bloque.
    """
    pending = [dict(it) for it in items]
    out = []
    while pending:
        row, left = [], cols
        placed = True
        while placed and left > 0:
            placed = False
            for idx, item in enumerate(pending):
                slack = sum(r['span'] - r['min'] for r in row)
                if item['min'] > left + slack:
                    continue
                need = item['min'] - left
                for r in reversed(row):
                    if need <= 0:
                        break
                    take = min(need, r['span'] - r['min'])
                    r['span'] -= take
                    left += take
                    need -= take
                item['span'] = min(item['pref'], left)
                left -= item['span']
                row.append(item)
                pending.pop(idx)
                placed = True
                break
        for r in row:
            extra = min(left, r['pref'] - r['span'])
            r['span'] += extra
            left -= extra
        row[-1]['span'] += left
        out.extend(row)
    return out


def build_layout(sections):
    """Orden y ancho de cada bloque del mosaico.

    Las secciones "flacas" se apilan de a dos en una misma columna (una debajo de
    la otra) para emparejarse con una sección alta al lado, en vez de estirarse a
    su altura. Cumpleaños y accesos rápidos van en la fila del encabezado.
    """
    def block(kind, size, sections_):
        pref, minimum = SPANS[size]
        return {'kind': kind, 'size': size, 'sections': sections_, 'section': sections_[0],
                'pref': pref, 'min': minimum, 'span': pref}

    slim = [s for s in sections if s.get('slim')]
    pares = [slim[i:i + 2] for i in range(0, len(slim) - 1, 2)]
    apiladas = {id(s): par for par in pares for s in par}

    items = []
    for s in sections:
        par = apiladas.get(id(s))
        if par is None:
            items.append(block('section', s['size'], [s]))
        elif par[0] is s:
            items.append(block('stack', 'half', par))
    layout = pack_layout(items)
    for item in layout:
        item['big'] = item['span'] >= 7
    return layout


def build_shortcuts(sections, limit=MAX_SHORTCUTS):
    """Accesos de las secciones visibles, sin repetir. Con muchas secciones
    se toman por rondas (el primero de cada sección, luego el segundo…)."""
    columns = [list(s.get('shortcuts', ())) for s in sections]
    shortcuts, seen = [], set()
    depth = max((len(c) for c in columns), default=0)
    for i in range(depth):
        for column in columns:
            if i < len(column) and column[i]['href'] not in seen:
                seen.add(column[i]['href'])
                shortcuts.append(column[i])
    return shortcuts[:limit]


def user_empresas(alcance):
    """Empresas dentro del alcance contable, para el filtro (una consulta)."""
    if alcance is None:
        return []
    qs = EmpresasModel.objects.order_by('nombre')
    if alcance['empresa_ids'] is not None:
        qs = qs.filter(pk__in=alcance['empresa_ids'])
    return [
        {'id': nit, 'nombre': nombre, 'corto': nombre_corto_empresa(nombre)}
        for nit, nombre in qs.values_list('pk', 'nombre')
    ]


_SUFIJO_SOCIETARIO = re.compile(r'[\s,]+(S\.?\s?A\.?\s?S\.?|S\.?\s?A\.?|LTDA\.?)$', re.IGNORECASE)


def nombre_corto_empresa(nombre):
    """'ANDINA CONCEPTOS INMOBILIARIOS SAS' -> 'Andina Conceptos Inmobiliarios'."""
    return _SUFIJO_SOCIETARIO.sub('', (nombre or '').strip()).title()


def asesores_externos(today):
    """Asesores externos para el selector: activos y los retirados en la ventana de
    la gráfica (pueden tener ventas recientes). Una consulta."""
    desde = trend_months(today)[0]
    qs = (
        asesores.objects.filter(tipo_asesor='Externo')
        .filter(Q(estado='Activo') | Q(fecha_baja__gte=desde))
        .order_by('nombre')
        .values_list('pk', 'nombre')
    )
    return [{'id': cedula, 'nombre': (nombre or '').strip().title()} for cedula, nombre in qs]


def build_dashboard(user, today=None, proyectos=None, empresas=None, asesor=None):
    """Contexto del dashboard.

    ``proyectos`` (lista) filtra las secciones por proyecto y ``empresas`` (lista de
    NIT) las de accounting. Los valores a los que el usuario no tiene acceso se
    descartan; una lista vacía equivale a "todos".
    ``asesor`` (lista con una cédula) filtra la card de ventas por asesor.
    """
    today = today or timezone.localdate()
    projects = user_project_names(user)
    elegidos = set(proyectos or ())
    proyectos_activos = [p for p in projects if p in elegidos]
    scope_projects = proyectos_activos or projects

    alcance = {'empresa_ids': None, 'oficinas': None} if user.is_superuser else get_alcance(user)
    empresas_alcance = user_empresas(alcance)
    elegidas = set(empresas or ())
    empresas_activas = [e for e in empresas_alcance if e['id'] in elegidas]
    if empresas_activas:
        alcance = {**alcance, 'empresa_ids': [e['id'] for e in empresas_activas]}

    group_names = list(user.groups.values_list('name', flat=True))
    ve_asesores = user.is_superuser or bool(set(group_names) & {'Jefe Ventas', 'Gerencia Comercial'})
    lista_asesores = asesores_externos(today) if ve_asesores else []
    elegido = (asesor or [None])[0]
    asesor_activo = next((a for a in lista_asesores if a['id'] == elegido), None)

    cache_key = (
        f'welcome-dashboard:v16:{user.pk}:{today.isoformat()}:'
        f'{",".join(proyectos_activos) or "*"}:{",".join(e["id"] for e in empresas_activas) or "*"}:'
        f'{asesor_activo["id"] if asesor_activo else "*"}'
    )
    data = cache.get(cache_key)
    if data is None:
        sections = visible_sections(
            group_names, user.is_superuser,
            has_pendientes=user_has_pendientes(user),
            has_accounting=alcance is not None,
        )
        sources = required_sources(sections)
        totals, series, global_series, failed = collect_metrics(
            sources, user, scope_projects, today, alcance,
            asesor=asesor_activo['id'] if asesor_activo else None,
        )
        charts = build_charts(sections, series, today, global_series)
        data = {
            'sections': _build_sections(sections, totals, charts),
            'charts': charts,
            'shortcuts': build_shortcuts(sections),
            'failed_projects': failed,
            'groups': ['Superusuario'] if user.is_superuser else sorted(group_names),
            'has_accounting_sections': any(s.get('scope') == 'accounting' for s in sections),
            'generated_at': timezone.localtime(),
        }
        data['layout'] = build_layout(data['sections'])
        cache.set(cache_key, data, CACHE_SECONDS)

    return {
        **data,
        'projects': projects,
        'proyectos_activos': proyectos_activos,
        'empresas': empresas_alcance if data['has_accounting_sections'] else [],
        'empresas_activas': empresas_activas,
        'empresas_activas_ids': [e['id'] for e in empresas_activas],
        'asesores': lista_asesores,
        'asesor_activo': asesor_activo,
        'asesor_activo_ids': [asesor_activo['id']] if asesor_activo else [],
        'birthdays': upcoming_birthdays(today),
        'hoy': today,
        'mes_inicio': month_bounds(today)[0],
    }
