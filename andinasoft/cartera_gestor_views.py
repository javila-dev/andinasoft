"""Vistas del dashboard de gestores de cobro y linea de tiempo por cliente."""
from __future__ import annotations

import datetime
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_date

from andina.decorators import check_project, group_perm_required
from andinasoft.cartera_gestor_service import (
    GESTOR_JURIDICO,
    asignar_gestor,
    asignar_gestor_bulk,
    build_carta_context,
    cerrar_compromiso,
    crear_seguimiento,
    dashboard_payload_all,
    guardar_config_cartas,
    listar_config_cartas,
    eliminar_compromiso,
    filter_snapshot_for_gestor,
    is_supervisor_cartera,
    label_periodo_presupuesto,
    listado_asignaciones,
    listar_gestores_opciones,
    registrar_envio_carta,
    registrar_generacion_carta,
    resolver_plantilla_carta,
    timeline_payload,
    ultimo_periodo_presupuesto,
)
from andinasoft.edades_cartera_service import edades_cartera_snapshot
from andinasoft.estado_cuenta_service import build_estado_cuenta_context
from andinasoft.forms import form_seguimiento
from andinasoft.models import CarteraCartaEnvio, CarteraCheckpoint
from andinasoft.presupuesto_cartera_service import proyectos_accesibles
from andinasoft.promesa_pdf import ConfigDocumentoInvalida, generar_documento_pdf_directo
from andinasoft.utilities import file_response_from_pdf_root, pdf_gen


def _assert_adj_visible(request, proyecto, adj):
    """Gestor solo puede ver ADJs de su cartera; supervisor/admin todos."""
    if is_supervisor_cartera(request.user):
        return
    adjudicaciones, _ = edades_cartera_snapshot(proyecto)
    rows = filter_snapshot_for_gestor(adjudicaciones, request.user)
    if not any(r.get('adj') == adj for r in rows):
        raise PermissionDenied


@login_required
@group_perm_required(perms=('andinasoft.view_presupuestocartera',), raise_exception=True)
def cartera_dashboard(request, proyecto=None):
    """Dashboard integrado; filtros ?proyecto= y ?edad= (bucket)."""
    if proyecto:
        qs = request.GET.urlencode()
        target = f'/cartera/dashboard?proyecto={proyecto}'
        if qs:
            # preservar otros query params si venian en redirect raro
            from urllib.parse import parse_qs, urlencode
            extra = {k: v[0] for k, v in parse_qs(qs).items() if k != 'proyecto'}
            if extra:
                target += '&' + urlencode(extra)
        return HttpResponseRedirect(target)

    filtro = (request.GET.get('proyecto') or '').strip() or None
    edad = (request.GET.get('edad') or '').strip() or None
    data = dashboard_payload_all(
        request.user,
        proyecto_filtro=filtro,
        bucket_filtro=edad,
    )
    proyecto_ctx = data.get('proyecto_filtro')
    context = {
        'proyecto': proyecto_ctx,
        'proyecto_filtro': proyecto_ctx,
        'bucket_filtro': data.get('bucket_filtro'),
        'proyectos_badges': data['proyectos_badges'],
        'periodo': data['fecha_consulta'].strftime('%d/%m/%Y'),
        'es_supervisor': data['es_supervisor'],
        'gestor_nombre': data['gestor_nombre'],
        'kpis': data['kpis'],
        'rows': data['rows'],
        'periodo_ppto': data['periodo_ppto'],
        'buckets': data['buckets'],
        'distribucion_lista': data['distribucion_lista'],
        'compromisos_preview': data['compromisos_preview'],
        'compromisos_all': data['compromisos_all'],
        'compromisos_total': data['compromisos_total'],
        'compromisos_hoy': data['compromisos_hoy'],
        'compromisos_vencidos': data['compromisos_vencidos'],
        'fechas_pactadas_preview': data['fechas_pactadas_preview'],
        'fechas_pactadas_all': data['fechas_pactadas_all'],
        'fechas_pactadas_total': data['fechas_pactadas_total'],
        'fechas_pactadas_hoy': data['fechas_pactadas_hoy'],
        'fechas_pactadas_vencidos': data['fechas_pactadas_vencidos'],
        'cobrar_hoy_preview': data['cobrar_hoy_preview'],
        'cobrar_hoy_all': data['cobrar_hoy_all'],
        'cobrar_hoy_total': data['cobrar_hoy_total'],
        'en_mora_preview': data['en_mora_preview'],
        'en_mora_all': data['en_mora_all'],
        'en_mora_total': data['en_mora_total'],
    }
    return render(request, 'cartera/dashboard.html', context)


