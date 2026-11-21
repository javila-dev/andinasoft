import datetime
import json
import logging
import os
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_http_methods

from andina.decorators import check_groups
from andinasoft.models import clientes, empresas
from conciliacion_terceros import engine
from conciliacion_terceros.export import construir_libro
from conciliacion_terceros.formatos import leer_fuente
from conciliacion_terceros import ajustes as ajustes_srv
from conciliacion_terceros import correccion, facturacion
from conciliacion_terceros import incluidos as incluidos_srv
from conciliacion_terceros.models import (
    AjusteConciliacion,
    ConfigFacturacion,
    FacturaConciliacion,
    CorreccionIdentificacion,
    Conciliacion,
    ConciliacionLinea,
    ConfigEmpresa,
    EquivalenciaIdentificacion,
    FuenteConciliacion,
)
from conciliacion_terceros.parser import BalanceParseError, norm_ident

logger = logging.getLogger(__name__)


def _guard(request):
    check_groups(request, ('Contabilidad',))


def _empresa_corta(nombre):
    return (nombre or '').split(' ')[0].upper()


def _mismo_nombre(a, b):
    limpio = lambda x: ' '.join(norm_ident(t) for t in (x or '').split() if norm_ident(t) not in ('SAS', 'SA', 'S', 'LTDA'))
    a, b = limpio(a), limpio(b)
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))


