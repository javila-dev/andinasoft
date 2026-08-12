"""Vistas: integraciones LLM + extraccion de fechas desde PDF."""
from __future__ import annotations

import datetime
import os

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from andina.decorators import group_perm_required
from andinasoft.documento_fechas_service import (
    DOCS_DESDE_DEFAULT,
    analyze_adj,
    analyze_adj_cascade_step,
    export_excel,
    list_adj_candidates,
    list_cascade_credentials,
    list_docs_adj,
    serialize_row_dates,
)
from andinasoft.llm_client import list_saved_model_options
from andinasoft.models import (
    AdjFechaDocumentoExtraccion,
    IntegrationCredential,
    IntegrationPurposeMapping,
)


def _check_perms(request, perms, raise_exception=True):
    from andinasoft.views import check_perms
    return check_perms(request, perms, raise_exception=raise_exception)


def _check_project(request, proyecto, raise_exception=True):
    from andinasoft.views import check_project
    return check_project(request, proyecto, raise_exception=raise_exception)


def _superuser_required(request):
    from django.core.exceptions import PermissionDenied

    if not request.user.is_superuser:
        raise PermissionDenied('Solo superusuario')
    return True


@login_required
@require_http_methods(['GET', 'POST'])
def integraciones_llm(request):
    _superuser_required(request)
    mensaje = None
    error = None

    if request.method == 'POST':
        action = request.POST.get('action')
        try:
            if action == 'save_credential':
                cred_id = request.POST.get('cred_id')
                provider = (request.POST.get('provider') or '').strip()
                label = (request.POST.get('label') or '').strip()
                default_model = (request.POST.get('default_model') or '').strip()
                api_key = (request.POST.get('api_key') or '').strip()
                activo = request.POST.get('activo') in ('1', 'on', 'true', 'True')
                if provider not in dict(IntegrationCredential.PROVIDER_CHOICES):
                    raise ValueError('Proveedor no valido')
                if cred_id:
                    cred = get_object_or_404(IntegrationCredential, pk=int(cred_id))
                    cred.provider = provider
                    cred.label = label
                    cred.default_model = default_model
                    cred.activo = activo
                    if api_key:
                        cred.api_key = api_key
                    cred.save()
                    mensaje = 'Credencial actualizada'
                else:
                    if not api_key:
                        raise ValueError('La API key es obligatoria al crear')
                    IntegrationCredential.objects.create(
                        provider=provider,
                        label=label,
                        default_model=default_model,
                        api_key=api_key,
                        activo=activo,
                    )
                    mensaje = 'Credencial creada'
            elif action == 'delete_credential':
                cred_id = int(request.POST.get('cred_id'))
                IntegrationCredential.objects.filter(pk=cred_id).delete()
                mensaje = 'Credencial eliminada'
            elif action == 'save_purpose':
                purpose = (request.POST.get('purpose') or '').strip()
                if purpose not in dict(IntegrationPurposeMapping.PURPOSE_CHOICES):
                    raise ValueError('Uso no valido')
                cred_raw = request.POST.get('credential_id') or ''
                model_override = (request.POST.get('model_override') or '').strip()
                cred = None
                if cred_raw:
                    cred = get_object_or_404(IntegrationCredential, pk=int(cred_raw))
                IntegrationPurposeMapping.objects.update_or_create(
                    purpose=purpose,
                    defaults={
                        'credential': cred,
                        'model_override': model_override,
                    },
                )
                mensaje = 'Uso de integracion guardado'
        except Exception as exc:
            error = str(exc)

    credentials = list(IntegrationCredential.objects.all())
    purposes = list(IntegrationPurposeMapping.PURPOSE_CHOICES)
    mappings = {
        m.purpose: m
        for m in IntegrationPurposeMapping.objects.select_related('credential').all()
    }
    purpose_rows = []
    for code, label in purposes:
        purpose_rows.append({
            'code': code,
            'label': label,
            'mapping': mappings.get(code),
        })

    from andinasoft.llm_models_catalog import DEFAULT_MODELS, catalog_as_dict

    return render(request, 'integraciones_llm.html', {
        'credentials': credentials,
        'purpose_rows': purpose_rows,
        'provider_choices': IntegrationCredential.PROVIDER_CHOICES,
        'models_catalog': catalog_as_dict(),
        'default_models': DEFAULT_MODELS,
        'mensaje': mensaje,
        'error': error,
    })