@login_required
@group_perm_required(perms=('andinasoft.view_presupuestocartera',), raise_exception=True)
def cartera_linea_tiempo(request, proyecto, adj):
    check_project(request, proyecto)
    _assert_adj_visible(request, proyecto, adj)

    alerta = False
    titulo = None
    mensaje = None

    if request.method == 'POST' and request.POST.get('agregarSeguimiento'):
        form = form_seguimiento(request.POST)
        if form.is_valid():
            crear_seguimiento(proyecto, adj, request.user, form.cleaned_data)
            return HttpResponseRedirect(request.path)
        alerta = True
        titulo = 'Error'
        mensaje = 'Revisa los datos del seguimiento.'
    elif request.method == 'POST' and request.POST.get('cerrarCompromiso'):
        form = form_seguimiento()
        try:
            cerrar_compromiso(proyecto, adj, request.POST.get('id_seg'), request.user)
            return HttpResponseRedirect(request.path)
        except (ValueError, TypeError) as exc:
            alerta = True
            titulo = 'Error'
            mensaje = str(exc) or 'No se pudo cerrar el compromiso.'
    elif request.method == 'POST' and request.POST.get('eliminarCompromiso'):
        form = form_seguimiento()
        try:
            eliminar_compromiso(proyecto, adj, request.POST.get('id_seg'), request.user)
            return HttpResponseRedirect(request.path)
        except (ValueError, TypeError) as exc:
            alerta = True
            titulo = 'Error'
            mensaje = str(exc) or 'No se pudo eliminar el compromiso.'
    elif request.method == 'POST' and request.POST.get('cargarSoporteCarta'):
        form = form_seguimiento()
        checkpoint_id = request.POST.get('checkpoint_id')
        soporte = request.FILES.get('soporte')
        canal = (request.POST.get('canal') or CarteraCartaEnvio.CANAL_WHATSAPP).strip()
        fecha_raw = (request.POST.get('fecha_envio') or '').strip()
        fecha_envio = parse_date(fecha_raw) or datetime.date.today()
        notas = (request.POST.get('notas') or '').strip()
        try:
            checkpoint = CarteraCheckpoint.objects.get(
                pk=checkpoint_id, proyecto_id=proyecto, activo=True,
            )
        except (CarteraCheckpoint.DoesNotExist, ValueError, TypeError):
            checkpoint = None
        if not checkpoint or not soporte:
            alerta = True
            titulo = 'Error'
            mensaje = 'Debes elegir checkpoint y adjuntar el soporte.'
        else:
            payload_tmp = timeline_payload(proyecto, adj)
            if payload_tmp is None or not checkpoint.alcanzado(payload_tmp['dias_mora']):
                alerta = True
                titulo = 'Error'
                mensaje = 'El cliente aun no alcanza este checkpoint.'
            else:
                registrar_envio_carta(
                    proyecto,
                    adj,
                    checkpoint,
                    request.user,
                    canal=canal,
                    fecha_envio=fecha_envio,
                    soporte=soporte,
                    notas=notas,
                )
                return HttpResponseRedirect(request.path)
    else:
        form = form_seguimiento()

    payload = timeline_payload(proyecto, adj)
    if payload is None:
        raise Http404('Adjudicacion no encontrada en edades de cartera')

    context = {
        'proyecto': proyecto,
        'adj': adj,
        'row': payload['row'],
        'periodo': payload['fecha_consulta'].strftime('%d/%m/%Y'),
        'dias_mora': payload['dias_mora'],
        'bucket_activo': payload['bucket_activo'],
        'visual_nodes': payload['visual_nodes'],
        'carta_nodes': payload['carta_nodes'],
        'seguimientos': payload['seguimientos'],
        'compromiso_activo': payload.get('compromiso_activo'),
        'titular': payload.get('titular'),
        'otros_titulares': payload.get('otros_titulares') or [],
        'canales_envio': payload.get('canales_envio') or CarteraCartaEnvio.CANAL_CHOICES,
        'deuda': payload.get('deuda') or {},
        'comportamiento': payload.get('comportamiento') or {},
        'comportamiento_json': json.dumps(payload.get('comportamiento') or {}),
        'hoy': datetime.date.today().isoformat(),
        'form_seguimiento': form,
        'alerta': alerta,
        'titulo_alerta': titulo,
        'mensaje': mensaje,
        'es_supervisor': is_supervisor_cartera(request.user),
        'gestores_opciones': listar_gestores_opciones() if is_supervisor_cartera(request.user) else [],
        'gestor_juridico': GESTOR_JURIDICO,
    }
    return render(request, 'cartera/linea_tiempo.html', context)


