import datetime
import json
import logging
import os
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
from conciliacion_terceros import correccion, facturacion
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
    path = os.path.join(folder, f'{timezone.now():%Y%m%d_%H%M%S}_{get_valid_filename(f.name)}')
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

    fuente, _ = FuenteConciliacion.objects.update_or_create(
        conciliacion=conc, empresa=emp,
        defaults={'formato': formato, 'archivo': path, 'archivo_nombre': f.name,
                  'fecha_corte_archivo': balance.fecha_hasta, 'created_by': request.user,
                  'confirmada': False, 'cuentas_usadas': []},
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
        usadas = sorted(c for c in balance.cuentas if request.POST.get(f'usar_{c}'))
        fuente.cuentas_usadas = usadas
        fuente.confirmada = True
        fuente.save(update_fields=['cuentas_usadas', 'confirmada'])
        ConfigEmpresa.objects.update_or_create(empresa=fuente.empresa, defaults={'cuentas': usadas})
        if usadas:
            messages.success(request, f'{fuente.empresa.nombre}: {len(usadas)} cuenta(s) seleccionada(s).')
        else:
            messages.warning(request, f'{fuente.empresa.nombre}: no seleccionaste cuentas, el archivo no suma nada.')
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
    return render(request, 'conciliacion_terceros/cuentas.html', {
        'conciliacion': conc, 'fuente': fuente, 'filas': filas,
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


def _ajuste_json(a):
    return {
        'id': a.pk, 'grupo': a.grupo, 'tipo': a.tipo, 'valor': str(a.valor), 'misma_empresa': a.misma_empresa,
        'origen': a.origen_identificacion, 'origen_empresa': a.origen_empresa_id, 'origen_cuenta': a.origen_cuenta,
        'origen_cuenta_nombre': a.origen_cuenta_nombre,
        'destino': a.destino_identificacion, 'destino_empresa': a.destino_empresa_id, 'destino_cuenta': a.destino_cuenta,
        'destino_cuenta_nombre': a.destino_cuenta_nombre, 'nota': a.nota, 'anulado': a.anulado,
        'journal_estado': a.journal_estado,
        'creado_por': a.created_by.get_username() if a.created_by else '',
        'creado_en': timezone.localtime(a.created_at).strftime('%d/%m/%Y %H:%M') if a.created_at else '',
        'anulado_por': a.anulado_por.get_username() if a.anulado_por else '',
    }


def _ajustes_por_tercero(conc, idents=None):
    qs = conc.ajustes.select_related('created_by', 'anulado_por')
    if idents is not None:
        qs = qs.filter(Q(origen_identificacion__in=idents) | Q(destino_identificacion__in=idents))
    out = defaultdict(list)
    for a in qs:
        j = _ajuste_json(a)
        out[a.origen_identificacion].append(j)
        if a.destino_identificacion != a.origen_identificacion:
            out[a.destino_identificacion].append(j)
    return out


def _factura_json(f):
    return {
        'id': f.pk, 'grupo': f.grupo, 'tipo': f.tipo, 'tipo_label': f.get_tipo_display(), 'empresa': f.empresa_id,
        'proyecto': f.proyecto, 'negocio_ref': f.negocio_ref, 'identificacion': f.identificacion, 'concepto': f.concepto,
        'concepto_label': f.get_concepto_display(), 'fecha': f.fecha.isoformat(), 'numero': f.numero,
        'valor_venta': str(f.valor_venta), 'valor_intereses': str(f.valor_intereses), 'total': str(f.total),
        'cruce_cuenta': f.cruce_cuenta, 'cruce_estado': f.cruce_estado, 'cruce_label': f.get_cruce_estado_display(),
        'estado': f.estado, 'estado_label': f.get_estado_display(), 'alegra_invoice_id': f.alegra_invoice_id,
        'alegra_journal_id': f.alegra_journal_id, 'error': f.error, 'nota': f.nota,
        'escritura_marcada': bool((f.respuesta or {}).get('escritura')),
        'costo': str(f.costo), 'costo_estado': f.costo_estado,
        'costo_label': {'no_aplica': '', 'pendiente': 'Pendiente', 'registrado': 'Registrado'}.get(f.costo_estado, ''),
        'creado_por': f.created_by.get_username() if f.created_by else '',
        'creado_en': timezone.localtime(f.created_at).strftime('%d/%m/%Y %H:%M') if f.created_at else '',
    }


def _facturas_por_tercero(conc, idents=None):
    qs = conc.facturas.select_related('created_by')
    if idents is not None:
        qs = qs.filter(identificacion__in=idents)
    out = defaultdict(list)
    for f in qs:
        out[f.identificacion].append(_factura_json(f))
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
    return render(request, 'conciliacion_terceros/detalle.html', {
        'conciliacion': conc,
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
        'resultados_adj': [('cuadra', 'Cuadra'), ('reparto', 'Cuadra en total, no por titular'), ('diferencia', 'Con diferencia'), ('sin_contable', 'Sin saldo en contabilidad'),
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
    linea.revision = revision
    linea.nota = (data.get('nota', linea.nota) or '')[:5000]
    linea.revisado_por = request.user
    linea.revisado_en = timezone.now()
    linea.save(update_fields=['revision', 'nota', 'revisado_por', 'revisado_en'])
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
        if datos['numeracion_journal_id'] and not datos['numeracion_journal_id'].isdigit():
            messages.error(request, 'La numeración de los journals debe ser el número (ID) de la numeración en Alegra, o quedar vacía.')
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


def _factura_respuesta(conc, facturas):
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, facturas=[_factura_json(f) for f in facturas],
                             **_lineas_afectadas(conc, [f.identificacion for f in facturas])))


@login_required
@require_http_methods(['POST'])
def factura_crear(request, pk):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    try:
        datos = json.loads(request.body or '{}')
        facturas = facturacion.registrar(conc, datos, request.user)
    except ValueError:
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)
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
    try:
        if accion == 'emitir':
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
        elif accion == 'reintentar':
            if f.estado != FacturaConciliacion.ESTADO_ERROR or f.alegra_invoice_id:
                raise facturacion.FacturacionError('Solo se reintenta una factura con error que no alcanzó a crearse en Alegra.')
            cfg = facturacion.config_de(f.proyecto)
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
    return _factura_respuesta(conc, [f])


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
    Registra uno o varios traslados de saldo contable:
    {"nota": "...", "movimientos": [{"origen", "origen_empresa", "origen_cuenta", "destino", "destino_empresa", "destino_cuenta", "valor"}]}
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

    catalogo = {(c['empresa'], c['cuenta']): c for c in (conc.resumen or {}).get('catalogo', [])}
    saldos = {}  # (ident, empresa, cuenta) -> saldo vigente
    for l in conc.lineas.filter(identificacion__in={norm_ident(m.get('origen')) for m in movimientos}):
        for c in l.cuentas:
            saldos[(l.identificacion, c['empresa'], c['cuenta'])] = Decimal(c['saldo'])

    nuevos, consumido = [], defaultdict(Decimal)
    for i, m in enumerate(movimientos, start=1):
        origen, destino = norm_ident(m.get('origen')), norm_ident(m.get('destino'))
        ko = (str(m.get('origen_empresa')), str(m.get('origen_cuenta')))
        kd = (str(m.get('destino_empresa')), str(m.get('destino_cuenta')))
        try:
            valor = Decimal(str(m.get('valor'))).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError):
            return JsonResponse({'detail': f'Fila {i}: valor inválido.'}, status=400)
        if not origen or not destino:
            return JsonResponse({'detail': f'Fila {i}: falta el tercero de origen o de destino.'}, status=400)
        if ko not in catalogo or kd not in catalogo:
            return JsonResponse({'detail': f'Fila {i}: la cuenta debe ser una de las cuentas seleccionadas de la conciliación.'}, status=400)
        if valor <= 0:
            return JsonResponse({'detail': f'Fila {i}: el valor debe ser mayor que cero.'}, status=400)
        if origen == destino and ko == kd:
            return JsonResponse({'detail': f'Fila {i}: el origen y el destino son la misma cuenta del mismo tercero.'}, status=400)
        disponible = saldos.get((origen,) + ko, Decimal(0)) - consumido[(origen,) + ko]
        if valor > disponible:
            return JsonResponse({'detail': f'Fila {i}: {origen} tiene ${disponible:,.0f} en la cuenta {ko[1]}; no se pueden trasladar ${valor:,.0f}.'}, status=400)
        consumido[(origen,) + ko] += valor
        nuevos.append(AjusteConciliacion(
            conciliacion=conc, tipo=AjusteConciliacion.TIPO_CUENTA if origen == destino else AjusteConciliacion.TIPO_TERCERO,
            origen_identificacion=origen, origen_empresa_id=ko[0], origen_cuenta=ko[1], origen_cuenta_nombre=catalogo[ko]['cuenta_nombre'],
            destino_identificacion=destino, destino_empresa_id=kd[0], destino_cuenta=kd[1], destino_cuenta_nombre=catalogo[kd]['cuenta_nombre'],
            valor=valor, misma_empresa=ko[0] == kd[0], nota=(data.get('nota') or '')[:2000], created_by=request.user,
        ))
    grupo = str(uuid.uuid4())
    for a in nuevos:
        a.grupo = grupo
    AjusteConciliacion.objects.bulk_create(nuevos)
    engine.ejecutar(conc, usar_cache=True)
    idents = [a.origen_identificacion for a in nuevos] + [a.destino_identificacion for a in nuevos]
    return JsonResponse(dict(ok=True, **_lineas_afectadas(conc, idents)))


@login_required
@require_http_methods(['POST'])
def ajuste_anular(request, pk, ajuste_id):
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    if conc.estado == Conciliacion.ESTADO_CERRADA:
        return JsonResponse({'detail': 'La conciliación está cerrada.'}, status=400)
    a = get_object_or_404(AjusteConciliacion, pk=ajuste_id, conciliacion=conc)
    if a.anulado:
        return JsonResponse({'detail': 'El ajuste ya estaba anulado.'}, status=400)
    if a.journal_estado == AjusteConciliacion.JOURNAL_ENVIADO:
        return JsonResponse({'detail': 'El ajuste ya se envió como journal; anúlalo en la contabilidad.'}, status=400)
    a.anulado, a.anulado_por, a.anulado_en = True, request.user, timezone.now()
    a.save(update_fields=['anulado', 'anulado_por', 'anulado_en'])
    engine.ejecutar(conc, usar_cache=True)
    return JsonResponse(dict(ok=True, **_lineas_afectadas(conc, [a.origen_identificacion, a.destino_identificacion])))


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
    _guard(request)
    conc = get_object_or_404(Conciliacion, pk=pk)
    conc.estado = Conciliacion.ESTADO_BORRADOR if conc.estado == Conciliacion.ESTADO_CERRADA else Conciliacion.ESTADO_CERRADA
    conc.notas = request.POST.get('notas', conc.notas)
    conc.save(update_fields=['estado', 'notas', 'updated_at'])
    return redirect('conciliacion-terceros-detalle', pk=pk)


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
