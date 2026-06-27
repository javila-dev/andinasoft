import json
import logging
from urllib.parse import parse_qs

from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.cache import cache

from django.views.decorators.csrf import csrf_exempt

from alegra_integration.exceptions import AlegraIntegrationError
from alegra_integration.models import (
    AlegraMapping,
    AlegraSyncBatch,
    AlegraWebhookInboundLog,
    AlegraWebhookSubscriptionLog,
)
from alegra_integration.services import (
    AlegraIntegrationService,
    ALEGRA_WEBHOOK_BILLS_INGEST_SUFFIX,
    ALEGRA_WEBHOOK_EVENTS,
    _contact_index_ident,
    _local_third_party_info,
    _mirror_tercero_raw_contact_mapping,
    _partner_display_name,
    _upsert_contact_index_for_mapping,
)
from andinasoft.models import cuentas_pagos, empresas, proyectos, clientes, asesores
from andinasoft.shared_models import formas_pago
from accounting.models import cuentas_intercompanias, info_interfaces, impuestos_legalizacion
from alegra_integration.mapping import MappingResolver, BANK_JOURNAL_LOCAL_CODE, BANK_JOURNAL_LOCAL_MODEL
from alegra_integration.client import AlegraMCPClient

logger = logging.getLogger(__name__)
from alegra_integration.webhook_bills import import_factura_from_alegra_bill, process_inbound_post
from alegra_integration.webhook_inbound_status import (
    INBOUND_CONSOLE_PAGE_SIZE,
    INBOUND_EVENT_CHOICES,
    INBOUND_STATUS_FILTER_CHOICES,
    build_inbound_log_rows,
    queryset_inbound_logs_for_console,
    update_inbound_log_from_process_result,
)


@login_required
def dashboard(request):
    return render(request, 'alegra_integration/dashboard.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
        'proyectos': proyectos.objects.filter(activo=True).order_by('proyecto'),
    })


def _empresa_nit_from_inbound_log(log):
    qs = (getattr(log, 'query_string', None) or '').strip()
    if not qs:
        return ''
    parsed = parse_qs(qs, keep_blank_values=False)
    for key in ('empresa',):
        vals = parsed.get(key) or []
        if vals and str(vals[0]).strip():
            return str(vals[0]).strip()
    return ''


@login_required
@require_http_methods(['GET'])
def webhooks_console(request):
    empresa_id = (request.GET.get('empresa') or '').strip()
    filter_evento = (request.GET.get('evento') or '').strip()
    filter_estado = (request.GET.get('estado') or '').strip()
    filter_buscar = (request.GET.get('buscar') or '').strip()
    active_tab = (request.GET.get('tab') or 'suscripcion').strip().lower()
    if active_tab not in ('suscripcion', 'recepciones'):
        active_tab = 'suscripcion'

    logs = []
    if empresa_id:
        logs = list(
            AlegraWebhookSubscriptionLog.objects.filter(empresa_id=empresa_id)
            .order_by('-created_at')[:40]
        )

    inbound_qs = queryset_inbound_logs_for_console(
        empresa=empresa_id,
        evento=filter_evento,
        estado=filter_estado,
        buscar=filter_buscar,
    )
    paginator = Paginator(inbound_qs, INBOUND_CONSOLE_PAGE_SIZE)
    inbound_page = paginator.get_page(request.GET.get('page'))
    inbound_logs = build_inbound_log_rows(
        inbound_page.object_list,
        empresa_filter=empresa_id,
    )

    return render(request, 'alegra_integration/webhooks.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
        'webhook_ingest_suffix': ALEGRA_WEBHOOK_BILLS_INGEST_SUFFIX,
        'webhook_events': sorted(ALEGRA_WEBHOOK_EVENTS),
        'selected_empresa': empresa_id,
        'initial_logs': logs,
        'inbound_logs': inbound_logs,
        'inbound_page': inbound_page,
        'filter_evento': filter_evento,
        'filter_estado': filter_estado,
        'filter_buscar': filter_buscar,
        'inbound_event_choices': INBOUND_EVENT_CHOICES,
        'inbound_status_choices': INBOUND_STATUS_FILTER_CHOICES,
        'active_tab': active_tab,
    })


@login_required
@require_http_methods(['POST'])
def webhooks_subscribe(request):
    try:
        payload = _payload(request)
        data = AlegraIntegrationService(user=request.user).subscribe_webhook(
            empresa_id=payload.get('empresa'),
            event=payload.get('event'),
            domain_base=payload.get('domain'),
        )
        return JsonResponse(data)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def webhooks_subscriptions_list(request):
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)
        data = AlegraIntegrationService(user=request.user).list_webhook_subscriptions(empresa_id=empresa_id)
        return JsonResponse(data)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def webhooks_inbound_replay(request):
    """
    Reprocesa un payload guardado en AlegraWebhookInboundLog (misma lógica que POST /webhooks/bills/).
    No crea otro registro de ingesta; devuelve el resultado para depurar radicados.
    """
    try:
        body = _payload(request)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)

    log_id = body.get('log_id')
    empresa_nit = (body.get('empresa') or '').strip()
    try:
        log = AlegraWebhookInboundLog.objects.get(pk=int(log_id))
    except (AlegraWebhookInboundLog.DoesNotExist, TypeError, ValueError):
        return JsonResponse({'detail': 'Recepción no encontrada'}, status=404)

    if (log.http_method or '').upper() != 'POST':
        return JsonResponse({'detail': 'Solo se puede reenviar recepciones POST'}, status=400)

    payload = log.payload if isinstance(log.payload, dict) else {}
    if not payload or payload.get('_json_parse_error'):
        return JsonResponse(
            {'detail': 'El payload guardado no es JSON válido; revisa el registro en Admin.'},
            status=400,
        )

    if not empresa_nit:
        from alegra_integration.webhook_inbound_status import resolve_empresa_nit_for_log
        bill = {}
        msg = payload.get('message')
        if isinstance(msg, dict) and isinstance(msg.get('bill'), dict):
            bill = msg['bill']
        bill_id = str(bill.get('id') or '').strip()
        empresa_nit = resolve_empresa_nit_for_log(log, '', bill_id=bill_id)
    if not empresa_nit:
        return JsonResponse(
            {
                'detail': (
                    'Indica la empresa (NIT) en el selector «Empresa» arriba. '
                    'En ingesta normal va en la URL: /webhooks/bills/<NIT>/'
                ),
            },
            status=400,
        )

    extra = process_inbound_post(empresa_nit, payload)
    update_inbound_log_from_process_result(log, empresa_nit, extra)
    return JsonResponse({
        'status': 'replayed',
        'replayed_from_log_id': log.pk,
        'empresa': empresa_nit,
        'subject': payload.get('subject'),
        'replayed_by': request.user.username,
        **extra,
    })