@login_required
@group_perm_required(perms=('andinasoft.change_presupuestocartera',), raise_exception=True)
def cartera_asignar_gestor(request, proyecto):
    """UI para reasignar gestor / pasar a cartera juridica (sync InfoCartera + Presupuesto)."""
    check_project(request, proyecto)
    if not is_supervisor_cartera(request.user):
        raise PermissionDenied

    alerta = False
    titulo = None
    mensaje = None
    filtro = (request.GET.get('gestor') or request.POST.get('filtro_gestor') or '').strip()

    if request.method == 'POST':
        accion = request.POST.get('accion') or ''
        adj_ids = request.POST.getlist('adj_ids')
        if not adj_ids:
            single = (request.POST.get('adj') or '').strip()
            if single:
                adj_ids = [single]
        nuevo = (request.POST.get('nuevo_gestor') or '').strip()
        if accion == 'pasar_juridico':
            nuevo = GESTOR_JURIDICO

        actualizar_ppto = (request.POST.get('actualizar_presupuesto') or '').strip() in (
            '1', 'true', 'on', 'yes', 'si',
        )
        periodo_ppto = ultimo_periodo_presupuesto(proyecto) if actualizar_ppto else None

        if not adj_ids:
            alerta = True
            titulo = 'Atencion'
            mensaje = 'Selecciona al menos una adjudicacion.'
        elif not nuevo:
            alerta = True
            titulo = 'Atencion'
            mensaje = 'Selecciona el nuevo gestor.'
        elif actualizar_ppto and not periodo_ppto:
            alerta = True
            titulo = 'Atencion'
            mensaje = 'No hay presupuesto cargado en este proyecto para actualizar el gestor.'
        else:
            result = asignar_gestor_bulk(
                proyecto,
                adj_ids,
                nuevo,
                request.user,
                actualizar_presupuesto=actualizar_ppto,
                actualizar_todos_periodos=False,
                periodo=periodo_ppto,
            )
            n_ok = len(result['ok'])
            n_err = len(result['errores'])
            alerta = True
            ppto_txt = (
                f' y en presupuesto {label_periodo_presupuesto(periodo_ppto)}'
                if actualizar_ppto and periodo_ppto
                else ' (sin cambiar presupuesto)'
            )
            if n_err and not n_ok:
                titulo = 'Error'
                mensaje = f'No se pudo actualizar. {result["errores"][0].get("error", "")}'
            elif n_err:
                titulo = 'Parcial'
                mensaje = f'Se actualizaron {n_ok} adjudicacion(es); {n_err} con error{ppto_txt}.'
            elif nuevo == GESTOR_JURIDICO:
                titulo = 'Listo'
                mensaje = f'{n_ok} adjudicacion(es) pasaron a cartera juridica{ppto_txt}.'
            else:
                titulo = 'Listo'
                mensaje = f'Se reasigno el gestor en {n_ok} adjudicacion(es){ppto_txt}.'

    rows, fecha = listado_asignaciones(proyecto, request.user, filtro_gestor=filtro or None)
    gestores = listar_gestores_opciones()
    # Gestores presentes en el listado (para filtro)
    gestores_en_lista = sorted({(r.get('gestor') or 'Sin Gestor') for r in rows})
    ultimo_ppto = ultimo_periodo_presupuesto(proyecto)

    context = {
        'proyecto': proyecto,
        'periodo': fecha.strftime('%d/%m/%Y'),
        'rows': rows,
        'gestores_opciones': gestores,
        'gestores_filtro': gestores_en_lista,
        'filtro_gestor': filtro,
        'gestor_juridico': GESTOR_JURIDICO,
        'ultimo_periodo_ppto': ultimo_ppto or '',
        'ultimo_periodo_ppto_label': label_periodo_presupuesto(ultimo_ppto) if ultimo_ppto else '',
        'alerta': alerta,
        'titulo_alerta': titulo,
        'mensaje': mensaje,
    }
    return render(request, 'cartera/asignar_gestor.html', context)


@login_required
@group_perm_required(perms=('andinasoft.change_presupuestocartera',), raise_exception=True)
def cartera_config_cartas(request):
    """UI supervisor: telefono, correo y nombre de firma de cartas por proyecto."""
    if not is_supervisor_cartera(request.user):
        raise PermissionDenied

    accesibles = proyectos_accesibles(request.user)
    alerta = False
    titulo = None
    mensaje = None

    if request.method == 'POST':
        proyectos = request.POST.getlist('row_proyecto')
        firmas = request.POST.getlist('row_firma')
        telefonos = request.POST.getlist('row_telefono')
        emails = request.POST.getlist('row_email')
        items = []
        for i, proyecto in enumerate(proyectos):
            items.append({
                'proyecto': proyecto,
                'firma_nombre': firmas[i] if i < len(firmas) else '',
                'telefono': telefonos[i] if i < len(telefonos) else '',
                'email': emails[i] if i < len(emails) else '',
            })
        saved = guardar_config_cartas(items, permitidos=accesibles)
        alerta = True
        titulo = 'Listo'
        mensaje = f'Se actualizo el contacto de cartas en {saved} proyecto(s).'

    rows = listar_config_cartas(accesibles)
    context = {
        'rows': rows,
        'alerta': alerta,
        'titulo_alerta': titulo,
        'mensaje': mensaje,
    }
    return render(request, 'cartera/config_cartas.html', context)


