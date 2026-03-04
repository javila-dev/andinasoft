import unicodedata
import hashlib
from django.shortcuts import render
from django.http import JsonResponse, FileResponse
from django.db.models import Avg, Max, Min, Sum, Q
from django.conf import settings
from django.contrib.auth.decorators import login_required
from andina.decorators import check_perms, group_perm_required
from andinasoft.create_pdf import GenerarPDF
from andinasoft.utilities import Utilidades, pdf_gen
from andinasoft.models import clientes, proyectos
from andinasoft.shared_models import Recaudos_general, Vista_Adjudicacion
from finance.models import recibos_internos
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from andinasoft.ajax_request import JSONRender
from finance.forms import form_recibo_int
from django.utils.html import strip_tags
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from api_auth.decorators import api_token_auth

ALLOWED_PDF_CONTENT_TYPES = {
    'application/pdf',
    'application/x-pdf',
    'application/pdf; charset=binary',
    'application/octet-stream',
    'binary/octet-stream',
}


def _is_pdf(uploaded_file):
    content_type = (uploaded_file.content_type or '').lower()
    if content_type in ALLOWED_PDF_CONTENT_TYPES:
        return True
    return uploaded_file.name.lower().endswith('.pdf')


def _get_file_hash(uploaded_file):
    uploaded_file.seek(0)
    hasher = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        hasher.update(chunk)
    uploaded_file.seek(0)
    return hasher.hexdigest()


