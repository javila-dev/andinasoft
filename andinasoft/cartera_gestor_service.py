"""
Servicios del dashboard de gestores de cobro.

Reutiliza edades_cartera_snapshot, InfoCartera.gestorasignado y seguimientos
(compromisos de pago) por base de datos de proyecto.
"""
from __future__ import annotations

import calendar
import datetime
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from andinasoft.edades_cartera_service import edades_cartera_snapshot
from andinasoft.informe_cartera_orm import (
    _dec,
    _recaudo_mes,
    _recaudo_nopptado,
    _recaudo_vencido,
)
from andinasoft.models import (
    CarteraCartaConfig,
    CarteraCartaEnvio,
    CarteraCartaGeneracion,
    CarteraCheckpoint,
    CarteraCartaPlantilla,
    clientes,
    proyectos as Proyectos,
)
from andinasoft.presupuesto_cartera_service import (
    ensure_presupuestos,
    periodo_actual,
    proyectos_accesibles,
)
from andinasoft.shared_models import (
    Adjudicacion,
    InfoCartera,
    PresupuestoCartera,
    Recaudos_general,
    Vista_Adjudicacion,
    saldos_adj,
    seguimientos,
    timeline,
)

NOTIF_PREVIEW_LIMIT = 5
# Solo compromisos "nuevos": el seguimiento se registro hace poco
COMPROMISO_REGISTRO_LOOKBACK_DAYS = 120
# Vencidos activos: la fecha pactada de pago no puede ser tan vieja (evita 2021 eternos)
COMPROMISO_VENCIDO_MAX_DIAS = 60

DEFAULT_CHECKPOINTS = (
    # codigo, label, dias_desde, dias_hasta, orden
    ('d30', '30 dias', 30, None, 10),
    ('d45', '45 dias', 45, None, 20),
    ('d60', '60 dias', 60, None, 30),
    ('d90', '90 dias o mas', 90, None, 40),
)

STUB_PLANTILLA = 'pdf/cartas_cobro/stub.html'
PLANTILLAS_POR_CODIGO = {
    'd30': 'pdf/cartas_cobro/lt30.html',
    'd45': 'pdf/cartas_cobro/lt60.html',
    'd60': 'pdf/cartas_cobro/lt90.html',
    'd90': 'pdf/cartas_cobro/d90.html',
}

CARTA_CIUDAD = 'Medellin'
CARTA_TELEFONO = '301 8585672'
CARTA_EMAIL = 'haroldtangarife@somosandina.co'
CARTA_FIRMA_NOMBRE = {
    'Oasis': 'OASIS DEL CARIBE',
}
CARTA_LOGO_STATIC = {
    'Oasis': 'img/logo_oasis.png',
    'Sandville Beach': 'img/sandville_beach.png',
    'Tesoro Escondido': 'img/logo-Tesoro-Escondido.png',
    'Perla del Mar': 'img/logo-perla-mar-nuevo.png',
    'Vegas de Venecia': 'img/logo_vegas_de_venecia.png',
    'Carmelo Reservado': 'img/logo_carmelo_reservado.png',
}
CARTA_FONDO_DEFAULT = 'img/bg-andina.jpg'
CARTA_FONDO_STATIC = {
    # PNG carta (Letter) por proyecto, cuando existan:
    # 'Oasis': 'img/cartas_cobro/oasis.png',
}
MESES_ES = (
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
)

BUCKET_KEYS = (
    ('por_vencer', 'Al dia / por vencer', 0),
    ('lt30', '0 a 30', 1),
    ('lt60', '30 a 60', 31),
    ('lt90', '60 a 90', 61),
    ('lt120', '90 a 120', 91),
    ('gt120', 'Mas de 120', 121),
)

BUCKET_LABELS = {codigo: label for codigo, label, _ in BUCKET_KEYS}
BUCKET_CODIGOS = frozenset(BUCKET_LABELS)


def plantilla_html_por_codigo(codigo: str) -> str:
    return PLANTILLAS_POR_CODIGO.get(codigo) or STUB_PLANTILLA


_UNIDADES_ES = (
    'cero', 'un', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve',
)
_ESPECIALES_ES = {
    10: 'diez', 11: 'once', 12: 'doce', 13: 'trece', 14: 'catorce', 15: 'quince',
    16: 'dieciseis', 17: 'diecisiete', 18: 'dieciocho', 19: 'diecinueve',
    20: 'veinte', 21: 'veintiun', 22: 'veintidos', 23: 'veintitres',
    24: 'veinticuatro', 25: 'veinticinco', 26: 'veintiseis', 27: 'veintisiete',
    28: 'veintiocho', 29: 'veintinueve',
}
_DECENAS_ES = {
    30: 'treinta', 40: 'cuarenta', 50: 'cincuenta', 60: 'sesenta',
    70: 'setenta', 80: 'ochenta', 90: 'noventa',
}


