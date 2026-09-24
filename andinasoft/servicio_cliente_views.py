"""Vistas internas de servicio al cliente: dashboard, ficha, PQRS y hitos."""
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from andina.decorators import check_perms, check_project, group_perm_required
from andinasoft.handlers_functions import upload_docs_contratos
from andinasoft.pqrs_service import (
    TIPOS_PQRS,
    agregar_nota,
    cerrar_pqrs,
    fecha_vencimiento_sugerida,
    ficha_pqrs,
    listar_pqrs,
    marcar_juridica,
    radicar_pqrs,
)
from andinasoft.promesas_service import (
    PASO_LABEL,
    marcar_entrega,
    marcar_hito_escritura,
    nombre_documento_paso,
    paso_index,
    registrar_fechas_firmadas,
    registrar_otrosi,
)
from andinasoft.servicio_cliente_service import dashboard_sac, ficha_cliente, url_ficha
from andinasoft.shared_models import documentos_contratos


def _can_sac(user):
    if user.is_superuser:
        return True
    return user.has_perm('andinasoft.view_pqrs') or user.has_perm('crm.view_actareunion')


def _require_sac(request):
    if not request.user.is_authenticated:
        raise PermissionDenied
    if not _can_sac(request.user):
        raise PermissionDenied


@login_required
def sac_dashboard(request):
    _require_sac(request)
    proyecto = request.GET.get('proyecto') or ''
    tipo = request.GET.get('tipo') or ''
    data = dashboard_sac(request.user, proyecto=proyecto or None, tipo=tipo or None)
    return render(request, 'servicio_cliente/dashboard.html', data)


@login_required
def sac_ficha_cliente(request, cliente_id):
    _require_sac(request)
    proyecto = request.GET.get('proyecto') or None
    adj = request.GET.get('adj') or None
    data = ficha_cliente(cliente_id, request.user, proyecto=proyecto, adj=adj)
    if not data:
        raise Http404('Cliente no encontrado')
    return render(request, 'servicio_cliente/ficha_cliente.html', data)


@group_perm_required(('andinasoft.view_pqrs',), raise_exception=True)
def pqrs_lista(request, proyecto):
    check_project(request, proyecto)
    filtros = {
        'estado': request.GET.get('estado', ''),
        'tipo': request.GET.get('tipo', ''),
        'vencimiento': request.GET.get('vencimiento', ''),
        'q': request.GET.get('q', ''),
        'juridica': request.GET.get('juridica', ''),
    }
    rows, kpis = listar_pqrs(
        proyecto,
        estado=filtros['estado'],
        tipo=filtros['tipo'],
        vencimiento=filtros['vencimiento'],
        q=filtros['q'],
        juridica=bool(filtros['juridica']),
    )
    return render(request, 'servicio_cliente/pqrs_lista.html', {
        'proyecto': proyecto,
        'rows': rows,
        'kpis': kpis,
        'filtros': filtros,
        'tipos': TIPOS_PQRS,
        'today': timezone.localdate(),
        'fecha_ven_sugerida': fecha_vencimiento_sugerida(timezone.localdate()),
    })


@group_perm_required(('andinasoft.view_pqrs',), raise_exception=True)
def pqrs_detalle(request, proyecto, radicado_id):
    check_project(request, proyecto)
    try:
        row = ficha_pqrs(proyecto, radicado_id)
    except Exception:
        raise Http404('Radicado no encontrado')
    if request.method == 'POST':
        if request.POST.get('agregar_nota'):
            check_perms(request, ('andinasoft.change_pqrs',))
            try:
                agregar_nota(proyecto, radicado_id, request.user, request.POST.get('comentario'))
                messages.success(request, 'Nota agregada.')
            except ValueError as exc:
                messages.error(request, str(exc))
            return HttpResponseRedirect(f'/servicio_cliente/pqrs/{proyecto}/{radicado_id}')
        if request.POST.get('marcar_juridica'):
            check_perms(request, ('andinasoft.change_pqrs',))
            marcar_juridica(
                proyecto, radicado_id,
                request.POST.get('relevante') == '1',
                usuario=request.user,
            )
            messages.success(request, 'Marcacion juridica actualizada.')
            return HttpResponseRedirect(f'/servicio_cliente/pqrs/{proyecto}/{radicado_id}')
        if request.POST.get('cerrar_pqrs'):
            check_perms(request, ('andinasoft.change_pqrs',))
            try:
                cerrar_pqrs(
                    proyecto,
                    radicado_id,
                    fecha_respuesta=request.POST.get('fecha_respuesta'),
                    medio=request.POST.get('forma_respuesta'),
                    archivo_respuesta=request.FILES.get('respuesta'),
                    archivo_envio=request.FILES.get('envio'),
                    usuario=request.user,
                    resumen_respuesta=request.POST.get('resumen_respuesta'),
                )
                messages.success(request, f'PQRS #{radicado_id} cerrada.')
            except ValueError as exc:
                messages.error(request, str(exc))
            return HttpResponseRedirect(f'/servicio_cliente/pqrs/{proyecto}/{radicado_id}')
    return render(request, 'servicio_cliente/pqrs_detalle.html', {
        'proyecto': proyecto,
        'row': row,
        'ficha_url': url_ficha(row.get('cliente_id'), proyecto, row.get('adj')),
        'today': timezone.localdate(),
    })