def _parse_date_param(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _build_soporte_url(request, soporte_field):
    if not soporte_field:
        return None
    url = soporte_field.url
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return request.build_absolute_uri(url)

@api_token_auth
@require_http_methods(["GET"])
def api_pending_receipts(request):
    if not request.user.is_authenticated or request.user.is_anonymous:
        return JsonResponse({'detail': 'Token inválido o no autenticado'}, status=401)
    today = date.today()
    default_from = today - relativedelta(months=1)
    fecha_desde = _parse_date_param(request.GET.get('fecha_desde')) or default_from
    fecha_hasta = _parse_date_param(request.GET.get('fecha_hasta')) or today
    if fecha_desde > fecha_hasta:
        fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
    
    proyecto_id = request.GET.get('proyecto')
    cliente_id = request.GET.get('cliente')
    solo_abonos = request.GET.get('abono_capital')
    fecha_pago_hasta = _parse_date_param(request.GET.get('fecha_pago_hasta'))

    queryset = recibos_internos.objects.filter(
        fecha__range = (fecha_desde, fecha_hasta),
        anulado = False,
        requiere_revision_manual = False
    ).filter(
        Q(recibo_asociado__isnull=True) | Q(recibo_asociado__exact='')
    ).select_related('proyecto','usuario_solicita')

    if fecha_pago_hasta:
        queryset = queryset.filter(fecha_pago__lte = fecha_pago_hasta)
    
    if proyecto_id and proyecto_id.lower() != 'todos':
        queryset = queryset.filter(proyecto = proyecto_id)
    if cliente_id:
        queryset = queryset.filter(cliente = cliente_id)
    if solo_abonos in ('1','true','True'):
        queryset = queryset.filter(abono_capital = True)
    
    perm_global = check_perms(request,('andinasoft.add_recaudos_general',),raise_exception=False)
    if not perm_global:
        queryset = queryset.filter(usuario_solicita = request.user)
    
    results = []
    for registro in queryset.order_by('-fecha','-pk'):
        soporte_url = registro.soporte.url if registro.soporte else None
        if soporte_url:
            soporte_url = request.build_absolute_uri(soporte_url)
        results.append({
            'id': registro.pk,
            'proyecto': registro.proyecto.pk,
            'proyecto_nombre': registro.proyecto.proyecto,
            'cliente': registro.cliente,
            'valor': registro.valor,
            'condonacion': registro.condonacion,
            'abono_capital': registro.abono_capital,
            'fecha_solicitud': registro.fecha.isoformat(),
            'fecha_pago': registro.fecha_pago.isoformat(),
            'usuario_solicita': registro.usuario_solicita.get_full_name() or registro.usuario_solicita.username,
            'soporte_url': soporte_url,
            'requiere_revision_manual': registro.requiere_revision_manual,
            'motivo_revision': registro.motivo_revision
        })
    
    data = {
        'filters': {
            'fecha_desde': fecha_desde.isoformat(),
            'fecha_hasta': fecha_hasta.isoformat(),
            'proyecto': proyecto_id,
            'cliente': cliente_id,
            'solo_abonos': solo_abonos in ('1','true','True'),
            'fecha_pago_hasta': fecha_pago_hasta.isoformat() if fecha_pago_hasta else None
        },
        'total': len(results),
        'results': results
    }
    
    return JsonResponse(data, status=200)

# Create your views here.

@login_required
@group_perm_required(('finance.view_recibos_internos',),raise_exception=True)
def solicitar_recibo_interno(request):
    today = date.today()
    default_from = today - relativedelta(months=1)
    context = {
        'proyectos':proyectos.objects.exclude(
            proyecto__icontains='Alttum'
            ).order_by('proyecto'),
        'form':form_recibo_int,
        'fecha_desde_default': default_from.strftime('%Y-%m-%d'),
        'fecha_hasta_default': today.strftime('%Y-%m-%d')
    }
    
    if request.is_ajax():
        if request.method == 'GET':
            todo = request.GET.get('todo')
            
            if todo == 'pendientes':
                proyecto = request.GET.get('proyecto')
                fecha_desde = request.GET.get('fecha_desde')
                fecha_hasta = request.GET.get('fecha_hasta')
                estado = request.GET.get('estado')

                fecha_desde = _parse_date_param(fecha_desde) or default_from
                fecha_hasta = _parse_date_param(fecha_hasta) or today
                if fecha_desde > fecha_hasta:
                    fecha_desde, fecha_hasta = fecha_hasta, fecha_desde

                obj_recibos = recibos_internos.objects.filter(
                    fecha__gte = fecha_desde,
                    fecha__lte = fecha_hasta,
                    anulado=False
                )
                perm = check_perms(request,('andinasoft.add_recaudos_general',),raise_exception=False)
                if not perm:
                    obj_recibos = obj_recibos.filter(usuario_solicita=request.user)

                if proyecto != 'todos':
                    obj_recibos = obj_recibos.filter(proyecto = proyecto)

                # Filtrar por estado
                if estado == 'realizados':
                    obj_recibos = obj_recibos.filter(recibo_asociado__isnull=False)
                elif estado == 'revision':
                    obj_recibos = obj_recibos.filter(requiere_revision_manual=True, recibo_asociado__isnull=True)
                elif estado == 'sin_realizar':
                    obj_recibos = obj_recibos.filter(recibo_asociado__isnull=True, requiere_revision_manual=False)

                rendered = JSONRender(obj_recibos,query_functions=['adj_info','titular']).render()
                soporte_urls = {
                    item.pk: _build_soporte_url(request, item.soporte)
                    for item in obj_recibos
                }
                for item in rendered:
                    item['soporte_url'] = soporte_urls.get(item.get('id'))

                data = {
                    'data': rendered
                }

                return JsonResponse(data)
            
            elif todo == 'verificar':
                proyecto = request.GET.get('proyecto')
                fecha = request.GET.get('fecha')
                fecha = datetime.strptime(fecha,'%Y-%m-%d')
                last_week = fecha - relativedelta(weeks=2)
                valor = request.GET.get('valor').replace(',','')
                valor = int(valor)
                cliente = request.GET.get('cliente')
                obj_ri = recibos_internos.objects.filter(
                    proyecto = proyecto, fecha_pago__gte =last_week,
                    valor = valor, cliente = cliente
                )
                
                if obj_ri.exists():
                    data = {
                        'msj':'Existen uno o mas recibos de caja por este mismo valor asociados a este cliente en fechas muy cercanas, revisalo antes de continuar.',
                        'class':'alert-danger'
                    }
                else:
                    data = {
                        'msj':'Todo esta bien, puedes continuar.',
                        'class':'alert-success'
                    }
                    
                return JsonResponse(data)
                
        
        if request.method == 'POST':
            todo = request.POST.get('todo')

            if todo == 'delete':
                perm = check_perms(request,('finance.delete_recibos_internos',),raise_exception=False)
                
                if perm:
                    id_rec = request.POST.get('id_rec')
                    obj_solic = recibos_internos.objects.get(pk=id_rec)
                    obj_solic.anulado = True
                    obj_solic.save()
                    status = 200
                else:
                    status = 403
                    
                data = {
                    'status': status
                }
                
                return JsonResponse(data)
    else:
        if request.method == 'POST':
            solicitud_id = request.POST.get('solicitud_id')
            is_update = True if solicitud_id else False
            perm = ('finance.change_recibos_internos',) if is_update else ('finance.add_recibos_internos',)
            check_perms(request,perm,raise_exception=True)

            proyecto = request.POST.get('proyecto_solic')
            fecha_pago = request.POST.get('fecha_pago')
            cliente = strip_tags(request.POST.get('cliente'))
            valor = request.POST.get('valor')
            valor = int(valor.replace(',',''))
            abono_capital = request.POST.get('abono_capital')
            abono_capital = True if abono_capital == 'on' else False
            condona_mora = request.POST.get('condona_mora')
            condona_mora = True if condona_mora == 'on' else False
            soporte = request.FILES.get('soporte')

            try:
                proyecto_obj = proyectos.objects.get(pk=proyecto)
            except proyectos.DoesNotExist:
                context['topalert'] = {
                    'alert':True,
                    'title':'Andinasoft dice:',
                    'message':'El proyecto seleccionado no es válido.',
                    'class':'alert-danger'
                }
                return render(request,'solicitar_recibo_interno.html',context)

            obj_editar = None
            if is_update:
                try:
                    obj_editar = recibos_internos.objects.get(pk=solicitud_id, anulado=False)
                except recibos_internos.DoesNotExist:
                    context['topalert'] = {
                        'alert':True,
                        'title':'Andinasoft dice:',
                        'message':'No encontramos la solicitud seleccionada o ya fue anulada.',
                        'class':'alert-danger'
                    }
                    return render(request,'solicitar_recibo_interno.html',context)

                if obj_editar.recibo_asociado:
                    context['topalert'] = {
                        'alert':True,
                        'title':'Andinasoft dice:',
                        'message':'Esta solicitud ya fue validada y no puede editarse.',
                        'class':'alert-danger'
                    }
                    return render(request,'solicitar_recibo_interno.html',context)

                perm_global = check_perms(request,('andinasoft.add_recaudos_general',),raise_exception=False)
                if obj_editar.usuario_solicita != request.user and not perm_global:
                    context['topalert'] = {
                        'alert':True,
                        'title':'Andinasoft dice:',
                        'message':'No tienes permisos para editar esta solicitud.',
                        'class':'alert-danger'
                    }
                    return render(request,'solicitar_recibo_interno.html',context)

            if soporte is None and not is_update:
                context['topalert'] = {
                    'alert':True,
                    'title':'Andinasoft dice:',
                    'message':'Debes adjuntar el soporte del pago en PDF.',
                    'class':'alert-danger'
                }
                return render(request,'solicitar_recibo_interno.html',context)

            soporte_hash = None
            if soporte:
                if not _is_pdf(soporte):
                    context['topalert'] = {
                        'alert':True,
                        'title':'Andinasoft dice:',
                        'message':'Solo se permiten archivos PDF como soporte.',
                        'class':'alert-danger'
                    }
                    return render(request,'solicitar_recibo_interno.html',context)

                soporte_hash = _get_file_hash(soporte)
                soporte.name = ''.join(c for c in unicodedata.normalize('NFD', soporte.name)
                                            if unicodedata.category(c) != 'Mn'
                                            ).replace('ñ','n')
            elif obj_editar:
                soporte_hash = obj_editar.soporte_hash

            fmt = datetime.strptime(fecha_pago,'%Y-%m-%d')
            month = fmt.month
            year = fmt.year
            
            obj_ri = recibos_internos.objects.filter(
                proyecto = proyecto_obj, 
                fecha_pago__month = month,
                fecha_pago__year = year,                
                valor = valor, cliente = cliente
            )
            if is_update:
                obj_ri = obj_ri.exclude(pk=obj_editar.pk)
            
            not_duplicated = request.POST.get('not_duplicated')
            nd = True if not_duplicated == 'on' else False
            
            soporte_duplicado = False
            if soporte_hash:
                soporte_duplicado = recibos_internos.objects.filter(soporte_hash=soporte_hash)
                if is_update:
                    soporte_duplicado = soporte_duplicado.exclude(pk=obj_editar.pk)
                soporte_duplicado = soporte_duplicado.exists()

            if obj_ri.exists() and not nd:
                context['topalert']={
                'alert':True,
                'title':'Andinasoft dice:',
                'message':f'''Ya existe un recibo en el mismo mes a este cliente por el mismo valor. Confirmalo
                            ''',
                'class':'alert-danger'
                    }
            elif soporte_duplicado:
                context['topalert']={
                'alert':True,
                'title':'Andinasoft dice:',
                'message':'Ya existe una solicitud con el mismo soporte registrado. Verifica antes de continuar.',
                'class':'alert-danger'
                    }
            else:
                if is_update and obj_editar:
                    obj_editar.proyecto = proyecto_obj
                    obj_editar.fecha_pago = fecha_pago
                    obj_editar.valor = valor
                    obj_editar.condonacion = condona_mora
                    obj_editar.abono_capital = abono_capital
                    obj_editar.cliente = cliente
                    if soporte:
                        obj_editar.soporte = soporte
                        obj_editar.soporte_hash = soporte_hash
                    obj_editar.save()
                    context['topalert']={
                        'alert':True,
                        'title':'Andinasoft dice:',
                        'message':'La solicitud de recibo fue actualizada con éxito.',
                        'class':'alert-success'
                            }
                else:            
                    obj_ri = recibos_internos.objects.create(
                        proyecto = proyecto_obj,fecha_pago = fecha_pago,
                        valor = valor, soporte = soporte, usuario_solicita = request.user,
                        condonacion = condona_mora, abono_capital = abono_capital, cliente = cliente,
                        soporte_hash = soporte_hash
                    )

                    context['topalert']={
                        'alert':True,
                        'title':'Andinasoft dice:',
                        'message':f'''La solicitud de recibo fue creada con exito.
                                    ''',
                        'class':'alert-success'
                            }
    
    return render(request,'solicitar_recibo_interno.html',context)

@login_required
@group_perm_required(('finance.view_recibos_internos',),raise_exception=True)
def solicitud_fractal(request):
    
    context = {
        'form':form_recibo_int,
        'ventas': Vista_Adjudicacion.objects.using('Fractal').exclude(Q(Estado__icontains='desistido')|Q(Estado__icontains='pagado'))
    }
    
    if request.is_ajax():
        today = date.today()
        default_from = today - relativedelta(months=1)
        if request.method == 'GET':
            todo = request.GET.get('todo')
            
            if todo == 'pendientes':
                proyecto = request.GET.get('proyecto')
                fecha_desde = _parse_date_param(request.GET.get('fecha_desde')) or default_from
                fecha_hasta = _parse_date_param(request.GET.get('fecha_hasta')) or today
                if fecha_desde > fecha_hasta:
                    fecha_desde, fecha_hasta = fecha_hasta, fecha_desde
                
                obj_recibos = recibos_internos.objects.filter(
                    fecha__gte = fecha_desde,
                    fecha__lte = fecha_hasta,
                    anulado=False
                )                
                perm = check_perms(request,('andinasoft.add_recaudos_general',),raise_exception=False)
                if not perm:
                    obj_recibos = obj_recibos.filter(usuario_solicita=request.user)
                
                if proyecto != 'todos':
                    obj_recibos = obj_recibos.filter(proyecto = proyecto)

                rendered = JSONRender(obj_recibos,query_functions=['adj_info','titular']).render()
                soporte_urls = {
                    item.pk: _build_soporte_url(request, item.soporte)
                    for item in obj_recibos
                }
                for item in rendered:
                    item['soporte_url'] = soporte_urls.get(item.get('id'))

                data = {
                    'data': rendered
                }
                
                return JsonResponse(data)
            
            elif todo == 'verificar':
                proyecto = request.GET.get('proyecto')
                fecha = request.GET.get('fecha')
                fecha = datetime.strptime(fecha,'%Y-%m-%d')
                last_week = fecha - relativedelta(weeks=2)
                valor = request.GET.get('valor').replace(',','')
                valor = int(valor)
                cliente = request.GET.get('cliente')
                obj_ri = recibos_internos.objects.filter(
                    proyecto = proyecto, fecha_pago__gte =last_week,
                    valor = valor, cliente = cliente
                )
                
                if obj_ri.exists():
                    data = {
                        'msj':'Existen uno o mas recibos de caja por este mismo valor asociados a este cliente en fechas muy cercanas, revisalo antes de continuar.',
                        'class':'alert-danger'
                    }
                else:
                    data = {
                        'msj':'Todo esta bien, puedes continuar.',
                        'class':'alert-success'
                    }
                    
                return JsonResponse(data)
                
        
        if request.method == 'POST':
            todo = request.POST.get('todo')

            if todo == 'delete':
                perm = check_perms(request,('finance.delete_recibos_internos',),raise_exception=False)
                
                if perm:
                    id_rec = request.POST.get('id_rec')
                    obj_solic = recibos_internos.objects.get(pk=id_rec)
                    obj_solic.anulado = True
                    obj_solic.save()
                    status = 200
                else:
                    status = 403
                    
                data = {
                    'status': status
                }
                
                return JsonResponse(data)
    else:
        if request.method == 'POST':
            check_perms(request,('finance.add_recibos_internos',),raise_exception=True)
            proyecto = 'Fractal'
            fecha_pago = request.POST.get('fecha_pago')
            cliente = strip_tags(request.POST.get('cliente'))
            valor = request.POST.get('valor')
            valor = int(valor.replace(',',''))
            abono_capital = request.POST.get('abono_capital')
            abono_capital = True if abono_capital == 'on' else False
            condona_mora = request.POST.get('condona_mora')
            condona_mora = True if condona_mora == 'on' else False
            soporte = request.FILES.get('soporte')
            if soporte is None:
                context['topalert']={
                    'alert':True,
                    'title':'Andinasoft dice:',
                    'message':'Debes adjuntar el soporte del pago en PDF.',
                    'class':'alert-danger'
                }
                return render(request,'recibos_fractal.html',context)

            if not _is_pdf(soporte):
                context['topalert']={
                    'alert':True,
                    'title':'Andinasoft dice:',
                    'message':'Solo se permiten archivos PDF como soporte.',
                    'class':'alert-danger'
                }
                return render(request,'recibos_fractal.html',context)

            soporte_hash = _get_file_hash(soporte)

            if recibos_internos.objects.filter(soporte_hash=soporte_hash).exists():
                context['topalert']={
                    'alert':True,
                    'title':'Andinasoft dice:',
                    'message':'Ya existe una solicitud con el mismo soporte registrado. Verifica antes de continuar.',
                    'class':'alert-danger'
                }
                return render(request,'recibos_fractal.html',context)

            soporte.name = ''.join(c for c in unicodedata.normalize('NFD', soporte.name)
                                        if unicodedata.category(c) != 'Mn'
                                        ).replace('ñ','n')
            
            
            obj_ri = recibos_internos.objects.create(
                proyecto = proyectos.objects.get(pk=proyecto),fecha_pago = fecha_pago,
                valor = valor, soporte = soporte, usuario_solicita = request.user,
                condonacion = condona_mora, abono_capital = abono_capital, cliente = cliente,
                soporte_hash = soporte_hash
            )

            context['topalert']={
                'alert':True,
                'title':'Andinasoft dice:',
                'message':f'''La solicitud de recibo fue creada con exito.
                            ''',
                'class':'alert-success'
                    }
        
    
    return render(request,'recibos_fractal.html',context)
    
@login_required
def imprimir_recibo(request):
    if request.method =='GET':
        proyecto = request.GET.get('proyecto')
        recibo = request.GET.get('recibo')


        filename = f'Recibo_caja_{recibo}_{proyecto}.pdf'

        obj_recibo = Recaudos_general.objects.using(proyecto).get(numrecibo = recibo)


        context = {
            'recibo':obj_recibo
        }

        pdf = pdf_gen(f'pdf/{proyecto}/recibo.html', context,filename)

        file = pdf.get('root')

        return FileResponse(open(file,'rb'),as_attachment=True,filename=filename)


@csrf_exempt
@api_token_auth
def api_update_receipt_status(request, receipt_id):
    """
    Endpoint para cambiar el estado de una solicitud de recibo.

    Estados soportados:
    - anulado: Anula una solicitud pendiente
    - activo: Reactiva una solicitud anulada (solo si no tiene recibo asociado)
    """
    if request.method != 'PATCH':
        return JsonResponse({'detail': 'Método no permitido'}, status=405)

    if not request.user.is_authenticated or request.user.is_anonymous:
        return JsonResponse({'detail': 'Token inválido o no autenticado'}, status=401)

    # Verificar permisos
    perm_delete = check_perms(request, ('finance.delete_recibos_internos',), raise_exception=False)
    perm_change = check_perms(request, ('finance.change_recibos_internos',), raise_exception=False)
    perm_global = check_perms(request, ('andinasoft.add_recaudos_general',), raise_exception=False)

    # Obtener la solicitud
    try:
        solicitud = recibos_internos.objects.get(pk=receipt_id)
    except recibos_internos.DoesNotExist:
        return JsonResponse({
            'detail': 'Solicitud de recibo no encontrada',
            'error_code': 'NOT_FOUND'
        }, status=404)

    # Verificar que el usuario tenga permiso sobre esta solicitud
    if not perm_global and solicitud.usuario_solicita != request.user:
        return JsonResponse({
            'detail': 'No tienes permiso para modificar esta solicitud',
            'error_code': 'PERMISSION_DENIED'
        }, status=403)

    # Parsear body JSON
    try:
        import json
        body = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            'detail': 'JSON inválido en el body',
            'error_code': 'INVALID_JSON'
        }, status=400)

    nuevo_estado = body.get('estado')
    requiere_revision = body.get('requiere_revision_manual')
    motivo_revision = body.get('motivo_revision', '')

    # Permitir cambiar solo el flag de revisión sin cambiar estado
    if requiere_revision is not None and nuevo_estado is None:
        # Verificar permisos para marcar revisión
        if not perm_change and not perm_global:
            return JsonResponse({
                'detail': 'No tienes permiso para marcar solicitudes para revisión',
                'error_code': 'PERMISSION_DENIED'
            }, status=403)

        # No se puede marcar para revisión si ya tiene recibo
        if solicitud.recibo_asociado:
            return JsonResponse({
                'detail': 'No se puede marcar para revisión una solicitud que ya tiene recibo asociado',
                'error_code': 'HAS_RECEIPT',
                'recibo_asociado': solicitud.recibo_asociado
            }, status=400)

        # No se puede marcar si está anulada
        if solicitud.anulado:
            return JsonResponse({
                'detail': 'No se puede marcar para revisión una solicitud anulada',
                'error_code': 'IS_ANULADO'
            }, status=400)

        solicitud.requiere_revision_manual = bool(requiere_revision)
        # Si se marca para revisión, guardar el motivo. Si se desmarca, limpiar el motivo
        if solicitud.requiere_revision_manual:
            solicitud.motivo_revision = motivo_revision if motivo_revision else None
        else:
            solicitud.motivo_revision = None
        solicitud.save()

        return JsonResponse({
            'id': solicitud.pk,
            'requiere_revision_manual': solicitud.requiere_revision_manual,
            'motivo_revision': solicitud.motivo_revision,
            'mensaje': f'Solicitud {"marcada" if solicitud.requiere_revision_manual else "desmarcada"} para revisión manual',
            'proyecto': solicitud.proyecto.proyecto,
            'cliente': solicitud.cliente,
            'valor': solicitud.valor,
            'fecha_solicitud': solicitud.fecha.isoformat(),
            'fecha_pago': solicitud.fecha_pago.isoformat()
        }, status=200)

    if not nuevo_estado:
        return JsonResponse({
            'detail': 'El campo "estado" es requerido',
            'error_code': 'MISSING_ESTADO',
            'estados_validos': ['anulado', 'activo']
        }, status=400)

    # Validar estado
    if nuevo_estado not in ['anulado', 'activo']:
        return JsonResponse({
            'detail': f'Estado "{nuevo_estado}" no válido',
            'error_code': 'INVALID_ESTADO',
            'estados_validos': ['anulado', 'activo']
        }, status=400)

    # Validaciones de negocio
    if nuevo_estado == 'anulado':
        # Para anular, necesita permiso de delete
        if not perm_delete and not perm_global:
            return JsonResponse({
                'detail': 'No tienes permiso para anular solicitudes',
                'error_code': 'PERMISSION_DENIED'
            }, status=403)

        # No se puede anular si ya tiene recibo asociado
        if solicitud.recibo_asociado:
            return JsonResponse({
                'detail': 'No se puede anular una solicitud que ya tiene recibo asociado',
                'error_code': 'HAS_RECEIPT',
                'recibo_asociado': solicitud.recibo_asociado
            }, status=400)

        # Si ya está anulada, no hay nada que hacer
        if solicitud.anulado:
            return JsonResponse({
                'detail': 'La solicitud ya está anulada',
                'error_code': 'ALREADY_ANULADO',
                'id': solicitud.pk,
                'estado': 'anulado'
            }, status=200)

        # Anular la solicitud
        solicitud.anulado = True
        solicitud.save()

        return JsonResponse({
            'id': solicitud.pk,
            'estado': 'anulado',
            'mensaje': 'Solicitud anulada exitosamente',
            'proyecto': solicitud.proyecto.proyecto,
            'cliente': solicitud.cliente,
            'valor': solicitud.valor,
            'fecha_solicitud': solicitud.fecha.isoformat(),
            'fecha_pago': solicitud.fecha_pago.isoformat()
        }, status=200)

    elif nuevo_estado == 'activo':
        # Para reactivar, necesita permiso de change o global
        if not perm_change and not perm_global:
            return JsonResponse({
                'detail': 'No tienes permiso para reactivar solicitudes',
                'error_code': 'PERMISSION_DENIED'
            }, status=403)

        # Solo se puede reactivar si está anulada
        if not solicitud.anulado:
            return JsonResponse({
                'detail': 'La solicitud ya está activa',
                'error_code': 'ALREADY_ACTIVE',
                'id': solicitud.pk,
                'estado': 'activo' if not solicitud.recibo_asociado else 'confirmado'
            }, status=200)

        # No se puede reactivar si tiene recibo asociado
        if solicitud.recibo_asociado:
            return JsonResponse({
                'detail': 'No se puede reactivar una solicitud que tiene recibo asociado',
                'error_code': 'HAS_RECEIPT',
                'recibo_asociado': solicitud.recibo_asociado
            }, status=400)

        # Reactivar la solicitud
        solicitud.anulado = False
        solicitud.save()

        return JsonResponse({
            'id': solicitud.pk,
            'estado': 'activo',
            'mensaje': 'Solicitud reactivada exitosamente',
            'proyecto': solicitud.proyecto.proyecto,
            'cliente': solicitud.cliente,
            'valor': solicitud.valor,
            'fecha_solicitud': solicitud.fecha.isoformat(),
            'fecha_pago': solicitud.fecha_pago.isoformat()
        }, status=200)