def _recalcular_si_listo(request, conc):
    """Calcula si todas las fuentes tienen sus cuentas seleccionadas; si no, manda a seleccionarlas."""
    pendiente = conc.fuentes.filter(confirmada=False).select_related('empresa').first()
    if pendiente:
        messages.info(request, f'Selecciona las cuentas a sumar del archivo de {pendiente.empresa.nombre}.')
        return redirect('conciliacion-terceros-cuentas', pk=conc.pk, fuente_id=pendiente.pk)
    if conc.fuentes.exists():
        engine.ejecutar(conc)
    return redirect('conciliacion-terceros-detalle', pk=conc.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def index(request):
    _guard(request)
    if request.method == 'POST':
        try:
            fecha = datetime.date.fromisoformat(request.POST.get('fecha_corte') or '')
        except ValueError:
            messages.error(request, 'Indica la fecha de corte.')
            return redirect('conciliacion-terceros')
        try:
            tolerancia = max(0, int(request.POST.get('tolerancia') or 1000))
        except ValueError:
            tolerancia = 1000
        anterior = Conciliacion.objects.order_by('-created_at').first()
        conc = Conciliacion.objects.create(
            fecha_corte=fecha, tolerancia=tolerancia, created_by=request.user,
            proyectos_excluidos=list(anterior.proyectos_excluidos or []) if anterior else [],
        )
        return redirect('conciliacion-terceros-detalle', pk=conc.pk)

    concs = list(Conciliacion.objects.select_related('created_by').prefetch_related('fuentes__empresa')[:50])
    return render(request, 'conciliacion_terceros/index.html', {'conciliaciones': concs})


@login_required
@require_http_methods(['POST'])
def fuente_agregar(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        messages.error(request, 'La conciliación está cerrada.')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    emp = get_object_or_404(empresas, pk=request.POST.get('empresa'))
    formato = request.POST.get('formato')
    if formato not in dict(FuenteConciliacion.FORMATO_CHOICES):
        messages.error(request, 'Selecciona el formato del archivo.')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    f = request.FILES.get('archivo')
    if not f:
        messages.error(request, 'Selecciona el archivo.')
        return redirect('conciliacion-terceros-detalle', pk=pk)

    folder = os.path.join(settings.MEDIA_ROOT, 'conciliacion_terceros', str(emp.pk))
    os.makedirs(folder, exist_ok=True)
    # Con microsegundos: el archivo anterior de la empresa se conserva para compararlo con el nuevo.
    path = os.path.join(folder, f'{timezone.now():%Y%m%d_%H%M%S_%f}_{get_valid_filename(f.name)}')
    with open(path, 'wb') as out:
        for chunk in f.chunks():
            out.write(chunk)

    def rechazar(msg):
        os.remove(path)
        messages.error(request, msg)
        return redirect('conciliacion-terceros-detalle', pk=pk)

    try:
        balance = leer_fuente(formato, path)
    except BalanceParseError as exc:
        return rechazar(f'No se pudo leer el archivo como «{dict(FuenteConciliacion.FORMATO_CHOICES)[formato]}»: {exc}')
    emp_nit = norm_ident(emp.pk)
    if balance.nit and not (balance.nit.startswith(emp_nit) or emp_nit.startswith(balance.nit)):
        return rechazar(f'El archivo es de la empresa NIT {balance.nit} ({balance.empresa_nombre}), no de {emp.nombre}.')
    if not balance.nit and balance.empresa_nombre and not _mismo_nombre(balance.empresa_nombre, emp.nombre):
        # SIIGO no trae el NIT en el encabezado: se valida por nombre.
        return rechazar(f'El archivo es de «{balance.empresa_nombre}», no de {emp.nombre}.')
    if balance.fecha_hasta != conc.fecha_corte:
        return rechazar(f'El archivo tiene corte {balance.fecha_hasta:%d/%m/%Y} y la conciliación es al '
                        f'{conc.fecha_corte:%d/%m/%Y}. Exporta el reporte con la misma fecha de corte.')

    previa = FuenteConciliacion.objects.filter(conciliacion=conc, empresa=emp).first()
    anterior = {}
    if previa and not previa.confirmada:
        anterior = previa.anterior or {}  # se compara siempre contra el último archivo confirmado
    elif previa and previa.archivo and os.path.exists(previa.archivo):
        anterior = {'archivo': previa.archivo, 'formato': previa.formato, 'archivo_nombre': previa.archivo_nombre,
                    'cargado_en': (previa.cargado_en or previa.created_at).isoformat(),
                    'incluidos': previa.incluidos}
    # Archivo nuevo: hay que volver a decidir qué movimientos de la conciliación ya trae.
    fuente, _ = FuenteConciliacion.objects.update_or_create(
        conciliacion=conc, empresa=emp,
        defaults={'formato': formato, 'archivo': path, 'archivo_nombre': f.name,
                  'fecha_corte_archivo': balance.fecha_hasta, 'created_by': request.user,
                  'confirmada': False, 'cuentas_usadas': [], 'cargado_en': timezone.now(),
                  'anterior': anterior, 'incluidos': {}},
    )
    messages.success(request, f'Archivo de {emp.nombre} leído: {len(balance.cuentas)} cuenta(s). Elige cuáles sumar.')
    return redirect('conciliacion-terceros-cuentas', pk=conc.pk, fuente_id=fuente.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def fuente_cuentas(request, pk, fuente_id):
    """Muestra las cuentas del archivo para elegir cuáles se suman; las demás se descartan."""
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    fuente = get_object_or_404(FuenteConciliacion.objects.select_related('empresa'), pk=fuente_id, conciliacion=conc)
    try:
        balance = leer_fuente(fuente.formato, fuente.archivo)
    except BalanceParseError as exc:
        messages.error(request, f'No se pudo leer el archivo: {exc}')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    config = ConfigEmpresa.objects.filter(empresa=fuente.empresa).first()

    if request.method == 'POST':
        if conc.estado == Conciliacion.ESTADO_CERRADA:
            messages.error(request, 'La conciliación está cerrada: no se pueden cambiar las cuentas ni los movimientos incluidos.')
            return redirect('conciliacion-terceros-detalle', pk=pk)
        usadas = sorted(c for c in balance.cuentas if request.POST.get(f'usar_{c}'))
        defaults = {'cuentas': usadas}
        if 'numeracion_journal_id' in request.POST:
            num = request.POST.get('numeracion_journal_id', '').strip()
            if num and not re.fullmatch(r'[A-Za-z0-9_-]{1,40}', num):
                messages.error(request, 'La numeración de los journals debe ser el ID de la numeración en Alegra (letras y números, sin espacios), o quedar vacía.')
                return redirect('conciliacion-terceros-cuentas', pk=pk, fuente_id=fuente.pk)
            defaults['numeracion_journal_id'] = num
        # Movimientos dentro del corte que este archivo ya trae (no se vuelven a sumar).
        candidatos = incluidos_srv.movimientos_en_corte(fuente)
        fuente.incluidos = {
            'ajustes': [m['id'] for m in candidatos if m['tipo'] == 'ajuste' and request.POST.get(f'incluido_ajuste_{m["id"]}')],
            'facturas': [m['id'] for m in candidatos if m['tipo'] == 'factura' and request.POST.get(f'incluido_factura_{m["id"]}')],
            'decidido_por': request.user.get_username(), 'decidido_en': timezone.now().isoformat(),
        }
        fuente.cuentas_usadas = usadas
        fuente.confirmada = True
        fuente.save(update_fields=['cuentas_usadas', 'confirmada', 'incluidos'])
        ConfigEmpresa.objects.update_or_create(empresa=fuente.empresa, defaults=defaults)
        if usadas:
            messages.success(request, f'{fuente.empresa.nombre}: {len(usadas)} cuenta(s) seleccionada(s).')
            # El archivo nuevo puede traer ya los saldos que alguien escribió a mano: si no se quitan, se cuentan dos veces.
            a_mano = conc.saldos_manuales.filter(empresa_id=fuente.empresa_id).count()
            if a_mano:
                messages.warning(request, f'{fuente.empresa.nombre} tiene {a_mano} saldo(s) puesto(s) a mano, que siguen '
                                          'mandando sobre este archivo. Revísalos en «Saldos puestos a mano» y quita los '
                                          'que el archivo nuevo ya traiga.')
        else:
            messages.warning(request, f'{fuente.empresa.nombre}: no seleccionaste cuentas, el archivo no suma nada.')
        n_inc = len(fuente.incluidos['ajustes']) + len(fuente.incluidos['facturas'])
        if n_inc:
            messages.info(request, f'{n_inc} movimiento(s) de la conciliación quedaron como incluidos en el archivo de '
                                   f'{fuente.empresa.nombre}: no se vuelven a sumar.')
        return _recalcular_si_listo(request, conc)

    if fuente.confirmada:
        marcadas = set(fuente.cuentas_usadas or [])
    elif config:
        marcadas = set(config.cuentas or [])
    else:
        marcadas = set(balance.cuentas)
    recordadas = set(config.cuentas or []) if config else set()
    filas = [{
        'codigo': codigo, 'nombre': cta.nombre, 'terceros': len(cta.terceros), 'saldo': cta.suma,
        'usar': codigo in marcadas, 'nueva': bool(config) and codigo not in recordadas and not fuente.confirmada,
    } for codigo, cta in balance.cuentas.items()]
    movimientos = incluidos_srv.sugerir(fuente, incluidos_srv.movimientos_en_corte(fuente))
    if fuente.confirmada:  # ya se decidió para este archivo: se muestra lo guardado
        ya = (incluidos_srv._ids(fuente.incluidos, 'ajustes'), incluidos_srv._ids(fuente.incluidos, 'facturas'))
        for m in movimientos:
            m['marcado'] = m['id'] in (ya[0] if m['tipo'] == 'ajuste' else ya[1])
    else:
        for m in movimientos:
            m['marcado'] = m['sugerido']
    return render(request, 'conciliacion_terceros/cuentas.html', {
        'conciliacion': conc, 'fuente': fuente, 'filas': filas, 'movimientos': movimientos,
        # Los verificados contra el archivo anterior ya traen la decisión; solo los dudosos piden atención.
        'claros': [m for m in movimientos if m.get('verificacion') in ('si', 'no')],
        'dudosos': [m for m in movimientos if m.get('verificacion') not in ('si', 'no')],
        'numeracion_journal_id': config.numeracion_journal_id if config else '',
        'saldos_json': {f['codigo']: str(f['saldo']) for f in filas},
    })


@login_required
@require_http_methods(['POST'])
def fuente_quitar(request, pk, fuente_id):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        messages.error(request, 'La conciliación está cerrada.')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    fuente = get_object_or_404(FuenteConciliacion, pk=fuente_id, conciliacion=conc)
    nombre = fuente.empresa.nombre
    fuente.delete()
    messages.success(request, f'Se quitó el archivo de {nombre}.')
    if conc.fuentes.exists():
        return _recalcular_si_listo(request, conc)
    conc.lineas.all().delete()
    conc.resumen = {}
    conc.save(update_fields=['resumen', 'updated_at'])
    return redirect('conciliacion-terceros-detalle', pk=pk)


def _falta_confirmar(conc):
    """Mensaje si hay archivos recargados sin confirmar: mientras tanto esas empresas no suman y no se registran movimientos."""
    nombres = [f.empresa.nombre for f in conc.fuentes.filter(confirmada=False).select_related('empresa')]
    if not nombres:
        return ''
    return (f'Falta confirmar las cuentas del archivo de {", ".join(nombres)}: mientras tanto sus saldos no se suman. '
            'Confírmalas antes de registrar traslados o facturas.')


def _incluidos(conc):
    return incluidos_srv.por_empresa(conc.fuentes.filter(confirmada=True))


def _ajuste_json(a, inc=None):
    return {
        'incluido_archivo': bool(inc) and incluidos_srv.ajuste_incluido(a, inc),
        'id': a.pk, 'grupo': a.grupo, 'tipo': a.tipo, 'valor': str(a.valor), 'misma_empresa': a.misma_empresa,
        'origen': a.origen_identificacion, 'origen_empresa': a.origen_empresa_id, 'origen_cuenta': a.origen_cuenta,
        'origen_cuenta_nombre': a.origen_cuenta_nombre,
        'destino': a.destino_identificacion, 'destino_empresa': a.destino_empresa_id, 'destino_cuenta': a.destino_cuenta,
        'destino_cuenta_nombre': a.destino_cuenta_nombre, 'nota': a.nota, 'anulado': a.anulado,
        'referencia': a.referencia, 'grupo_ref': a.grupo_ref,
        'journal_estado': a.journal_estado, 'journal_label': a.get_journal_estado_display(), 'journal_ref': a.journal_ref,
        'journal_error': a.journal_error, 'aplicado': a.aplicado, 'via': 'alegra' if a.via_alegra else 'manual',
        'fecha': a.fecha.isoformat() if a.fecha else '',
        'enviando': bool(a.envio_en_curso_desde),
        'enviado_por': a.enviado_por.get_username() if a.enviado_por else '',
        'enviado_en': timezone.localtime(a.enviado_en).strftime('%d/%m/%Y %H:%M') if a.enviado_en else '',
        'creado_por': a.created_by.get_username() if a.created_by else '',
        'creado_en': timezone.localtime(a.created_at).strftime('%d/%m/%Y %H:%M') if a.created_at else '',
        'anulado_por': a.anulado_por.get_username() if a.anulado_por else '',
    }


def _ajustes_por_tercero(conc, idents=None):
    qs = conc.ajustes.select_related('created_by', 'anulado_por', 'enviado_por', 'origen_empresa')
    if idents is not None:
        qs = qs.filter(Q(origen_identificacion__in=idents) | Q(destino_identificacion__in=idents))
    out, inc = defaultdict(list), _incluidos(conc)
    for a in qs:
        j = _ajuste_json(a, inc)
        out[a.origen_identificacion].append(j)
        if a.destino_identificacion != a.origen_identificacion:
            out[a.destino_identificacion].append(j)
    return out


def _ajustes_manuales(conc):
    """Ajustes de empresas sin Alegra (vigentes): lo que hay que registrar a mano y lo ya registrado, con su asiento."""
    out, inc = [], _incluidos(conc)
    for a in conc.ajustes.filter(anulado=False).select_related('origen_empresa', 'created_by', 'enviado_por').order_by('created_at', 'id'):
        if a.via_alegra and a.journal_estado != AjusteConciliacion.JOURNAL_MANUAL:
            continue
        out.append(dict(_ajuste_json(a, inc), empresa_nombre=a.origen_empresa.nombre, referencia=a.referencia,
                        lineas=ajustes_srv.lineas_asiento(a)))
    return out


def _factura_json(f, inc=None):
    return {
        'incluido_archivo': bool(inc) and incluidos_srv.factura_incluida(f, inc),
        'siguiente': facturacion.siguiente_paso(f),
        'id': f.pk, 'grupo': f.grupo, 'tipo': f.tipo, 'tipo_label': f.get_tipo_display(), 'empresa': f.empresa_id,
        'proyecto': f.proyecto, 'negocio_ref': f.negocio_ref, 'identificacion': f.identificacion, 'concepto': f.concepto,
        'concepto_label': f.get_concepto_display(), 'fecha': f.fecha.isoformat(), 'numero': f.numero,
        'valor_venta': str(f.valor_venta), 'valor_intereses': str(f.valor_intereses), 'total': str(f.total),
        'intereses_previos': str(f.intereses_previos),
        'cruce_cuenta': f.cruce_cuenta, 'cruce_estado': f.cruce_estado, 'cruce_label': f.get_cruce_estado_display(),
        'estado': f.estado, 'estado_label': f.get_estado_display(), 'alegra_invoice_id': f.alegra_invoice_id,
        'alegra_journal_id': f.alegra_journal_id, 'error': f.error, 'nota': f.nota,
        'escritura_marcada': bool((f.respuesta or {}).get('escritura')),
        'costo': str(f.costo), 'costo_estado': f.costo_estado, 'error_costo': f.error_costo, 'error_cruce': f.error_cruce,
        'alegra_costo_journal_id': f.alegra_costo_journal_id, 'paso_en_curso': f.paso_en_curso,
        'costo_label': {'no_aplica': '', 'pendiente': 'Pendiente', 'registrado': 'Registrado'}.get(f.costo_estado, ''),
        'autorrenta': str(f.autorrenta), 'autorrenta_estado': f.autorrenta_estado,
        'autorrenta_tarifa': str(f.autorrenta_tarifa), 'error_autorrenta': f.error_autorrenta,
        'alegra_autorrenta_journal_id': f.alegra_autorrenta_journal_id,
        'autorrenta_por_registrar': str(facturacion.autorrenta_pendiente(f)),
        'creado_por': f.created_by.get_username() if f.created_by else '',
        'creado_en': timezone.localtime(f.created_at).strftime('%d/%m/%Y %H:%M') if f.created_at else '',
    }


def _crudos():
    """Solo los Id que en Andinasoft están guardados con puntos, guiones o espacios: {normalizado: como está}."""
    return {k: v[0] for k, v in engine.identificaciones_andina().items() if v[0] != k}


def _facturas_por_tercero(conc, idents=None):
    qs = conc.facturas.select_related('created_by')
    if idents is not None:
        qs = qs.filter(identificacion__in=idents)
    out, inc = defaultdict(list), _incluidos(conc)
    for f in qs:
        out[f.identificacion].append(_factura_json(f, inc))
    return out


def _linea_json(l, ajustes=None, correcciones=None, facturas=None, equivs=None, crudos=None):
    return {
        'facturas': (facturas or {}).get(l.identificacion, []),
        'correcciones': (correcciones or {}).get(l.identificacion, []),
        'ajustes': (ajustes or {}).get(l.identificacion, []),
        'id': l.pk, 'identificacion': l.identificacion, 'nombre': l.nombre,
        'andina': str(l.saldo_andina), 'contable': str(l.saldo_contable), 'diferencia': str(l.diferencia),
        'capital': str(l.capital), 'intereses': str(l.intereses), 'estado': l.estado,
        'negocios': l.negocios, 'cuentas': l.cuentas, 'alertas': l.alertas,
        'observacion': l.observacion, 'sugerencia': l.sugerencia,
        'equivalencia': (equivs or {}).get(l.identificacion, ''),
        # Id tal como está guardado en Andinasoft cuando trae puntos, guiones o espacios.
        'identificacion_andina': (crudos or {}).get(l.identificacion, ''),
        'revision': l.revision, 'nota': l.nota,
        'justificado_valor': str(l.justificado_valor) if l.justificado_valor is not None else '',
        'revisado_por': l.revisado_por.get_username() if l.revisado_por else '',
        'revisado_en': l.revisado_en.strftime('%d/%m/%Y %H:%M') if l.revisado_en else '',
    }


@login_required
@require_http_methods(['GET'])
def detalle(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    fuentes = list(conc.fuentes.select_related('empresa', 'created_by'))
    lineas = list(conc.lineas.select_related('revisado_por'))
    ajustes = _ajustes_por_tercero(conc)
    facturas = _facturas_por_tercero(conc)
    correcciones = defaultdict(list)
    for c in CorreccionIdentificacion.objects.select_related('created_by'):
        j = _correccion_json(c)
        correcciones[c.id_errado].append(j)
        correcciones[c.id_correcto].append(j)
    resumen = conc.resumen or {}
    for c in resumen.get('cuentas', []):
        c['empresa_corta'] = _empresa_corta(c.get('empresa_nombre'))
    andina = sum((l.saldo_andina for l in lineas), 0)
    contable = sum((l.saldo_contable for l in lineas), 0)
    manuales = _ajustes_manuales(conc)
    return render(request, 'conciliacion_terceros/detalle.html', {
        'conciliacion': conc,
        'falta_confirmar': _falta_confirmar(conc),
        'saldos_manuales': _saldos_manuales_json(conc),
        'ajustes_manuales': manuales,
        'manuales_pendientes': sum(1 for a in manuales if a['journal_estado'] == AjusteConciliacion.JOURNAL_PENDIENTE),
        'hoy': timezone.localdate().isoformat(),
        'fuentes': fuentes,
        'empresas_fuente': empresas.objects.order_by('nombre'),
        'formatos': FuenteConciliacion.FORMATO_CHOICES,
        'resumen': resumen,
        'total_andina': andina,
        'total_contable': contable,
        'diferencia_total': contable - andina,
        'lineas_json': [_linea_json(l, ajustes, correcciones, facturas, engine.equivalencias()[1], _crudos()) for l in lineas],
        'config_facturacion': {
            c.proyecto: {'empresa': c.empresa_id, 'empresa_nombre': c.empresa.nombre, 'modo': c.modo, 'emision': c.emision,
                         'faltantes': c.faltantes_alegra() if c.modo == ConfigFacturacion.MODO_ALEGRA else []}
            for c in ConfigFacturacion.objects.select_related('empresa')
        },
        'empresas_factura': [{'id': f.empresa_id, 'nombre': f.empresa.nombre, 'alegra': f.empresa.alegra_enabled} for f in fuentes],
        'alegra_empresas': list(empresas.objects.filter(alegra_enabled=True).values_list('pk', flat=True)),
        'catalogo': resumen.get('catalogo', []),
        'empresas_lineas': [(f.empresa_id, _empresa_corta(f.empresa.nombre)) for f in fuentes],
        'proyectos_lineas': [p['proyecto'] for p in resumen.get('proyectos', [])],
        'proyectos_todos': [(p, p not in (conc.proyectos_excluidos or [])) for p in engine.proyectos_conciliables()],
        'estados': ConciliacionLinea.ESTADO_CHOICES,
        'revisiones': ConciliacionLinea.REVISION_CHOICES,
        'resultados_adj': [('cuadra', 'Cuadra'), ('justificado', 'Cuadra con justificación'), ('reparto', 'Cuadra en total, no por titular'), ('diferencia', 'Con diferencia'), ('sin_contable', 'Sin saldo en contabilidad'),
                           ('no_cuenta', 'Desistido o anulado con saldo')],
    })


@login_required
@require_http_methods(['POST'])
def linea_revision(request, pk, linea_id):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    linea = get_object_or_404(ConciliacionLinea, pk=linea_id, conciliacion=conc)
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    revision = data.get('revision', linea.revision)
    if revision not in dict(ConciliacionLinea.REVISION_CHOICES):
        return JsonResponse({'detail': 'Revisión inválida.'}, status=400)
    nota = (data.get('nota', linea.nota) or '')[:5000]
    justificado = None
    if revision == ConciliacionLinea.REVISION_JUSTIFICADO:
        # Se acepta una diferencia por un valor exacto y con explicación; si la diferencia cambia, deja de valer.
        if not nota.strip():
            return JsonResponse({'detail': 'Para marcarlo como «Cuadra con justificación» escribe la explicación en la nota.'}, status=400)
        try:
            justificado = Decimal(str(data.get('justificado_valor') if data.get('justificado_valor') not in (None, '')
                                      else linea.diferencia)).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError):
            return JsonResponse({'detail': 'El valor justificado no es válido.'}, status=400)
        if abs(linea.diferencia) <= Decimal(conc.tolerancia):
            return JsonResponse({'detail': 'Esta línea ya cuadra: no hay diferencia que justificar.'}, status=400)
    linea.revision = revision
    linea.nota = nota
    linea.justificado_valor = justificado
    linea.revisado_por = request.user
    linea.revisado_en = timezone.now()
    engine.aplicar_justificacion(linea, Decimal(conc.tolerancia))
    linea.save(update_fields=['revision', 'nota', 'justificado_valor', 'estado', 'alertas', 'revisado_por', 'revisado_en'])
    return JsonResponse({'ok': True, 'linea': _linea_json(linea, _ajustes_por_tercero(conc, [linea.identificacion]),
                                                          equivs=engine.equivalencias()[1], crudos=_crudos())})


def _lineas_afectadas(conc, idents):
    idents = sorted(set(idents))
    ajustes = _ajustes_por_tercero(conc, idents)
    facturas = _facturas_por_tercero(conc, idents)
    lineas = conc.lineas.filter(identificacion__in=idents).select_related('revisado_por')
    estados = defaultdict(int)
    for e in conc.lineas.values_list('estado', flat=True):
        estados[e] += 1
    equivs, crudos = engine.equivalencias()[1], _crudos()
    return {'lineas': [_linea_json(l, ajustes, None, facturas, equivs, crudos) for l in lineas], 'estados': dict(estados)}


# ---------------------------------------------------------------------------
# Facturación
# ---------------------------------------------------------------------------

def _referencias_ajenas(emp, datos):
    """Referencias configuradas que no existen en el Alegra de la empresa (None si no se pudo consultar)."""
    try:
        refs = facturacion.referencias_alegra(emp)
    except Exception:
        logger.warning('No se pudieron leer las referencias de Alegra de %s', getattr(emp, 'pk', emp), exc_info=True)
        return None
    listas = {
        'numeracion_id': ('numeración de factura', 'numeraciones_factura'), 'item_venta_id': ('ítem de venta', 'items'),
        'item_intereses_id': ('ítem de intereses', 'items'), 'impuesto_id': ('impuesto', 'impuestos'),
        'centro_costo_id': ('centro de costo', 'centros_costo'), 'cuenta_cxc_id': ('cuenta por cobrar', 'cuentas'),
        'cuenta_costo_id': ('cuenta de costo', 'cuentas'), 'cuenta_inventario_id': ('cuenta de inventario', 'cuentas'),
    }
    out = []
    for campo, (nombre, lista) in listas.items():
        valor = datos.get(campo)
        if valor and valor not in {str(x.get('id')) for x in refs.get(lista, [])}:
            out.append(nombre)
    return out


def _guardar_autorrenta(request):
    """Tarifa y cuentas de la autorretención de una empresa: se configuran una sola vez y valen para todos sus
    proyectos, porque la obligación es de la empresa. Con tarifa en 0 la empresa no autorretiene."""
    emp = get_object_or_404(empresas, pk=request.POST.get('empresa'))
    try:
        tarifa = Decimal(str(request.POST.get('autorrenta_tarifa') or 0).replace(',', '.'))
    except InvalidOperation:
        tarifa = None
    if tarifa is None or tarifa < 0 or tarifa > 100:
        messages.error(request, 'La tarifa de autorretención es un porcentaje entre 0 y 100 (p. ej. 1,1).')
        return redirect('conciliacion-terceros-facturacion')
    campos = ['autorrenta_cuenta_anticipo_id', 'autorrenta_cuenta_anticipo_codigo', 'autorrenta_cuenta_anticipo_nombre',
              'autorrenta_cuenta_pasivo_id', 'autorrenta_cuenta_pasivo_codigo', 'autorrenta_cuenta_pasivo_nombre']
    datos = {c: (request.POST.get(c) or '').strip() for c in campos}
    datos['autorrenta_tarifa'] = tarifa
    if tarifa > 0:
        if not (datos['autorrenta_cuenta_anticipo_id'] and datos['autorrenta_cuenta_pasivo_id']):
            messages.error(request, 'Con tarifa mayor que cero hay que elegir las dos cuentas del asiento '
                                    '(anticipo de renta y autorretenciones por pagar); no se guardó.')
            return redirect('conciliacion-terceros-facturacion')
        try:
            ids = {str(c['id']) for c in facturacion.cuentas_alegra(emp)}
        except Exception:
            logger.warning('No se pudieron leer las cuentas de Alegra de %s', emp.pk, exc_info=True)
            messages.error(request, f'No se pudieron consultar las cuentas de {emp.nombre} en Alegra para '
                                    'verificarlas; no se guardó. Intenta de nuevo en un momento.')
            return redirect('conciliacion-terceros-facturacion')
        ajenas = [datos[f'autorrenta_cuenta_{k}_codigo'] or k for k in ('anticipo', 'pasivo')
                  if datos[f'autorrenta_cuenta_{k}_id'] not in ids]
        if ajenas:
            messages.error(request, f'Estas cuentas no existen en el Alegra de {emp.nombre} (¿quedaron de otra '
                                    f'empresa?): {", ".join(ajenas)}. Vuelve a elegirlas; no se guardó.')
            return redirect('conciliacion-terceros-facturacion')
    ConfigEmpresa.objects.update_or_create(empresa=emp, defaults=datos)
    if tarifa > 0:
        pendientes = FacturaConciliacion.objects.filter(
            empresa_id=emp.pk, autorrenta_estado=FacturaConciliacion.CRUCE_PENDIENTE,
            estado__in=facturacion.ESTADOS_FACTURADA).count()
        messages.success(request, f'{emp.nombre}: autorretención al {tarifa}% guardada.' + (
            f' Quedan {pendientes} factura(s) ya emitida(s) sin el asiento: se registran desde el módulo de facturas.'
            if pendientes else ''))
    else:
        messages.success(request, f'{emp.nombre}: queda sin autorretención (tarifa en 0).')
    return redirect('conciliacion-terceros-facturacion')


@login_required
@require_http_methods(['GET', 'POST'])
def facturacion_config(request):
    _guard(request)
    proyectos_lista = engine.proyectos_conciliables()
    if request.method == 'POST' and request.POST.get('form') == 'autorrenta':
        return _guardar_autorrenta(request)
    if request.method == 'POST':
        proyecto = request.POST.get('proyecto')
        if proyecto not in proyectos_lista:
            messages.error(request, 'Proyecto inválido.')
            return redirect('conciliacion-terceros-facturacion')
        emp = get_object_or_404(empresas, pk=request.POST.get('empresa'))
        campos = ['modo', 'emision', 'forma_pago', 'numeracion_id', 'numeracion_nombre', 'item_venta_id', 'item_venta_nombre',
                  'item_intereses_id', 'item_intereses_nombre', 'impuesto_id', 'impuesto_nombre', 'centro_costo_id',
                  'centro_costo_nombre',
                  'cuenta_cxc_id', 'cuenta_cxc_codigo', 'cuenta_cxc_nombre', 'numeracion_journal_id', 'numeracion_journal_nombre',
                  'cuenta_costo_id', 'cuenta_costo_codigo', 'cuenta_costo_nombre',
                  'cuenta_inventario_id', 'cuenta_inventario_codigo', 'cuenta_inventario_nombre']
        datos = {c: (request.POST.get(c) or '').strip() for c in campos}
        if datos['modo'] not in dict(ConfigFacturacion.MODO_CHOICES):
            datos['modo'] = ConfigFacturacion.MODO_INFORMATIVA
        if datos['modo'] == ConfigFacturacion.MODO_ALEGRA and not emp.alegra_enabled:
            messages.error(request, f'{emp.nombre} no tiene integración con Alegra: solo puede facturar de forma informativa.')
            return redirect('conciliacion-terceros-facturacion')
        if datos['emision'] not in dict(ConfigFacturacion.EMISION_CHOICES):
            datos['emision'] = ConfigFacturacion.EMISION_BORRADOR
        # Igual que caja: el ID de la numeración es el que entrega Alegra (p. ej. 01KT9P5PEQY7D978MMYH0MNHTR).
        if datos['numeracion_journal_id'] and not re.fullmatch(r'[A-Za-z0-9_-]+', datos['numeracion_journal_id']):
            messages.error(request, 'La numeración de los journals debe ser el ID de la numeración en Alegra (letras y números, sin espacios), o quedar vacía.')
            return redirect('conciliacion-terceros-facturacion')
        datos['numeracion_journal_nombre'] = ''
        if datos['forma_pago'] not in ('CREDIT', 'CASH'):
            datos['forma_pago'] = 'CREDIT'
        try:
            datos['dias_vencimiento'] = max(0, int(request.POST.get('dias_vencimiento') or 0))
        except ValueError:
            datos['dias_vencimiento'] = 0
        try:
            datos['costo_m2'] = max(Decimal(0), Decimal(str(request.POST.get('costo_m2') or 0).replace(',', '')))
        except InvalidOperation:
            datos['costo_m2'] = Decimal(0)
        if datos['modo'] == ConfigFacturacion.MODO_ALEGRA:
            ajenas = _referencias_ajenas(emp, datos)
            if ajenas is None:
                messages.error(request, f'No se pudieron consultar las referencias de {emp.nombre} en Alegra para verificarlas; '
                                        'no se guardó. Intenta de nuevo en un momento.')
                return redirect('conciliacion-terceros-facturacion')
            if ajenas:
                messages.error(request, f'Estas referencias no existen en Alegra para {emp.nombre} (¿quedaron de otra empresa?): '
                                        f'{", ".join(ajenas)}. Vuelve a elegirlas; no se guardó.')
                return redirect('conciliacion-terceros-facturacion')
        cfg, _ = ConfigFacturacion.objects.update_or_create(proyecto=proyecto, defaults=dict(datos, empresa=emp, updated_by=request.user))
        faltan = cfg.faltantes_alegra() if cfg.modo == ConfigFacturacion.MODO_ALEGRA else []
        if faltan:
            messages.warning(request, f'{proyecto}: guardado, pero para crear facturas en Alegra falta: {", ".join(faltan)}.')
        else:
            messages.success(request, f'{proyecto}: configuración guardada.')
        return redirect('conciliacion-terceros-facturacion')

    configs = {c.proyecto: c for c in ConfigFacturacion.objects.select_related('empresa')}
    filas = [{'proyecto': p, 'cfg': configs.get(p)} for p in proyectos_lista]
    datos_js = {
        p: ({f.name: getattr(c, f.attname) for f in ConfigFacturacion._meta.concrete_fields if f.name not in ('id', 'updated_by', 'updated_at')}
            if c else None)
        for p, c in configs.items()
    }
    cfgs_emp = {str(c.empresa_id): c for c in ConfigEmpresa.objects.all()}
    pendientes = {r['empresa_id']: r['n'] for r in FacturaConciliacion.objects.filter(
        autorrenta_estado=FacturaConciliacion.CRUCE_PENDIENTE, estado__in=facturacion.ESTADOS_FACTURADA,
    ).values('empresa_id').annotate(n=Count('pk'))}
    campos_autorrenta = ['autorrenta_tarifa', 'autorrenta_cuenta_anticipo_id', 'autorrenta_cuenta_anticipo_codigo',
                         'autorrenta_cuenta_anticipo_nombre', 'autorrenta_cuenta_pasivo_id',
                         'autorrenta_cuenta_pasivo_codigo', 'autorrenta_cuenta_pasivo_nombre']
    empresas_alegra = [e for e in empresas.objects.order_by('nombre') if e.alegra_enabled]
    filas_autorrenta = [{'empresa': e, 'cfg': cfgs_emp.get(str(e.pk)), 'pendientes': pendientes.get(str(e.pk), 0)}
                        for e in empresas_alegra]
    autorrenta_js = {str(e.pk): ({c: str(getattr(cfgs_emp[str(e.pk)], c)) for c in campos_autorrenta}
                                 if cfgs_emp.get(str(e.pk)) else None) for e in empresas_alegra}
    return render(request, 'conciliacion_terceros/facturacion.html', {
        'filas': filas,
        'empresas': empresas.objects.order_by('nombre'),
        'modos': ConfigFacturacion.MODO_CHOICES,
        'emisiones': ConfigFacturacion.EMISION_CHOICES,
        'configs_json': datos_js,
        'filas_autorrenta': filas_autorrenta,
        'autorrenta_json': autorrenta_js,
    })


# ---------------------------------------------------------------------------
# Módulo de facturas: todas las facturas registradas, en qué va cada una y qué le falta.
# Es la pantalla para los pasos contables de una factura ya emitida (costo, cruce y autorretención),
# incluidas las de conciliaciones cerradas: esos asientos no cambian ninguna cifra de la conciliación.
# ---------------------------------------------------------------------------

PASOS_FACTURA = {
    'autorrenta': 'Autorretención por registrar',
    'costo': 'Costo por registrar',
    'cruzar': 'Cruce por registrar',
    'enviar': 'Sin crear en Alegra',
    'emitir': 'En borrador por emitir',
}


def _fila_factura(f, cfgs_emp):
    """Una factura para el listado: sus cuatro pasos y lo que le falta."""
    cfg_emp = cfgs_emp.get(str(f.empresa_id))
    pendiente = facturacion.autorrenta_pendiente(f, cfg_emp)
    siguiente = facturacion.siguiente_paso(f, cfg_emp)
    if not siguiente and f.tipo == FacturaConciliacion.TIPO_ALEGRA and f.estado == FacturaConciliacion.ESTADO_BORRADOR:
        siguiente = 'emitir'
    return {
        'f': f,
        'siguiente': siguiente,
        'siguiente_label': PASOS_FACTURA.get(siguiente, ''),
        'autorrenta_pendiente': pendiente,
        'tarifa': cfg_emp.autorrenta_tarifa if cfg_emp else 0,
        # El cruce y el costo solo se pueden mandar desde aquí si la factura está emitida en Alegra.
        'puede_pasos': f.tipo == FacturaConciliacion.TIPO_ALEGRA and f.estado == FacturaConciliacion.ESTADO_EMITIDA,
    }


def _facturas_filtradas(request):
    """El queryset del listado según los filtros de la URL, y los filtros ya normalizados."""
    filtros = {k: (request.GET.get(k) or '').strip() for k in ('empresa', 'proyecto', 'estado', 'tipo', 'paso', 'q')}
    qs = FacturaConciliacion.objects.select_related('empresa', 'conciliacion', 'created_by')
    if filtros['empresa']:
        qs = qs.filter(empresa_id=filtros['empresa'])
    if filtros['proyecto']:
        qs = qs.filter(proyecto=filtros['proyecto'])
    if filtros['tipo']:
        qs = qs.filter(tipo=filtros['tipo'])
    if filtros['estado']:
        qs = qs.filter(estado=filtros['estado'])
    elif filtros['paso']:
        qs = qs.exclude(estado=FacturaConciliacion.ESTADO_ANULADA)
    if filtros['paso'] == 'autorrenta':
        # Solo las de empresas que autorretienen: en las demás el paso no existe.
        configuradas = [str(c.empresa_id) for c in ConfigEmpresa.objects.all() if c.autorrenta_activa]
        qs = qs.filter(autorrenta_estado=FacturaConciliacion.CRUCE_PENDIENTE, estado__in=facturacion.ESTADOS_FACTURADA,
                       empresa_id__in=configuradas)
    elif filtros['paso'] == 'costo':
        qs = qs.filter(costo_estado=FacturaConciliacion.CRUCE_PENDIENTE, costo__gt=0)
    elif filtros['paso'] == 'cruzar':
        qs = qs.filter(cruce_estado=FacturaConciliacion.CRUCE_PENDIENTE).exclude(cruce_cuenta='')
    elif filtros['paso'] == 'enviar':
        qs = qs.filter(tipo=FacturaConciliacion.TIPO_ALEGRA,
                       estado__in=(FacturaConciliacion.ESTADO_PENDIENTE, FacturaConciliacion.ESTADO_ERROR))
    elif filtros['paso'] == 'emitir':
        qs = qs.filter(tipo=FacturaConciliacion.TIPO_ALEGRA, estado=FacturaConciliacion.ESTADO_BORRADOR)
    if filtros['q']:
        t = filtros['q']
        qs = qs.filter(Q(identificacion__icontains=t) | Q(nombre__icontains=t) | Q(negocio_ref__icontains=t)
                       | Q(numero__icontains=t) | Q(proyecto__icontains=t))
    return qs.order_by('-fecha', '-id'), filtros


@login_required
@require_http_methods(['GET'])
def facturas(request):
    _guard(request)
    qs, filtros = _facturas_filtradas(request)
    cfgs_emp = {str(c.empresa_id): c for c in ConfigEmpresa.objects.all()}
    pagina = Paginator(qs, 100).get_page(request.GET.get('p') or 1)
    filas = [_fila_factura(f, cfgs_emp) for f in pagina.object_list]
    # Cuántas facturas esperan cada paso (sobre todas, no solo esta página): son los atajos de arriba.
    vigentes = FacturaConciliacion.objects.exclude(estado=FacturaConciliacion.ESTADO_ANULADA)
    empresas_autorrenta = [k for k, c in cfgs_emp.items() if c.autorrenta_activa]
    conteos = {
        'autorrenta': vigentes.filter(autorrenta_estado=FacturaConciliacion.CRUCE_PENDIENTE,
                                      estado__in=facturacion.ESTADOS_FACTURADA,
                                      empresa_id__in=empresas_autorrenta).count(),
        'costo': vigentes.filter(costo_estado=FacturaConciliacion.CRUCE_PENDIENTE, costo__gt=0).count(),
        'cruzar': vigentes.filter(cruce_estado=FacturaConciliacion.CRUCE_PENDIENTE).exclude(cruce_cuenta='').count(),
        'enviar': vigentes.filter(tipo=FacturaConciliacion.TIPO_ALEGRA,
                                  estado__in=(FacturaConciliacion.ESTADO_PENDIENTE, FacturaConciliacion.ESTADO_ERROR)).count(),
        'emitir': vigentes.filter(tipo=FacturaConciliacion.TIPO_ALEGRA, estado=FacturaConciliacion.ESTADO_BORRADOR).count(),
    }
    abierta = Conciliacion.objects.filter(estado=Conciliacion.ESTADO_BORRADOR).order_by('-fecha_corte', '-id').first()
    return render(request, 'conciliacion_terceros/facturas.html', {
        'filas': filas,
        'pagina': pagina,
        'filtros': filtros,
        'conteos': conteos,
        'pasos': PASOS_FACTURA,
        'empresas': empresas.objects.order_by('nombre'),
        'proyectos': sorted(set(FacturaConciliacion.objects.values_list('proyecto', flat=True).distinct())),
        'estados': FacturaConciliacion.ESTADO_CHOICES,
        'tipos': FacturaConciliacion.TIPO_CHOICES,
        'conciliacion_abierta': abierta,
        'sin_autorrenta': not empresas_autorrenta,
    })



def _cuentas_del_titular(linea, empresa_id):
    """Las cuentas de esa empresa donde el titular tiene saldo, de mayor a menor."""
    out = []
    for c in (linea.cuentas if linea else []):
        if str(c.get('empresa')) != str(empresa_id):
            continue
        out.append({'cuenta': c.get('cuenta'), 'cuenta_nombre': c.get('cuenta_nombre') or '',
                    'saldo': str(c.get('saldo') or 0), 'manual': bool(c.get('manual'))})
    return sorted(out, key=lambda c: Decimal(c['saldo']), reverse=True)


def _negocio_para_facturar(conc, proyecto, ref):
    """Todo lo que el asistente necesita de un negocio: sus titulares con lo recaudado, la cuenta de anticipos donde
    cada uno tiene el saldo, cómo está cada uno frente a la contabilidad y qué facturas ya tiene el negocio."""
    n = next((x for x in _negocios_facturables(conc) if x['proyecto'] == proyecto and x['ref'] == ref), None)
    if not n:
        return None
    cfg = facturacion.config_de(proyecto)
    empresa_id = str(cfg.empresa_id) if cfg else ''
    lineas = {l.identificacion: l for l in conc.lineas.filter(identificacion__in=n['titulares'])}
    estados = dict(ConciliacionLinea.ESTADO_CHOICES)

    def del_negocio(l):
        for x in (l.negocios if l else []):
            if x.get('proyecto') == proyecto and str(x.get('ref')) == ref and x.get('situacion') != 'factura':
                return x
        return None

    titulares, cuenta_veces = [], defaultdict(int)
    for ident in n['titulares']:
        l = lineas.get(ident)
        neg = del_negocio(l)
        cuentas = _cuentas_del_titular(l, empresa_id) if empresa_id else []
        con_saldo = [c for c in cuentas if Decimal(c['saldo']) > 0]
        if con_saldo:
            cuenta_veces[con_saldo[0]['cuenta']] += 1
        titulares.append({
            'identificacion': ident, 'nombre': (l.nombre if l else '') or '',
            'capital': str(Decimal(neg['capital'])) if neg else '0',
            'intereses': str(Decimal(neg['intereses'])) if neg else '0',
            'total': str(Decimal(neg['valor'])) if neg else '0',
            'cuentas': cuentas, 'cuenta': con_saldo[0]['cuenta'] if con_saldo else '',
            'estado': l.estado if l else '', 'estado_label': estados.get(l.estado, 'Sin línea') if l else 'Sin línea',
            'diferencia': str(l.diferencia) if l else '0', 'andina': str(l.saldo_andina) if l else '0',
            'contable': str(l.saldo_contable) if l else '0',
            'sin_cuenta': not con_saldo,
        })
    # Un titular sin saldo propio usa la cuenta donde están los demás: suele ser el mismo anticipo del negocio.
    defecto = max(cuenta_veces, key=lambda c: cuenta_veces[c]) if cuenta_veces else ''
    for t in titulares:
        if not t['cuenta'] and defecto:
            t['cuenta'] = defecto
        nombre = next((c['cuenta_nombre'] for c in t['cuentas'] if c['cuenta'] == t['cuenta']), '')
        if not nombre and defecto == t['cuenta']:
            nombre = next((c['cuenta_nombre'] for x in titulares for c in x['cuentas'] if c['cuenta'] == t['cuenta']), '')
        t['cuenta_nombre'] = nombre
    previas = [{'id': f.pk, 'identificacion': f.identificacion, 'numero': f.numero or f'#{f.pk}', 'total': str(f.total),
                'fecha': f.fecha.isoformat(), 'estado': f.get_estado_display(), 'tipo': f.get_tipo_display()}
               for f in FacturaConciliacion.objects.filter(proyecto=proyecto, negocio_ref=ref,
                                                           identificacion__in=n['titulares'])
               .exclude(estado=FacturaConciliacion.ESTADO_ANULADA).order_by('id')]
    return {'negocio': n, 'titulares': titulares, 'cfg': cfg, 'previas': previas, 'empresa_id': empresa_id}


@login_required
@require_http_methods(['GET'])
def factura_nueva(request):
    """
    Asistente para facturar un negocio: el paso 1 (elegir el negocio) viene del módulo de facturas; aquí se revisa
    todo en una sola pantalla y se confirma. Lo que no es una decisión —empresa, numeración, cuentas, costo— sale
    de la configuración del proyecto y se muestra en texto; se puede cambiar, pero no hay que contestarlo.
    """
    _guard(request)
    conc = Conciliacion.objects.filter(estado=Conciliacion.ESTADO_BORRADOR).order_by('-fecha_corte', '-id').first()
    if not conc:
        messages.error(request, 'No hay una conciliación en revisión: para facturar hay que tener una abierta.')
        return redirect('conciliacion-terceros-facturas')
    proyecto = (request.GET.get('proyecto') or '').strip()
    ref = (request.GET.get('ref') or '').strip()
    datos = _negocio_para_facturar(conc, proyecto, ref) if proyecto and ref else None
    if not datos:
        messages.error(request, f'{proyecto} {ref}: ese negocio no está entre los que esperan saldo en la '
                                f'conciliación al {conc.fecha_corte:%d/%m/%Y}.')
        return redirect('conciliacion-terceros-facturas')
    cfg = datos['cfg']
    faltantes = cfg.faltantes_alegra() if cfg and cfg.modo == ConfigFacturacion.MODO_ALEGRA else []
    cfg_emp = facturacion.config_empresa(cfg.empresa_id) if cfg else None
    total = sum(Decimal(t['total']) for t in datos['titulares'])
    tarifa = cfg_emp.autorrenta_tarifa if (cfg_emp and cfg_emp.autorrenta_activa) else Decimal(0)
    return render(request, 'conciliacion_terceros/factura_nueva.html', {
        'conciliacion': conc,
        'negocio': datos['negocio'],
        'titulares': datos['titulares'],
        'previas': datos['previas'],
        'cfg': cfg,
        'faltantes': faltantes,
        'puede_alegra': bool(cfg and cfg.modo == ConfigFacturacion.MODO_ALEGRA and not faltantes),
        'empresa': cfg.empresa if cfg else None,
        'catalogo': [c for c in (conc.resumen or {}).get('catalogo', []) if str(c['empresa']) == datos['empresa_id']],
        'total': total,
        'tarifa_autorrenta': tarifa,
        'autorrenta': facturacion.autorrenta_valor(total, tarifa),
        'hoy': timezone.localdate().isoformat(),
        'titulares_json': datos['titulares'],
    })


@login_required
@require_http_methods(['POST'])
def facturas_accion(request, factura_id, accion):
    """Pasos contables de una factura ya creada, desde el módulo: no dependen del estado de la conciliación,
    porque ninguno cambia sus cifras. Crear la factura en Alegra sigue siendo cosa de la conciliación."""
    _guard(request)
    f = get_object_or_404(FacturaConciliacion.objects.select_related('empresa'), pk=factura_id)
    try:
        if accion == 'autorrenta':
            facturacion.registrar_autorrenta(f)
        elif accion in ('costo', 'cruzar'):
            cfg = facturacion.config_de(f.proyecto)
            if not cfg:
                raise facturacion.FacturacionError('El proyecto no tiene configuración de facturación.')
            (facturacion.registrar_costo if accion == 'costo' else facturacion.cruzar)(f, cfg)
        elif accion == 'emitir':
            facturacion.emitir(f)
        else:
            return JsonResponse({'detail': 'Acción desconocida.'}, status=400)
    except facturacion.FacturacionError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    f.refresh_from_db()
    cfg_emp = facturacion.config_empresa(f.empresa_id)
    return JsonResponse({'ok': True, 'factura': {
        'id': f.pk, 'estado': f.estado, 'estado_label': f.get_estado_display(),
        'autorrenta': str(f.autorrenta), 'autorrenta_estado': f.autorrenta_estado,
        'autorrenta_label': f.get_autorrenta_estado_display(), 'error_autorrenta': f.error_autorrenta,
        'autorrenta_pendiente': str(facturacion.autorrenta_pendiente(f, cfg_emp)),
        'costo_estado': f.costo_estado, 'error_costo': f.error_costo,
        'cruce_estado': f.cruce_estado, 'error_cruce': f.error_cruce,
        'siguiente': facturacion.siguiente_paso(f, cfg_emp),
    }})


@login_required
@require_http_methods(['POST'])
def facturas_autorrenta_lote(request):
    """Registra la autorretención de varias facturas de una pasada. La pantalla manda tandas cortas porque cada
    factura son dos llamadas a Alegra (buscar el journal y crearlo): así ninguna petición se queda sin respuesta."""
    _guard(request)
    try:
        ids = [int(x) for x in (json.loads(request.body or '{}').get('ids') or [])][:20]
    except (ValueError, TypeError):
        return JsonResponse({'detail': 'Lista de facturas inválida.'}, status=400)
    if not ids:
        return JsonResponse({'detail': 'No hay facturas seleccionadas.'}, status=400)
    resultados = []
    for f in FacturaConciliacion.objects.select_related('empresa').filter(pk__in=ids).order_by('fecha', 'id'):
        try:
            facturacion.registrar_autorrenta(f)
            f.refresh_from_db()
            resultados.append({'id': f.pk, 'ok': not f.error_autorrenta, 'valor': str(f.autorrenta),
                               'estado': f.autorrenta_estado, 'detail': f.error_autorrenta})
        except facturacion.FacturacionError as exc:
            resultados.append({'id': f.pk, 'ok': False, 'valor': '0', 'estado': f.autorrenta_estado, 'detail': str(exc)})
        except Exception as exc:
            logger.exception('Autorretención de la factura %s', f.pk)
            resultados.append({'id': f.pk, 'ok': False, 'valor': '0', 'estado': f.autorrenta_estado, 'detail': str(exc)})
    return JsonResponse({'ok': True, 'resultados': resultados})


def _negocios_facturables(conc):
    """Negocios con saldo de la conciliación abierta: [{proyecto, ref, total, titulares, busqueda}].
    Se arma una vez y se guarda en caché: recorrer las líneas en cada tecleo del buscador sería caro."""
    clave = f'ct:negocios_facturables:{conc.pk}:{conc.updated_at.timestamp() if conc.updated_at else 0}'
    hit = cache.get(clave)
    if hit is not None:
        return hit
    out = {}
    for negocios in conc.lineas.values_list('negocios', flat=True).iterator():
        for n in (negocios or []):
            if not n.get('suma') or n.get('situacion') == 'factura' or Decimal(str(n.get('total_negocio') or 0)) <= 0:
                continue
            k = (n.get('proyecto') or '', str(n.get('ref') or ''))
            if k in out:
                continue
            titulares = [str(t) for t in (n.get('titulares') or [])]
            out[k] = {'proyecto': k[0], 'ref': k[1], 'total': str(n.get('total_negocio') or 0), 'titulares': titulares,
                      'busqueda': ' '.join([k[0], k[1]] + titulares).lower()}
    filas = sorted(out.values(), key=lambda r: (r['proyecto'], r['ref']))
    cache.set(clave, filas, timeout=60 * 10)
    return filas


@login_required
@require_http_methods(['GET'])
def facturas_negocios(request):
    """Paso 1 del asistente: elegir el negocio. Devuelve los que esperan saldo en la conciliación abierta, cada uno
    con el enlace al asistente de facturación."""
    _guard(request)
    conc = Conciliacion.objects.filter(estado=Conciliacion.ESTADO_BORRADOR).order_by('-fecha_corte', '-id').first()
    if not conc:
        return JsonResponse({'detail': 'No hay una conciliación en revisión: para facturar hay que tener una abierta.'},
                            status=400)
    q = (request.GET.get('q') or '').strip().lower()
    proyecto = (request.GET.get('proyecto') or '').strip()
    base = reverse('conciliacion-terceros-factura-nueva')
    filas = _negocios_facturables(conc)
    if proyecto:
        filas = [n for n in filas if n['proyecto'] == proyecto]
    if q:
        palabras = q.split()
        filas = [n for n in filas if all(w in n['busqueda'] for w in palabras)]
    salida = []
    for n in filas[:60]:
        salida.append(dict(n, url=f'{base}?proyecto={quote(n["proyecto"])}&ref={quote(n["ref"])}'))
    return JsonResponse({'ok': True, 'total': len(filas), 'negocios': salida,
                         'conciliacion': {'id': conc.pk, 'corte': conc.fecha_corte.isoformat(), 'url': base}})


@login_required
@require_http_methods(['GET'])
def factura_costo_sugerido(request, pk):
    _guard(request)
    get_object_or_404(Conciliacion, pk=pk)
    try:
        return JsonResponse({'ok': True, **facturacion.costo_sugerido(request.GET.get('proyecto'), request.GET.get('ref'))})
    except Exception as exc:
        return JsonResponse({'detail': f'No se pudo calcular el costo: {exc}'}, status=400)


@login_required
@require_http_methods(['GET'])
def facturacion_referencias(request):
    _guard(request)
    emp = get_object_or_404(empresas, pk=request.GET.get('empresa'))
    if not emp.alegra_enabled:
        return JsonResponse({'detail': 'La empresa no tiene integración con Alegra.'}, status=400)
    try:
        return JsonResponse({'ok': True, 'referencias': facturacion.referencias_alegra(emp)})
    except Exception as exc:
        logger.exception('Referencias de facturación %s', emp.pk)
        return JsonResponse({'detail': f'No se pudieron cargar los datos de Alegra: {exc}'}, status=502)


@login_required
@require_http_methods(['POST'])
def equivalencia(request, pk):
    """El mismo tercero con otro Id en contabilidad: {"identificacion", "identificacion_contable", "nota"} lo guarda y
    {"identificacion", "quitar": true} lo deshace. No cambia nada en Andinasoft ni en Alegra: solo cómo se busca."""
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    ident = norm_ident(data.get('identificacion'))
    if not ident:
        return JsonResponse({'detail': 'Falta el tercero.'}, status=400)
    if data.get('quitar'):
        EquivalenciaIdentificacion.objects.filter(Q(identificacion=ident) | Q(identificacion_contable=ident)).delete()
        engine.ejecutar(conc)
        return JsonResponse(dict(ok=True, **_lineas_afectadas(conc, [ident])))
    contable = norm_ident(data.get('identificacion_contable'))
    if not contable:
        return JsonResponse({'detail': 'Escribe la identificación con la que el tercero está en contabilidad.'}, status=400)
    if contable == ident:
        return JsonResponse({'detail': 'Es la misma identificación: no hace falta equivalencia.'}, status=400)
    # Uno a uno: ninguno de los dos puede estar ya en otra equivalencia (ni como Andinasoft ni como contable).
    otra = EquivalenciaIdentificacion.objects.filter(
        Q(identificacion__in=(ident, contable)) | Q(identificacion_contable__in=(ident, contable))).first()
    if otra:
        return JsonResponse({'detail': f'{otra.identificacion} ya está enlazado con {otra.identificacion_contable} en contabilidad; '
                                       'quita esa equivalencia primero.'}, status=400)
    if conc.lineas.filter(identificacion=contable, saldo_andina__isnull=False).exclude(saldo_andina=0).exists():
        return JsonResponse({'detail': f'{contable} también tiene negocios en Andinasoft: son dos terceros distintos, '
                                       'no una equivalencia. Si es un Id mal digitado, usa «Corregir identificación».'}, status=400)
    EquivalenciaIdentificacion.objects.create(identificacion=ident, identificacion_contable=contable,
                                              nota=(data.get('nota') or '')[:2000], created_by=request.user)
    logger.info('Conciliación %s: %s enlazó %s con %s en contabilidad', conc.pk, request.user, ident, contable)
    engine.ejecutar(conc)
    return JsonResponse(dict(ok=True, **_lineas_afectadas(conc, [ident, contable])))


@login_required
@require_http_methods(['GET'])
def cuentas_alegra(request):
    """Cuentas de movimiento activas de la empresa en Alegra (código, nombre e id), para elegir la otra cuenta de un cruce."""
    _guard(request)
    emp = get_object_or_404(empresas, pk=request.GET.get('empresa'))
    if not emp.alegra_enabled:
        return JsonResponse({'detail': 'La empresa no tiene integración con Alegra.'}, status=400)
    try:
        return JsonResponse({'ok': True, 'cuentas': facturacion.cuentas_alegra(emp)})
    except Exception as exc:
        logger.exception('Cuentas de Alegra %s', emp.pk)
        return JsonResponse({'detail': f'No se pudieron consultar las cuentas en Alegra: {exc}'}, status=502)


@login_required
@require_http_methods(['GET', 'POST'])
def contacto_alegra(request):
    """Enlaza un tercero con su contacto de Alegra por id. GET valida (devuelve nombre e identificación en Alegra);
    POST guarda el enlace. Es el mismo enlace de «Enlazar tercero» en la integración de Alegra."""
    from conciliacion_terceros import contactos
    _guard(request)
    datos = request.GET if request.method == 'GET' else (json.loads(request.body or '{}') if request.body else {})
    empresa_id = str(datos.get('empresa') or '').strip()
    ident = norm_ident(datos.get('identificacion'))
    alegra_id = str(datos.get('alegra_id') or '').strip()
    if not empresa_id or not ident or not alegra_id:
        return JsonResponse({'detail': 'Faltan la empresa, el tercero o el ID de Alegra.'}, status=400)
    try:
        contacto = contactos.validar(empresa_id, ident, alegra_id)
        if request.method == 'GET':
            return JsonResponse({'ok': True, 'contacto': contacto})
        if not contacto['coincide'] and not datos.get('confirmar'):
            return JsonResponse({'detail': f'En Alegra el contacto {alegra_id} tiene la identificación «{contacto["identificacion"]}», '
                                           f'que no coincide con {ident}.', 'contacto': contacto, 'confirmar': True}, status=409)
        contactos.enlazar(empresa_id, ident, contacto['id'], contacto['nombre'])
    except contactos.EnlaceError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    logger.info('Conciliación: %s enlazó %s con el contacto %s de Alegra (empresa %s)', request.user, ident, alegra_id, empresa_id)
    return JsonResponse({'ok': True, 'contacto': contacto})


def _factura_respuesta(conc, facturas, mensaje=''):
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, mensaje=mensaje, facturas=[_factura_json(f) for f in facturas],
                             **_lineas_afectadas(conc, [f.identificacion for f in facturas])))


@login_required
@require_http_methods(['POST'])
def factura_crear(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    if _falta_confirmar(conc):
        return JsonResponse({'detail': _falta_confirmar(conc)}, status=400)
    try:
        datos = json.loads(request.body or '{}')
        facturas = facturacion.registrar(conc, datos, request.user)
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    except facturacion.RequiereConfirmacion as exc:
        return JsonResponse({'detail': str(exc), 'confirmar': True}, status=409)
    except facturacion.FacturacionError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    return _factura_respuesta(conc, facturas)


@login_required
@require_http_methods(['POST'])
def factura_accion(request, pk, factura_id, accion):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    f = get_object_or_404(FacturaConciliacion.objects.select_related('empresa'), pk=factura_id, conciliacion=conc)
    mensaje = ''
    try:
        if accion == 'verificar':
            _, mensaje = facturacion.verificar_anulacion(f, request.user)
        elif accion == 'emitir':
            facturacion.emitir(f)
        elif accion == 'costo':
            cfg = facturacion.config_de(f.proyecto)
            if not cfg:
                raise facturacion.FacturacionError('El proyecto no tiene configuración de facturación.')
            facturacion.registrar_costo(f, cfg)
        elif accion == 'cruzar':
            cfg = facturacion.config_de(f.proyecto)
            if not cfg:
                raise facturacion.FacturacionError('El proyecto no tiene configuración de facturación.')
            facturacion.cruzar(f, cfg)
        elif accion == 'autorrenta':
            facturacion.registrar_autorrenta(f)
        elif accion in ('enviar', 'reintentar'):
            if f.tipo != FacturaConciliacion.TIPO_ALEGRA or f.estado not in (FacturaConciliacion.ESTADO_ERROR, FacturaConciliacion.ESTADO_PENDIENTE):
                raise facturacion.FacturacionError('Solo se envía una factura de Alegra que no alcanzó a crearse.')
            cfg = facturacion.config_de(f.proyecto)
            if not cfg:
                raise facturacion.FacturacionError('El proyecto no tiene configuración de facturación.')
            facturacion.crear_en_alegra(f, cfg, request.user)
        elif accion == 'anular':
            facturacion.anular_registro(f, request.user)
        else:
            return JsonResponse({'detail': 'Acción inválida.'}, status=400)
    except facturacion.FacturacionError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    except Exception as exc:
        logger.exception('Factura %s %s', f.pk, accion)
        return JsonResponse({'detail': str(exc)}, status=502)
    f.refresh_from_db()
    return _factura_respuesta(conc, [f], mensaje)


def _correccion_json(c):
    return {
        'id': c.pk, 'errado': c.id_errado, 'correcto': c.id_correcto, 'modo': c.modo, 'estado': c.estado,
        'estado_label': c.get_estado_display(), 'motivo': c.motivo, 'error': c.error, 'alegra': c.alegra,
        'creado_por': c.created_by.get_username() if c.created_by else '',
        'creado_en': timezone.localtime(c.created_at).strftime('%d/%m/%Y %H:%M'),
        'proyectos': {p: sum(len(x['pks']) for x in cambios) for p, cambios in ((c.detalle or {}).get('proyectos') or {}).items()},
    }


@login_required
@require_http_methods(['GET'])
def correccion_previa(request, pk):
    _guard(request)
    get_object_or_404(Conciliacion, pk=pk)
    try:
        prev = correccion.vista_previa(request.GET.get('errado'), request.GET.get('correcto'))
    except correccion.CorreccionError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    return JsonResponse({'ok': True, 'previa': prev})


@login_required
@require_http_methods(['POST'])
def correccion_ejecutar(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    try:
        data = json.loads(request.body or '{}')
        prev = correccion.vista_previa(data.get('errado'), data.get('correcto'))
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    except correccion.CorreccionError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    if prev.get('bloqueado'):
        return JsonResponse({'detail': 'No se puede ejecutar: ' + ' '.join(prev['avisos'])}, status=400)
    empresas_alegra = [str(e) for e in (data.get('empresas_alegra') or [])]
    registro = CorreccionIdentificacion.objects.create(
        conciliacion=conc, id_errado=prev['errado'], id_correcto=prev['correcto'], modo=prev['modo'],
        motivo=(data.get('motivo') or '')[:2000], vista_previa=prev, created_by=request.user,
    )
    correccion.ejecutar(registro, prev, empresas_alegra, request.user)
    # Andinasoft cambió: se vuelve a leer completo.
    engine.ejecutar(conc)
    return JsonResponse({'ok': True, 'correccion': _correccion_json(registro)})


@login_required
@require_http_methods(['POST'])
def correccion_revertir(request, pk, correccion_id):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    registro = get_object_or_404(CorreccionIdentificacion, pk=correccion_id)
    if registro.estado == CorreccionIdentificacion.ESTADO_REVERTIDA:
        return JsonResponse({'detail': 'Ya estaba revertida.'}, status=400)
    if any(a.get('estado') == 'ok' for a in registro.alegra or []):
        return JsonResponse({'detail': 'Esta corrección también cambió contactos en Alegra; revierte primero el contacto en Alegra y luego pide la reversión manual.'}, status=400)
    correccion.revertir(registro)
    engine.ejecutar(conc)
    return JsonResponse({'ok': True, 'correccion': _correccion_json(registro)})


@login_required
@require_http_methods(['GET'])
def buscar_tercero(request, pk):
    """Busca terceros por Id o nombre: primero en la conciliación (con su estado) y luego en clientes de Andinasoft."""
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    q = (request.GET.get('q') or '').strip()
    if len(q) < 3:
        return JsonResponse({'resultados': []})
    ident = norm_ident(q)
    filtro = Q(nombre__icontains=q)
    if ident:
        filtro |= Q(identificacion__startswith=ident)
    resultados, vistos = [], set()
    for l in conc.lineas.filter(filtro).order_by('nombre')[:15]:
        vistos.add(l.identificacion)
        resultados.append({'identificacion': l.identificacion, 'nombre': l.nombre, 'estado': l.estado,
                           'andina': str(l.saldo_andina), 'contable': str(l.saldo_contable), 'diferencia': str(l.diferencia),
                           'cuentas': l.cuentas, 'en_conciliacion': True})
    filtro_c = Q(nombrecompleto__icontains=q)
    if ident:
        filtro_c |= Q(idTercero__startswith=ident)
    for c in clientes.objects.filter(filtro_c).exclude(pk='').order_by('nombrecompleto')[:15]:
        k = norm_ident(c.pk)
        if k in vistos:
            continue
        vistos.add(k)
        resultados.append({'identificacion': k, 'nombre': c.nombrecompleto, 'estado': '', 'andina': '0', 'contable': '0',
                           'diferencia': '0', 'cuentas': [], 'en_conciliacion': False})
    return JsonResponse({'resultados': resultados[:20]})



# ---------------------------------------------------------------------------
# Saldos puestos a mano: cuando el archivo de una empresa queda desactualizado y nadie va a volver a exportarlo,
# se escribe el saldo que la contabilidad muestra hoy para ese tercero en esa cuenta. No mueve nada: solo cambia
# contra qué se compara lo que espera Andinasoft.
# ---------------------------------------------------------------------------

def _saldo_archivo_actual(conc, ident, empresa_id, cuenta):
    """Lo que dice el archivo para ese tercero en esa cuenta, aunque ya haya un saldo puesto a mano encima."""
    linea = conc.lineas.filter(identificacion=ident).first()
    for c in (linea.cuentas if linea else []):
        if str(c.get('empresa')) == empresa_id and c.get('cuenta') == cuenta:
            return Decimal(str((c.get('manual') or {}).get('archivo', c.get('saldo_archivo') or 0)))
    return Decimal(0)


def _movimientos_de_la_cuenta(conc, ident, empresa_id, cuenta):
    """Traslados y cruces ya aplicados sobre esa cuenta de ese tercero: lo que un saldo leído hoy en la
    contabilidad ya trae. Se guardan por id, igual que los del archivo."""
    ajustes, facturas = [], []
    for a in conc.ajustes.filter(anulado=False, journal_estado__in=AjusteConciliacion.ESTADOS_APLICADOS):
        origen = (a.origen_empresa_id == empresa_id and a.origen_cuenta == cuenta and a.origen_identificacion == ident)
        destino = (not a.es_cruce and a.destino_empresa_id == empresa_id and a.destino_cuenta == cuenta
                   and a.destino_identificacion == ident)
        if origen or destino:
            ajustes.append(a.pk)
    for f in conc.facturas.filter(empresa_id=empresa_id, cruce_cuenta=cuenta, identificacion=ident):
        alegra = f.tipo == FacturaConciliacion.TIPO_ALEGRA
        hecho = (f.cruce_estado == FacturaConciliacion.CRUCE_REGISTRADO if alegra
                 else f.cruce_estado != FacturaConciliacion.CRUCE_NO_APLICA)
        if f.vigente and hecho:
            facturas.append(f.pk)
    return {'ajustes': ajustes, 'facturas': facturas}


def _saldos_manuales_json(conc):
    """Los saldos puestos a mano de la conciliación, con el aviso de si el archivo se recargó después."""
    cargados = {f.empresa_id: f.cargado_en for f in conc.fuentes.filter(confirmada=True)}
    out = []
    for s in conc.saldos_manuales.select_related('empresa', 'created_by'):
        cargado = cargados.get(s.empresa_id)
        out.append({
            'id': s.pk, 'empresa': s.empresa_id, 'empresa_nombre': s.empresa.nombre,
            'cuenta': s.cuenta, 'cuenta_nombre': s.cuenta_nombre,
            'identificacion': s.identificacion, 'nombre': s.nombre,
            'saldo': str(s.saldo), 'archivo': str(s.saldo_archivo), 'nota': s.nota,
            'con_movimientos': bool((s.incluidos or {}).get('ajustes') or (s.incluidos or {}).get('facturas')),
            'por': s.created_by.get_username() if s.created_by else '',
            'en': timezone.localtime(s.updated_at).strftime('%d/%m/%Y %H:%M') if s.updated_at else '',
            # El archivo de la empresa se cargó después de poner este saldo: puede que ya lo traiga.
            'archivo_nuevo': bool(cargado and s.archivo_cargado_en and cargado > s.archivo_cargado_en),
        })
    return out


@login_required
@require_http_methods(['POST'])
def saldo_manual(request, pk):
    """
    Pone a mano el saldo de un tercero en una cuenta: {"identificacion", "empresa", "cuenta", "cuenta_nombre",
    "saldo", "nota", "con_movimientos"}. Con {"quitar": true} vuelve a mandar el archivo.
    `con_movimientos` dice si ese saldo ya refleja los traslados y cruces registrados aquí (es lo normal cuando se
    consulta la contabilidad después de enviarlos): esos no se vuelven a sumar.
    """
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    try:
        d = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    ident = norm_ident(d.get('identificacion'))
    empresa_id = str(d.get('empresa') or '').strip()
    cuenta = str(d.get('cuenta') or '').strip()
    if not (ident and empresa_id and cuenta):
        return JsonResponse({'detail': 'Faltan el tercero, la empresa o la cuenta.'}, status=400)
    if d.get('quitar'):
        borrados, _ = conc.saldos_manuales.filter(empresa_id=empresa_id, cuenta=cuenta, identificacion=ident).delete()
        if not borrados:
            return JsonResponse({'detail': 'Esa cuenta no tiene un saldo puesto a mano.'}, status=400)
        engine.ejecutar(conc, usar_cache=True)
        return JsonResponse(dict(ok=True, mensaje=f'{cuenta}: vuelve a mandar el saldo del archivo.',
                                 saldos_manuales=_saldos_manuales_json(conc), **_lineas_afectadas(conc, [ident])))
    fuente = conc.fuentes.filter(empresa_id=empresa_id, confirmada=True).select_related('empresa').first()
    if not fuente:
        return JsonResponse({'detail': 'Esa empresa no tiene archivo confirmado en esta conciliación: sin archivo no hay '
                                       'saldo contable que corregir.'}, status=400)
    if cuenta not in set(fuente.cuentas_usadas or []):
        return JsonResponse({'detail': f'La cuenta {cuenta} no está entre las que suma el archivo de '
                                       f'{fuente.empresa.nombre}; elige una de esas.'}, status=400)
    try:
        saldo = Decimal(str(d.get('saldo', '')).replace(',', '').strip() or 'x')
    except InvalidOperation:
        return JsonResponse({'detail': 'El saldo no es un número.'}, status=400)
    nota = (d.get('nota') or '').strip()
    if len(nota) < 5:
        return JsonResponse({'detail': 'Escribe de dónde salió el saldo (p. ej. «consultado en Alegra el 21/11»).'},
                            status=400)
    linea = conc.lineas.filter(identificacion=ident).first()
    con_movimientos = d.get('con_movimientos', True)
    conc.saldos_manuales.update_or_create(
        empresa_id=empresa_id, cuenta=cuenta, identificacion=ident,
        defaults={
            'cuenta_nombre': (d.get('cuenta_nombre') or '').strip(),
            'nombre': (linea.nombre if linea else '') or (d.get('nombre') or ''),
            'saldo': saldo.quantize(Decimal('0.01')),
            'saldo_archivo': _saldo_archivo_actual(conc, ident, empresa_id, cuenta),
            'nota': nota[:2000],
            'incluidos': _movimientos_de_la_cuenta(conc, ident, empresa_id, cuenta) if con_movimientos else {},
            'archivo_cargado_en': fuente.cargado_en,
            'created_by': request.user,
        })
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, mensaje=f'{cuenta}: saldo puesto a mano en ${saldo:,.0f}.',
                             saldos_manuales=_saldos_manuales_json(conc), **_lineas_afectadas(conc, [ident])))


@login_required
@require_http_methods(['POST'])
def ajuste_crear(request, pk):
    """
    Registra uno o varios traslados de saldo contable y, en empresas con Alegra, envía cada uno como journal:
    {"nota": "...", "fecha": "AAAA-MM-DD", "movimientos": [{"origen", "origen_empresa", "origen_cuenta", "destino",
     "destino_empresa", "destino_cuenta", "valor"}]}
    Un ajuste solo mueve saldos cuando Alegra confirma el journal; si falla queda pendiente con el error.
    En empresas sin Alegra queda pendiente hasta que alguien marque que lo registró a mano.
    """
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    movimientos = data.get('movimientos') or []
    if not movimientos:
        return JsonResponse({'detail': 'Agrega al menos un traslado.'}, status=400)
    if _falta_confirmar(conc):
        return JsonResponse({'detail': _falta_confirmar(conc)}, status=400)
    fecha, error = _fecha_journal(data.get('fecha'))
    if error:
        return JsonResponse({'detail': error}, status=400)

    catalogo = {(c['empresa'], c['cuenta']): c for c in (conc.resumen or {}).get('catalogo', [])}
    origenes = {norm_ident(m.get('origen')) for m in movimientos}
    saldos = {}  # (ident, empresa, cuenta) -> saldo aplicado
    for l in conc.lineas.filter(identificacion__in=origenes):
        for c in l.cuentas:
            saldos[(l.identificacion, c['empresa'], c['cuenta'])] = Decimal(c['saldo'])

    # Los pendientes aún no restan del saldo, pero ya comprometen ese valor: no se puede trasladar dos veces.
    nuevos, consumido = [], defaultdict(Decimal)
    for p in conc.ajustes.filter(anulado=False, journal_estado=AjusteConciliacion.JOURNAL_PENDIENTE, origen_identificacion__in=origenes):
        consumido[(p.origen_identificacion, p.origen_empresa_id, p.origen_cuenta)] += p.valor
    empresas_por_id = {e.pk: e for e in empresas.objects.filter(pk__in={str(m.get('origen_empresa')) for m in movimientos})}
    cuentas_cache = {}
    for i, m in enumerate(movimientos, start=1):
        cruce = bool(m.get('cruce'))
        origen = norm_ident(m.get('origen'))
        ko = (str(m.get('origen_empresa')), str(m.get('origen_cuenta')))
        if cruce:
            # Cruce con otra cuenta del mismo tercero y la misma empresa, que no hace parte de la conciliación.
            destino, kd = origen, (ko[0], re.sub(r'\s+', '', str(m.get('destino_cuenta') or '')))
        else:
            destino = norm_ident(m.get('destino'))
            kd = (str(m.get('destino_empresa')), str(m.get('destino_cuenta')))
        try:
            valor = Decimal(str(m.get('valor'))).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError):
            return JsonResponse({'detail': f'Fila {i}: valor inválido.'}, status=400)
        if not origen or not destino:
            return JsonResponse({'detail': f'Fila {i}: falta el tercero de origen o de destino.'}, status=400)
        if ko not in catalogo or (not cruce and kd not in catalogo):
            return JsonResponse({'detail': f'Fila {i}: la cuenta debe ser una de las cuentas seleccionadas de la conciliación.'}, status=400)
        if valor <= 0:
            return JsonResponse({'detail': f'Fila {i}: el valor debe ser mayor que cero.'}, status=400)
        if ko[0] not in empresas_por_id:
            return JsonResponse({'detail': f'Fila {i}: la empresa {ko[0]} no existe.'}, status=400)
        if cruce:
            if not re.fullmatch(r'\d{4,20}', kd[1]):
                return JsonResponse({'detail': f'Fila {i}: escribe el código de la cuenta contra la que se cruza (solo números, p. ej. 13050501).'}, status=400)
            if kd in catalogo:
                return JsonResponse({'detail': f'Fila {i}: la cuenta {kd[1]} es de la conciliación; para moverla usa «Entre cuentas».'}, status=400)
            emp = empresas_por_id[ko[0]]
            if getattr(emp, "alegra_enabled", False):
                try:
                    if emp.pk not in cuentas_cache:
                        cuentas_cache[emp.pk] = facturacion.cuentas_alegra(emp)
                except Exception as exc:
                    return JsonResponse({'detail': f'No se pudieron consultar las cuentas de {emp.nombre} en Alegra ({exc}).'}, status=400)
                halladas = [c for c in cuentas_cache[emp.pk] if c['codigo'] == kd[1]]
                if len(halladas) != 1:
                    return JsonResponse({'detail': f'Fila {i}: la cuenta {kd[1]} ' + ('no existe en Alegra como cuenta de movimiento'
                                         if not halladas else 'está repetida en Alegra') + f' ({emp.nombre}).'}, status=400)
                nombre_destino = halladas[0]['nombre']
            else:
                nombre_destino = str(m.get('destino_cuenta_nombre') or '').strip()
        else:
            if origen == destino and ko == kd:
                return JsonResponse({'detail': f'Fila {i}: el origen y el destino son la misma cuenta del mismo tercero.'}, status=400)
            if ko[0] != kd[0]:
                return JsonResponse({'detail': f'Fila {i}: por ahora solo se trasladan saldos dentro de la misma empresa.'}, status=400)
            if ajustes_srv.naturaleza(ko[1]) != ajustes_srv.naturaleza(kd[1]):
                return JsonResponse({'detail': f'Fila {i}: las cuentas {ko[1]} y {kd[1]} son de distinta naturaleza (débito/crédito); '
                                               'el asiento no cuadraría.'}, status=400)
            nombre_destino = catalogo[kd]['cuenta_nombre']
        disponible = saldos.get((origen,) + ko, Decimal(0)) - consumido[(origen,) + ko]
        if valor > disponible:
            return JsonResponse({'detail': f'Fila {i}: {origen} tiene ${disponible:,.0f} disponible en la cuenta {ko[1]} '
                                           f'(descontando traslados pendientes); no se pueden trasladar ${valor:,.0f}.'}, status=400)
        consumido[(origen,) + ko] += valor
        nuevos.append(AjusteConciliacion(
            conciliacion=conc, tipo=(AjusteConciliacion.TIPO_CRUCE if cruce else
                                     AjusteConciliacion.TIPO_CUENTA if origen == destino else AjusteConciliacion.TIPO_TERCERO),
            origen_identificacion=origen, origen_empresa=empresas_por_id[ko[0]], origen_cuenta=ko[1], origen_cuenta_nombre=catalogo[ko]['cuenta_nombre'],
            destino_identificacion=destino, destino_empresa_id=kd[0], destino_cuenta=kd[1], destino_cuenta_nombre=nombre_destino[:255],
            valor=valor, misma_empresa=True, nota=(data.get('nota') or '')[:2000], created_by=request.user, fecha=fecha,
        ))

    # Antes de guardar: cuentas y contactos en Alegra. Si falta algo, no se registra nada.
    for i, a in enumerate(nuevos, start=1):
        if not a.via_alegra:
            continue
        emp = a.origen_empresa
        try:
            if emp.pk not in cuentas_cache:
                cuentas_cache[emp.pk] = facturacion.cuentas_alegra(emp)
            ajustes_srv.resolver(a, cuentas_cache[emp.pk])
        except Exception as exc:
            return JsonResponse({'detail': f'Fila {i}: {exc} No se registró ningún traslado.',
                                 'falta_contacto': getattr(exc, 'falta_contacto', None)}, status=400)

    grupo = str(uuid.uuid4())
    for a in nuevos:
        a.grupo = grupo
        a.save()  # uno a uno: cada ajuste necesita su id para la referencia AJ-CT-<id>
    # Los de una misma empresa que van a Alegra se envían en un solo comprobante, con la referencia del grupo.
    por_empresa = defaultdict(list)
    for a in nuevos:
        if a.via_alegra:
            por_empresa[a.origen_empresa_id].append(a)
    for ajs in por_empresa.values():
        ref = f'AJ-CT-G{min(x.pk for x in ajs)}'
        for a in ajs:
            a.grupo_ref = ref
        AjusteConciliacion.objects.filter(pk__in=[x.pk for x in ajs]).update(grupo_ref=ref)
    # Quedan pendientes (no mueven saldos). La pantalla envía cada uno a Alegra en su propia petición y espera
    # la respuesta: así ninguna petición junta varias llamadas largas a Alegra (el servidor corta a los 120 s).
    idents = [a.origen_identificacion for a in nuevos] + [a.destino_identificacion for a in nuevos]
    # Un envío por comprobante: el primero de cada grupo manda todos los traslados de ese grupo.
    return JsonResponse(dict(ok=True, resultados=[_resultado_ajuste(a) for a in nuevos],
                             por_enviar=[min(x.pk for x in ajs) for ajs in por_empresa.values()],
                             **_lineas_afectadas(conc, idents)))


