import json

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
from alegra_integration.services import AlegraIntegrationService, ALEGRA_WEBHOOK_BILLS_INGEST_SUFFIX, ALEGRA_WEBHOOK_EVENTS
from andinasoft.models import cuentas_pagos, empresas, proyectos, clientes, asesores
from accounting.models import cuentas_intercompanias, info_interfaces
from alegra_integration.mapping import MappingResolver
from alegra_integration.client import AlegraMCPClient
from alegra_integration.webhook_bills import process_inbound_post


@login_required
def dashboard(request):
    return render(request, 'alegra_integration/dashboard.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
        'proyectos': proyectos.objects.filter(activo=True).order_by('proyecto'),
    })


@login_required
@require_http_methods(['GET'])
def webhooks_console(request):
    empresa_id = (request.GET.get('empresa') or '').strip()
    logs = []
    if empresa_id:
        logs = list(
            AlegraWebhookSubscriptionLog.objects.filter(empresa_id=empresa_id)
            .order_by('-created_at')[:40]
        )
    inbound_logs = list(AlegraWebhookInboundLog.objects.order_by('-created_at')[:30])
    return render(request, 'alegra_integration/webhooks.html', {
        'empresas': empresas.objects.filter(alegra_enabled=True).order_by('nombre'),
        'webhook_ingest_suffix': ALEGRA_WEBHOOK_BILLS_INGEST_SUFFIX,
        'webhook_events': sorted(ALEGRA_WEBHOOK_EVENTS),
        'selected_empresa': empresa_id,
        'initial_logs': logs,
        'inbound_logs': inbound_logs,
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


def _persist_alegra_webhook_inbound(request):
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

    AlegraWebhookInboundLog.objects.create(
        http_method=(request.method or '')[:16],
        content_type=(request.META.get('CONTENT_TYPE') or '')[:255],
        remote_addr=remote,
        query_string=(request.META.get('QUERY_STRING') or '')[:5000],
        payload=payload,
        raw_body=raw_store if payload.get('_json_parse_error') else '',
    )
    return payload


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
    payload = _persist_alegra_webhook_inbound(request)
    # Prefer querystring, fallback to path param (más robusto: algunos deliveries descartan query params).
    empresa_qs = (request.GET.get('empresa') or '').strip() or (str(empresa_id or '').strip())
    extra = process_inbound_post(empresa_qs, payload)
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

        data = AlegraIntegrationService(user=request.user).reference_sync(empresa_id=empresa_id)

        # Allow fetching individual reference groups.
        if ref_type in ('banks', 'categories', 'cost_centers'):
            return JsonResponse({ref_type: data.get(ref_type, [])})
        if ref_type in ('journal_numerations', 'journal_numeration', 'journals_numerations'):
            return JsonResponse({'journal_numerations': data.get('journal_numerations', [])})
        if ref_type in ('number_templates', 'numerations', 'numeration'):
            return JsonResponse({'number_templates': data.get('number_templates', {})})

        return JsonResponse(data)
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

        qs = AlegraMapping.objects.filter(empresa_id=empresa_id).order_by('mapping_type', 'local_model', 'local_pk', 'local_code')
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


@login_required
@require_http_methods(['POST'])
def references_save_bank_mapping(request):
    try:
        payload = _payload(request)
        empresa_id = payload.get('empresa')
        local_idcuenta = payload.get('local_idcuenta')
        alegra_id = payload.get('alegra_id')

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

        # Best-effort: if this Alegra bank account has an associated ledger category,
        # auto-create a CATEGORY mapping for the local accounting code (nro_cuentacontable).
        auto_category = None
        if getattr(cuenta, 'nro_cuentacontable', None):
            try:
                empresa = empresas.objects.get(pk=empresa_id)
                client = AlegraMCPClient(empresa)
                bank_detail = client.rest('GET', f'/bank-accounts/{alegra_id}?fields=category')
                if isinstance(bank_detail, dict):
                    cat = bank_detail.get('category') or {}
                    cat_id = cat.get('id') if isinstance(cat, dict) else None
                    if cat_id:
                        AlegraMapping.objects.update_or_create(
                            empresa_id=empresa_id,
                            proyecto=None,
                            mapping_type=AlegraMapping.CATEGORY,
                            local_model='',
                            local_pk='',
                            local_code=str(cuenta.nro_cuentacontable),
                            defaults={
                                'alegra_id': str(cat_id),
                                'description': (cat.get('name') or f'bank category {cuenta.nro_cuentacontable}')[:255],
                                'active': True,
                                'alegra_payload': {'source': 'bank_account', 'bank_account_id': str(alegra_id)},
                            },
                        )
                        auto_category = {'local_code': str(cuenta.nro_cuentacontable), 'alegra_category_id': str(cat_id)}
            except Exception:
                # Don't block saving bank mapping if auto-category fails
                auto_category = None

        return JsonResponse({'ok': True, 'created': created, 'mapping_id': m.pk, 'auto_category': auto_category})
    except AlegraIntegrationError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc, status=500)


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
        m, created = AlegraMapping.objects.update_or_create(
            empresa_id=empresa_id,
            proyecto=proyecto,
            mapping_type=AlegraMapping.CATEGORY,
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
    qs = AlegraSyncBatch.objects.select_related('empresa', 'proyecto', 'created_by').order_by('-created_at')
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)
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
    return JsonResponse({'detail': str(exc)}, status=status)


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
def contact_sync(request):
    try:
        payload = _payload(request)
        action = payload.get('action') or 'start'
        data = AlegraIntegrationService(user=request.user).contact_sync_progress(
            empresa_id=payload.get('empresa'),
            action=action,
            chunk_size=int(payload.get('chunk_size') or 250),
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
        elif local_model == 'andinasoft.terceros_raw':
            # For cases where we only have an external/local id in documents (no dedicated local table).
            obj = True
            name = ''
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