@login_required
@require_http_methods(['POST'])
def webhooks_inbound_import_bill(request):
    """
    Crea o reconcilia un radicado consultando GET /bills/{id} en Alegra.
    Util cuando no llego el webhook o el radicado fue eliminado.
    """
    try:
        body = _payload(request)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)

    empresa_id = (body.get('empresa') or '').strip()
    bill_id = str(body.get('bill_id') or '').strip()
    if not empresa_id:
        return JsonResponse({'detail': 'Selecciona la empresa (NIT).'}, status=400)
    if not bill_id:
        return JsonResponse({'detail': 'Indica el numero de factura en Alegra.'}, status=400)

    try:
        empresa = empresas.objects.get(pk=empresa_id)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada.'}, status=404)

    if not empresa.alegra_enabled:
        return JsonResponse({'detail': 'La empresa no tiene integracion Alegra activa.'}, status=400)

    try:
        result = import_factura_from_alegra_bill(empresa, bill_id, sync_pdf=True)
    except ValueError as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        logger.exception('webhooks_inbound_import_bill empresa=%s bill=%s', empresa_id, bill_id)
        return _error_response(exc, status=500)

    return JsonResponse({
        'status': 'imported',
        'empresa': empresa_id,
        'bill_id': bill_id,
        'imported_by': request.user.username,
        'created': bool(result.get('created')),
        'idempotent': not bool(result.get('created')),
        'factura_pk': result.get('factura_pk'),
        'alegra_bill_id': result.get('alegra_bill_id'),
        'pdf_saved': bool(result.get('pdf_saved')),
        'enriched_fields': result.get('enriched_fields') or [],
    })


@login_required
@require_http_methods(['POST'])
def webhooks_subscriptions_delete(request):
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        subscription_id = (payload.get('subscription_id') or '').strip()
        if not empresa_id or not subscription_id:
            return JsonResponse({'detail': 'empresa y subscription_id son requeridos'}, status=400)
        data = AlegraIntegrationService(user=request.user).delete_webhook_subscription(
            empresa_id=empresa_id,
            subscription_id=subscription_id,
        )
        return JsonResponse({'ok': True, **data})
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


def _persist_alegra_webhook_inbound(request, empresa_nit=''):
    """
    Guarda el cuerpo recibido para analizar la estructura que envía Alegra (antes de mapear a Facturas).
    """
    MAX_BYTES = 500_000
    MAX_RAW_STORE = 100_000
    raw_bytes = request.body or b''
    truncated = len(raw_bytes) > MAX_BYTES
    raw_bytes = raw_bytes[:MAX_BYTES]
    raw_text = raw_bytes.decode('utf-8', errors='replace')
    xfwd = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    remote = (xfwd or request.META.get('REMOTE_ADDR') or '')[:255]

    payload = {}
    raw_store = raw_text[:MAX_RAW_STORE]
    try:
        parsed = json.loads(raw_text) if raw_text.strip() else None
    except json.JSONDecodeError:
        payload = {'_json_parse_error': True}
    else:
        if isinstance(parsed, dict):
            payload = parsed
        elif isinstance(parsed, list):
            payload = {'_json_array': parsed}
        elif parsed is not None:
            payload = {'_json_primitive': parsed}
        else:
            raw_store = raw_text[:MAX_RAW_STORE] if raw_text else ''

    if truncated and isinstance(payload, dict):
        payload = {**payload, '_body_truncated': True}

    log = AlegraWebhookInboundLog.objects.create(
        http_method=(request.method or '')[:16],
        content_type=(request.META.get('CONTENT_TYPE') or '')[:255],
        remote_addr=remote,
        query_string=(request.META.get('QUERY_STRING') or '')[:5000],
        payload=payload,
        raw_body=raw_store if payload.get('_json_parse_error') else '',
        empresa_nit=(empresa_nit or '')[:32],
    )
    return log, payload


@csrf_exempt
@require_http_methods(['GET', 'HEAD', 'POST'])
def webhooks_bills_ingest(request, empresa_id=None):
    """
    Donde Alegra **envía** los eventos (p. ej. new-bill): POST con JSON.

    La **suscripción** (`/accounting/alegra/webhooks/subscribe`) solo registra en la API de Alegra
    la URL de este endpoint; no recibe facturas.

    GET/HEAD: respuesta mínima para validación de URL al crear la suscripción (sin persistir).
    POST: persiste en `AlegraWebhookInboundLog` y, si viene `?empresa=<NIT>` o el NIT viene en el path,
    intenta crear/actualizar `Facturas`.
    """
    if request.method in ('GET', 'HEAD'):
        return JsonResponse({'status': 'ok', 'endpoint': 'alegra-webhooks-bills'})
    # Path /webhooks/bills/<NIT>/ (suscripción actual) o ?empresa=<NIT>.
    empresa_qs = (str(empresa_id or '').strip()) or (request.GET.get('empresa') or '').strip()
    log, payload = _persist_alegra_webhook_inbound(request, empresa_nit=empresa_qs)
    extra = process_inbound_post(empresa_qs, payload)
    update_inbound_log_from_process_result(log, empresa_qs, extra)
    body = {'status': 'accepted', 'endpoint': 'alegra-webhooks-bills', **extra}
    return JsonResponse(body, status=200)


@login_required
def references(request):
    return render(request, 'alegra_integration/references.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
        'proyectos': proyectos.objects.filter(activo=True).order_by('proyecto'),
    })