def _fecha_journal(valor):
    """(fecha, error). La fecha del journal la elige el usuario (se sugiere hoy); no puede ser futura."""
    try:
        fecha = datetime.date.fromisoformat(str(valor or ''))
    except ValueError:
        return None, 'Indica la fecha del comprobante.'
    if fecha > timezone.localdate():
        return None, 'La fecha del comprobante no puede ser futura.'
    return fecha, ''


def _resultado_ajuste(a):
    return {'id': a.pk, 'referencia': a.referencia, 'estado': a.journal_estado, 'aplicado': a.aplicado,
            'via': 'alegra' if a.via_alegra else 'manual', 'journal_ref': a.journal_ref, 'error': a.journal_error,
            'empresa': a.origen_empresa.nombre, 'valor': str(a.valor)}


def _ajuste_abierto(request, pk, ajuste_id):
    """(conciliación, ajuste, respuesta de error)."""
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return conc, None, JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    a = get_object_or_404(AjusteConciliacion.objects.select_related('origen_empresa', 'conciliacion'), pk=ajuste_id, conciliacion=conc)
    if a.anulado:
        return conc, a, JsonResponse({'detail': 'El traslado está anulado.'}, status=400)
    return conc, a, None


@login_required
@require_http_methods(['POST'])
def ajuste_anular(request, pk, ajuste_id):
    _guard(request)
    conc, a, err = _ajuste_abierto(request, pk, ajuste_id)
    if err:
        return err
    if a.journal_estado == AjusteConciliacion.JOURNAL_ENVIADO:
        return JsonResponse({'detail': f'El traslado ya está en Alegra (journal {a.journal_ref}); anúlalo allá.'}, status=400)
    if a.journal_estado == AjusteConciliacion.JOURNAL_MANUAL:
        return JsonResponse({'detail': 'El traslado ya se registró a mano en la contabilidad; revírtelo allá.'}, status=400)
    limite = timezone.now() - datetime.timedelta(minutes=ajustes_srv.BLOQUEO_MINUTOS)
    if a.envio_en_curso_desde and a.envio_en_curso_desde > limite:
        return JsonResponse({'detail': 'El traslado se está enviando a Alegra en este momento; espera y recarga la página.'}, status=400)
    # Siempre que la empresa tenga Alegra se verifica allá: el journal pudo quedar creado aunque aquí no haya
    # error registrado (p. ej. si el servidor cortó la petición justo después del envío).
    if a.via_alegra:
        try:
            from alegra_integration.journal_reconcile import _journal_reference, list_journals_by_reference
            hallados = [j for j in list_journals_by_reference(facturacion._client(a.origen_empresa), a.referencia)
                        if _journal_reference(j) == a.referencia]
        except Exception as exc:
            return JsonResponse({'detail': f'No se pudo verificar en Alegra si el journal «{a.referencia}» existe ({exc}). '
                                           'Intenta de nuevo en un momento.'}, status=400)
        if hallados:
            return JsonResponse({'detail': f'En Alegra sí existe el journal «{a.referencia}». Usa «Reintentar» para dejarlo '
                                           'aplicado, o elimínalo en Alegra antes de anular.'}, status=400)
    # Cambio condicional: si mientras tanto empezó un envío o cambió el estado, no se anula.
    anulado = AjusteConciliacion.objects.filter(
        Q(envio_en_curso_desde__isnull=True) | Q(envio_en_curso_desde__lt=limite),
        pk=a.pk, anulado=False, journal_estado=AjusteConciliacion.JOURNAL_PENDIENTE,
    ).update(anulado=True, anulado_por=request.user, anulado_en=timezone.now())
    if not anulado:
        return JsonResponse({'detail': 'El traslado cambió mientras se anulaba (¿se está enviando?); recarga la página.'}, status=400)
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, **_lineas_afectadas(conc, [a.origen_identificacion, a.destino_identificacion])))


