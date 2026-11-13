import datetime
import json
import logging
import os
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
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
        'creado_por': f.created_by.get_username() if f.created_by else '',
        'creado_en': timezone.localtime(f.created_at).strftime('%d/%m/%Y %H:%M') if f.created_at else '',
    }


def _facturas_por_tercero(conc, idents=None):
    qs = conc.facturas.select_related('created_by')
    if idents is not None:
        qs = qs.filter(identificacion__in=idents)
    out, inc = defaultdict(list), _incluidos(conc)
    for f in qs:
        out[f.identificacion].append(_factura_json(f, inc))
    return out


def _linea_json(l, ajustes=None, correcciones=None, facturas=None):
    return {
        'facturas': (facturas or {}).get(l.identificacion, []),
        'correcciones': (correcciones or {}).get(l.identificacion, []),
        'ajustes': (ajustes or {}).get(l.identificacion, []),
        'id': l.pk, 'identificacion': l.identificacion, 'nombre': l.nombre,
        'andina': str(l.saldo_andina), 'contable': str(l.saldo_contable), 'diferencia': str(l.diferencia),
        'capital': str(l.capital), 'intereses': str(l.intereses), 'estado': l.estado,
        'negocios': l.negocios, 'cuentas': l.cuentas, 'alertas': l.alertas,
        'observacion': l.observacion, 'sugerencia': l.sugerencia,
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
        'lineas_json': [_linea_json(l, ajustes, correcciones, facturas) for l in lineas],
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
    return JsonResponse({'ok': True, 'linea': _linea_json(linea, _ajustes_por_tercero(conc, [linea.identificacion]))})


def _lineas_afectadas(conc, idents):
    idents = sorted(set(idents))
    ajustes = _ajustes_por_tercero(conc, idents)
    facturas = _facturas_por_tercero(conc, idents)
    lineas = conc.lineas.filter(identificacion__in=idents).select_related('revisado_por')
    estados = defaultdict(int)
    for e in conc.lineas.values_list('estado', flat=True):
        estados[e] += 1
    return {'lineas': [_linea_json(l, ajustes, None, facturas) for l in lineas], 'estados': dict(estados)}


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


@login_required
@require_http_methods(['GET', 'POST'])
def facturacion_config(request):
    _guard(request)
    proyectos_lista = engine.proyectos_conciliables()
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
    return render(request, 'conciliacion_terceros/facturacion.html', {
        'filas': filas,
        'empresas': empresas.objects.order_by('nombre'),
        'modos': ConfigFacturacion.MODO_CHOICES,
        'emisiones': ConfigFacturacion.EMISION_CHOICES,
        'configs_json': datos_js,
    })


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
    # Quedan pendientes (no mueven saldos). La pantalla envía cada uno a Alegra en su propia petición y espera
    # la respuesta: así ninguna petición junta varias llamadas largas a Alegra (el servidor corta a los 120 s).
    idents = [a.origen_identificacion for a in nuevos] + [a.destino_identificacion for a in nuevos]
    return JsonResponse(dict(ok=True, resultados=[_resultado_ajuste(a) for a in nuevos],
                             por_enviar=[a.pk for a in nuevos if a.via_alegra],
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
    if data.get('fecha') or not a.fecha:
        fecha, error = _fecha_journal(data.get('fecha'))
        if error:
            return JsonResponse({'detail': error}, status=400)
        a.fecha = fecha
        a.save(update_fields=['fecha'])
    try:
        ajustes_srv.enviar(a, request.user)
    except ajustes_srv.AjusteError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, resultados=[_resultado_ajuste(a)],
                             **_lineas_afectadas(conc, [a.origen_identificacion, a.destino_identificacion])))


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