def _parse_docs_desde(raw: str) -> datetime.date:
    raw = (raw or '').strip()
    if not raw:
        return DOCS_DESDE_DEFAULT
    try:
        return datetime.date.fromisoformat(raw[:10])
    except ValueError:
        return DOCS_DESDE_DEFAULT


@login_required
@group_perm_required(('andinasoft.view_promesas',), raise_exception=True)
@require_http_methods(['GET', 'POST'])
def extraccion_fechas_documentos(request, proyecto):
    _check_project(request, proyecto)

    if request.method == 'POST' and (
        request.is_ajax() or request.headers.get('x-requested-with') == 'XMLHttpRequest'
    ):
        _check_perms(request, ('andinasoft.change_promesas',), raise_exception=True)
        action = request.POST.get('action') or 'analyze'
        docs_desde = _parse_docs_desde(request.POST.get('docs_desde'))
        force = request.POST.get('force') in ('1', 'true', 'on', 'True')
        resync = request.POST.get('resync_promesas') in ('1', 'true', 'on', 'True')
        overwrite = request.POST.get('overwrite_promesas') in ('1', 'true', 'on', 'True')

        if action == 'list_docs':
            adj = (request.POST.get('adj') or '').strip()
            if not adj:
                return JsonResponse({'passed': False, 'msj': 'Falta ADJ'}, status=400)
            # Modal: mostrar todos los PDF relevantes del ADJ (sin filtro docs_desde)
            docs = list_docs_adj(
                proyecto, adj,
                docs_desde=docs_desde,
                aplicar_filtro_fecha=False,
            )
            return JsonResponse({'passed': True, 'adj': adj, 'documentos': docs})

        if action == 'list_batch_adjs':
            # Solo lista ADJs (sin LLM). El cliente analiza 1 por request en serie.
            mode = request.POST.get('mode') or 'selected'
            if mode == 'filtered':
                rows = list_adj_candidates(
                    proyecto,
                    inmueble_contains=request.POST.get('inmueble_contains') or '',
                    adj_query=request.POST.get('adj_query') or '',
                    titular_query=request.POST.get('titular_query') or '',
                    estado_extraccion=request.POST.get('estado_extraccion') or '',
                    solo_pendientes=request.POST.get('solo_pendientes') in ('1', 'true', 'on'),
                )
                adj_list = [r['adj'] for r in rows]
            else:
                adj_list = request.POST.getlist('adj')
            adj_list = [a.strip() for a in adj_list if a and str(a).strip()]
            return JsonResponse({'passed': True, 'adjs': adj_list, 'total': len(adj_list)})

        if action in ('analyze_one', 'analyze_cascade_step'):
            adj = (request.POST.get('adj') or '').strip()
            if not adj:
                return JsonResponse({'passed': False, 'msj': 'Falta ADJ'}, status=400)
            cred_raw = (request.POST.get('credential_id') or '').strip()
            model_override = (request.POST.get('model_override') or '').strip()
            credential_id = int(cred_raw) if cred_raw.isdigit() else None
            try:
                if action == 'analyze_cascade_step':
                    provider = (request.POST.get('provider') or '').strip().lower()
                    if not provider:
                        return JsonResponse({'passed': False, 'msj': 'Falta provider'}, status=400)
                    result = analyze_adj_cascade_step(
                        proyecto, adj,
                        provider=provider,
                        docs_desde=docs_desde,
                        force=force,
                        resync_promesas=resync,
                        overwrite_promesas=overwrite,
                        cascade_reset=request.POST.get('cascade_reset') in ('1', 'true', 'on', 'True'),
                        credential_id=credential_id,
                        model_override=model_override,
                    )
                else:
                    result = analyze_adj(
                        proyecto, adj,
                        docs_desde=docs_desde,
                        force=force,
                        resync_promesas=resync,
                        overwrite_promesas=overwrite,
                        credential_id=credential_id,
                        model_override=model_override,
                    )
            except Exception as exc:
                err = str(exc)[:1000]
                AdjFechaDocumentoExtraccion.objects.update_or_create(
                    proyecto_id=proyecto,
                    adj=adj,
                    defaults={
                        'estado': AdjFechaDocumentoExtraccion.ESTADO_ERROR,
                        'error_msg': err,
                    },
                )
                # passed=True para que el lote marque la fila y continue con la siguiente
                return JsonResponse({
                    'passed': True,
                    'result': serialize_row_dates({
                        'adj': adj,
                        'skipped': False,
                        'estado': AdjFechaDocumentoExtraccion.ESTADO_ERROR,
                        'fecha_contrato': None,
                        'fecha_escritura': None,
                        'fecha_entrega': None,
                        'documento_usado': '',
                        'documento_url': '',
                        'error_msg': err,
                        'provider': '',
                        'model': '',
                        'cascade_complete': False,
                    }),
                })
            return JsonResponse({'passed': True, 'result': serialize_row_dates(result)})

        if action == 'analyze_batch':
            # Compat: un solo ADJ por request (evitar timeout de workers en prod).
            # El UI moderno usa list_batch_adjs + analyze_one en serie.
            adj_list = [a.strip() for a in request.POST.getlist('adj') if a and a.strip()]
            if not adj_list:
                return JsonResponse({'passed': False, 'msj': 'Falta ADJ'}, status=400)
            adj = adj_list[0]
            try:
                result = serialize_row_dates(analyze_adj(
                    proyecto, adj,
                    docs_desde=docs_desde,
                    force=force,
                    resync_promesas=resync,
                    overwrite_promesas=overwrite,
                ))
            except Exception as exc:
                err = str(exc)[:1000]
                AdjFechaDocumentoExtraccion.objects.update_or_create(
                    proyecto_id=proyecto,
                    adj=adj,
                    defaults={
                        'estado': AdjFechaDocumentoExtraccion.ESTADO_ERROR,
                        'error_msg': err,
                    },
                )
                result = {
                    'adj': adj,
                    'estado': AdjFechaDocumentoExtraccion.ESTADO_ERROR,
                    'error_msg': err,
                }
            return JsonResponse({
                'passed': True,
                'processed': 1,
                'remaining': max(0, len(adj_list) - 1),
                'results': [result],
            })

        return JsonResponse({'passed': False, 'msj': 'Accion no valida'}, status=400)

    inmueble_contains = request.GET.get('inmueble_contains') or ''
    adj_query = request.GET.get('adj_query') or ''
    titular_query = request.GET.get('titular_query') or ''
    estado_extraccion = request.GET.get('estado_extraccion') or ''
    solo_pendientes = request.GET.get('solo_pendientes') in ('1', 'on', 'true')
    docs_desde_raw = request.GET.get('docs_desde') or DOCS_DESDE_DEFAULT.isoformat()
    docs_desde = _parse_docs_desde(docs_desde_raw)

    rows = list_adj_candidates(
        proyecto,
        inmueble_contains=inmueble_contains,
        adj_query=adj_query,
        titular_query=titular_query,
        estado_extraccion=estado_extraccion,
        solo_pendientes=solo_pendientes,
    )

    if request.GET.get('export') == '1':
        ruta = export_excel(proyecto, rows)
        return FileResponse(
            open(ruta, 'rb'),
            as_attachment=True,
            filename=os.path.basename(ruta),
        )

    return render(request, 'extraccion_fechas_documentos.html', {
        'proyecto': proyecto,
        'rows': rows,
        'filters': {
            'inmueble_contains': inmueble_contains,
            'adj_query': adj_query,
            'titular_query': titular_query,
            'estado_extraccion': estado_extraccion,
            'solo_pendientes': solo_pendientes,
            'docs_desde': docs_desde.isoformat(),
        },
        'estado_choices': AdjFechaDocumentoExtraccion.ESTADO_CHOICES,
        'total': len(rows),
        'saved_models': list_saved_model_options(),
        'cascade_credentials': list_cascade_credentials(),
    })