@login_required
@require_http_methods(['POST'])
def ajuste_enviar(request, pk, ajuste_id):
    """Reintenta el envío del journal de un ajuste pendiente. {"fecha": "AAAA-MM-DD"} opcional."""
    _guard(request)
    conc, a, err = _ajuste_abierto(request, pk, ajuste_id)
    if err:
        return err
    if a.journal_estado != AjusteConciliacion.JOURNAL_PENDIENTE:
        return JsonResponse({'detail': 'El traslado ya no está pendiente.'}, status=400)
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        data = {}
    # Un comprobante tiene una sola fecha: si se cambia, se cambia para todos sus traslados pendientes.
    grupo = ajustes_srv.pendientes_del_grupo(a)
    if data.get('fecha') or not a.fecha:
        fecha, error = _fecha_journal(data.get('fecha'))
        if error:
            return JsonResponse({'detail': error}, status=400)
        AjusteConciliacion.objects.filter(pk__in=[x.pk for x in grupo]).update(fecha=fecha)
        a.refresh_from_db()
    try:
        ajustes_srv.enviar(a, request.user)
    except ajustes_srv.AjusteError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    engine.ejecutar(conc, usar_cache=True)
    afectados = list(AjusteConciliacion.objects.filter(pk__in=[x.pk for x in grupo]).select_related('origen_empresa')) or [a]
    idents = [i for x in afectados for i in (x.origen_identificacion, x.destino_identificacion)]
    return JsonResponse(dict(ok=True, resultados=[_resultado_ajuste(x) for x in afectados],
                             **_lineas_afectadas(conc, idents)))