@login_required
@group_perm_required(('finance.view_recibos_internos',), raise_exception=True)
def api_receipt_stats(request):
    """
    Endpoint para obtener estadísticas de solicitudes de recibos.
    Retorna: realizados, revision_manual, sin_realizar
    """
    if request.method != 'GET':
        return JsonResponse({'detail': 'Método no permitido'}, status=405)

    today = date.today()
    default_from = today - relativedelta(months=1)

    proyecto = request.GET.get('proyecto')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')

    # Parse fechas
    fecha_desde = _parse_date_param(fecha_desde) or default_from
    fecha_hasta = _parse_date_param(fecha_hasta) or today

    if fecha_desde > fecha_hasta:
        fecha_desde, fecha_hasta = fecha_hasta, fecha_desde

    # Filtrar recibos
    obj_recibos = recibos_internos.objects.filter(
        fecha__gte=fecha_desde,
        fecha__lte=fecha_hasta,
        anulado=False
    )

    # Verificar permisos
    perm = check_perms(request, ('andinasoft.add_recaudos_general',), raise_exception=False)
    if not perm:
        obj_recibos = obj_recibos.filter(usuario_solicita=request.user)

    # Filtrar por proyecto
    if proyecto and proyecto != 'todos':
        obj_recibos = obj_recibos.filter(proyecto=proyecto)

    # Calcular estadísticas con totales en dinero
    from django.db.models import Sum

    realizados_qs = obj_recibos.filter(recibo_asociado__isnull=False)
    revision_manual_qs = obj_recibos.filter(requiere_revision_manual=True, recibo_asociado__isnull=True)
    sin_realizar_qs = obj_recibos.filter(recibo_asociado__isnull=True, requiere_revision_manual=False)

    realizados = realizados_qs.count()
    revision_manual = revision_manual_qs.count()
    sin_realizar = sin_realizar_qs.count()

    # Calcular totales en dinero
    total_realizados = realizados_qs.aggregate(total=Sum('valor'))['total'] or 0
    total_revision = revision_manual_qs.aggregate(total=Sum('valor'))['total'] or 0
    total_sin_realizar = sin_realizar_qs.aggregate(total=Sum('valor'))['total'] or 0
    total_general = obj_recibos.aggregate(total=Sum('valor'))['total'] or 0

    return JsonResponse({
        'realizados': realizados,
        'revision_manual': revision_manual,
        'sin_realizar': sin_realizar,
        'total': obj_recibos.count(),
        'total_realizados': float(total_realizados),
        'total_revision': float(total_revision),
        'total_sin_realizar': float(total_sin_realizar),
        'total_general': float(total_general)
    }, status=200)