@login_required
@require_http_methods(['GET'])
def references_data(request):
    try:
        empresa_id = request.GET.get('empresa')
        ref_type = (request.GET.get('type') or '').strip().lower()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)

        cache_key = f'alegra:refs:{empresa_id}:{ref_type or "all"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return JsonResponse(cached)

        data = AlegraIntegrationService(user=request.user).reference_sync(
            empresa_id=empresa_id,
            ref_type=ref_type or None,
        )

        if ref_type in ('banks', 'categories', 'cost_centers'):
            payload = {ref_type: data.get(ref_type, [])}
        elif ref_type in ('journal_numerations', 'journal_numeration', 'journals_numerations'):
            payload = {'journal_numerations': data.get('journal_numerations', [])}
        elif ref_type in ('number_templates', 'numerations', 'numeration'):
            payload = {'number_templates': data.get('number_templates', {})}
        elif ref_type == 'retentions':
            payload = {'retentions': data.get('retentions', [])}
        elif ref_type == 'taxes':
            payload = {'taxes': data.get('taxes', [])}
        else:
            payload = data

        cache.set(cache_key, payload, timeout=60 * 10)
        return JsonResponse(payload)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_mappings(request):
    try:
        empresa_id = request.GET.get('empresa')
        mapping_type = (request.GET.get('mapping_type') or '').strip()
        local_pk = (request.GET.get('local_pk') or '').strip()
        local_model = (request.GET.get('local_model') or '').strip()
        local_code = (request.GET.get('local_code') or '').strip()
        alegra_id = (request.GET.get('alegra_id') or '').strip()
        proyecto_id = (request.GET.get('proyecto') or '').strip()
        include_null = (request.GET.get('include_null') or '').strip() in ('1', 'true', 'True')
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)

        qs = AlegraMapping.objects.filter(empresa_id=empresa_id).order_by(
            'mapping_type', 'local_model', 'local_pk', 'local_code', '-proyecto_id', '-updated_at',
        )
        if mapping_type:
            qs = qs.filter(mapping_type=mapping_type)
        if proyecto_id:
            if include_null:
                qs = qs.filter(Q(proyecto_id=proyecto_id) | Q(proyecto__isnull=True))
            else:
                qs = qs.filter(proyecto_id=proyecto_id)
        else:
            qs = qs.filter(proyecto__isnull=True)
        if local_model:
            qs = qs.filter(local_model=local_model)
        if local_pk:
            qs = qs.filter(local_pk=local_pk)
        if local_code:
            qs = qs.filter(local_code=local_code)
        if alegra_id:
            qs = qs.filter(alegra_id=alegra_id)

        rows = [
            {
                'id': m.pk,
                'mapping_type': m.mapping_type,
                'proyecto': m.proyecto_id,
                'local_model': m.local_model,
                'local_pk': m.local_pk,
                'local_code': m.local_code,
                'alegra_id': m.alegra_id,
                'description': m.description,
                'active': m.active,
                'updated_at': m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in qs[:2000]
        ]
        return JsonResponse({'mappings': rows})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_local_accounts(request):
    try:
        empresa_id = request.GET.get('empresa')
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)
        qs = cuentas_pagos.objects.filter(nit_empresa_id=empresa_id, activo=True).order_by('idcuenta')
        rows = [
            {
                'idcuenta': c.idcuenta,
                'cuentabanco': c.cuentabanco or '',
                'nro_cuentacontable': c.nro_cuentacontable,
                'es_caja': bool(c.es_caja),
            }
            for c in qs
        ]
        return JsonResponse({'local_accounts': rows})
    except Exception as exc:
        return _error_response(exc, status=500)


def _alegra_bank_category_from_api(client, bank_id):
    bank_detail = client.rest('GET', f'/bank-accounts/{bank_id}?fields=category')
    if not isinstance(bank_detail, dict):
        return None, ''
    cat = bank_detail.get('category') or {}
    if not isinstance(cat, dict):
        return None, ''
    cat_id = cat.get('id')
    if not cat_id:
        return None, ''
    label_parts = [str(cat.get('code') or '').strip(), str(cat.get('name') or cat.get('description') or '').strip()]
    label = ' · '.join(p for p in label_parts if p) or f'ID {cat_id}'
    return str(cat_id), label[:255]


def _upsert_bank_journal_category_mapping(
    *,
    empresa_id,
    cuenta,
    alegra_bank_id,
    category_alegra_id,
    category_description='',
):
    puc = getattr(cuenta, 'nro_cuentacontable', None)
    if not puc:
        return None
    category_alegra_id = str(category_alegra_id or '').strip()
    if not category_alegra_id:
        return None
    desc = (category_description or f'bank journal {cuenta.cuentabanco or cuenta.idcuenta}')[:255]
    cat_m, cat_created = AlegraMapping.objects.update_or_create(
        empresa_id=empresa_id,
        proyecto=None,
        mapping_type=AlegraMapping.CATEGORY,
        local_model=BANK_JOURNAL_LOCAL_MODEL,
        local_pk=str(cuenta.idcuenta),
        local_code=BANK_JOURNAL_LOCAL_CODE,
        defaults={
            'alegra_id': category_alegra_id,
            'description': desc,
            'active': True,
            'alegra_payload': {
                'source': 'bank_account',
                'bank_account_id': str(alegra_bank_id),
                'local_idcuenta': str(cuenta.idcuenta),
                'nro_cuentacontable': str(puc),
            },
        },
    )
    return {
        'created': cat_created,
        'mapping_id': cat_m.pk,
        'local_idcuenta': str(cuenta.idcuenta),
        'local_code': str(puc),
        'alegra_category_id': category_alegra_id,
        'description': desc,
    }


@login_required
@require_http_methods(['GET'])
def references_suggest_bank_category(request):
    """Sugiere la categoría contable asociada a un banco Alegra (para journals)."""
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        bank_id = (request.GET.get('bank_id') or '').strip()
        if not empresa_id or not bank_id:
            return JsonResponse({'detail': 'empresa y bank_id son requeridos'}, status=400)
        empresa = empresas.objects.get(pk=empresa_id)
        client = AlegraMCPClient(empresa)
        cat_id, label = _alegra_bank_category_from_api(client, bank_id)
        if not cat_id:
            return JsonResponse({'category_id': None, 'category_label': ''})
        return JsonResponse({'category_id': cat_id, 'category_label': label})
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def references_save_bank_mapping(request):
    try:
        payload = _payload(request)
        empresa_id = payload.get('empresa')
        local_idcuenta = payload.get('local_idcuenta')
        alegra_id = payload.get('alegra_id')
        category_alegra_id = (payload.get('category_alegra_id') or '').strip()
        category_description = (payload.get('category_description') or '').strip()

        if not empresa_id or not local_idcuenta or not alegra_id:
            return JsonResponse({'detail': 'empresa, local_idcuenta y alegra_id son requeridos'}, status=400)

        cuenta = cuentas_pagos.objects.filter(nit_empresa_id=empresa_id, idcuenta=local_idcuenta).first()
        if not cuenta:
            return JsonResponse({'detail': 'Cuenta bancaria local no encontrada para esa empresa'}, status=404)

        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=None,
            mapping_type=AlegraMapping.BANK_ACCOUNT,
            local_model='andinasoft.cuentas_pagos',
            local_pk=str(cuenta.idcuenta),
            local_code='',
            defaults={
                'alegra_id': str(alegra_id),
                'description': (cuenta.cuentabanco or '')[:255],
                'active': True,
            },
        )

        category_mapping = None
        if getattr(cuenta, 'nro_cuentacontable', None):
            if not category_alegra_id:
                try:
                    empresa = empresas.objects.get(pk=empresa_id)
                    client = AlegraMCPClient(empresa)
                    suggested_id, suggested_label = _alegra_bank_category_from_api(client, alegra_id)
                    if suggested_id:
                        category_alegra_id = suggested_id
                        category_description = category_description or suggested_label
                except Exception:
                    category_alegra_id = ''
            if not category_alegra_id:
                return JsonResponse({
                    'detail': (
                        f'La cuenta {cuenta.cuentabanco or cuenta.idcuenta} tiene PUC '
                        f'{cuenta.nro_cuentacontable}: indica la cuenta del PUC en Alegra '
                        f'(la misma que usa el journal intercompany).'
                    ),
                }, status=400)
            category_mapping = _upsert_bank_journal_category_mapping(
                empresa_id=empresa_id,
                cuenta=cuenta,
                alegra_bank_id=alegra_id,
                category_alegra_id=category_alegra_id,
                category_description=category_description,
            )

        return JsonResponse({
            'ok': True,
            'created': created,
            'mapping_id': m.pk,
            'category_mapping': category_mapping,
        })
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