@login_required
@require_http_methods(['POST'])
def ajuste_verificar(request, pk, ajuste_id):
    """Traslado enviado: si el journal se anuló en Alegra, se anula aquí y deja de contar."""
    _guard(request)
    conc, a, err = _ajuste_abierto(request, pk, ajuste_id)
    if err:
        return err
    try:
        _, mensaje = ajustes_srv.verificar_anulacion(a, request.user)
    except ajustes_srv.AjusteError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, mensaje=mensaje, **_lineas_afectadas(conc, [a.origen_identificacion, a.destino_identificacion])))


@login_required
@require_http_methods(['POST'])
def ajuste_manual(request, pk, ajuste_id):
    """Empresa sin Alegra: marca el ajuste como registrado a mano. {"comprobante": "...", "fecha": "AAAA-MM-DD"}"""
    _guard(request)
    conc, a, err = _ajuste_abierto(request, pk, ajuste_id)
    if err:
        return err
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
    fecha = a.fecha
    if data.get('fecha'):
        fecha, error = _fecha_journal(data.get('fecha'))
        if error:
            return JsonResponse({'detail': error}, status=400)
    try:
        ajustes_srv.marcar_manual(a, request.user, data.get('comprobante') or '', fecha)
    except ajustes_srv.AjusteError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, resultados=[_resultado_ajuste(a)],
                             **_lineas_afectadas(conc, [a.origen_identificacion, a.destino_identificacion])))