@group_perm_required(('andinasoft.add_pqrs',), raise_exception=True)
def pqrs_radicar(request, proyecto):
    check_project(request, proyecto)
    adj = request.GET.get('adj') or request.POST.get('adj') or ''
    if request.method == 'POST':
        try:
            rad, _gestion = radicar_pqrs(
                proyecto,
                adj,
                tipo=request.POST.get('tipo'),
                asunto=request.POST.get('asunto'),
                fecha_rad=request.POST.get('fecha_recibido'),
                fecha_ven=request.POST.get('fecha_vencimiento'),
                req_respuesta=request.POST.get('req_respuesta') or 'Si',
                archivo=request.FILES.get('peticion'),
                usuario=request.user,
                canal=request.POST.get('canal') or '',
                relevante_juridica=request.POST.get('relevante_juridica') == 'on',
                resumen=request.POST.get('resumen') or '',
                origen='interno',
            )
            messages.success(request, f'Radicado #{rad.pk} creado.')
            return HttpResponseRedirect(f'/servicio_cliente/pqrs/{proyecto}/{rad.pk}')
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, 'servicio_cliente/pqrs_radicar.html', {
        'proyecto': proyecto,
        'adj': adj,
        'tipos': TIPOS_PQRS,
        'today': timezone.localdate(),
        'fecha_ven_sugerida': fecha_vencimiento_sugerida(timezone.localdate()),
    })


@login_required
@require_POST
def marcar_hito_view(request, proyecto, adj):
    check_project(request, proyecto)
    check_perms(request, ('andinasoft.change_promesas',))
    paso = request.POST.get('paso')
    fecha = request.POST.get('fecha')
    nota = request.POST.get('nota') or ''
    archivo = request.FILES.get('documento')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or f'/operaciones/promesas/{proyecto}'
    try:
        doc_name = nombre_documento_paso(paso, archivo)
    except ValueError as exc:
        messages.error(request, str(exc))
        if request.is_ajax() or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'passed': False, 'msj': str(exc)}, status=400)
        return HttpResponseRedirect(next_url)
    if doc_name:
        upload_docs_contratos(archivo, adj, proyecto, doc_name)
        documentos_contratos.objects.using(proyecto).create(
            adj=adj, descripcion_doc=doc_name,
            fecha_carga=str(datetime.datetime.today()), usuario_carga=str(request.user),
        )
    try:
        marcar_hito_escritura(
            proyecto, adj, paso, fecha, request.user,
            nota=nota,
            documento=doc_name,
            es_superuser=request.user.is_superuser,
        )
    except ValueError as exc:
        if request.is_ajax() or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'passed': False, 'msj': str(exc)}, status=400)
        messages.error(request, str(exc))
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or f'/operaciones/promesas/{proyecto}'
        return HttpResponseRedirect(next_url)
    messages.success(request, f'Paso {PASO_LABEL.get(paso, paso)} registrado.')
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or f'/operaciones/promesas/{proyecto}'
    if request.is_ajax() or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'passed': True, 'msj': 'Paso registrado', 'paso': paso, 'paso_idx': paso_index(paso)})
    return HttpResponseRedirect(next_url)


def _next_ficha(request, proyecto):
    return request.POST.get('next') or request.META.get('HTTP_REFERER') or (
        '/operaciones/promesas/%s' % proyecto
    )


def _guardar_pdf_contrato(archivo, adj, proyecto, usuario, prefijo, *, requerido=False):
    if not archivo:
        if requerido:
            raise ValueError('Cargue el PDF de %s.' % prefijo.lower())
        return ''
    if not str(archivo.name).lower().endswith('.pdf'):
        raise ValueError('%s debe ser PDF.' % prefijo)
    doc_name = '%s_%s' % (prefijo, datetime.datetime.today())
    upload_docs_contratos(archivo, adj, proyecto, doc_name)
    documentos_contratos.objects.using(proyecto).create(
        adj=adj, descripcion_doc=doc_name,
        fecha_carga=str(datetime.datetime.today()), usuario_carga=str(usuario),
    )
    return doc_name


@login_required
@require_POST
def actualizar_promesa_view(request, proyecto, adj):
    check_project(request, proyecto)
    check_perms(request, ('andinasoft.change_promesas',))
    accion = request.POST.get('accion')
    next_url = _next_ficha(request, proyecto)
    try:
        if accion == 'fechas':
            registrar_fechas_firmadas(
                proyecto, adj,
                request.POST.get('fecha_promesa'),
                request.POST.get('fecha_entrega'),
                request.POST.get('fecha_escritura'),
                request.user,
            )
            messages.success(request, 'Fechas pactadas registradas.')
        elif accion == 'entrega':
            entregado = request.POST.get('entregado') in ('true', 'True', '1', 'on')
            doc_name = _guardar_pdf_contrato(
                request.FILES.get('documento'), adj, proyecto, request.user,
                'Acta de entrega',
            )
            marcar_entrega(
                proyecto, adj, entregado, request.POST.get('fecha_entrega_real'),
                request.user, documento=doc_name,
            )
            messages.success(request, 'Estado de entrega actualizado.')
        elif accion == 'otrosi':
            doc_name = _guardar_pdf_contrato(
                request.FILES.get('documento'), adj, proyecto, request.user,
                'Otrosi', requerido=True,
            )
            registrar_otrosi(
                proyecto, adj, request.POST.get('tipo_otrosi'), request.user,
                fecha_entrega_nueva=request.POST.get('fecha_entrega_nueva'),
                fecha_escritura_nueva=request.POST.get('fecha_escritura_nueva'),
                observaciones=request.POST.get('observaciones') or '',
                documento=doc_name,
            )
            messages.success(request, 'Otrosi registrado.')
        else:
            raise ValueError('Accion no reconocida.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return HttpResponseRedirect(next_url)
