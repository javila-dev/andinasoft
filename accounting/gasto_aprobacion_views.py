import json
import logging
import os
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.core import signing
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.utils.dateparse import parse_date
from django.utils.html import escape

logger = logging.getLogger(__name__)

from accounting.gasto_poll import poll_gastos_alegra_notificaciones
from accounting.gasto_tesoreria_poll import poll_gastos_tesoreria_aprobados
from accounting.n8n_http import n8n_inbound_authorized
from accounting.gasto_aprobacion import (
    aprobadores_para_empresa,
    aprobar_gasto_alegra,
    aprobar_gasto_alegra_para_usuario,
    asignar_gasto_alegra,
    crear_radicado_gasto_alegra,
    reasignar_gasto_alegra,
    empresa_config_sin_aprobador,
    factura_a_dict,
    sugerencias_asignacion_gasto_alegra,
    normalizar_alegra_bill_id,
    parse_aprobador_user_id_opcional,
    usuario_es_aprobador_gasto,
    usuario_puede_ver_soporte_gasto,
)
from accounting.gasto_aprobacion_link import verify_gasto_aprobacion_link_token
from accounting.gasto_n8n_notify import ensure_soporte_radicado_descargable
from accounting.journal_cxp import (
    detalle_pago_desde_factura,
    parsear_journal_para_radicado,
    persist_journal_cxp_mappings,
    serializar_detalle_journal_pago,
)
from accounting.models import Facturas, Pagos
from andina.decorators import check_groups, check_perms, group_perm_required
from alegra_integration.bill_mapping import bill_descripcion_candidatos, parse_alegra_bill_id_for_api
from alegra_integration.client import AlegraMCPClient
from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError
from andinasoft.models import empresas


def _json_error(exc, status=400):
    if isinstance(exc, PermissionDenied):
        detail = (
            'No tiene permiso para esta acción. '
            'Revise que su usuario tenga el grupo Contabilidad y los permisos de facturas '
            '(ver/agregar según la operación).'
        )
    else:
        detail = str(exc).strip() or 'Error en la operación.'
    return JsonResponse({'detail': detail}, status=status)


def _log_gastos_alegra_denied(request, endpoint, detail, status=403):
    logger.warning(
        'gastos-alegra %s: user=%s status=%s detail=%s',
        endpoint,
        getattr(request.user, 'username', '?'),
        status,
        detail,
    )


@login_required
@group_perm_required(('accounting.view_facturas',), raise_exception=True)
def gastos_alegra_asignar(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return render(request, 'accounting/gastos_alegra_denied.html', status=403)
    return render(request, 'accounting/gastos_alegra_asignar.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
    })


@login_required
def gastos_alegra_aprobar(request):
    es_contabilidad = (
        check_groups(request, ('Contabilidad',), raise_exception=False)
        or request.user.is_superuser
    )
    if not usuario_es_aprobador_gasto(request.user) and not es_contabilidad:
        return render(request, 'accounting/gastos_alegra_denied.html', {
            'mensaje': 'No está configurado como aprobador de gastos Alegra.',
        }, status=403)
    return render(request, 'accounting/gastos_alegra_aprobar.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
        'es_contabilidad': es_contabilidad,
    })


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_notificaciones_poll(request):
    try:
        since_pk = int(request.GET.get('since_pk') or 0)
    except (TypeError, ValueError):
        since_pk = 0
    payload = poll_gastos_alegra_notificaciones(request.user, since_pk=since_pk)
    if payload.get('enabled'):
        payload['since_pk'] = since_pk
    return JsonResponse(payload)