def dias_en_letras(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    if n < 0:
        n = 0
    if n < 10:
        return _UNIDADES_ES[n]
    if n in _ESPECIALES_ES:
        return _ESPECIALES_ES[n]
    if n < 100:
        dec = (n // 10) * 10
        uni = n % 10
        base = _DECENAS_ES.get(dec, '')
        if uni == 0:
            return base
        return f'{base} y {_UNIDADES_ES[uni]}'
    if n == 100:
        return 'cien'
    if n < 200:
        resto = n - 100
        return f'ciento {dias_en_letras(resto)}'
    if n < 1000:
        cent = (n // 100) * 100
        resto = n % 100
        centenas = {
            200: 'doscientos', 300: 'trescientos', 400: 'cuatrocientos',
            500: 'quinientos', 600: 'seiscientos', 700: 'setecientos',
            800: 'ochocientos', 900: 'novecientos',
        }
        base = centenas.get(cent, '')
        if resto == 0:
            return base
        return f'{base} {dias_en_letras(resto)}'
    return str(n)


def fecha_en_letras(value) -> str:
    if value is None:
        return ''
    if isinstance(value, datetime.datetime):
        value = value.date()
    if not isinstance(value, datetime.date):
        return str(value)
    mes = MESES_ES[value.month] if 1 <= value.month <= 12 else ''
    return f'{value.day} de {mes} del {value.year}'


def id_cuota_label(tipocta, nrocta) -> str:
    tipo = (tipocta or '').strip().upper()
    if nrocta is None or nrocta == '':
        return tipo
    try:
        nro = int(nrocta)
    except (TypeError, ValueError):
        return f'{tipo}{nrocta}'
    return f'{tipo}{nro}'


def firma_proyecto_carta(proyecto: str) -> str:
    """Fallback de firma (sin consultar BD). Las cartas usan contacto_carta_proyecto."""
    key = (proyecto or '').strip()
    return CARTA_FIRMA_NOMBRE.get(key) or key.upper()


def contacto_carta_proyecto(proyecto: str, *, config=None, lookup=True) -> dict:
    """Telefono, correo y nombre de firma para pie / Atentamente, por proyecto."""
    key = (proyecto or '').strip()
    firma = firma_proyecto_carta(key)
    telefono = CARTA_TELEFONO
    email = CARTA_EMAIL
    if lookup and config is None:
        try:
            config = CarteraCartaConfig.objects.filter(proyecto_id=key).first()
        except Exception:
            config = None
    if config is not None:
        if (getattr(config, 'firma_nombre', None) or '').strip():
            firma = config.firma_nombre.strip()
        telefono = (getattr(config, 'telefono', None) or '').strip()
        email = (getattr(config, 'email', None) or '').strip()
    return {
        'firma_nombre': firma,
        'telefono': telefono,
        'email': email,
    }


def listar_config_cartas(nombres):
    """Filas de UI: contacto efectivo por proyecto (BD o fallback)."""
    nombres = list(nombres or [])
    by_p = {
        c.proyecto_id: c
        for c in CarteraCartaConfig.objects.filter(proyecto_id__in=nombres)
    }
    rows = []
    for nombre in nombres:
        cfg = by_p.get(nombre)
        contacto = contacto_carta_proyecto(nombre, config=cfg, lookup=False)
        rows.append({
            'proyecto': nombre,
            'firma_nombre': (cfg.firma_nombre or '').strip() if cfg else '',
            'firma_placeholder': contacto['firma_nombre'],
            'telefono': contacto['telefono'],
            'email': contacto['email'],
        })
    return rows


def guardar_config_cartas(items, *, permitidos):
    """Crea/actualiza CarteraCartaConfig. items: dicts proyecto/firma_nombre/telefono/email."""
    permitidos = set(permitidos or [])
    saved = 0
    for item in items or []:
        proyecto = (item.get('proyecto') or '').strip()
        if not proyecto or proyecto not in permitidos:
            continue
        if not Proyectos.objects.filter(pk=proyecto).exists():
            continue
        CarteraCartaConfig.objects.update_or_create(
            proyecto_id=proyecto,
            defaults={
                'firma_nombre': (item.get('firma_nombre') or '').strip()[:120],
                'telefono': (item.get('telefono') or '').strip()[:40],
                'email': (item.get('email') or '').strip()[:120],
            },
        )
        saved += 1
    return saved


def logo_carta_static(proyecto: str) -> str:
    return CARTA_LOGO_STATIC.get((proyecto or '').strip()) or ''


def fondo_carta_static(proyecto: str) -> str:
    return CARTA_FONDO_STATIC.get((proyecto or '').strip()) or CARTA_FONDO_DEFAULT


def resolver_plantilla_carta(checkpoint):
    rec = plantilla_activa_checkpoint(checkpoint)
    mapped = PLANTILLAS_POR_CODIGO.get(getattr(checkpoint, 'codigo', None))
    if rec is None and not mapped:
        return None
    return {
        'motor': rec.motor if rec else CarteraCartaPlantilla.MOTOR_WEASYPRINT,
        'plantilla': mapped or rec.plantilla,
        'record': rec,
    }


def gestor_nombre_from_user(user) -> str:
    return f'{user.first_name} {user.last_name}'.upper().strip()


def is_supervisor_cartera(user) -> bool:
    """Solo grupo Supervisor Cartera (y superuser)."""
    if getattr(user, 'is_superuser', False):
        return True
    return user.groups.filter(name='Supervisor Cartera').exists()


def ensure_default_checkpoints(proyecto: str) -> None:
    """Crea checkpoints de carta (30/45/60/90+) si el proyecto aun no tiene ninguno."""
    try:
        proyecto_obj = Proyectos.objects.get(pk=proyecto)
    except Proyectos.DoesNotExist:
        return
    if CarteraCheckpoint.objects.filter(proyecto=proyecto_obj).exists():
        return
    for codigo, label, dias_desde, dias_hasta, orden in DEFAULT_CHECKPOINTS:
        ck = CarteraCheckpoint.objects.create(
            proyecto=proyecto_obj,
            codigo=codigo,
            label=label,
            dias_desde=dias_desde,
            dias_hasta=dias_hasta,
            orden=orden,
            activo=True,
        )
        CarteraCartaPlantilla.objects.create(
            checkpoint=ck,
            motor=CarteraCartaPlantilla.MOTOR_WEASYPRINT,
            plantilla=plantilla_html_por_codigo(codigo),
            activo=True,
        )


def filter_snapshot_for_gestor(adjudicaciones, user):
    """Supervisor ve todo; gestor solo su cartera asignada."""
    if is_supervisor_cartera(user):
        return list(adjudicaciones)
    nombre = gestor_nombre_from_user(user)
    if not nombre:
        return []
    return [
        row for row in adjudicaciones
        if (row.get('gestor') or '').upper().strip() == nombre
        or nombre in (row.get('gestor') or '').upper()
    ]


def bucket_codigo_from_dias(dias_mora: int) -> str:
    d = int(dias_mora or 0)
    if d <= 0:
        return 'por_vencer'
    if d <= 30:
        return 'lt30'
    if d <= 60:
        return 'lt60'
    if d <= 90:
        return 'lt90'
    if d <= 120:
        return 'lt120'
    return 'gt120'


def monto_bucket(row: dict, codigo: str) -> Decimal:
    if codigo == 'por_vencer':
        return Decimal(row.get('por_vencer') or 0)
    return Decimal(row.get(codigo) or 0)


def visual_nodes_cartas(checkpoints, dias_mora, total_pendiente):
    """Nodos de la linea visual: 30 / 45 / 60 / 90+. Activo = ultimo umbral alcanzado."""
    try:
        dias = int(dias_mora or 0)
    except (TypeError, ValueError):
        dias = 0
    total = Decimal(total_pendiente or 0)
    alcanzado = [ck for ck in checkpoints if int(ck.dias_desde or 0) <= dias]
    activo_codigo = alcanzado[-1].codigo if alcanzado else None
    nodes = []
    for ck in checkpoints:
        umbral = int(ck.dias_desde or 0)
        es_activo = ck.codigo == activo_codigo
        if umbral >= 90:
            label = '90 días+'
        else:
            label = f'{umbral} días'
        nodes.append({
            'codigo': ck.codigo,
            'label': label,
            'monto': total if es_activo else Decimal(0),
            'activo': es_activo,
            'superado': umbral <= dias and not es_activo,
            'umbral': umbral,
        })
    return nodes


def _parse_fecha_compromiso(raw):
    if raw is None or raw == '':
        return None
    if isinstance(raw, datetime.datetime):
        return raw.date()
    if isinstance(raw, datetime.date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d', '%d-%m-%Y'):
        try:
            return datetime.datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _cliente_map(proyecto: str, adj_ids):
    if not adj_ids:
        return {}
    return {
        row['IdAdjudicacion']: (row.get('Nombre') or '')
        for row in Vista_Adjudicacion.objects.using(proyecto)
        .filter(IdAdjudicacion__in=adj_ids)
        .values('IdAdjudicacion', 'Nombre')
    }


def _recaudo_adj_desde_lista(by_adj_fechas, adj, desde):
    total = Decimal(0)
    for fecha, valor in by_adj_fechas.get(adj, []):
        f = fecha.date() if isinstance(fecha, datetime.datetime) else fecha
        if f is not None and f >= desde:
            total += valor
    return total


def evaluar_cumplimiento_compromiso(proyecto, adj, fecha_compromiso, valor, *, today=None, recaudos_cache=None):
    """
    Verifica si el compromiso de pago se cumplio.

    Regla: suma de recibos reales (Recaudos_general, excluye N*/A*) desde la
    fecha_compromiso inclusive >= valor_compromiso → cumplido.
    """
    today = today or datetime.date.today()
    fecha_c = _parse_fecha_compromiso(fecha_compromiso)
    valor = Decimal(valor or 0)
    if not fecha_c or valor <= 0:
        return {
            'estado': 'sin_compromiso',
            'label': 'Sin compromiso',
            'recaudo': Decimal(0),
            'faltante': Decimal(0),
            'fecha_compromiso': None,
            'valor': Decimal(0),
        }

    if recaudos_cache is not None:
        recaudo = _recaudo_adj_desde_lista(recaudos_cache, adj, fecha_c)
    else:
        total = (
            Recaudos_general.objects.using(proyecto)
            .filter(idadjudicacion=adj, fecha__gte=fecha_c)
            .exclude(numrecibo__startswith='N')
            .exclude(numrecibo__startswith='A')
            .aggregate(t=Sum('valor'))
            .get('t')
        )
        recaudo = Decimal(total or 0)

    faltante = max(valor - recaudo, Decimal(0))
    if recaudo >= valor:
        estado, label = 'cumplido', 'Cumplido'
    elif fecha_c > today:
        estado, label = 'pendiente', 'Por pagar'
    elif fecha_c == today:
        estado, label = 'hoy', 'Paga hoy'
    else:
        estado, label = 'vencido', 'Vencido'

    return {
        'estado': estado,
        'label': label,
        'recaudo': recaudo,
        'faltante': faltante,
        'fecha_compromiso': fecha_c,
        'valor': valor,
    }


def compromisos_gestor(proyecto: str, adj_ids, *, today=None):
    """
    Compromisos MANUALES del gestor (seguimientos recientes con valor_compromiso).

    - Ignora registros viejos (seguimiento.fecha fuera del lookback).
    - Ignora fechas de compromiso vencidas hace mas de COMPROMISO_VENCIDO_MAX_DIAS.
    - Cumplimiento: recaudo real desde fecha_compromiso >= valor → no se lista.
    """
    today = today or datetime.date.today()
    hoy_list = []
    vencidos_list = []
    if not adj_ids:
        return {'hoy': hoy_list, 'vencidos': vencidos_list, 'count_hoy': 0}

    registro_desde = today - datetime.timedelta(days=COMPROMISO_REGISTRO_LOOKBACK_DAYS)
    vencido_desde = today - datetime.timedelta(days=COMPROMISO_VENCIDO_MAX_DIAS)

    clientes = _cliente_map(proyecto, adj_ids)
    rows = list(
        seguimientos.objects.using(proyecto)
        .filter(adj__in=adj_ids, valor_compromiso__gt=0, fecha__gte=registro_desde)
        .order_by('-fecha', '-id_seg')
    )

    # Ultimo compromiso por ADJ segun fecha de registro del seguimiento (no 2021)
    latest_by_adj = {}
    for seg in rows:
        fecha_c = _parse_fecha_compromiso(seg.fecha_compromiso)
        if not fecha_c:
            continue
        valor = int(seg.valor_compromiso or 0)
        if valor <= 0:
            continue
        prev = latest_by_adj.get(seg.adj)
        if prev is None:
            latest_by_adj[seg.adj] = (seg.fecha, seg, fecha_c, valor)
            continue
        prev_fecha, prev_seg, _, _ = prev
        if seg.fecha > prev_fecha or (seg.fecha == prev_fecha and seg.id_seg > prev_seg.id_seg):
            latest_by_adj[seg.adj] = (seg.fecha, seg, fecha_c, valor)

    venc_candidates = []
    for adj, (_reg, seg, fecha_c, valor) in latest_by_adj.items():
        item = {
            'proyecto': proyecto,
            'adj': adj,
            'cliente': clientes.get(adj, ''),
            'valor': valor,
            'fecha_compromiso': fecha_c,
            'fecha_registro': seg.fecha,
            'tipo_seguimiento': seg.tipo_seguimiento or '',
            'comentarios': seg.respuesta_cliente or '',
            'usuario': str(seg.usuario or ''),
            'id_seg': seg.id_seg,
            'es_hoy': fecha_c == today,
        }
        if fecha_c == today:
            hoy_list.append(item)
        elif fecha_c < today:
            if fecha_c < vencido_desde:
                continue  # demasiado viejo para seguirlo como activo
            venc_candidates.append(item)
        # fecha_c > today: proximo; no entra a alertas de hoy/vencidos

    if venc_candidates:
        min_fecha = min(i['fecha_compromiso'] for i in venc_candidates)
        recaudos_rows = (
            Recaudos_general.objects.using(proyecto)
            .filter(
                idadjudicacion__in=[i['adj'] for i in venc_candidates],
                fecha__gte=min_fecha,
            )
            .exclude(numrecibo__startswith='N')
            .exclude(numrecibo__startswith='A')
            .values_list('idadjudicacion', 'fecha', 'valor')
        )
        by_adj = {}
        for adj, fecha, valor in recaudos_rows:
            by_adj.setdefault(adj, []).append((fecha, Decimal(valor or 0)))

        for item in venc_candidates:
            ev = evaluar_cumplimiento_compromiso(
                proyecto,
                item['adj'],
                item['fecha_compromiso'],
                item['valor'],
                today=today,
                recaudos_cache=by_adj,
            )
            if ev['estado'] == 'cumplido':
                continue
            item['recaudo_desde'] = ev['recaudo']
            item['faltante'] = ev['faltante']
            item['estado'] = ev['estado']
            item['estado_label'] = ev['label']
            vencidos_list.append(item)

    for item in hoy_list:
        item['estado'] = 'hoy'
        item['estado_label'] = 'Paga hoy'

    hoy_list.sort(key=lambda x: (x['cliente'], x['adj']))
    vencidos_list.sort(key=lambda x: (x['fecha_compromiso'], x['cliente']))
    return {'hoy': hoy_list, 'vencidos': vencidos_list, 'count_hoy': len(hoy_list)}


def fechas_pactadas_gestor(proyecto: str, adj_ids, *, today=None):
    """
    Fechas pactadas = cuotas del plan con saldo (saldos_cuotas), 1 linea por cliente/ADJ.

    Muestra cuantas cuotas vencidas/hoy y dias de mora (max). No es compromiso manual.
    """
    today = today or datetime.date.today()
    hoy_list = []
    vencidos_list = []
    if not adj_ids:
        return {'hoy': hoy_list, 'vencidos': vencidos_list, 'count_hoy': 0, 'count_vencidos': 0}

    clientes = _cliente_map(proyecto, adj_ids)
    cuotas = (
        saldos_adj.objects.using(proyecto)
        .filter(adj__in=adj_ids, saldocuota__gt=0, fecha__lte=today)
        .values('adj', 'fecha', 'saldocuota', 'diasmora')
    )

    by_adj = {}
    for c in cuotas:
        adj = c['adj']
        bucket = by_adj.setdefault(adj, {
            'valor': Decimal(0),
            'cuotas_vencidas': 0,
            'cuotas_hoy': 0,
            'dias_mora': 0,
            'fecha_pactada': None,
        })
        fecha = c['fecha']
        if isinstance(fecha, datetime.datetime):
            fecha = fecha.date()
        saldo = Decimal(c['saldocuota'] or 0)
        dias = int(c['diasmora'] or 0)
        bucket['valor'] += saldo
        if dias > bucket['dias_mora']:
            bucket['dias_mora'] = dias
        if fecha == today:
            bucket['cuotas_hoy'] += 1
        elif fecha is not None and fecha < today:
            bucket['cuotas_vencidas'] += 1
            if bucket['fecha_pactada'] is None or fecha < bucket['fecha_pactada']:
                bucket['fecha_pactada'] = fecha
        if bucket['fecha_pactada'] is None and fecha is not None:
            bucket['fecha_pactada'] = fecha

    for adj, data in by_adj.items():
        if data['cuotas_vencidas'] <= 0 and data['cuotas_hoy'] <= 0:
            continue
        es_hoy = data['cuotas_vencidas'] <= 0 and data['cuotas_hoy'] > 0
        item = {
            'proyecto': proyecto,
            'adj': adj,
            'cliente': clientes.get(adj, ''),
            'valor': data['valor'],
            'fecha_pactada': data['fecha_pactada'] or today,
            'cuotas_vencidas': data['cuotas_vencidas'],
            'cuotas_hoy': data['cuotas_hoy'],
            'cuotas_pendientes': data['cuotas_vencidas'] + data['cuotas_hoy'],
            'dias_mora': data['dias_mora'],
            'es_hoy': es_hoy,
        }
        if es_hoy:
            hoy_list.append(item)
        else:
            vencidos_list.append(item)

    hoy_list.sort(key=lambda x: (x['cliente'], x['adj']))
    vencidos_list.sort(key=lambda x: (-x['dias_mora'], x['cliente']))
    return {
        'hoy': hoy_list,
        'vencidos': vencidos_list,
        'count_hoy': len(hoy_list),
        'count_vencidos': len(vencidos_list),
    }


def _latest_compromisos_by_adj(proyecto, adj_ids, *, today):
    """Ultimo compromiso abierto por ADJ (valor>0), con estado hoy/manana/roto/futuro/cumplido."""
    if not adj_ids:
        return {}
    registro_desde = today - datetime.timedelta(days=COMPROMISO_REGISTRO_LOOKBACK_DAYS)
    vencido_desde = today - datetime.timedelta(days=COMPROMISO_VENCIDO_MAX_DIAS)
    manana = today + datetime.timedelta(days=1)
    rows = list(
        seguimientos.objects.using(proyecto)
        .filter(adj__in=adj_ids, valor_compromiso__gt=0, fecha__gte=registro_desde)
        .order_by('-fecha', '-id_seg')
    )
    latest = {}
    for seg in rows:
        fecha_c = _parse_fecha_compromiso(seg.fecha_compromiso)
        if not fecha_c:
            continue
        valor = int(seg.valor_compromiso or 0)
        if valor <= 0:
            continue
        prev = latest.get(seg.adj)
        if prev is None or seg.fecha > prev['fecha_registro'] or (
            seg.fecha == prev['fecha_registro'] and seg.id_seg > prev['id_seg']
        ):
            latest[seg.adj] = {
                'adj': seg.adj,
                'valor': valor,
                'fecha_compromiso': fecha_c,
                'fecha_registro': seg.fecha,
                'id_seg': seg.id_seg,
                'usuario': str(seg.usuario or ''),
            }

    # Evaluar cumplimiento solo para vencidos
    venc_adjs = [
        adj for adj, c in latest.items()
        if c['fecha_compromiso'] < today and c['fecha_compromiso'] >= vencido_desde
    ]
    recaudos_cache = {}
    if venc_adjs:
        min_f = min(latest[a]['fecha_compromiso'] for a in venc_adjs)
        for adj_id, fecha, valor in (
            Recaudos_general.objects.using(proyecto)
            .filter(idadjudicacion__in=venc_adjs, fecha__gte=min_f)
            .exclude(numrecibo__startswith='N')
            .exclude(numrecibo__startswith='A')
            .values_list('idadjudicacion', 'fecha', 'valor')
        ):
            recaudos_cache.setdefault(adj_id, []).append((fecha, Decimal(valor or 0)))

    out = {}
    for adj, c in latest.items():
        fecha_c = c['fecha_compromiso']
        if fecha_c == today:
            estado = 'hoy'
        elif fecha_c == manana:
            estado = 'manana'
        elif fecha_c < today:
            if fecha_c < vencido_desde:
                continue
            ev = evaluar_cumplimiento_compromiso(
                proyecto, adj, fecha_c, c['valor'], today=today, recaudos_cache=recaudos_cache,
            )
            if ev['estado'] == 'cumplido':
                continue
            c['faltante'] = ev['faltante']
            c['recaudo'] = ev['recaudo']
            estado = 'roto'
        else:
            # futuro > manana: no entra a cola A
            continue
        c['estado'] = estado
        out[adj] = c
    return out


def _cuotas_resumen_by_adj(proyecto, adj_ids, *, today):
    """Resumen de cuotas con saldo: hoy, manana, vencidas (+ fecha vencida mas reciente)."""
    if not adj_ids:
        return {}
    manana = today + datetime.timedelta(days=1)
    cuotas = (
        saldos_adj.objects.using(proyecto)
        .filter(adj__in=adj_ids, saldocuota__gt=0, fecha__lte=manana)
        .values('adj', 'fecha', 'saldocuota', 'diasmora')
    )
    by_adj = {}
    for c in cuotas:
        adj = c['adj']
        bucket = by_adj.setdefault(adj, {
            'valor_hoy': Decimal(0),
            'valor_manana': Decimal(0),
            'valor_vencido': Decimal(0),
            'cuotas_hoy': 0,
            'cuotas_manana': 0,
            'cuotas_vencidas': 0,
            'dias_mora': 0,
            'fecha_vencida_reciente': None,
            'fecha_vencida_antigua': None,
        })
        fecha = c['fecha']
        if isinstance(fecha, datetime.datetime):
            fecha = fecha.date()
        saldo = Decimal(c['saldocuota'] or 0)
        dias = int(c['diasmora'] or 0)
        if dias > bucket['dias_mora']:
            bucket['dias_mora'] = dias
        if fecha == today:
            bucket['cuotas_hoy'] += 1
            bucket['valor_hoy'] += saldo
        elif fecha == manana:
            bucket['cuotas_manana'] += 1
            bucket['valor_manana'] += saldo
        elif fecha is not None and fecha < today:
            bucket['cuotas_vencidas'] += 1
            bucket['valor_vencido'] += saldo
            if bucket['fecha_vencida_reciente'] is None or fecha > bucket['fecha_vencida_reciente']:
                bucket['fecha_vencida_reciente'] = fecha
            if bucket['fecha_vencida_antigua'] is None or fecha < bucket['fecha_vencida_antigua']:
                bucket['fecha_vencida_antigua'] = fecha
    return by_adj


def colas_cobranza_gestor(proyecto: str, adj_ids, *, today=None):
    """
    Dos colas de trabajo del gestor (1 fila por ADJ):

    A) Cobrar hoy/manana: compromisos (hoy, manana, rotos) + cuotas pactadas hoy/manana.
    B) En mora: ADJs con cuotas vencidas excluyendo los de A.
       Orden: fecha de cuota vencida mas reciente → mas antigua.
    """
    today = today or datetime.date.today()
    manana = today + datetime.timedelta(days=1)
    if not adj_ids:
        return {
            'cobrar_hoy': [],
            'en_mora': [],
            'count_a': 0,
            'count_b': 0,
        }

    clientes = _cliente_map(proyecto, adj_ids)
    comps = _latest_compromisos_by_adj(proyecto, adj_ids, today=today)
    cuotas = _cuotas_resumen_by_adj(proyecto, adj_ids, today=today)

    cola_a = {}
    # Compromisos elegibles
    for adj, c in comps.items():
        tags = []
        if c['estado'] == 'roto':
            tags.append('Compromiso incumplido')
        elif c['estado'] == 'hoy':
            tags.append('Compromiso hoy')
        elif c['estado'] == 'manana':
            tags.append('Compromiso manana')
        else:
            continue
        cola_a[adj] = {
            'proyecto': proyecto,
            'adj': adj,
            'cliente': clientes.get(adj, ''),
            'tags': tags,
            'valor': Decimal(c['faltante'] if c.get('faltante') is not None else c['valor']),
            'valor_compromiso': Decimal(c['valor']),
            'fecha_compromiso': c['fecha_compromiso'],
            'faltante': c.get('faltante'),
            'prioridad': 0 if c['estado'] == 'roto' else (1 if c['estado'] == 'hoy' else 2),
            'motivo_principal': tags[0],
            'es_roto': c['estado'] == 'roto',
            'es_hoy': c['estado'] == 'hoy',
            'es_manana': c['estado'] == 'manana',
        }

    # Cuotas hoy / manana
    for adj, q in cuotas.items():
        if q['cuotas_hoy'] <= 0 and q['cuotas_manana'] <= 0:
            continue
        item = cola_a.get(adj)
        if item is None:
            item = {
                'proyecto': proyecto,
                'adj': adj,
                'cliente': clientes.get(adj, ''),
                'tags': [],
                'valor': Decimal(0),
                'valor_compromiso': Decimal(0),
                'fecha_compromiso': None,
                'faltante': None,
                'prioridad': 1,
                'motivo_principal': '',
                'es_roto': False,
                'es_hoy': False,
                'es_manana': False,
            }
            cola_a[adj] = item
        if q['cuotas_hoy'] > 0:
            item['tags'].append(f"Cuota hoy ({q['cuotas_hoy']})")
            item['es_hoy'] = True
            item['prioridad'] = min(item['prioridad'], 1)
        if q['cuotas_manana'] > 0:
            item['tags'].append(f"Cuota manana ({q['cuotas_manana']})")
            item['es_manana'] = True
            if not item['es_roto'] and not item['es_hoy']:
                item['prioridad'] = min(item['prioridad'], 2)
        # Valor: compromiso (faltante si roto) manda; si no, cuotas hoy+manana
        if item['valor_compromiso']:
            item['valor'] = (
                item['faltante'] if item.get('faltante') is not None else item['valor_compromiso']
            )
        else:
            item['valor'] = q['valor_hoy'] + q['valor_manana']
        if not item['motivo_principal']:
            item['motivo_principal'] = item['tags'][0] if item['tags'] else 'Cobrar'

    # Normalizar tags unicos y motivo
    for item in cola_a.values():
        # dedupe tags preserving order
        seen = set()
        tags = []
        for t in item['tags']:
            if t not in seen:
                seen.add(t)
                tags.append(t)
        item['tags'] = tags
        item['motivo_principal'] = tags[0] if tags else 'Cobrar'
        item['cuotas_vencidas'] = (cuotas.get(item['adj']) or {}).get('cuotas_vencidas', 0)
        item['dias_mora'] = (cuotas.get(item['adj']) or {}).get('dias_mora', 0)

    cobrar_hoy = list(cola_a.values())
    cobrar_hoy.sort(key=lambda x: (
        x['prioridad'],
        -float(x['valor'] or 0),
        (x['cliente'] or '').upper(),
        x['adj'],
    ))

    # Cola B: vencidas fuera de A
    en_mora = []
    for adj, q in cuotas.items():
        if adj in cola_a:
            continue
        if q['cuotas_vencidas'] <= 0:
            continue
        en_mora.append({
            'proyecto': proyecto,
            'adj': adj,
            'cliente': clientes.get(adj, ''),
            'valor': q['valor_vencido'],
            'cuotas_vencidas': q['cuotas_vencidas'],
            'dias_mora': q['dias_mora'],
            'fecha_vencida_reciente': q['fecha_vencida_reciente'],
            'fecha_vencida_antigua': q['fecha_vencida_antigua'],
            'tags': [f"{q['cuotas_vencidas']} cuota(s) vencida(s)"],
            'motivo_principal': 'Cuota vencida',
        })
    # Mas reciente (fecha cuota vencida) → mas antigua
    en_mora.sort(key=lambda x: (
        -(x['fecha_vencida_reciente'].toordinal() if x['fecha_vencida_reciente'] else 0),
        -float(x['valor'] or 0),
        (x['cliente'] or '').upper(),
    ))

    return {
        'cobrar_hoy': cobrar_hoy,
        'en_mora': en_mora,
        'count_a': len(cobrar_hoy),
        'count_b': len(en_mora),
        'manana': manana,
    }


def kpis_from_rows(rows, compromisos, fechas_pactadas=None):
    dist = {k: Decimal(0) for k, _, _ in BUCKET_KEYS}
    dist_count = {k: 0 for k, _, _ in BUCKET_KEYS}
    total_pendiente = Decimal(0)
    for row in rows:
        dist['por_vencer'] += Decimal(row.get('por_vencer') or 0)
        dist['lt30'] += Decimal(row.get('lt30') or 0)
        dist['lt60'] += Decimal(row.get('lt60') or 0)
        dist['lt90'] += Decimal(row.get('lt90') or 0)
        dist['lt120'] += Decimal(row.get('lt120') or 0)
        dist['gt120'] += Decimal(row.get('gt120') or 0)
        total_pendiente += Decimal(row.get('total_pendiente') or 0)
        codigo = bucket_codigo_from_dias(row.get('dias_mora') or 0)
        dist_count[codigo] = dist_count.get(codigo, 0) + 1

    total_mora = (
        dist['lt30'] + dist['lt60'] + dist['lt90'] + dist['lt120'] + dist['gt120']
    )
    fp = fechas_pactadas or {}
    return {
        'clientes': len(rows),
        'total_mora': total_mora,
        'total_pendiente': total_pendiente,
        'compromisos_hoy': compromisos.get('count_hoy', 0),
        'compromisos_vencidos': len(compromisos.get('vencidos') or []),
        'fechas_pactadas_hoy': fp.get('count_hoy', 0),
        'fechas_pactadas_vencidas': fp.get('count_vencidos', len(fp.get('vencidos') or [])),
        'distribucion': dist,
        'distribucion_count': dist_count,
    }


def _recaudo_vacio():
    z = Decimal('0')
    return {
        'recaudo_total': z,
        'recaudo_cuota_mes': z,
        'recaudo_vencido': z,
        'recaudo_nopptado': z,
    }


def _clasificar_recaudos_adj(recaudo_by_adj, ppto_by_adj):
    """
    Misma clasificacion que informe_cartera / presupuesto:
    cuota mes, vencido y no esperado (por encima del presupuesto).
    """
    tot = Decimal('0')
    mes = Decimal('0')
    venc = Decimal('0')
    nop = Decimal('0')
    for adj, recaudo in recaudo_by_adj.items():
        r = _dec(recaudo)
        if r <= 0:
            continue
        p = ppto_by_adj.get(adj) or {}
        ppto_mes = _dec(p.get('ppto_mes'))
        ppto_vencido = _dec(p.get('ppto_vencido'))
        presupuesto = _dec(p.get('presupuesto'))
        tot += r
        mes += _recaudo_mes(r, ppto_vencido, ppto_mes, presupuesto)
        venc += _recaudo_vencido(r, ppto_vencido)
        nop += _recaudo_nopptado(r, presupuesto)
    return {
        'recaudo_total': tot,
        'recaudo_cuota_mes': mes,
        'recaudo_vencido': venc,
        'recaudo_nopptado': nop,
    }


def _adj_ids_alcance_recaudo(proyecto, user, periodo, snapshot_adj_ids):
    """
    ADJs del gestor para medir recaudo del periodo.
    None = supervisor (todos los ADJs del proyecto).
    Incluye asignados aunque ya no tengan saldo (pagaron en el mes).
    """
    if is_supervisor_cartera(user):
        return None

    ids = set(snapshot_adj_ids or [])
    nombre = gestor_nombre_from_user(user)
    if not nombre:
        return ids
    ids.update(
        InfoCartera.objects.using(proyecto)
        .filter(gestorasignado__icontains=nombre)
        .values_list('idadjudicacion', flat=True)
    )
    ids.update(
        PresupuestoCartera.objects.using(proyecto)
        .filter(periodo=periodo, asesor__icontains=nombre)
        .values_list('idadjudicacion', flat=True)
        .distinct()
    )
    return ids


def recaudo_mes_resumen_proyecto(proyecto, adj_ids, periodo):
    """
    Recaudo del periodo para un set de ADJs, excluyendo ventas del mes.

    Parte de recaudos del mes (GROUP BY) y solo consulta ppto/adj de quien pago.
    adj_ids=None → todo el proyecto (vista supervisor).
    """
    empty = _recaudo_vacio()
    if adj_ids is not None and not adj_ids:
        return empty

    try:
        y = int(str(periodo)[:4])
        m = int(str(periodo)[4:6])
    except (ValueError, TypeError):
        return empty

    fecha_corte = datetime.date(y, m, 1)
    fecha_final = datetime.date(y, m, calendar.monthrange(y, m)[1])
    zero = Decimal('0')

    # 1) Recaudos del mes (filtro por cartera solo si hay set acotado)
    qs_rec = (
        Recaudos_general.objects.using(proyecto)
        .filter(fecha__gte=fecha_corte, fecha__lte=fecha_final)
        .exclude(numrecibo__startswith='N')
        .exclude(numrecibo__startswith='A')
    )
    if adj_ids is not None:
        qs_rec = qs_rec.filter(idadjudicacion__in=list(adj_ids))

    recaudo_by_adj = {
        row['idadjudicacion']: row['t'] or zero
        for row in qs_rec.values('idadjudicacion').annotate(t=Coalesce(Sum('valor'), zero))
    }
    if not recaudo_by_adj:
        return empty

    # 2) De quien pago: excluir canje/desistidos y ventas del mes
    paid = list(recaudo_by_adj.keys())
    elegibles = set(
        Adjudicacion.objects.using(proyecto)
        .filter(pk__in=paid)
        .exclude(origenventa='Canje')
        .filter(Q(estado__isnull=True) | ~Q(estado__startswith='Des'))
        .filter(Q(fechacontrato__isnull=True) | Q(fechacontrato__lt=fecha_corte))
        .values_list('pk', flat=True)
    )
    recaudo_by_adj = {k: v for k, v in recaudo_by_adj.items() if k in elegibles}
    if not recaudo_by_adj:
        return empty

    # 3) Presupuesto solo de ADJs con recaudo elegible
    adj_con_recaudo = list(recaudo_by_adj.keys())
    ppto_by_adj = {}
    for row in (
        PresupuestoCartera.objects.using(proyecto)
        .filter(periodo=periodo, idadjudicacion__in=adj_con_recaudo)
        .values('idadjudicacion')
        .annotate(
            presupuesto=Coalesce(Sum('cuota'), zero),
            ppto_mes=Coalesce(
                Sum('cuota', filter=Q(fecha__date__gte=fecha_corte)),
                zero,
            ),
            ppto_vencido=Coalesce(
                Sum('cuota', filter=Q(fecha__date__lt=fecha_corte)),
                zero,
            ),
        )
    ):
        ppto_by_adj[row['idadjudicacion']] = {
            'presupuesto': row['presupuesto'] or zero,
            'ppto_mes': row['ppto_mes'] or zero,
            'ppto_vencido': row['ppto_vencido'] or zero,
        }

    return _clasificar_recaudos_adj(recaudo_by_adj, ppto_by_adj)


def _sumar_recaudo_dicts(parts):
    out = _recaudo_vacio()
    for part in parts:
        for key in out:
            out[key] += _dec(part.get(key))
    return out


def _cliente_contacto_dict(c):
    if c is None:
        return None
    return {
        'id': str(c.idTercero).strip(),
        'nombre': (c.nombrecompleto or f'{c.nombres or ""} {c.apellidos or ""}').strip(),
        'celular1': (c.celular1 or '').strip(),
        'celular2': (c.celular2 or '').strip(),
        'telefono1': (c.telefono1 or '').strip(),
        'telefono2': (c.telefono2 or '').strip(),
        'email': (c.email or '').strip(),
    }


def titulares_contacto(proyecto: str, adj: str):
    """Titular principal + otros terceros de la adjudicacion (contactos)."""
    try:
        obj = Adjudicacion.objects.using(proyecto).get(pk=adj)
    except Adjudicacion.DoesNotExist:
        return {'titular': None, 'otros': []}

    ids = []
    for tid in (obj.idtercero1, obj.idtercero2, obj.idtercero3, obj.idtercero4):
        if tid and str(tid).strip():
            ids.append(str(tid).strip())
    by_id = {}
    if ids:
        for c in clientes.objects.filter(idTercero__in=ids):
            by_id[str(c.idTercero).strip()] = _cliente_contacto_dict(c)

    def _resolve(tid, rol):
        key = str(tid).strip() if tid else ''
        if not key:
            return None
        data = by_id.get(key) or {
            'id': key,
            'nombre': key,
            'celular1': '',
            'celular2': '',
            'telefono1': '',
            'telefono2': '',
            'email': '',
        }
        data = dict(data)
        data['rol'] = rol
        return data

    titular = _resolve(obj.idtercero1, 'Titular 1')
    otros = []
    for i, tid in enumerate((obj.idtercero2, obj.idtercero3, obj.idtercero4), start=2):
        item = _resolve(tid, f'Titular {i}')
        if item:
            otros.append(item)
    return {'titular': titular, 'otros': otros}


def deuda_detalle_adj(proyecto: str, adj: str, *, today=None):
    """
    Cuotas pendientes a la fecha (saldos_cuotas) con mora por cuota.

    Misma fuente que detalle ADJ / edades: saldos_adj con saldocuota > 0 y fecha <= hoy.
    """
    today = today or datetime.date.today()
    rows = list(
        saldos_adj.objects.using(proyecto)
        .filter(adj=adj, saldocuota__gt=0, fecha__lte=today)
        .exclude(tipocta='SF')
        .order_by('fecha', 'nrocta')
    )
    cuotas = []
    tot_capital = Decimal(0)
    tot_interes = Decimal(0)
    tot_cuota = Decimal(0)
    tot_mora = Decimal(0)
    max_dias = 0
    for r in rows:
        capital = Decimal(r.saldocapital or 0)
        interes = Decimal(r.saldointcte or 0)
        saldo = Decimal(r.saldocuota or 0)
        mora = Decimal(r.saldomora or 0)
        dias = int(r.diasmora or 0)
        if dias > max_dias:
            max_dias = dias
        cuotas.append({
            'nrocta': r.nrocta,
            'tipocta': r.tipocta or '',
            'id_cuota': id_cuota_label(r.tipocta, r.nrocta),
            'fecha': r.fecha,
            'saldocapital': capital,
            'saldointcte': interes,
            'saldocuota': saldo,
            'diasmora': dias,
            'saldomora': mora,
            'total': saldo + mora,
        })
        tot_capital += capital
        tot_interes += interes
        tot_cuota += saldo
        tot_mora += mora
    return {
        'cuotas': cuotas,
        'count': len(cuotas),
        'total_capital': tot_capital,
        'total_interes': tot_interes,
        'total_cuotas': tot_cuota,
        'total_mora': tot_mora,
        'total_adeudado': tot_cuota + tot_mora,
        'dias_mora_max': max_dias,
    }


def listar_envios_carta(proyecto: str, adj: str, checkpoint_ids=None):
    qs = (
        CarteraCartaEnvio.objects.filter(proyecto_id=proyecto, adj=adj)
        .select_related('checkpoint', 'usuario')
        .order_by('-fecha_envio', '-id')
    )
    if checkpoint_ids is not None:
        qs = qs.filter(checkpoint_id__in=list(checkpoint_ids))
    return list(qs)


def listar_generaciones_carta(proyecto: str, adj: str, checkpoint_ids=None):
    qs = (
        CarteraCartaGeneracion.objects.filter(proyecto_id=proyecto, adj=adj)
        .select_related('checkpoint', 'usuario')
        .order_by('-created_at', '-id')
    )
    if checkpoint_ids is not None:
        qs = qs.filter(checkpoint_id__in=list(checkpoint_ids))
    return list(qs)


def registrar_generacion_carta(proyecto, adj, checkpoint, user):
    return CarteraCartaGeneracion.objects.create(
        proyecto_id=proyecto,
        adj=adj,
        checkpoint=checkpoint,
        usuario=user,
    )


_CANAL_A_CONTACTO = {
    CarteraCartaEnvio.CANAL_WHATSAPP: 'Whatsapp',
    CarteraCartaEnvio.CANAL_EMAIL: 'Correo Electronico',
    CarteraCartaEnvio.CANAL_FISICO: 'Mensajeria',
    CarteraCartaEnvio.CANAL_OTRO: 'No aplica',
}


def registrar_envio_carta(proyecto, adj, checkpoint, user, *, canal, fecha_envio, soporte, notas=''):
    envio = CarteraCartaEnvio.objects.create(
        proyecto_id=proyecto,
        adj=adj,
        checkpoint=checkpoint,
        canal=canal or CarteraCartaEnvio.CANAL_WHATSAPP,
        fecha_envio=fecha_envio or datetime.date.today(),
        soporte=soporte,
        notas=(notas or '')[:255],
        usuario=user,
    )
    canal_label = envio.get_canal_display()
    ck_label = checkpoint.label or checkpoint.codigo
    fecha_txt = envio.fecha_envio.strftime('%d/%m/%Y') if envio.fecha_envio else ''
    comentario = f'Carta "{ck_label}" enviada por {canal_label} el {fecha_txt}.'
    if notas:
        comentario = f'{comentario} {notas}'.strip()
    crear_seguimiento(proyecto, adj, user, {
        'tipo_seguimiento': 'Envio informacion',
        'forma_contacto': _CANAL_A_CONTACTO.get(envio.canal, 'No aplica'),
        'comentarios': comentario[:255],
        'tiene_compromiso': False,
        'valor_compromiso': 0,
        'fecha_compromiso': None,
    }, fecha=envio.fecha_envio)
    return envio


def _enrich_rows(rows, proyecto):
    out = []
    for r in rows:
        item = dict(r)
        item['proyecto'] = proyecto
        item['bucket'] = bucket_codigo_from_dias(item.get('dias_mora') or 0)
        item['bucket_label'] = BUCKET_LABELS.get(item['bucket'], item['bucket'])
        out.append(item)
    return out


def _dist_lista(kpis, bucket_activo=None):
    return [
        {
            'codigo': codigo,
            'label': label,
            'count': kpis['distribucion_count'].get(codigo, 0),
            'monto': kpis['distribucion'].get(codigo, Decimal(0)),
            'activo': bucket_activo == codigo,
        }
        for codigo, label, _ in BUCKET_KEYS
    ]


def _notif_bundle(compromisos, fechas_pactadas, colas=None):
    comp_all = list(compromisos.get('hoy') or []) + list(compromisos.get('vencidos') or [])
    pact_all = list(fechas_pactadas.get('hoy') or []) + list(fechas_pactadas.get('vencidos') or [])
    colas = colas or {'cobrar_hoy': [], 'en_mora': [], 'count_a': 0, 'count_b': 0}
    cobrar = list(colas.get('cobrar_hoy') or [])
    mora = list(colas.get('en_mora') or [])
    return {
        'compromisos_hoy': compromisos.get('hoy') or [],
        'compromisos_vencidos': compromisos.get('vencidos') or [],
        'compromisos_all': comp_all,
        'compromisos_preview': comp_all[:NOTIF_PREVIEW_LIMIT],
        'compromisos_total': len(comp_all),
        'fechas_pactadas_hoy': fechas_pactadas.get('hoy') or [],
        'fechas_pactadas_vencidos': fechas_pactadas.get('vencidos') or [],
        'fechas_pactadas_all': pact_all,
        'fechas_pactadas_preview': pact_all[:NOTIF_PREVIEW_LIMIT],
        'fechas_pactadas_total': len(pact_all),
        'cobrar_hoy_all': cobrar,
        'cobrar_hoy_preview': cobrar[:NOTIF_PREVIEW_LIMIT],
        'cobrar_hoy_total': len(cobrar),
        'en_mora_all': mora,
        'en_mora_preview': mora[:NOTIF_PREVIEW_LIMIT],
        'en_mora_total': len(mora),
    }


def dashboard_payload(proyecto: str, user, *, today=None):
    """Payload de un solo proyecto (compat). Preferir dashboard_payload_all."""
    return dashboard_payload_all(user, proyecto_filtro=proyecto, today=today)


def dashboard_payload_all(
    user,
    *,
    proyecto_filtro=None,
    bucket_filtro=None,
    today=None,
    ensure_ppto=True,
):
    """
    Dashboard integrado multi-proyecto.

    proyecto_filtro: None / '' / 'all' = todos; si no, solo ese proyecto.
    bucket_filtro: codigo de edad (por_vencer, lt30, ...); None = todas.
    ensure_ppto: ensure silencioso del periodo actual antes de armar datos.
    """
    today = today or datetime.date.today()
    periodo = periodo_actual(today)
    accesibles = proyectos_accesibles(user)
    if ensure_ppto and accesibles:
        ensure_presupuestos(accesibles, periodo, user)

    filtro = (proyecto_filtro or '').strip()
    if filtro in ('', 'all', 'todos'):
        proyectos_scope = list(accesibles)
        filtro_activo = None
    else:
        if filtro not in accesibles:
            proyectos_scope = []
        else:
            proyectos_scope = [filtro]
        filtro_activo = filtro if proyectos_scope else filtro

    bucket = (bucket_filtro or '').strip()
    if bucket not in BUCKET_CODIGOS:
        bucket = None

    all_rows = []
    rows_por_proyecto = {p: [] for p in accesibles}
    adj_ids_snapshot = {p: [] for p in accesibles}
    fecha_consulta = today

    for proyecto in accesibles:
        ensure_default_checkpoints(proyecto)
        try:
            adjudicaciones, fecha_consulta = edades_cartera_snapshot(proyecto, today=today)
        except Exception:
            continue
        rows = filter_snapshot_for_gestor(adjudicaciones, user)
        # Antes del filtro de saldo: sirve para recaudo (incluye quien ya pago)
        adj_ids_snapshot[proyecto] = [r['adj'] for r in rows if r.get('adj')]
        rows = [
            r for r in rows
            if Decimal(r.get('total_pendiente') or 0) > 0 or int(r.get('dias_mora') or 0) > 0
        ]
        rows = _enrich_rows(rows, proyecto)
        rows_por_proyecto[proyecto] = rows
        if proyecto in proyectos_scope:
            all_rows.extend(rows)

    # Distribucion por edad sobre el alcance de proyecto (antes de filtrar edad)
    dist_kpis = kpis_from_rows(
        all_rows,
        {'hoy': [], 'vencidos': [], 'count_hoy': 0},
        {'hoy': [], 'vencidos': [], 'count_hoy': 0, 'count_vencidos': 0},
    )
    distribucion_lista = _dist_lista(dist_kpis, bucket_activo=bucket)

    # Filtrar tabla / KPIs / notifs por bucket activo
    if bucket:
        rows = [r for r in all_rows if r.get('bucket') == bucket]
    else:
        rows = list(all_rows)

    compromisos = {'hoy': [], 'vencidos': [], 'count_hoy': 0}
    fechas_pactadas = {'hoy': [], 'vencidos': [], 'count_hoy': 0, 'count_vencidos': 0}
    colas = {'cobrar_hoy': [], 'en_mora': [], 'count_a': 0, 'count_b': 0}
    by_proj_adj = {}
    for r in rows:
        by_proj_adj.setdefault(r['proyecto'], []).append(r['adj'])
    for proyecto, adj_ids in by_proj_adj.items():
        c = compromisos_gestor(proyecto, adj_ids, today=today)
        f = fechas_pactadas_gestor(proyecto, adj_ids, today=today)
        q = colas_cobranza_gestor(proyecto, adj_ids, today=today)
        compromisos['hoy'].extend(c['hoy'])
        compromisos['vencidos'].extend(c['vencidos'])
        compromisos['count_hoy'] += c['count_hoy']
        fechas_pactadas['hoy'].extend(f['hoy'])
        fechas_pactadas['vencidos'].extend(f['vencidos'])
        fechas_pactadas['count_hoy'] += f['count_hoy']
        fechas_pactadas['count_vencidos'] += f['count_vencidos']
        colas['cobrar_hoy'].extend(q['cobrar_hoy'])
        colas['en_mora'].extend(q['en_mora'])
        colas['count_a'] += q['count_a']
        colas['count_b'] += q['count_b']

    compromisos['hoy'].sort(key=lambda x: (x.get('cliente') or '', x.get('adj') or ''))
    compromisos['vencidos'].sort(
        key=lambda x: (x.get('fecha_compromiso') or today, x.get('cliente') or '')
    )
    fechas_pactadas['hoy'].sort(key=lambda x: (x.get('cliente') or '', x.get('adj') or ''))
    fechas_pactadas['vencidos'].sort(
        key=lambda x: (x.get('fecha_pactada') or today, x.get('cliente') or '')
    )
    colas['cobrar_hoy'].sort(key=lambda x: (
        x.get('prioridad', 9),
        -float(x.get('valor') or 0),
        (x.get('cliente') or '').upper(),
        x.get('adj') or '',
    ))
    colas['en_mora'].sort(key=lambda x: (
        -(x['fecha_vencida_reciente'].toordinal() if x.get('fecha_vencida_reciente') else 0),
        -float(x.get('valor') or 0),
        (x.get('cliente') or '').upper(),
    ))

    kpis = kpis_from_rows(rows, compromisos, fechas_pactadas)
    kpis['cobrar_hoy'] = colas['count_a']
    kpis['en_mora'] = colas['count_b']

    # Recaudo del mes (alcance por proyecto, sin filtro de edad): excluye ventas del mes
    recaudo_parts = []
    for proyecto in proyectos_scope:
        adj_ids = _adj_ids_alcance_recaudo(
            proyecto, user, periodo, adj_ids_snapshot.get(proyecto) or [],
        )
        recaudo_parts.append(recaudo_mes_resumen_proyecto(proyecto, adj_ids, periodo))
    kpis['recaudo'] = _sumar_recaudo_dicts(recaudo_parts)

    notifs = _notif_bundle(compromisos, fechas_pactadas, colas)

    # Badges de proyecto: si hay filtro de edad, el count refleja ese bucket
    proyectos_badges = []
    for p in accesibles:
        prow = rows_por_proyecto.get(p) or []
        if bucket:
            count = sum(1 for r in prow if r.get('bucket') == bucket)
        else:
            count = len(prow)
        proyectos_badges.append({
            'nombre': p,
            'count': count,
            'activo': filtro_activo == p,
        })

    return {
        'proyecto_filtro': filtro_activo,
        'bucket_filtro': bucket,
        'proyectos_accesibles': accesibles,
        'proyectos_badges': proyectos_badges,
        'fecha_consulta': fecha_consulta,
        'es_supervisor': is_supervisor_cartera(user),
        'gestor_nombre': gestor_nombre_from_user(user),
        'rows': rows,
        'kpis': kpis,
        'periodo_ppto': periodo,
        'buckets': BUCKET_KEYS,
        'distribucion_lista': distribucion_lista,
        'notificaciones_hoy': notifs['compromisos_hoy'],
        'notificaciones_vencidos': notifs['compromisos_vencidos'],
        **notifs,
    }


def timeline_payload(proyecto: str, adj: str, *, today=None):
    today = today or datetime.date.today()
    ensure_default_checkpoints(proyecto)
    adjudicaciones, fecha_consulta = edades_cartera_snapshot(proyecto, today=today)
    row = next((r for r in adjudicaciones if r.get('adj') == adj), None)
    if row is None:
        return None

    dias_mora = int(row.get('dias_mora') or 0)
    activo = bucket_codigo_from_dias(dias_mora)

    checkpoints = list(
        CarteraCheckpoint.objects.filter(proyecto_id=proyecto, activo=True)
        .prefetch_related('plantillas')
        .order_by('orden', 'dias_desde')
    )
    visual_nodes = visual_nodes_cartas(
        checkpoints,
        dias_mora,
        row.get('total_pendiente'),
    )
    carta_nodes = []
    ck_ids = [ck.id for ck in checkpoints]
    envios = listar_envios_carta(proyecto, adj, checkpoint_ids=ck_ids)
    generaciones = listar_generaciones_carta(proyecto, adj, checkpoint_ids=ck_ids)
    envios_by_ck = {}
    for ev in envios:
        envios_by_ck.setdefault(ev.checkpoint_id, []).append({
            'id': ev.id,
            'canal': ev.canal,
            'canal_label': ev.get_canal_display(),
            'fecha_envio': ev.fecha_envio,
            'notas': ev.notas,
            'usuario': str(ev.usuario),
            'tiene_soporte': bool(ev.soporte),
            'created_at': ev.created_at,
        })
    gens_by_ck = {}
    for g in generaciones:
        gens_by_ck.setdefault(g.checkpoint_id, []).append({
            'id': g.id,
            'usuario': str(g.usuario),
            'created_at': g.created_at,
        })

    for ck in checkpoints:
        plantilla = next((p for p in ck.plantillas.all() if p.activo), None)
        alcanzado = ck.alcanzado(dias_mora)
        ck_envios = envios_by_ck.get(ck.id, [])
        ck_gens = gens_by_ck.get(ck.id, [])
        carta_nodes.append({
            'checkpoint': ck,
            'alcanzado': alcanzado,
            'tiene_plantilla': plantilla is not None,
            'plantilla': plantilla,
            'monto': monto_bucket(row, ck.codigo) if ck.codigo in BUCKET_CODIGOS else Decimal(0),
            'envios': ck_envios,
            'generaciones': ck_gens,
            'generada': bool(ck_gens),
            'enviada': bool(ck_envios),
            'ultima_generacion': ck_gens[0]['created_at'] if ck_gens else None,
            'ultimo_envio': ck_envios[0]['fecha_envio'] if ck_envios else None,
        })

    segs = list(
        seguimientos.objects.using(proyecto)
        .filter(adj=adj)
        .order_by('-fecha', '-id_seg')[:50]
    )

    # Prefetch recaudos para evaluar cumplimiento de compromisos en la lista
    fechas_comp = []
    for seg in segs:
        if int(seg.valor_compromiso or 0) > 0:
            fc = _parse_fecha_compromiso(seg.fecha_compromiso)
            if fc:
                fechas_comp.append(fc)
    recaudos_cache = {}
    if fechas_comp:
        min_f = min(fechas_comp)
        for adj_id, fecha, valor in (
            Recaudos_general.objects.using(proyecto)
            .filter(idadjudicacion=adj, fecha__gte=min_f)
            .exclude(numrecibo__startswith='N')
            .exclude(numrecibo__startswith='A')
            .values_list('idadjudicacion', 'fecha', 'valor')
        ):
            recaudos_cache.setdefault(adj_id, []).append((fecha, Decimal(valor or 0)))

    seguimientos_enriched = []
    compromiso_activo = None
    registro_desde = today - datetime.timedelta(days=COMPROMISO_REGISTRO_LOOKBACK_DAYS)
    for seg in segs:
        item = {
            'id_seg': seg.id_seg,
            'fecha': seg.fecha,
            'usuario': seg.usuario,
            'tipo_seguimiento': seg.tipo_seguimiento,
            'forma_contacto': seg.forma_contacto,
            'respuesta_cliente': seg.respuesta_cliente,
            'valor_compromiso': int(seg.valor_compromiso or 0),
            'fecha_compromiso': seg.fecha_compromiso,
            'cumplimiento': None,
        }
        if item['valor_compromiso'] > 0:
            ev = evaluar_cumplimiento_compromiso(
                proyecto,
                adj,
                seg.fecha_compromiso,
                item['valor_compromiso'],
                today=today,
                recaudos_cache=recaudos_cache,
            )
            item['cumplimiento'] = ev
            # Compromiso activo = ultimo registro reciente no cumplido
            if (
                compromiso_activo is None
                and seg.fecha
                and seg.fecha >= registro_desde
                and ev['estado'] in ('hoy', 'vencido', 'pendiente')
            ):
                compromiso_activo = {
                    'id_seg': seg.id_seg,
                    'valor': ev['valor'],
                    'fecha_compromiso': ev['fecha_compromiso'],
                    'estado': ev['estado'],
                    'label': ev['label'],
                    'recaudo': ev['recaudo'],
                    'faltante': ev['faltante'],
                    'usuario': seg.usuario,
                    'fecha_registro': seg.fecha,
                }
        seguimientos_enriched.append(item)

    contactos = titulares_contacto(proyecto, adj)
    deuda = deuda_detalle_adj(proyecto, adj, today=today)

    return {
        'proyecto': proyecto,
        'adj': adj,
        'row': row,
        'fecha_consulta': fecha_consulta,
        'dias_mora': dias_mora,
        'bucket_activo': activo,
        'visual_nodes': visual_nodes,
        'carta_nodes': carta_nodes,
        'seguimientos': seguimientos_enriched,
        'compromiso_activo': compromiso_activo,
        'titular': contactos.get('titular'),
        'otros_titulares': contactos.get('otros') or [],
        'canales_envio': CarteraCartaEnvio.CANAL_CHOICES,
        'deuda': deuda,
    }


def nro_contrato_from_adj(adj_obj, adj_id: str) -> str:
    """Numero de contrato (columna Contrato), no el id de adjudicacion."""
    nro = str(getattr(adj_obj, 'contrato', None) or '').strip()
    return nro or str(adj_id)


def _adj_carta_info(proyecto: str, adj: str):
    info = {
        'nro_contrato': adj,
        'fecha_contrato': None,
        'inmueble': '',
    }
    try:
        obj = Adjudicacion.objects.using(proyecto).only(
            'idadjudicacion', 'contrato', 'fechacontrato', 'idinmueble',
        ).get(pk=adj)
    except Adjudicacion.DoesNotExist:
        return info
    info['nro_contrato'] = nro_contrato_from_adj(obj, adj)
    info['fecha_contrato'] = obj.fechacontrato
    info['inmueble'] = (obj.idinmueble or '').strip()
    return info


def plantilla_activa_checkpoint(checkpoint: CarteraCheckpoint):
    return (
        CarteraCartaPlantilla.objects.filter(checkpoint=checkpoint, activo=True)
        .order_by('id')
        .first()
    )


def build_carta_context(proyecto: str, adj: str, checkpoint: CarteraCheckpoint, *, today=None, payload=None):
    today = today or datetime.date.today()
    payload = payload if payload is not None else timeline_payload(proyecto, adj, today=today)
    if payload is None:
        return None
    row = payload['row']
    titular = payload.get('titular') or {}
    nombre = (titular.get('nombre') or row.get('cliente') or '').strip()
    deuda = payload.get('deuda') or {}
    adj_info = _adj_carta_info(proyecto, adj)
    fecha_ctr = adj_info.get('fecha_contrato')
    contacto = contacto_carta_proyecto(proyecto)
    return {
        'proyecto': proyecto,
        'adj': adj,
        'cliente': row.get('cliente') or '',
        'nombre_cliente': nombre,
        'nro_contrato': adj_info.get('nro_contrato') or adj,
        'fecha_contrato': fecha_ctr,
        'fecha_contrato_letras': fecha_en_letras(fecha_ctr),
        'cartera': row.get('cartera') or '',
        'gestor': row.get('gestor') or '',
        'dias_mora': payload['dias_mora'],
        'dias_mora_letras': dias_en_letras(payload['dias_mora']),
        'total_pendiente': row.get('total_pendiente') or 0,
        'por_vencer': row.get('por_vencer') or 0,
        'lt30': row.get('lt30') or 0,
        'lt60': row.get('lt60') or 0,
        'lt90': row.get('lt90') or 0,
        'lt120': row.get('lt120') or 0,
        'gt120': row.get('gt120') or 0,
        'ultimo_pago': row.get('ultimo_pago'),
        'checkpoint': checkpoint,
        'checkpoint_label': checkpoint.label,
        'fecha': today,
        'fecha_letras': fecha_en_letras(today),
        'fecha_consulta': payload['fecha_consulta'],
        'ciudad': CARTA_CIUDAD,
        'deuda': deuda,
        'cuotas': deuda.get('cuotas') or [],
        'inmueble': adj_info.get('inmueble') or '',
        'logo_static': logo_carta_static(proyecto),
        'fondo_static': fondo_carta_static(proyecto),
        'firma_nombre': contacto['firma_nombre'],
        'telefono_cartera': contacto['telefono'],
        'email_cartera': contacto['email'],
    }


def crear_seguimiento(proyecto, adj, user, cleaned, *, fecha=None):
    """Persiste un seguimiento (misma forma que detalle_adjudicacion)."""
    valor = cleaned.get('valor_compromiso') or 0
    fecha_c = cleaned.get('fecha_compromiso')
    if not cleaned.get('tiene_compromiso'):
        valor = 0
        fecha_c = None
    if fecha_c and hasattr(fecha_c, 'isoformat'):
        fecha_c = fecha_c.isoformat()

    # Un nuevo compromiso reemplaza (cierra) los anteriores del ADJ
    if int(valor or 0) > 0:
        cerrar_compromisos_previos(proyecto, adj, user, motivo='reemplazado')

    return seguimientos.objects.using(proyecto).create(
        adj=adj,
        fecha=fecha or datetime.date.today(),
        tipo_seguimiento=cleaned.get('tipo_seguimiento'),
        forma_contacto=cleaned.get('forma_contacto'),
        respuesta_cliente=(cleaned.get('comentarios') or '')[:255],
        valor_compromiso=valor or 0,
        fecha_compromiso=fecha_c or '',
        usuario=user,
    )


def _marcar_compromiso_cerrado(seg, *, motivo='cerrado'):
    """Deja el seguimiento historico pero quita el valor/fecha de compromiso."""
    etiqueta = 'Reemplazado' if motivo == 'reemplazado' else 'Cerrado'
    nota = f'[Compromiso {etiqueta.lower()} {datetime.date.today().isoformat()}]'
    prev = (seg.respuesta_cliente or '').strip()
    texto = f'{nota} {prev}'.strip() if prev else nota
    seg.respuesta_cliente = texto[:255]
    seg.valor_compromiso = 0
    seg.fecha_compromiso = ''
    seg.save(update_fields=['respuesta_cliente', 'valor_compromiso', 'fecha_compromiso'])
    return seg


def cerrar_compromisos_previos(proyecto, adj, user, *, motivo='reemplazado', excepto_id=None):
    """Cierra todos los compromisos abiertos (valor>0) del ADJ."""
    qs = (
        seguimientos.objects.using(proyecto)
        .filter(adj=adj, valor_compromiso__gt=0)
        .order_by('-fecha', '-id_seg')
    )
    if excepto_id is not None:
        qs = qs.exclude(pk=excepto_id)
    cerrados = 0
    for seg in qs:
        _marcar_compromiso_cerrado(seg, motivo=motivo)
        cerrados += 1
    if cerrados:
        timeline.objects.using(proyecto).create(
            adj=adj,
            fecha=datetime.date.today(),
            usuario=user,
            accion=(
                f'Reemplazo compromiso anterior ({cerrados})'
                if motivo == 'reemplazado'
                else f'Cerro {cerrados} compromiso(s) anterior(es)'
            ),
        )
    return cerrados


def cerrar_compromiso(proyecto, adj, id_seg, user):
    """Cierra un compromiso concreto sin borrar el seguimiento."""
    try:
        pk = int(id_seg)
    except (TypeError, ValueError) as exc:
        raise ValueError('Compromiso no valido') from exc
    try:
        seg = seguimientos.objects.using(proyecto).get(pk=pk, adj=adj)
    except seguimientos.DoesNotExist as exc:
        raise ValueError('Compromiso no encontrado') from exc
    if int(seg.valor_compromiso or 0) <= 0:
        raise ValueError('Este seguimiento no tiene un compromiso activo')
    valor = int(seg.valor_compromiso or 0)
    fecha_c = seg.fecha_compromiso or ''
    _marcar_compromiso_cerrado(seg, motivo='cerrado')
    timeline.objects.using(proyecto).create(
        adj=adj,
        fecha=datetime.date.today(),
        usuario=user,
        accion=f'Cerro compromiso de ${valor:,} ({fecha_c})',
    )
    return seg


def eliminar_compromiso(proyecto, adj, id_seg, user):
    """Elimina el seguimiento que contiene el compromiso."""
    try:
        pk = int(id_seg)
    except (TypeError, ValueError) as exc:
        raise ValueError('Compromiso no valido') from exc
    try:
        seg = seguimientos.objects.using(proyecto).get(pk=pk, adj=adj)
    except seguimientos.DoesNotExist as exc:
        raise ValueError('Compromiso no encontrado') from exc
    if int(seg.valor_compromiso or 0) <= 0:
        raise ValueError('Este seguimiento no tiene un compromiso activo')
    valor = int(seg.valor_compromiso or 0)
    fecha_c = seg.fecha_compromiso or ''
    seg.delete()
    timeline.objects.using(proyecto).create(
        adj=adj,
        fecha=datetime.date.today(),
        usuario=user,
        accion=f'Elimino compromiso de ${valor:,} ({fecha_c})',
    )
    return True


# --- Asignacion de gestor / cartera juridica ---------------------------------

GESTOR_JURIDICO = 'JURIDICO'
GESTOR_ESPECIAL = 'ESPECIAL'
GESTORES_FIJOS = (GESTOR_JURIDICO, GESTOR_ESPECIAL)


def listar_gestores_opciones(*, include_fijos: bool = True):
    """
    Opciones de gestor: usuarios activos del grupo Gestor Cartera.
    Si include_fijos=True, agrega JURIDICO/ESPECIAL (reasignacion/dashboard).
    """
    from django.contrib.auth.models import User

    opciones = []
    vistos = set()
    for u in User.objects.filter(groups__name='Gestor Cartera', is_active=True).order_by(
        'first_name', 'last_name'
    ):
        nombre = gestor_nombre_from_user(u)
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        opciones.append((nombre, nombre))
    if include_fijos:
        for fijo in GESTORES_FIJOS:
            if fijo not in vistos:
                opciones.append((fijo, fijo))
                vistos.add(fijo)
    return opciones


def periodo_actual(today=None) -> str:
    today = today or datetime.date.today()
    return f'{today.year}{today.month:02d}'


def ultimo_periodo_presupuesto(proyecto: str):
    """Periodo YYYYMM mas reciente con filas en presupuesto_cartera del proyecto."""
    return (
        PresupuestoCartera.objects.using(proyecto)
        .exclude(periodo__isnull=True)
        .exclude(periodo='')
        .order_by('-periodo')
        .values_list('periodo', flat=True)
        .first()
    )


def label_periodo_presupuesto(periodo: str) -> str:
    """YYYYMM -> 'YYYY-MM' legible."""
    p = (periodo or '').strip()
    if len(p) == 6 and p.isdigit():
        return f'{p[:4]}-{p[4:]}'
    return p or ''


def asignar_gestor(
    proyecto: str,
    adj: str,
    nuevo_gestor: str,
    user,
    *,
    actualizar_presupuesto: bool = True,
    actualizar_todos_periodos: bool = True,
    periodo: str | None = None,
):
    """
    Reasigna gestor de cobro.

    Actualiza:
    - info_cartera.GestorAsignado
    - presupuesto_cartera.Asesor (opcional: periodo indicado / todos / ninguno)
    - adjudicacion.es_juridico (1 si JURIDICO, 0 en otro caso)
    - timeline_adj (auditoria)
    """
    nuevo = (nuevo_gestor or '').strip().upper()
    if not nuevo:
        raise ValueError('Debe indicar un gestor')
    if not Adjudicacion.objects.using(proyecto).filter(pk=adj).exists():
        raise ValueError(f'Adjudicacion {adj} no existe')

    # InfoCartera
    info_qs = InfoCartera.objects.using(proyecto).filter(idadjudicacion=adj)
    anterior = ''
    if info_qs.exists():
        info = info_qs.get()
        anterior = (info.gestorasignado or '').strip()
        info.gestorasignado = nuevo
        info.save(update_fields=['gestorasignado'])
    else:
        InfoCartera.objects.using(proyecto).create(
            idadjudicacion=adj,
            gestorasignado=nuevo,
        )

    # PresupuestoCartera.asesor
    cuotas_actualizadas = 0
    if actualizar_presupuesto:
        ppto_qs = PresupuestoCartera.objects.using(proyecto).filter(idadjudicacion=adj)
        if not actualizar_todos_periodos:
            per = periodo or periodo_actual()
            ppto_qs = ppto_qs.filter(periodo=per)
        for cuota in ppto_qs:
            if (cuota.asesor or '').strip().upper() != nuevo:
                cuota.asesor = nuevo
                cuota.save(update_fields=['asesor'])
                cuotas_actualizadas += 1

    # Flag juridico en adjudicacion
    adj_obj = Adjudicacion.objects.using(proyecto).get(pk=adj)
    es_jur = 1 if nuevo == GESTOR_JURIDICO else 0
    if adj_obj.es_juridico != es_jur:
        adj_obj.es_juridico = es_jur
        adj_obj.save(update_fields=['es_juridico'])

    # Auditoria
    if nuevo == GESTOR_JURIDICO:
        accion = f'Paso a cartera juridica (gestor {nuevo})'
    elif anterior:
        accion = f'Cambio gestor de cartera de {anterior} a {nuevo}'
    else:
        accion = f'Asigno gestor de cartera {nuevo}'
    if actualizar_presupuesto:
        if actualizar_todos_periodos:
            accion += ' (presupuesto: todos los periodos)'
        else:
            per = periodo or periodo_actual()
            accion += f' (presupuesto periodo {per})'
    else:
        accion += ' (sin actualizar presupuesto)'
    timeline.objects.using(proyecto).create(
        adj=adj,
        fecha=datetime.date.today(),
        usuario=user,
        accion=accion,
    )

    return {
        'adj': adj,
        'gestor_anterior': anterior,
        'gestor_nuevo': nuevo,
        'es_juridico': nuevo == GESTOR_JURIDICO,
        'cuotas_ppto_actualizadas': cuotas_actualizadas,
        'presupuesto_actualizado': bool(actualizar_presupuesto),
    }


def asignar_gestor_bulk(proyecto, adj_ids, nuevo_gestor, user, **kwargs):
    resultados = []
    errores = []
    for adj in adj_ids:
        adj = (adj or '').strip()
        if not adj:
            continue
        try:
            resultados.append(asignar_gestor(proyecto, adj, nuevo_gestor, user, **kwargs))
        except Exception as exc:
            errores.append({'adj': adj, 'error': str(exc)})
    return {'ok': resultados, 'errores': errores}


def listado_asignaciones(proyecto: str, user, *, filtro_gestor: str | None = None):
    """Filas del snapshot con gestor actual para la pantalla de asignacion."""
    adjudicaciones, fecha = edades_cartera_snapshot(proyecto)
    rows = filter_snapshot_for_gestor(adjudicaciones, user)
    # Incluir tambien sin saldo pendiente (para poder reasignar juridicos al dia)
    if is_supervisor_cartera(user):
        adjudicaciones_all, fecha = edades_cartera_snapshot(proyecto)
        rows = adjudicaciones_all

    filtro = (filtro_gestor or '').strip().upper()
    out = []
    for r in rows:
        gestor = (r.get('gestor') or 'Sin Gestor').strip()
        if filtro and filtro not in gestor.upper() and gestor.upper() != filtro:
            continue
        r = dict(r)
        r['es_juridico'] = gestor.upper() == GESTOR_JURIDICO
        out.append(r)
    out.sort(key=lambda x: ((x.get('gestor') or ''), (x.get('cliente') or ''), x.get('adj') or ''))
    return out, fecha