@login_required
@group_perm_required(perms=('andinasoft.change_presupuestocartera',), raise_exception=True)
def cartera_reasignar_adj(request, proyecto, adj):
    """POST rapido desde linea de tiempo: cambia gestor de un ADJ."""
    check_project(request, proyecto)
    if not is_supervisor_cartera(request.user):
        raise PermissionDenied
    if request.method != 'POST':
        return HttpResponseRedirect(f'/cartera/linea_tiempo/{proyecto}/{adj}')

    nuevo = (request.POST.get('nuevo_gestor') or '').strip()
    if request.POST.get('pasar_juridico'):
        nuevo = GESTOR_JURIDICO
    if not nuevo:
        return HttpResponseRedirect(f'/cartera/linea_tiempo/{proyecto}/{adj}')

    try:
        asignar_gestor(proyecto, adj, nuevo, request.user, actualizar_todos_periodos=True)
    except ValueError:
        pass
    return HttpResponseRedirect(f'/cartera/linea_tiempo/{proyecto}/{adj}')


@login_required
@group_perm_required(perms=('andinasoft.view_presupuestocartera',), raise_exception=True)
def cartera_descargar_carta(request, proyecto, adj, checkpoint_id):
    check_project(request, proyecto)
    _assert_adj_visible(request, proyecto, adj)

    checkpoint = get_object_or_404(
        CarteraCheckpoint,
        pk=checkpoint_id,
        proyecto_id=proyecto,
        activo=True,
    )
    payload = timeline_payload(proyecto, adj)
    if payload is None:
        raise Http404('Adjudicacion no encontrada')
    if not checkpoint.alcanzado(payload['dias_mora']):
        raise PermissionDenied('El cliente aun no alcanza este checkpoint')

    plantilla = resolver_plantilla_carta(checkpoint)
    if plantilla is None:
        raise Http404('No hay plantilla activa para este checkpoint')

    html_context = build_carta_context(proyecto, adj, checkpoint, payload=payload)
    filename = f'carta_cobro_{proyecto}_{adj}_{checkpoint.codigo}.pdf'.replace(' ', '_')
    try:
        result = generar_documento_pdf_directo(
            plantilla['motor'],
            plantilla['plantilla'],
            html_context=html_context,
            filename=filename,
        )
    except ConfigDocumentoInvalida as exc:
        raise Http404(str(exc)) from exc

    root = result.get('root')
    if not root:
        raise Http404('No se pudo generar el PDF')
    registrar_generacion_carta(proyecto, adj, checkpoint, request.user)
    return file_response_from_pdf_root(root, filename=result.get('filename') or filename)


@login_required
@group_perm_required(perms=('andinasoft.view_presupuestocartera',), raise_exception=True)
def cartera_estado_cuenta(request, proyecto, adj):
    """PDF estado de cuenta (misma generacion que detalle ADJ)."""
    check_project(request, proyecto)
    _assert_adj_visible(request, proyecto, adj)
    context, err_ec = build_estado_cuenta_context(proyecto, adj, request.user)
    if err_ec:
        raise Http404(err_ec)
    filename = f'Estado_de_cuenta_{adj}_{proyecto}.pdf'
    pdf = pdf_gen('pdf/statement_of_account.html', context, filename)
    if not isinstance(pdf, dict) or not pdf.get('root'):
        raise Http404('No se pudo generar el estado de cuenta')
    return file_response_from_pdf_root(pdf['root'], filename=filename)


@login_required
@group_perm_required(perms=('andinasoft.view_presupuestocartera',), raise_exception=True)
def cartera_soporte_carta(request, proyecto, adj, envio_id):
    """Descarga el archivo de soporte de un envio de carta."""
    check_project(request, proyecto)
    _assert_adj_visible(request, proyecto, adj)
    envio = get_object_or_404(
        CarteraCartaEnvio,
        pk=envio_id,
        proyecto_id=proyecto,
        adj=adj,
    )
    if not envio.soporte:
        raise Http404('Sin archivo')
    try:
        fh = envio.soporte.open('rb')
    except Exception as exc:
        raise Http404('No se pudo abrir el soporte') from exc
    filename = envio.soporte.name.rsplit('/', 1)[-1]
    return FileResponse(fh, as_attachment=True, filename=filename)