@login_required
@require_http_methods(['GET'])
def ajax_gastos_tesoreria_notificaciones_poll(request):
    since_ts = (request.GET.get('since_ts') or '').strip() or None
    payload = poll_gastos_tesoreria_aprobados(request.user, since_ts=since_ts)
    if payload.get('enabled'):
        payload['since_ts'] = since_ts or ''
    return JsonResponse(payload)


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_sugerencias_asignacion(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)
    radicado = (request.GET.get('radicado') or '').strip()
    empresa_id = (request.GET.get('empresa') or '').strip()
    id_tercero = (request.GET.get('id_tercero') or '').strip()
    exclude_pk = None
    if radicado:
        try:
            exclude_pk = int(radicado)
        except (TypeError, ValueError):
            return JsonResponse({'detail': 'radicado inválido'}, status=400)
        fac = Facturas.objects.filter(pk=exclude_pk).only(
            'pk', 'empresa_id', 'idtercero', 'origen',
        ).first()
        if not fac:
            return JsonResponse({'detail': 'Radicado no encontrado'}, status=404)
        if fac.origen != 'Alegra':
            return JsonResponse({'detail': 'Solo aplica a radicados Alegra'}, status=400)
        empresa_id = fac.empresa_id
        id_tercero = fac.idtercero or ''
    if not empresa_id or not id_tercero:
        return JsonResponse({
            'detail': 'Indique radicado o empresa e id_tercero',
        }, status=400)
    payload = sugerencias_asignacion_gasto_alegra(
        empresa_id, id_tercero, exclude_pk=exclude_pk,
    )
    return JsonResponse(payload)


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_pendientes_asignar(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)
    empresa = (request.GET.get('empresa') or '').strip()
    qs = Facturas.objects.filter(
        origen='Alegra',
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
    ).select_related('empresa').order_by('-fecharadicado', '-pk')
    if empresa:
        qs = qs.filter(empresa_id=empresa)
    data = [factura_a_dict(f) for f in qs[:500]]
    return JsonResponse({'data': data})


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_pendientes_aprobar(request):
    es_contabilidad = (
        check_groups(request, ('Contabilidad',), raise_exception=False)
        or request.user.is_superuser
    )
    if not usuario_es_aprobador_gasto(request.user) and not es_contabilidad:
        return _json_error('No es aprobador de gastos.', 403)
    empresa = (request.GET.get('empresa') or '').strip()
    qs = Facturas.objects.filter(
        origen='Alegra',
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
    ).select_related('empresa', 'gasto_aprobador_asignado', 'gasto_asignado_por')
    if not es_contabilidad:
        qs = qs.filter(gasto_aprobador_asignado=request.user)
    if empresa:
        qs = qs.filter(empresa_id=empresa)
    qs = qs.order_by('-gasto_asignado_en', '-pk')
    data = [factura_a_dict(f) for f in qs[:500]]
    return JsonResponse({'data': data, 'es_contabilidad': es_contabilidad})


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_aprobadores(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)
    empresa = (request.GET.get('empresa') or '').strip()
    if not empresa:
        return JsonResponse({'detail': 'empresa es requerida'}, status=400)
    items = []
    for row in aprobadores_para_empresa(empresa):
        u = row.user
        label = u.get_full_name() or u.username
        if row.empresa_id:
            label += f' ({row.empresa_id})'
        items.append({'id': u.pk, 'label': label})
    cfg = empresa_config_sin_aprobador(empresa)
    return JsonResponse({
        'aprobadores': items,
        'permite_sin_aprobador': cfg['permite_sin_aprobador'],
        'max_sin_aprobador': cfg['max_sin_aprobador'],
        'mensaje_requiere_aprobador': cfg['mensaje_requiere_aprobador'],
    })


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_journal_preview(request):
    """
    GET /journals/{id} en Alegra — respuesta cruda para diseñar mapeo (solo Contabilidad).
    Query: empresa (NIT), journal_id (numérico).
    """
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)
    empresa_id = (request.GET.get('empresa') or '').strip()
    journal_id = (request.GET.get('journal_id') or '').strip()
    if not empresa_id:
        return _json_error('empresa es requerida.', 400)
    if not journal_id:
        return _json_error('journal_id es requerido.', 400)
    if not re.fullmatch(r'\d+', journal_id):
        return _json_error('journal_id debe ser solo dígitos.', 400)
    try:
        empresa = empresas.objects.get(pk=empresa_id)
    except empresas.DoesNotExist:
        return _json_error('Empresa no encontrada.', 404)

    alegra_ref = normalizar_alegra_bill_id(empresa_id, journal_id, es_radicado_manual=True)
    fac_existente = Facturas.objects.filter(alegra_bill_id=alegra_ref).select_related('empresa').first()

    try:
        client = AlegraMCPClient(empresa)
        journal = client.get_journal(journal_id)
        payload = {
            'ok': True,
            'empresa': empresa_id,
            'journal_id': journal_id,
            'alegra_bill_id': alegra_ref,
            'radicado_existente': factura_a_dict(fac_existente) if fac_existente else None,
            'duplicate_journal': fac_existente is not None,
        }
        try:
            radicado = parsear_journal_para_radicado(journal)
            rows = serializar_detalle_journal_pago(radicado.get('pago_detallado', []))
            try:
                emp = empresas.objects.get(pk=empresa_id)
                rows = persist_journal_cxp_mappings(emp, rows)
            except empresas.DoesNotExist:
                pass
            radicado['pago_detallado'] = rows
            payload['radicado'] = radicado
        except ValueError as exc:
            payload['radicado_error'] = str(exc)
        return JsonResponse(payload)
    except AlegraConfigurationError as exc:
        return _json_error(str(exc), 400)
    except AlegraClientError as exc:
        return _json_error(str(exc), 502)


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_bill_preview(request):
    """
    GET /bills/{id} en Alegra — respuesta cruda para revisar descripción y mapeo.
    Query: empresa (NIT) + bill_id, o radicado (pk local).
    """
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)

    empresa_id = (request.GET.get('empresa') or '').strip()
    bill_id = (request.GET.get('bill_id') or '').strip()
    radicado_pk = (request.GET.get('radicado') or '').strip()

    factura_local = None
    if radicado_pk:
        try:
            fac = Facturas.objects.select_related('empresa').get(pk=int(radicado_pk))
        except (Facturas.DoesNotExist, TypeError, ValueError):
            return _json_error('Radicado no encontrado.', 404)
        factura_local = factura_a_dict(fac)
        if not bill_id and fac.alegra_bill_id:
            empresa_id, bill_id = parse_alegra_bill_id_for_api(fac.alegra_bill_id)
            if not empresa_id:
                empresa_id = str(fac.empresa_id)
        elif not empresa_id:
            empresa_id = str(fac.empresa_id)

    if not empresa_id:
        return _json_error('empresa (NIT) es requerida.', 400)
    if not bill_id or not re.fullmatch(r'\d+', bill_id):
        return _json_error('bill_id numérico es requerido (o radicado con alegra_bill_id).', 400)

    try:
        empresa = empresas.objects.get(pk=empresa_id)
    except empresas.DoesNotExist:
        return _json_error('Empresa no encontrada.', 404)

    fields = (request.GET.get('fields') or '').strip() or None
    try:
        client = AlegraMCPClient(empresa)
        bill = client.get_bill(bill_id, fields=fields)
    except AlegraConfigurationError as exc:
        return _json_error(str(exc), 400)
    except AlegraClientError as exc:
        return _json_error(str(exc), 502)

    return JsonResponse({
        'ok': True,
        'empresa': empresa_id,
        'bill_id': bill_id,
        'fields_requested': fields,
        'api': f'GET /bills/{bill_id}',
        'factura_local': factura_local,
        'descripcion_candidatos': bill_descripcion_candidatos(bill),
        'bill': bill,
    })


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_journal_detalle_radicado(request):
    """Detalle CxP guardado al radicar desde journal (para tesorería)."""
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        if not usuario_es_aprobador_gasto(request.user):
            return _json_error('Sin permiso.', 403)
    pk = (request.GET.get('radicado') or '').strip()
    if not pk:
        return _json_error('radicado es requerido.', 400)
    try:
        fac = Facturas.objects.get(pk=pk)
    except Facturas.DoesNotExist:
        return _json_error('Radicado no encontrado.', 404)
    detalle = detalle_pago_desde_factura(fac)
    return JsonResponse({
        'ok': True,
        'radicado': fac.pk,
        'alegra_bill_id': fac.alegra_bill_id or '',
        'pago_detallado': detalle or [],
    })