@login_required
@require_http_methods(['POST'])
def proyectos(request, pk):
    """Proyectos de Andinasoft que entran al cruce."""
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        messages.error(request, 'La conciliación está cerrada.')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    todos = engine.proyectos_conciliables()
    incluidos = set(request.POST.getlist('proyecto'))
    conc.proyectos_excluidos = [p for p in todos if p not in incluidos]
    conc.save(update_fields=['proyectos_excluidos', 'updated_at'])
    messages.success(request, 'Proyectos actualizados.')
    return _recalcular_si_listo(request, conc)


@login_required
@require_http_methods(['POST'])
def recalcular(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        messages.error(request, 'La conciliación está cerrada; reábrela para recalcular.')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    messages.success(request, 'Conciliación recalculada. Se conservaron las revisiones y notas.')
    return _recalcular_si_listo(request, conc)


@login_required
@require_http_methods(['POST'])
def cambiar_estado(request, pk):
    """Cierra o reabre según la acción pedida (no es un interruptor: un doble envío no deshace el cierre)."""
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    accion = request.POST.get('accion')
    if accion == 'reabrir':
        conc.estado = Conciliacion.ESTADO_BORRADOR
    elif accion == 'cerrar':
        if conc.estado == Conciliacion.ESTADO_CERRADA:
            return redirect('conciliacion-terceros-detalle', pk=pk)
        faltan = _pendientes_para_cerrar(conc)
        if faltan:
            messages.error(request, 'No se puede cerrar todavía: ' + '; '.join(faltan) + '.')
            return redirect('conciliacion-terceros-detalle', pk=pk)
        borradores = conc.facturas.filter(tipo=FacturaConciliacion.TIPO_ALEGRA, estado=FacturaConciliacion.ESTADO_BORRADOR).count()
        if borradores:
            messages.warning(request, f'Se cerró con {borradores} factura(s) en borrador en Alegra: no cuentan como facturadas.')
        conc.estado = Conciliacion.ESTADO_CERRADA
    else:
        messages.error(request, 'Acción inválida.')
        return redirect('conciliacion-terceros-detalle', pk=pk)
    conc.notas = request.POST.get('notas', conc.notas)
    conc.save(update_fields=['estado', 'notas', 'updated_at'])
    return redirect('conciliacion-terceros-detalle', pk=pk)


def _pendientes_para_cerrar(conc):
    """Lo que impide cerrar: cosas a medio hacer que cambiarían el resultado de la conciliación."""
    out = []
    sin_confirmar = [f.empresa.nombre for f in conc.fuentes.filter(confirmada=False).select_related('empresa')]
    if sin_confirmar:
        out.append('falta confirmar las cuentas de ' + ', '.join(sin_confirmar))
    n = conc.ajustes.filter(anulado=False, journal_estado=AjusteConciliacion.JOURNAL_PENDIENTE).count()
    if n:
        out.append(f'{n} traslado(s) pendiente(s) de enviar o registrar a mano (envíalos o anúlalos)')
    n = conc.facturas.filter(tipo=FacturaConciliacion.TIPO_ALEGRA, estado__in=(
        FacturaConciliacion.ESTADO_PENDIENTE, FacturaConciliacion.ESTADO_ERROR)).count()
    if n:
        out.append(f'{n} factura(s) que no alcanzaron a crearse en Alegra')
    n = conc.facturas.filter(tipo=FacturaConciliacion.TIPO_ALEGRA, estado=FacturaConciliacion.ESTADO_EMITIDA).filter(
        Q(cruce_estado=FacturaConciliacion.CRUCE_PENDIENTE) | Q(costo_estado=FacturaConciliacion.CRUCE_PENDIENTE)).count()
    if n:
        out.append(f'{n} factura(s) emitida(s) con el costo o el cruce pendiente')
    return out


@login_required
@require_http_methods(['GET'])
def exportar(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    wb = construir_libro(conc)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="conciliacion_terceros_{conc.fecha_corte:%Y%m%d}.xlsx"'
    wb.save(response)
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def muestra_formato(request):
    """Carga de un archivo de muestra (p. ej. de otro sistema contable) para analizar su estructura."""
    _guard(request)
    guardado = None
    if request.method == 'POST':
        f = request.FILES.get('archivo')
        if not f or not f.name.lower().endswith(('.xlsx', '.xls', '.csv', '.txt')):
            messages.error(request, 'Selecciona un archivo .xlsx, .xls, .csv o .txt.')
        else:
            folder = os.path.join(settings.MEDIA_ROOT, 'tmp', 'conciliacion_terceros', 'muestras')
            os.makedirs(folder, exist_ok=True)
            nombre = f'{timezone.now():%Y%m%d_%H%M%S}_{get_valid_filename(f.name)}'
            with open(os.path.join(folder, nombre), 'wb') as out:
                for chunk in f.chunks():
                    out.write(chunk)
            guardado = nombre
    return render(request, 'conciliacion_terceros/muestra.html', {'guardado': guardado})