def _upsert_receipt_forma_debit_mapping(
    *,
    empresa_id,
    proyecto,
    forma,
    alegra_id,
    description='',
    intercompany=False,
    counterparty_nit='',
):
    forma = (forma or '').strip()
    alegra_id = (alegra_id or '').strip()
    if not forma or not alegra_id:
        raise ValueError('forma y alegra_id son requeridos')
    intercompany = bool(intercompany)
    counterparty_nit = (counterparty_nit or '').strip()
    if intercompany and not counterparty_nit:
        raise ValueError(
            f'Indica el NIT de la empresa contraparte para la forma de pago «{forma}» (intercompany).'
        )
    alegra_payload = {'intercompany': intercompany}
    if intercompany:
        alegra_payload['counterparty_nit'] = counterparty_nit
    return AlegraMapping.objects.update_or_create(
        empresa_id=empresa_id,
        proyecto=proyecto,
        mapping_type=AlegraMapping.CATEGORY,
        local_model='andinasoft.formas_pago',
        local_pk=forma,
        local_code='receipt_debit',
        defaults={
            'alegra_id': alegra_id,
            'description': (description or forma)[:255],
            'alegra_payload': alegra_payload,
            'active': True,
        },
    )


@login_required
@require_http_methods(['POST'])
def references_save_category_mapping(request):
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        local_code = (payload.get('local_code') or '').strip()
        alegra_id = (payload.get('alegra_id') or '').strip()
        description = (payload.get('description') or '').strip()
        proyecto_id = (payload.get('proyecto') or '').strip()
        local_model = (payload.get('local_model') or '').strip()
        local_pk = (payload.get('local_pk') or '').strip()

        if not empresa_id or not local_code or not alegra_id:
            return JsonResponse({'detail': 'empresa, local_code y alegra_id son requeridos'}, status=400)

        proyecto = proyectos.objects.get(pk=proyecto_id) if proyecto_id else None

        if local_model == 'andinasoft.formas_pago' and local_code == 'receipt_debit':
            if not proyecto_id:
                return JsonResponse({'detail': 'proyecto es requerido para formas de pago de recibos'}, status=400)
            try:
                m, created = _upsert_receipt_forma_debit_mapping(
                    empresa_id=empresa_id,
                    proyecto=proyecto,
                    forma=local_pk,
                    alegra_id=alegra_id,
                    description=description,
                    intercompany=bool(payload.get('intercompany')),
                    counterparty_nit=(payload.get('counterparty_nit') or '').strip(),
                )
            except ValueError as exc:
                return JsonResponse({'detail': str(exc)}, status=400)
            return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})

        defaults = {
            'alegra_id': alegra_id,
            'description': (description or local_code)[:255],
            'active': True,
        }

        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=proyecto,
            mapping_type=AlegraMapping.CATEGORY,
            local_model=local_model,
            local_pk=local_pk,
            local_code=local_code,
            defaults=defaults,
        )
        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def references_save_receipt_formas_pago(request):
    """Guarda en lote los mapeos débito/intercompany de formas de pago (recibos)."""
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        proyecto_id = (payload.get('proyecto') or '').strip()
        items = payload.get('formas') or []
        if not empresa_id or not proyecto_id:
            return JsonResponse({'detail': 'empresa y proyecto son requeridos'}, status=400)
        if not isinstance(items, list):
            return JsonResponse({'detail': 'formas debe ser una lista'}, status=400)

        proyecto = proyectos.objects.get(pk=proyecto_id)
        saved = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            forma = (item.get('forma') or item.get('descripcion') or '').strip()
            alegra_id = (item.get('alegra_id') or item.get('catId') or '').strip()
            if not forma or not alegra_id:
                continue
            try:
                _upsert_receipt_forma_debit_mapping(
                    empresa_id=empresa_id,
                    proyecto=proyecto,
                    forma=forma,
                    alegra_id=alegra_id,
                    description=(item.get('description') or item.get('catLabel') or forma).strip(),
                    intercompany=bool(item.get('intercompany')),
                    counterparty_nit=(item.get('counterparty_nit') or '').strip(),
                )
                saved += 1
            except ValueError as exc:
                return JsonResponse({'detail': str(exc), 'saved': saved}, status=400)

        return JsonResponse({'ok': True, 'saved': saved})
    except proyectos.DoesNotExist:
        return JsonResponse({'detail': 'Proyecto no encontrado'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_receipt_formas_pago(request):
    """
    Formas de pago del proyecto (tabla local) con mapeo Alegra de débito por recibo.
    """
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        proyecto_id = (request.GET.get('proyecto') or '').strip()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)
        if not proyecto_id:
            return JsonResponse({'detail': 'Proyecto requerido'}, status=400)

        proyectos.objects.get(pk=proyecto_id)
        formas = formas_pago.objects.using(proyecto_id).all().order_by('descripcion')
        maps = {
            m.local_pk: m
            for m in AlegraMapping.objects.filter(
                empresa_id=empresa_id,
                proyecto_id=proyecto_id,
                mapping_type=AlegraMapping.CATEGORY,
                local_model='andinasoft.formas_pago',
                local_code='receipt_debit',
                active=True,
            )
        }
        rows = []
        for forma in formas:
            desc = (forma.descripcion or '').strip()
            m = maps.get(desc)
            extra = m.alegra_payload if m and isinstance(m.alegra_payload, dict) else {}
            rows.append({
                'descripcion': desc,
                'cuenta_contable': (forma.cuenta_contable or '').strip(),
                'cuenta_banco': (forma.cuenta_banco or '').strip() or None,
                'alegra_category_id': m.alegra_id if m else '',
                'alegra_category_label': (m.description or '').strip() if m else '',
                'intercompany': bool(extra.get('intercompany')),
                'counterparty_nit': str(extra.get('counterparty_nit') or '').strip(),
            })
        return JsonResponse({'proyecto': proyecto_id, 'formas_pago': rows, 'total': len(rows)})
    except proyectos.DoesNotExist:
        return JsonResponse({'detail': 'Proyecto no encontrado'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_interfaces(request):
    """
    List accounting interfaces (info_interfaces) for a company to configure per-concept Alegra category links.
    """
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)
        qs = info_interfaces.objects.filter(empresa_id=empresa_id).order_by('descripcion', 'id_doc')
        rows = [
            {
                'id': i.id_doc,
                'descripcion': i.descripcion or '',
                'tipo_doc': i.tipo_doc or '',
                'cuenta_credito_1': (i.cuenta_credito_1 or '').strip(),
                'cuenta_debito_1': (i.cuenta_debito_1 or '').strip(),
            }
            for i in qs
        ]
        return JsonResponse({'interfaces': rows})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_intercompany(request):
    """
    List intercompany account relations for a company (either side).
    """
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)
        qs = cuentas_intercompanias.objects.filter(Q(empresa_desde_id=empresa_id) | Q(empresa_hacia_id=empresa_id)) \
            .select_related('empresa_desde', 'empresa_hacia') \
            .order_by('empresa_desde_id', 'empresa_hacia_id')
        rows = [
            {
                'id': r.pk,
                'empresa_desde': r.empresa_desde_id,
                'empresa_desde_nombre': getattr(r.empresa_desde, 'nombre', '') or '',
                'empresa_hacia': r.empresa_hacia_id,
                'empresa_hacia_nombre': getattr(r.empresa_hacia, 'nombre', '') or '',
                'cuenta_por_cobrar': str(getattr(r, 'cuenta_por_cobrar', '') or ''),
                'cuenta_por_pagar': str(getattr(r, 'cuenta_por_pagar', '') or ''),
                'documento': getattr(r, 'documento', '') or '',
            }
            for r in qs
        ]
        return JsonResponse({'relations': rows})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def references_save_numeration_mapping(request):
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        local_code = (payload.get('local_code') or '').strip()
        alegra_id = (payload.get('alegra_id') or '').strip()
        description = (payload.get('description') or '').strip()
        proyecto_id = (payload.get('proyecto') or '').strip()

        if not empresa_id or not local_code or not alegra_id:
            return JsonResponse({'detail': 'empresa, local_code y alegra_id son requeridos'}, status=400)

        proyecto = proyectos.objects.get(pk=proyecto_id) if proyecto_id else None
        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=proyecto,
            mapping_type=AlegraMapping.NUMERATION,
            local_model='',
            local_pk='',
            local_code=local_code,
            defaults={
                'alegra_id': alegra_id,
                'description': (description or local_code)[:255],
                'active': True,
            },
        )
        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def references_save_retention_mapping(request):
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        local_code = (payload.get('local_code') or '').strip()
        alegra_id = (payload.get('alegra_id') or '').strip()
        description = (payload.get('description') or '').strip()

        if not empresa_id or not local_code or not alegra_id:
            return JsonResponse({'detail': 'empresa, local_code y alegra_id son requeridos'}, status=400)

        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=None,
            mapping_type=AlegraMapping.RETENTION,
            local_model='',
            local_pk='',
            local_code=local_code,
            defaults={
                'alegra_id': alegra_id,
                'description': (description or local_code)[:255],
                'active': True,
            },
        )
        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def references_save_cost_center_mapping(request):
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        proyecto_id = (payload.get('proyecto') or '').strip()
        local_model = (payload.get('local_model') or 'andinasoft.proyectos').strip()
        local_pk = (payload.get('local_pk') or proyecto_id or '').strip()
        local_code = (payload.get('local_code') or 'commission').strip()
        alegra_id = (payload.get('alegra_id') or '').strip()
        description = (payload.get('description') or '').strip()

        if not empresa_id or not alegra_id:
            return JsonResponse({'detail': 'empresa y alegra_id son requeridos'}, status=400)

        if local_model == 'andinasoft.cuentas_pagos':
            if not local_pk:
                return JsonResponse({'detail': 'local_pk (caja) es requerido'}, status=400)
            proyecto = None
            local_code = 'caja_cost_center'
        else:
            if not proyecto_id:
                return JsonResponse({'detail': 'empresa, proyecto y alegra_id son requeridos'}, status=400)
            proyecto = proyectos.objects.get(pk=proyecto_id)
            local_pk = proyecto_id

        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=proyecto,
            mapping_type=AlegraMapping.COST_CENTER,
            local_model=local_model,
            local_pk=local_pk,
            local_code=local_code,
            defaults={
                'alegra_id': alegra_id,
                'description': (description or local_code)[:255],
                'active': True,
            },
        )
        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})
    except proyectos.DoesNotExist:
        return JsonResponse({'detail': 'Proyecto no encontrado'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_caja_impuestos(request):
    """Impuestos de legalizacion local con mapeos Alegra (tax / retention) para caja."""
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)

        tax_maps = {
            m.local_pk: m
            for m in AlegraMapping.objects.filter(
                empresa_id=empresa_id,
                mapping_type=AlegraMapping.TAX,
                local_model='accounting.impuestos_legalizacion',
                local_code='impuesto_tax',
                active=True,
            )
        }
        retention_maps = {
            m.local_pk: m
            for m in AlegraMapping.objects.filter(
                empresa_id=empresa_id,
                mapping_type=AlegraMapping.RETENTION,
                local_model='accounting.impuestos_legalizacion',
                local_code='impuesto_retention',
                active=True,
            )
        }

        rows = []
        for imp in impuestos_legalizacion.objects.filter(activo=True).order_by('descripcion'):
            pk = str(imp.pk)
            desc = (imp.descripcion or '').lower()
            skip = 'ajuste' in desc
            is_rte = (not skip) and any(x in desc for x in ('rte', 'retef', 'reten'))
            is_iva = (not skip) and any(x in desc for x in ('iva', 'impuesto'))
            if not skip and not is_iva and not is_rte:
                is_iva = True
                is_rte = True
            tm = tax_maps.get(pk)
            rm = retention_maps.get(pk)
            rows.append({
                'id': imp.pk,
                'descripcion': imp.descripcion,
                'es_iva': is_iva,
                'es_rte': is_rte,
                'tax_alegra_id': tm.alegra_id if tm else '',
                'tax_description': tm.description if tm else '',
                'retention_alegra_id': rm.alegra_id if rm else '',
                'retention_description': rm.description if rm else '',
            })
        return JsonResponse({'impuestos': rows})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_caja_conceptos(request):
    """Conceptos de legalizacion con PUC local y mapeo Alegra para gastos de caja."""
    try:
        from accounting.models import conceptos_legalizacion
        from alegra_integration.caja_mapping import (
            CAJA_EXPENSE_LOCAL_CODE,
            caja_puc_attr_for_empresa,
            caja_puc_code,
            caja_puc_field_label,
        )

        empresa_id = (request.GET.get('empresa') or '').strip()
        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)

        empresa = empresas.objects.get(pk=empresa_id)
        puc_attr = caja_puc_attr_for_empresa(empresa)
        category_maps = {
            m.local_pk: m
            for m in AlegraMapping.objects.filter(
                empresa_id=empresa_id,
                mapping_type=AlegraMapping.CATEGORY,
                local_model='accounting.conceptos_legalizacion',
                local_code=CAJA_EXPENSE_LOCAL_CODE,
                active=True,
            )
        }
        puc_maps = {
            m.local_code: m
            for m in AlegraMapping.objects.filter(
                empresa_id=empresa_id,
                proyecto__isnull=True,
                mapping_type=AlegraMapping.CATEGORY,
                local_model='',
                local_pk='',
                active=True,
            )
            if m.local_code and m.local_code not in (
                'caja_cxp', 'caja_credit', 'caja_ajuste_aproximacion',
                'default_cxp', 'commission_expense', 'commission_debit', 'commission_credit',
            )
        }

        rows = []
        for concept in conceptos_legalizacion.objects.filter(activo=True).order_by('descripcion'):
            pk = str(concept.pk)
            puc = caja_puc_code(concept, puc_attr)
            cm = category_maps.get(pk)
            pm = puc_maps.get(puc) if puc else None
            alegra_id = ''
            alegra_desc = ''
            if cm:
                alegra_id = cm.alegra_id
                alegra_desc = cm.description or ''
            elif pm:
                alegra_id = pm.alegra_id
                alegra_desc = pm.description or ''
            rows.append({
                'id': concept.pk,
                'descripcion': concept.descripcion,
                'puc': puc,
                'category_alegra_id': alegra_id,
                'category_description': alegra_desc,
            })

        return JsonResponse({
            'puc_field': puc_attr,
            'puc_field_label': caja_puc_field_label(puc_attr),
            'conceptos': rows,
        })
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def references_save_impuesto_mapping(request):
    """
    Guarda mapeo Alegra para una fila de impuestos_legalizacion.
    Body: { empresa, impuesto_id, kind: 'tax'|'retention', alegra_id, description? }
    """
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        impuesto_id = str(payload.get('impuesto_id') or '').strip()
        kind = (payload.get('kind') or '').strip().lower()
        alegra_id = (payload.get('alegra_id') or '').strip()
        description = (payload.get('description') or '').strip()

        if not empresa_id or not impuesto_id or kind not in ('tax', 'retention'):
            return JsonResponse({'detail': 'empresa, impuesto_id y kind (tax|retention) son requeridos'}, status=400)

        imp = impuestos_legalizacion.objects.filter(pk=impuesto_id, activo=True).first()
        if not imp:
            return JsonResponse({'detail': 'Impuesto local no encontrado'}, status=404)

        if not alegra_id:
            AlegraMapping.objects.filter(
                empresa_id=empresa_id,
                mapping_type=AlegraMapping.TAX if kind == 'tax' else AlegraMapping.RETENTION,
                local_model='accounting.impuestos_legalizacion',
                local_pk=impuesto_id,
                local_code='impuesto_tax' if kind == 'tax' else 'impuesto_retention',
            ).update(active=False)
            return JsonResponse({'ok': True, 'cleared': True})

        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=None,
            mapping_type=AlegraMapping.TAX if kind == 'tax' else AlegraMapping.RETENTION,
            local_model='accounting.impuestos_legalizacion',
            local_pk=impuesto_id,
            local_code='impuesto_tax' if kind == 'tax' else 'impuesto_retention',
            defaults={
                'alegra_id': alegra_id,
                'description': (description or imp.descripcion or alegra_id)[:255],
                'active': True,
            },
        )
        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def references_categories_search(request):
    """
    Server-side search for Alegra categories to avoid downloading huge catalogs to the browser.
    """
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        q = (request.GET.get('q') or '').strip().lower()
        limit = int(request.GET.get('limit') or 50)
        limit = max(1, min(limit, 200))

        if not empresa_id:
            return JsonResponse({'detail': 'Empresa requerida'}, status=400)
        if not q or len(q) < 2:
            return JsonResponse({'categories': []})

        cache_key = f'alegra:categories:{empresa_id}'
        categories = cache.get(cache_key)
        if categories is None:
            empresa = empresas.objects.get(pk=empresa_id)
            client = AlegraMCPClient(empresa)
            categories = client.rest('GET', '/categories?format=plain')
            if isinstance(categories, dict) and 'data' in categories:
                categories = categories['data']
            if not isinstance(categories, list):
                categories = []
            cache.set(cache_key, categories, timeout=60 * 10)

        def _haystack(c):
            if not isinstance(c, dict):
                return ''
            return ' '.join([
                str(c.get('id') or ''),
                str(c.get('code') or ''),
                str(c.get('name') or ''),
                str(c.get('description') or ''),
            ]).lower()

        hits = []
        for c in categories:
            if q in _haystack(c):
                hits.append(c)
                if len(hits) >= limit:
                    break

        return JsonResponse({'categories': hits})
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def debug_mapping_check(request):
    """
    Diagnostic endpoint to verify what MappingResolver sees for a given key.
    """
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        proyecto_id = (request.GET.get('proyecto') or '').strip()
        mapping_type = (request.GET.get('mapping_type') or '').strip()
        local_model = (request.GET.get('local_model') or '').strip()
        local_pk = (request.GET.get('local_pk') or '').strip()
        local_code = (request.GET.get('local_code') or '').strip()

        if not empresa_id or not mapping_type:
            return JsonResponse({'detail': 'empresa y mapping_type son requeridos'}, status=400)

        empresa = empresas.objects.get(pk=empresa_id)
        proyecto = proyectos.objects.get(pk=proyecto_id) if proyecto_id else None

        resolver = MappingResolver(empresa, proyecto)
        # Try to resolve; if missing, also return candidates.
        try:
            alegra_id = resolver.get(
                mapping_type,
                local_model=local_model,
                local_pk=local_pk,
                local_code=local_code,
            )
            resolved = True
        except Exception as exc:
            alegra_id = None
            resolved = False
            err = str(exc)

        qs = AlegraMapping.objects.filter(empresa_id=empresa.pk, mapping_type=mapping_type)
        if mapping_type in (AlegraMapping.CONTACT, AlegraMapping.PAYMENT_METHOD):
            qs = qs.filter(proyecto__isnull=True)
        else:
            if proyecto:
                qs = qs.filter(Q(proyecto=proyecto) | Q(proyecto__isnull=True))
            else:
                qs = qs.filter(proyecto__isnull=True)
        if local_model:
            qs = qs.filter(local_model=local_model)
        if local_pk:
            qs = qs.filter(local_pk=str(local_pk).strip())
        if local_code:
            qs = qs.filter(local_code=str(local_code).strip())

        candidates = [
            {
                'id': m.pk,
                'empresa': m.empresa_id,
                'proyecto': m.proyecto_id,
                'mapping_type': m.mapping_type,
                'local_model': m.local_model,
                'local_pk': m.local_pk,
                'local_code': m.local_code,
                'alegra_id': m.alegra_id,
                'active': m.active,
                'updated_at': m.updated_at.isoformat() if m.updated_at else None,
            }
            for m in qs.order_by('-proyecto_id', '-updated_at')[:10]
        ]

        resp = {
            'resolved': resolved,
            'alegra_id': alegra_id,
            'candidates': candidates,
        }
        if not resolved:
            resp['error'] = err
        return JsonResponse(resp)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except proyectos.DoesNotExist:
        return JsonResponse({'detail': 'Proyecto no encontrado'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)

@login_required
@require_http_methods(['GET'])
def batch_list(request):
    empresa_id = request.GET.get('empresa')
    document_type = (request.GET.get('document_type') or '').strip()
    qs = AlegraSyncBatch.objects.select_related('empresa', 'proyecto', 'created_by').order_by('-created_at')
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
    if document_type:
        qs = qs.filter(document_type=document_type)
    batches = list(qs[:30])
    return JsonResponse({
        'batches': [
            {
                'id': b.pk,
                'empresa': b.empresa_id,
                'empresa_nombre': b.empresa.nombre,
                'proyecto': b.proyecto_id or '',
                'document_type': b.document_type,
                'fecha_desde': b.fecha_desde.isoformat(),
                'fecha_hasta': b.fecha_hasta.isoformat(),
                'status': b.status,
                'total_documents': b.total_documents,
                'success_count': b.success_count,
                'error_count': b.error_count,
                'created_by': (getattr(b.created_by, 'username', None) or str(b.created_by)) if b.created_by_id else '',
                'created_at': b.created_at.strftime('%d/%m/%Y %H:%M'),
            }
            for b in batches
        ]
    })


def _payload(request):
    if request.body:
        return json.loads(request.body.decode('utf-8'))
    return request.POST.dict()


def _error_response(exc, status=400):
    detail = str(exc) or repr(exc)
    return JsonResponse({'detail': detail, 'error_type': type(exc).__name__}, status=status)


@login_required
@require_http_methods(['POST'])
def preview(request):
    try:
        payload = _payload(request)
        data = AlegraIntegrationService(user=request.user).preview(
            empresa_id=payload.get('empresa'),
            proyecto_id=payload.get('proyecto'),
            document_type=payload.get('document_type'),
            fecha_desde=payload.get('fecha_desde'),
            fecha_hasta=payload.get('fecha_hasta'),
            caja_id=payload.get('caja_id'),
        )
        return JsonResponse(data)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def send(request):
    try:
        payload = _payload(request)
        data = AlegraIntegrationService(user=request.user).send(
            empresa_id=payload.get('empresa'),
            proyecto_id=payload.get('proyecto'),
            document_type=payload.get('document_type'),
            fecha_desde=payload.get('fecha_desde'),
            fecha_hasta=payload.get('fecha_hasta'),
            caja_id=payload.get('caja_id'),
            retry_failed=payload.get('retry_failed', True),
        )
        return JsonResponse(data)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def batch_delete_previews(request):
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip() or None
        batch_id = payload.get('batch_id')
        if batch_id not in (None, ''):
            batch_id = int(batch_id)
        else:
            batch_id = None
        data = AlegraIntegrationService(user=request.user).delete_preview_batches(
            empresa_id=empresa_id,
            batch_id=batch_id,
        )
        return JsonResponse(data)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def batch_detail(request, batch_id):
    try:
        data = AlegraIntegrationService(user=request.user).batch_detail(batch_id)
        return JsonResponse(data)
    except AlegraSyncBatch.DoesNotExist:
        return JsonResponse({'detail': 'Lote no encontrado'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def batch_send_one(request, batch_id):
    """
    Envía un solo documento del lote (evita timeout de Gunicorn en lotes grandes).
    Repetir hasta complete=true en la respuesta.
    """
    try:
        payload = _payload(request)
        data = AlegraIntegrationService(user=request.user).send_one_batch_document(
            batch_id=batch_id,
            document_id=payload.get('document_id'),
            retry_failed=payload.get('retry_failed', True),
        )
        return JsonResponse(data)
    except AlegraSyncBatch.DoesNotExist:
        return JsonResponse({'detail': 'Lote no encontrado'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def batch_send(request, batch_id):
    """
    Envia un lote existente (ideal para lotes en status=preview) sin reconstruir documentos.
    """
    try:
        payload = _payload(request)
        data = AlegraIntegrationService(user=request.user).send_existing_batch(
            batch_id=batch_id,
            retry_failed=payload.get('retry_failed', True),
        )
        return JsonResponse(data)
    except AlegraSyncBatch.DoesNotExist:
        return JsonResponse({'detail': 'Lote no encontrado'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def contact_sync(request):
    payload = {}
    action = 'start'
    empresa_id = None
    try:
        payload = _payload(request)
        action = payload.get('action') or 'start'
        empresa_id = payload.get('empresa')
        chunk_size = int(payload.get('chunk_size') or 250)
        logger.info(
            'contact_sync request user=%s empresa=%s action=%s chunk_size=%s',
            getattr(request.user, 'pk', None),
            empresa_id,
            action,
            chunk_size,
        )
        data = AlegraIntegrationService(user=request.user).contact_sync_progress(
            empresa_id=empresa_id,
            action=action,
            chunk_size=chunk_size,
        )
        logger.info(
            'contact_sync ok user=%s empresa=%s action=%s status=%s phase=%s stage=%s '
            'alegra_loaded=%s processed=%s/%s',
            getattr(request.user, 'pk', None),
            empresa_id,
            action,
            data.get('status'),
            data.get('phase'),
            data.get('stage'),
            data.get('alegra_loaded'),
            data.get('processed'),
            data.get('total_local'),
        )
        return JsonResponse(data)
    except json.JSONDecodeError:
        logger.warning('contact_sync JSON invalido user=%s', getattr(request.user, 'pk', None))
        return JsonResponse({'detail': 'JSON invalido', 'error_type': 'JSONDecodeError'}, status=400)
    except empresas.DoesNotExist:
        logger.warning('contact_sync empresa no encontrada empresa=%s', empresa_id)
        return JsonResponse({'detail': 'Empresa no encontrada', 'error_type': 'DoesNotExist'}, status=404)
    except AlegraIntegrationError as exc:
        logger.error(
            'contact_sync AlegraIntegrationError user=%s empresa=%s action=%s: %s',
            getattr(request.user, 'pk', None),
            empresa_id,
            action,
            exc,
            exc_info=True,
        )
        return _error_response(exc)
    except Exception as exc:
        logger.exception(
            'contact_sync unexpected error user=%s empresa=%s action=%s payload_keys=%s',
            getattr(request.user, 'pk', None),
            empresa_id,
            action,
            sorted(payload.keys()) if isinstance(payload, dict) else None,
        )
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def contact_link(request):
    """
    Manual link of a local third party to an Alegra contact id.
    """
    try:
        payload = _payload(request)
        empresa_id = (payload.get('empresa') or '').strip()
        local_model = (payload.get('local_model') or '').strip()
        local_pk = (payload.get('local_pk') or '').strip()
        alegra_id = (payload.get('alegra_id') or '').strip()
        name = (payload.get('name') or '').strip()

        if not empresa_id or not local_model or not local_pk or not alegra_id:
            return JsonResponse({'detail': 'empresa, local_model, local_pk y alegra_id son requeridos'}, status=400)

        # Ensure the Alegra contact id is not already linked to a different local third party in this company.
        existing_by_alegra = AlegraMapping.objects.filter(
            empresa_id=empresa_id,
            proyecto__isnull=True,
            mapping_type=AlegraMapping.CONTACT,
            alegra_id=alegra_id,
            active=True,
        ).exclude(local_model=local_model, local_pk=local_pk).first()
        if existing_by_alegra:
            return JsonResponse(
                {'detail': f'El Alegra ID {alegra_id} ya está enlazado a {existing_by_alegra.local_model} pk={existing_by_alegra.local_pk}.'},
                status=409,
            )

        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=None,
            mapping_type=AlegraMapping.CONTACT,
            local_model=local_model,
            local_pk=local_pk,
            local_code='',
            defaults={
                'alegra_id': alegra_id,
                'description': (name or '')[:255],
                'active': True,
            },
        )
        if local_model != 'andinasoft.terceros_raw':
            _mirror_tercero_raw_contact_mapping(
                empresa_id,
                local_pk=local_pk,
                alegra_id=alegra_id,
                name=name or m.description,
            )
        empresa = empresas.objects.get(pk=empresa_id)
        resolved_model, ident, resolved_name, contact_types = _local_third_party_info(local_model, local_pk)
        _upsert_contact_index_for_mapping(
            empresa,
            ident=_contact_index_ident(resolved_model, ident or local_pk),
            alegra_id=alegra_id,
            name=(name or resolved_name or m.description or '')[:255],
            contact_types=contact_types,
        )
        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def contact_link_lookup_local(request):
    """
    Lookup local third party name by pk for confirmation.
    """
    try:
        local_model = (request.GET.get('local_model') or '').strip()
        local_pk = (request.GET.get('local_pk') or '').strip()
        if not local_model or not local_pk:
            return JsonResponse({'detail': 'local_model y local_pk son requeridos'}, status=400)

        if local_model == 'andinasoft.clientes':
            obj = clientes.objects.filter(pk=local_pk).first()
            name = (obj.nombrecompleto if obj else '') or ''
        elif local_model == 'andinasoft.asesores':
            obj = asesores.objects.filter(pk=local_pk).first()
            name = (obj.nombre if obj else '') or ''
        elif local_model == 'andinasoft.empresas':
            obj = empresas.objects.filter(pk=local_pk).first()
            name = (obj.nombre if obj else '') or ''
        elif local_model == 'accounting.partners':
            from accounting.models import Partners
            obj = Partners.objects.filter(pk=local_pk).first()
            name = _partner_display_name(obj) if obj else ''
        elif local_model == 'andinasoft.profiles':
            from andinasoft.models import Profiles
            obj = Profiles.objects.filter(pk=local_pk).first()
            if not obj:
                obj = Profiles.objects.filter(identificacion=local_pk).first()
            name = str(obj) if obj else ''
        elif local_model == 'andinasoft.terceros_raw':
            obj = True
            name = f'NIT/idtercero {local_pk}'
        else:
            return JsonResponse({'detail': f'local_model no soportado: {local_model}'}, status=400)

        if not obj:
            return JsonResponse({'found': False, 'name': ''}, status=404)
        return JsonResponse({'found': True, 'name': name})
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def contact_link_validate_alegra(request):
    """
    Validate an Alegra contact id:
    - not already linked to another local third party in this company
    - fetch and return Alegra contact name for confirmation
    """
    try:
        empresa_id = (request.GET.get('empresa') or '').strip()
        local_model = (request.GET.get('local_model') or '').strip()
        local_pk = (request.GET.get('local_pk') or '').strip()
        alegra_id = (request.GET.get('alegra_id') or '').strip()
        if not empresa_id or not alegra_id:
            return JsonResponse({'detail': 'empresa y alegra_id son requeridos'}, status=400)

        conflict = AlegraMapping.objects.filter(
            empresa_id=empresa_id,
            proyecto__isnull=True,
            mapping_type=AlegraMapping.CONTACT,
            alegra_id=alegra_id,
            active=True,
        ).exclude(local_model=local_model, local_pk=local_pk).first()
        if conflict:
            return JsonResponse(
                {
                    'ok': False,
                    'conflict': True,
                    'conflict_with': {'local_model': conflict.local_model, 'local_pk': conflict.local_pk},
                    'alegra': None,
                },
                status=409,
            )

        empresa = empresas.objects.get(pk=empresa_id)
        client = AlegraMCPClient(empresa)
        alegra_contact = client.rest('GET', f'/contacts/{alegra_id}')
        if not isinstance(alegra_contact, dict):
            return JsonResponse({'detail': 'Respuesta inválida desde Alegra'}, status=502)

        name = alegra_contact.get('name') or alegra_contact.get('businessName') or ''
        ident = alegra_contact.get('identification') or ''
        if isinstance(ident, dict):
            ident = ident.get('number') or ''

        return JsonResponse(
            {
                'ok': True,
                'conflict': False,
                'alegra': {
                    'id': str(alegra_contact.get('id') or alegra_id),
                    'name': name,
                    'identification': str(ident or ''),
                    'type': alegra_contact.get('type'),
                },
            }
        )
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def contacts_bulk_create_from_batch(request):
    """
    Bulk-create missing contacts in Alegra based on preview errors for a given batch.
    """
    try:
        payload = _payload(request)
        batch_id = payload.get('batch_id')
        if not batch_id:
            return JsonResponse({'detail': 'batch_id es requerido'}, status=400)
        data = AlegraIntegrationService(user=request.user).bulk_create_missing_contacts(batch_id=int(batch_id))
        return JsonResponse(data)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['GET'])
def contacts_missing_in_alegra_from_batch(request):
    """
    List third parties referenced by invalid docs (missing contact mapping) that do not exist in Alegra yet.
    Useful to ask the user to create them first (no duplicates).
    """
    try:
        batch_id = (request.GET.get('batch_id') or '').strip()
        if not batch_id:
            return JsonResponse({'detail': 'batch_id es requerido'}, status=400)
        data = AlegraIntegrationService(user=request.user).contacts_missing_in_alegra(batch_id=int(batch_id))
        return JsonResponse(data)
    except Exception as exc:
        return _error_response(exc, status=500)


@login_required
@require_http_methods(['POST'])
def reference_sync(request):
    try:
        payload = _payload(request)
        data = AlegraIntegrationService(user=request.user).reference_sync(
            empresa_id=payload.get('empresa')
        )
        return JsonResponse(data)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'JSON invalido'}, status=400)
    except empresas.DoesNotExist:
        return JsonResponse({'detail': 'Empresa no encontrada'}, status=404)
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)