@login_required
@require_http_methods(['POST'])
def ajax_gastos_alegra_crear(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        detail = 'Sin permiso Contabilidad.'
        _log_gastos_alegra_denied(request, 'crear', detail)
        return _json_error(detail, 403)
    # Misma puerta que la pantalla asignar (view_facturas). add_facturas solo en radicar clásico.
    if not request.user.is_superuser and not check_perms(
        request, ('accounting.view_facturas',), raise_exception=False
    ):
        detail = (
            'Sin permiso accounting.view_facturas para crear radicados Alegra. '
            'Solicite el mismo acceso que para «Asignar gastos Alegra».'
        )
        _log_gastos_alegra_denied(request, 'crear', detail)
        return _json_error(detail, 403)
    try:
        empresa_id = (request.POST.get('empresa') or '').strip()
        fecha_factura = parse_date((request.POST.get('fecha_factura') or '')[:10])
        fecha_vencimiento = parse_date((request.POST.get('fecha_vencimiento') or '')[:10])
        if not fecha_factura or not fecha_vencimiento:
            return _json_error('Fechas de factura y vencimiento son obligatorias (YYYY-MM-DD).', 400)
        soporte = request.FILES.get('soporte')
        detalle_raw = (request.POST.get('alegra_journal_detalle') or '').strip()
        alegra_journal_detalle = detalle_raw or None
        fac = crear_radicado_gasto_alegra(
            request,
            empresa_id=empresa_id,
            nro_factura=request.POST.get('nro_factura'),
            fecha_factura=fecha_factura,
            fecha_vencimiento=fecha_vencimiento,
            id_tercero=request.POST.get('id_tercero'),
            nombre_tercero=request.POST.get('nombre_tercero'),
            valor=request.POST.get('valor'),
            descripcion=request.POST.get('descripcion'),
            soporte=soporte,
            oficina=(request.POST.get('oficina') or '').strip(),
            aprobador_user_id=parse_aprobador_user_id_opcional(request.POST.get('aprobador_id')),
            comentario_contable=(request.POST.get('comentario_contable') or '').strip(),
            referencia_alegra=(request.POST.get('referencia_alegra') or '').strip(),
            alegra_journal_detalle=alegra_journal_detalle,
        )
        return JsonResponse({'ok': True, 'factura': factura_a_dict(fac)})
    except PermissionDenied:
        detail = (
            'No tiene permiso para crear radicados Alegra. '
            'Revise grupo Contabilidad y permiso accounting.view_facturas.'
        )
        _log_gastos_alegra_denied(request, 'crear', detail)
        return _json_error(detail, 403)
    except PermissionError as exc:
        detail = str(exc)
        _log_gastos_alegra_denied(request, 'crear', detail)
        return _json_error(detail, 403)
    except (ValueError, TypeError) as exc:
        detail = str(exc)
        logger.info(
            'gastos-alegra crear validación: user=%s detail=%s',
            request.user.username,
            detail,
        )
        return _json_error(detail, 400)
    except Exception as exc:
        logger.exception('gastos-alegra crear: user=%s', request.user.username)
        return _json_error(exc, 500)


@login_required
@require_http_methods(['POST'])
def ajax_gastos_alegra_asignar(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)
    try:
        if request.content_type and 'application/json' in request.content_type:
            body = json.loads(request.body.decode() or '{}')
        else:
            body = request.POST
        radicado = body.get('radicado')
        oficina = (body.get('oficina') or '').strip()
        aprobador_id = body.get('aprobador_id')
        comentario = (body.get('comentario_contable') or '').strip()
        fac = Facturas.objects.get(pk=radicado)
        if Pagos.objects.filter(nroradicado=fac).exists():
            return _json_error('El radicado ya tiene pagos asociados.')
        asignar_gasto_alegra(
            request,
            factura=fac,
            oficina=oficina,
            aprobador_user_id=parse_aprobador_user_id_opcional(aprobador_id),
            comentario_contable=comentario,
        )
        return JsonResponse({'ok': True, 'factura': factura_a_dict(fac)})
    except Facturas.DoesNotExist:
        return _json_error('Radicado no encontrado.', 404)
    except PermissionError as exc:
        return _json_error(exc, 403)
    except (ValueError, TypeError) as exc:
        return _json_error(exc, 400)
    except Exception as exc:
        return _json_error(exc, 500)


@login_required
@require_http_methods(['POST'])
def ajax_gastos_alegra_reasignar(request):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        return _json_error('Sin permiso Contabilidad.', 403)
    try:
        if request.content_type and 'application/json' in request.content_type:
            body = json.loads(request.body.decode() or '{}')
        else:
            body = request.POST
        radicado = body.get('radicado')
        oficina = (body.get('oficina') or '').strip()
        aprobador_id = body.get('aprobador_id')
        comentario = (body.get('comentario_contable') or '').strip()
        fac = Facturas.objects.get(pk=radicado)
        if Pagos.objects.filter(nroradicado=fac).exists():
            return _json_error('El radicado ya tiene pagos asociados.')
        reasignar_gasto_alegra(
            request,
            factura=fac,
            oficina=oficina,
            aprobador_user_id=aprobador_id,
            comentario_contable=comentario,
        )
        return JsonResponse({
            'ok': True,
            'factura': factura_a_dict(fac),
            'notifico_aprobador': bool(getattr(fac, '_gasto_reasignacion_notifico_aprobador', False)),
        })
    except Facturas.DoesNotExist:
        return _json_error('Radicado no encontrado.', 404)
    except PermissionError as exc:
        return _json_error(exc, 403)
    except (ValueError, TypeError) as exc:
        return _json_error(exc, 400)
    except Exception as exc:
        return _json_error(exc, 500)


def _html_or_json_error(request, message, status=404):
    accept = request.META.get('HTTP_ACCEPT', '')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in accept:
        return JsonResponse({'detail': message}, status=status)
    return HttpResponse(
        f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>Soporte PDF</title></head>'
        f'<body><p>{escape(message)}</p></body></html>',
        status=status,
        content_type='text/html; charset=utf-8',
    )


def _servir_soporte_radicado_pdf(request, factura, radicado_pk, *, log_prefix='soporte_pdf'):
    f, detail, http_status = ensure_soporte_radicado_descargable(factura)
    if detail:
        if http_status and http_status >= 500:
            logger.error(
                '%s: soporte no legible radicado=%s detail=%s',
                log_prefix, radicado_pk, detail,
            )
        return _html_or_json_error(request, detail, http_status or 404)

    try:
        handle = f.open('rb')
    except Exception:
        logger.exception('%s: no se pudo abrir soporte radicado=%s', log_prefix, radicado_pk)
        return _html_or_json_error(request, 'No se pudo leer el archivo de soporte.', 503)

    filename = os.path.basename(f.name or '') or f'soporte-radicado-{radicado_pk}.pdf'
    response = FileResponse(handle, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@login_required
@require_http_methods(['GET'])
def ajax_gastos_alegra_soporte_pdf(request, radicado_pk):
    """
    Soporte PDF para UI (aprobación / asignación).
    Storage primero; si no es legible y es bill Alegra, descarga desde Alegra.
    """
    factura = get_object_or_404(Facturas.objects.select_related('gasto_aprobador_asignado'), pk=radicado_pk)
    if not usuario_puede_ver_soporte_gasto(request.user, factura):
        return _html_or_json_error(request, 'Sin permiso para ver este soporte.', 403)
    return _servir_soporte_radicado_pdf(
        request, factura, radicado_pk, log_prefix='ajax_gastos_alegra_soporte_pdf',
    )


@login_required
@require_http_methods(['POST'])
def ajax_gastos_alegra_aprobar(request):
    try:
        if request.content_type and 'application/json' in request.content_type:
            body = json.loads(request.body.decode() or '{}')
        else:
            body = request.POST
        radicado = body.get('radicado')
        fac = Facturas.objects.get(pk=radicado)
        if Pagos.objects.filter(nroradicado=fac).exists():
            return _json_error('El radicado ya tiene pagos asociados.')
        aprobar_gasto_alegra(request, factura=fac)
        return JsonResponse({'ok': True, 'factura': factura_a_dict(fac)})
    except Facturas.DoesNotExist:
        return _json_error('Radicado no encontrado.', 404)
    except PermissionError as exc:
        return _json_error(exc, 403)
    except ValueError as exc:
        return _json_error(exc, 400)
    except Exception as exc:
        return _json_error(exc, 500)


def _link_aprobacion_response(request, *, ok, message, factura=None, status=200):
    wants_json = (
        'application/json' in (request.headers.get('Accept') or '')
        or (request.GET.get('format') or '').strip().lower() == 'json'
    )
    payload = {'ok': ok, 'message': message}
    if factura is not None:
        payload['factura'] = factura_a_dict(factura)
    if wants_json:
        return JsonResponse(payload, status=status)
    return HttpResponse(message, content_type='text/plain; charset=utf-8', status=status)


@csrf_exempt
@require_http_methods(['GET'])
def gasto_aprobacion_link_aprobar(request, radicado_pk, token):
    """
    Aprobación en un clic (WhatsApp): GET con token firmado en la URL.
    GET /accounting/gastos-alegra/aprobar-link/<radicado>/<token>/
    """
    try:
        fac = Facturas.objects.select_related('empresa', 'gasto_aprobador_asignado').get(pk=radicado_pk)
    except Facturas.DoesNotExist:
        return _link_aprobacion_response(
            request, ok=False, message='Radicado no encontrado.', status=404,
        )

    aprobador = fac.gasto_aprobador_asignado
    if not aprobador or not aprobador.is_active:
        return _link_aprobacion_response(
            request, ok=False, message='Este gasto no tiene aprobador asignado activo.', status=400,
        )

    try:
        verify_gasto_aprobacion_link_token(radicado_pk, aprobador.pk, token)
    except signing.SignatureExpired:
        return _link_aprobacion_response(
            request, ok=False, message='El enlace de aprobación expiró.', status=403,
        )
    except signing.BadSignature:
        return _link_aprobacion_response(
            request, ok=False, message='Enlace de aprobación inválido.', status=403,
        )

    if Pagos.objects.filter(nroradicado=fac).exists():
        return _link_aprobacion_response(
            request, ok=False, message='El radicado ya tiene pagos asociados.', status=400,
        )

    if fac.gasto_aprobacion_estado == Facturas.GASTO_APROB_APROBADO:
        msg = f'Gasto #{fac.pk} ({fac.nombretercero}) ya estaba aprobado.'
        return _link_aprobacion_response(request, ok=True, message=msg, factura=fac)

    try:
        with transaction.atomic():
            aprobar_gasto_alegra_para_usuario(fac, aprobador, canal='link/WhatsApp')
        msg = f'Gasto #{fac.pk} ({fac.nombretercero}) aprobado correctamente.'
        return _link_aprobacion_response(request, ok=True, message=msg, factura=fac)
    except PermissionError as exc:
        return _link_aprobacion_response(request, ok=False, message=str(exc), status=403)
    except ValueError as exc:
        return _link_aprobacion_response(request, ok=False, message=str(exc), status=400)
    except Exception:
        logger.exception('gasto_aprobacion_link_aprobar radicado=%s', radicado_pk)
        return _link_aprobacion_response(
            request, ok=False, message='Error al aprobar el gasto.', status=500,
        )


@csrf_exempt
@require_http_methods(['GET'])
def webhook_n8n_gasto_soporte_pdf(request, radicado_pk):
    """
    Descarga del soporte PDF para n8n (bucket S3 privado: la app lee con credenciales AWS).
    GET /accounting/webhooks/n8n/gastos-alegra/soporte-pdf/<radicado>
    Auth: mismo Bearer que webhooks salientes, X-Andina-Webhook-Secret o Token APIToken.
    """
    ok, err_response = n8n_inbound_authorized(request)
    if not ok:
        return err_response

    factura = get_object_or_404(Facturas, pk=radicado_pk)
    return _servir_soporte_radicado_pdf(
        request, factura, radicado_pk, log_prefix='webhook_n8n_gasto_soporte_pdf',
    )


@csrf_exempt
@require_http_methods(['POST'])
def webhook_n8n_gasto_aprobacion(request):
    """
    Entrada desde n8n (p. ej. aprobación por WhatsApp).
    POST /accounting/webhooks/n8n/gasto-aprobacion
    Auth: X-Andina-Webhook-Secret o Authorization: Token <APIToken>
    """
    ok, err_response = n8n_inbound_authorized(request)
    if not ok:
        return err_response

    try:
        if request.content_type and 'application/json' in request.content_type:
            body = json.loads(request.body.decode() or '{}')
        else:
            body = request.POST.dict()
    except (json.JSONDecodeError, TypeError, ValueError):
        return JsonResponse({'detail': 'JSON inválido.'}, status=400)

    accion = str(body.get('accion') or body.get('action') or 'aprobar').strip().lower()
    if accion != 'aprobar':
        return JsonResponse(
            {'detail': f'Acción no soportada: {accion}. Use accion=aprobar.'},
            status=400,
        )

    try:
        radicado = int(body.get('radicado'))
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'radicado (entero) es requerido.'}, status=400)

    try:
        aprobador_user_id = int(body.get('aprobador_user_id'))
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'aprobador_user_id (entero) es requerido.'}, status=400)

    canal = str(body.get('canal') or 'WhatsApp/n8n').strip()[:64]

    User = get_user_model()
    aprobador = User.objects.filter(pk=aprobador_user_id, is_active=True).first()
    if not aprobador:
        return JsonResponse({'detail': 'aprobador_user_id no encontrado o inactivo.'}, status=404)

    try:
        fac = Facturas.objects.select_related('empresa', 'gasto_aprobador_asignado').get(pk=radicado)
    except Facturas.DoesNotExist:
        return JsonResponse({'detail': 'Radicado no encontrado.'}, status=404)

    if Pagos.objects.filter(nroradicado=fac).exists():
        return JsonResponse({'detail': 'El radicado ya tiene pagos asociados.'}, status=400)

    try:
        with transaction.atomic():
            aprobar_gasto_alegra_para_usuario(fac, aprobador, canal=canal)
        return JsonResponse({
            'ok': True,
            'accion': 'aprobar',
            'canal': canal,
            'factura': factura_a_dict(fac),
        })
    except PermissionError as exc:
        return _json_error(exc, 403)
    except ValueError as exc:
        return _json_error(exc, 400)
    except Exception as exc:
        logger.exception('webhook_n8n_gasto_aprobacion radicado=%s', radicado)
        return _json_error(exc, 500)
