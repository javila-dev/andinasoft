from django import forms as django_forms
from django.shortcuts import render
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, FileResponse
from django.urls import path
from django.core.exceptions import PermissionDenied
from django.db import models, IntegrityError
from django.db.models import Avg, Max, Min, Sum, Count, Q, F, Case, When, Value, Subquery, OuterRef, Func
from django.db.models.functions import Coalesce
from django.core import serializers
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.auth.models import User, Group, Permission
from django.utils import dateparse, html, timezone
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, PrependedText, PrependedAppendedText, TabHolder, Tab
from andina.decorators import check_perms, check_groups
from andinasoft.models import proyectos, empresas, notificaciones_correo, Profiles, asesores
from andinasoft.handlers_functions import envio_notificacion
from andina.decorators import group_perm_required, check_project
from crm.models import leads, historyline_lead, Operaciones, eventos, asistentes_evento, historyline_lead, usuario_gestor
from crm import forms as crm_forms
import datetime
import json
import math
import traceback
from decimal import Decimal

@group_perm_required(('crm.view_leads',),raise_exception=True)
def principal(request):
    
    return render(request,'crm/principal.html')

@group_perm_required(('crm.change_leads',),raise_exception=True)
def admin_leads(request):
    obj_sinAsignar = leads.objects.all()
    operadores = User.objects.filter(groups__name="Teleoperador",is_active=True)
    context = {
        'sin_asignar':obj_sinAsignar,
        'operadores':operadores,
        'form':crm_forms.form_Leads,
    }
        
    return render(request,'crm/manage_leads.html',context)

@group_perm_required(('crm.view_leads',),raise_exception=True)
def leads_view(request):
    is_asesor = check_groups(request,('Asesores',),raise_exception=False)
    is_supertlmk = check_groups(request,('Supervisor TLMK',),raise_exception=False)
    if is_asesor:
        asesor_rel = usuario_gestor.objects.filter(usuario=request.user)
        if asesor_rel.exists():
            lista_asesores = asesores.objects.filter(pk=asesor_rel[0].asesor.pk)
        else:
            lista_asesores = []
    if is_supertlmk:
        lista_asesores = asesores.objects.filter(estado='Activo',tipo_asesor='Externo').order_by('nombre')
    
    context={
        'asesores':lista_asesores,
        'show_todos':is_supertlmk,
        'form':crm_forms.form_Leads,
        'operaciones':Operaciones.objects.all()
    }
    
    if request.method == 'POST':
        if request.POST.get('btnGrabar'):
            form = crm_forms.form_Leads(request.POST)
            if form.is_valid():
                id_lead = request.POST.get('lead')
                nombre = request.POST.get('nombre')
                cedula = request.POST.get('identificacion')
                tipo_lead = request.POST.get('tipo_lead')
                celular = request.POST.get('celular')
                telefono = request.POST.get('telefono')
                email = request.POST.get('email')
                fecha_nac = request.POST.get('fecha_nacimiento')
                if fecha_nac =="": fecha_nac =None
                estado_civil = request.POST.get('estado_civil')
                gestor = request.POST.get('gestor_capta')
                direccion = request.POST.get('direccion')
                ciudad = request.POST.get('ciudad')
                if id_lead == 'Nuevo':
                    gestor_capta = asesores.objects.get(nombre__iexact=gestor)
                    leads.objects.create(
                        cedula=cedula,nombre=nombre,celular=celular,email=email,
                        telefono=telefono,direccion=direccion,ciudad=ciudad,
                        estado_civil=estado_civil,fecha_nacimiento=fecha_nac,
                        gestor_capta=gestor_capta,gestor_aseginado=gestor_capta,
                        estado='Activo',tipo=tipo_lead,fecha_capta=datetime.date.today()
                    )
                    historyline_lead.objects.create(
                        lead=leads.objects.last(),usuario=request.user,fecha=timezone.now(),
                        observacion=f"Creó el lead"
                    )
                    alert = {
                        'alert':1,
                        'title':'!Hecho!',
                        'message':f'El lead fue creado con exito',
                        'class':'alert-success'
                    }
                    context['topalert']=alert
                    
                else:
                    check_perms(request,('crm.change_leads',))
                    obj_lead = leads.objects.get(pk=id_lead)
                    obj_lead.cedula=cedula
                    obj_lead.nombre=nombre
                    obj_lead.celular=celular
                    obj_lead.email=email
                    obj_lead.telefono=telefono
                    obj_lead.direccion=direccion
                    obj_lead.ciudad=ciudad
                    obj_lead.estado_civil=estado_civil
                    obj_lead.fecha_nacimiento=fecha_nac
                    obj_lead.gestor_capta=gestor_capta
                    obj_lead.gestor_aseginado=gestor_capta
                    obj_lead.tipo=tipo_lead
                    
                    alert = {
                        'alert':1,
                        'title':'!Hecho!',
                        'message':f'El lead fue modificado con exito',
                        'class':'alert-success'
                    }
                    context['topalert']=alert
            else:
                context['form']=form
                context['form_error']=1
        if request.POST.get('btnConfirmarCita'):
            id_lead = request.POST.get('id_lead_cita')
            operacion = request.POST.get('id_operacion_cita')
            nombre_operacion = request.POST.get('operacion_evento')
            asistentes = request.POST.get('num_asistentes')
            evento = request.POST.get('evento_cita')
            evento = evento.split(' - ')
            fecha_evento = evento[0]
            hora_evento = evento[1]
            
            obj_evento = eventos.objects.get(hora_evento=hora_evento,fecha_evento=fecha_evento,
                                             operacion=operacion)
            obj_lead = leads.objects.get(pk=id_lead)
            alert=''
            try:
                asistentes_evento.objects.create(evento=obj_evento,asistente=obj_lead,
                                                usuario_asigna=request.user,estado_cliente='Pendiente',
                                                cupos=asistentes)
                historyline_lead.objects.create(
                    lead=obj_lead,usuario=request.user,fecha=timezone.now(),
                    observacion=f"Agendó evento - {nombre_operacion}"
                )
                obj_lead.estado = 'En evento'
                obj_lead.save()
                alert = {
                            'alert':1,
                            'title':'!Hecho!',
                            'message':f'La cita se creo de forma correcta',
                            'class':'alert-success'
                        }
            except IntegrityError as e:
                
                alert = {
                            'alert':1,
                            'title':'!Error!',
                            'message':html.escapejs(f'{e}'),
                            'class':'alert-danger'
                        }
            context['topalert']=alert
                
    return render(request,'crm/leads.html',context)

@group_perm_required(('crm.view_eventos',),raise_exception=True)
def eventos_leads(request):
    is_supertlmk = check_groups(request,('Supervisor TLMK',),raise_exception=False)
    if is_supertlmk:
        obj_operaciones = Operaciones.objects.all()
    else:
        obj_operaciones = Operaciones.objects.filter(lider=request.user.pk)
    
    obj_eventos = eventos.objects.filter(estado_evento='Abierto')
    context={
        'operaciones':obj_operaciones,
        'eventos':obj_eventos,
        'form':crm_forms.form_Leads,
        'form_evento':crm_forms.formCrearEvento,
    }
    return render(request,'crm/events.html',context)

@group_perm_required(('crm.change_eventos',),raise_exception=True)
def admin_eventos(request):
    context={
        
    }
    return render(request,'crm/allevents.html',context)

# ajax requests
def ajax_leads(request):
    if request.method == 'GET':
        if request.is_ajax():
            estado = request.GET.get('estado')
            asesor = request.GET.get('asesor')
            sinasignar = request.GET.get('sinasignar')
            operador_ppal = check_perms(request,('crm.delete_leads',),raise_exception=False)                
            if estado=='TODOS':
                obj_lead = leads.objects.all()
            elif asesor == 'TODOS':
                obj_lead = leads.objects.filter(estado=estado)
            else:
                obj_lead = leads.objects.filter(estado=estado,gestor_aseginado__nombre=asesor)
            
            leads_list = []
            i=1
            for lead in obj_lead:
                if lead.operador == None: operador = ""
                else: operador = lead.operador.username
                leads_list.append(
                    {
                    'id':i,
                    'pk':lead.pk,
                    'nombre':lead.nombre,
                    'cedula':lead.cedula,
                    'celular':lead.celular,
                    'direccion':lead.direccion,
                    'estado_civil':lead.estado_civil,
                    'gestor_asignado':lead.gestor_aseginado.nombre,
                    'tipo':lead.tipo,
                    'telefono':lead.telefono,
                    'operador':operador,
                    'fecha_nacimiento':lead.fecha_nacimiento,
                    'email':lead.email,
                    'fecha_reg':lead.fecha_capta,
                    'estado':lead.estado,
                    'ciudad':lead.ciudad,
                    'tipo':lead.tipo,
                    'id_gestor':lead.gestor_aseginado.pk
                    }
                )
                i+=1
            data={
                'data':leads_list
            }
            return JsonResponse(data)

def ajax_history_lead(request):
    if request.method == 'GET':
        if request.is_ajax():
            id_lead = request.GET.get('lead')
            obj_history = historyline_lead.objects.filter(lead=id_lead).order_by('-fecha')
            history = []
            
            for comment in obj_history:
                avatar = Profiles.objects.get(user=comment.usuario.pk)
                avatar = f'/media/{avatar.avatar.image}'
                history.append({
                    'usuario':comment.usuario.first_name+" "+comment.usuario.last_name,
                    'fecha':comment.fecha,
                    'observacion':comment.observacion,
                    'avatar': avatar,
                })
            data = {
                'data':history
            }
            return JsonResponse(data)

def ajax_eventos(request):
    if request.method == 'GET':
        if request.is_ajax():
            operacion = request.GET.get('operacion')
            obj_eventos = eventos.objects.filter(operacion=operacion,estado_evento='Abierto')
            
            json_evento = serializers.serialize('json',obj_eventos)
            data = {
                'eventos':json_evento
            }
            return JsonResponse(data)

def ajax_newObs(request,id_lead):
    if request.method == 'POST':
        if request.is_ajax():
            comentario = request.POST.get('nuevaObs')
            obj_lead = leads.objects.get(pk=id_lead)
            verif = historyline_lead.objects.filter(fecha=datetime.date.today(),
                                                    lead = id_lead,
                                                    observacion = comentario)
            fecha = timezone.now()
            if not verif.exists():
                historyline_lead.objects.create(lead = obj_lead,observacion=comentario,
                                                usuario=request.user,fecha=fecha)
                response = True
                avatar = Profiles.objects.get(user=request.user.pk)
                avatar = f'/media/{avatar.avatar.image}'
                new_data = {
                    'fecha':fecha,
                    'avatar':avatar,
                    'obs':comentario.upper(),
                    'usuario':f'{request.user.first_name} {request.user.last_name}'
                }
            else:
                response = False
        
        return JsonResponse({'response':response,'data':new_data})

def ajax_changeTipo(request):
    if request.method == 'POST':
        if request.is_ajax():
            id_lead = request.POST.get('id_lead')
            tipo = request.POST.get('tipo')
            obj_lead = leads.objects.get(pk=id_lead)
            obj_lead.tipo = tipo
            obs = f'Cambió el tipo de lead de {obj_lead.tipo.upper()} a {tipo.upper()}'
            obj_lead.save()
            historyline_lead.objects.create(
                lead=obj_lead,observacion=obs,usuario=request.user,
                fecha=timezone.now()
            )
            data = {
                'response':True
            }
            
            return JsonResponse(data)

def ajax_changeEstado(request):
    if request.method == 'POST':
        if request.is_ajax():
            id_lead = request.POST.get('id_lead')
            estado = request.POST.get('estado')
            obj_lead = leads.objects.get(pk=id_lead)
            obj_lead.estado = estado
            obj_lead.save()
            historyline_lead.objects.create(
                lead=obj_lead,
                observacion=f'Cambió el estado a {estado.upper()}',
                usuario=request.user,
                fecha=timezone.now()
            )
            
            return JsonResponse({'success':True})

def ajax_asistentes_evento(request):
    if request.method == 'GET':
        if request.is_ajax():
            asesor = request.GET.get('asesor')
            operacion = request.GET.get('operacion')
            id_evento = request.GET.get('evento')
            estado = request.GET.get('estado')
            if not operacion and not id_evento:
                return JsonResponse({'data':{}})
            
            operador_ppal = check_perms(request,('crm.delete_leads',),raise_exception=False)                
            if estado == 'TODOS':
                obj_asistentes = asistentes_evento.objects.filter(
                evento__operacion = operacion
            )
            else:
                obj_asistentes = asistentes_evento.objects.filter(
                    evento__estado_evento = 'Abierto',
                    evento__operacion = operacion
                )
            if id_evento and id_evento!='TODOS':
                obj_asistentes=obj_asistentes.filter(evento__pk=id_evento)      
            if asesor != 'TODOS':
                obj_asistentes = obj_asistentes.filter(
                    asistente__gestor_aseginado__nombre=asesor
                )  
            """ if not operador_ppal:
                obj_asistentes = obj_asistentes.filter(
                    asistente__operador=request.user
                ) """
            list_asistentes = []
            i=1
            for asistente in obj_asistentes:
                if asistente.asistente.operador is None: 
                    operador = ""
                else: operador = asistente.asistente.operador.pk
                cita=f'{asistente.evento.fecha_evento} - {asistente.evento.hora_evento}'
                list_asistentes.append({
                    'id':i,
                    'pk':asistente.asistente.pk,
                    'nombre':asistente.asistente.nombre,
                    'celular':asistente.asistente.celular,
                    'direccion':asistente.asistente.direccion,
                    'estado_civil':asistente.asistente.estado_civil,
                    'gestor_asignado':asistente.asistente.gestor_aseginado.nombre,
                    'tipo':asistente.asistente.tipo,
                    'telefono':asistente.asistente.telefono,
                    'operador':operador,
                    'fecha_nacimiento':asistente.asistente.fecha_nacimiento,
                    'email':asistente.asistente.email,
                    'fecha_reg':asistente.asistente.fecha_capta,
                    'cupos':asistente.cupos,
                    'cita':cita,
                    'estado':asistente.asistente.estado,
                    'asistencia':asistente.estado_cliente
                })
                i+=1
            data = {
                'data':list_asistentes
            }
            return JsonResponse(data)

def ajax_estadoEvento(request):
    if request.method == 'POST':
        if request.is_ajax():
            idlead = request.POST.get('id_lead')
            estado = request.POST.get('estado')
            evento = request.POST.get('evento')
            operacion = request.POST.get('operacion')
            ev_fecha = evento.split(' - ')[0]
            ev_hora = evento.split(' - ')[1]
            obj_lead = leads.objects.get(pk=idlead)
            obj_evento = eventos.objects.get(hora_evento=ev_hora,
                                             fecha_evento=ev_fecha,
                                             operacion=operacion)
            obj_asist=asistentes_evento.objects.get(asistente=idlead,evento=obj_evento.pk)
            if estado == 'Eliminar':
                obj_asist.delete()
                msj = f'Se elimino el lead de la cita del {evento}'
                historyline_lead.objects.create(
                    lead=obj_lead,
                    observacion=msj,
                    usuario=request.user,
                    fecha=timezone.now()
                )
                obj_lead.estado='Activo'
                obj_lead.save()
            elif obj_asist.estado_cliente != estado:
                obj_asist.estado_cliente = estado
                obj_asist.save()
                msj = f'El lead {estado} la cita del {evento}'
                historyline_lead.objects.create(
                    lead=obj_lead,
                    observacion=msj,
                    usuario=request.user,
                    fecha=timezone.now()
                )
            data = {
                
            }   
            return JsonResponse(data)        

def ajax_changeOP(request):
    if request.method == 'POST':
        if request.is_ajax():
            lead = request.POST.get('id_lead')
            newop = request.POST.get('newop')
            obj_op = User.objects.get(pk=newop)
            obj_lead = leads.objects.get(pk=lead)
            obj_lead.operador = obj_op
            obj_lead.save()
            msj = f'Asignó el lead al operador {obj_op.username}'
            historyline_lead.objects.create(
                lead=obj_lead,
                observacion=msj,
                usuario=request.user,
                fecha=timezone.now()
            )
            return JsonResponse({})           

def ajax_actualizarLead(request):
    if request.method == 'POST':
        if request.is_ajax():
            id_lead=request.POST.get('lead')
            nombre = request.POST.get('nombre')
            celular = request.POST.get('celular')
            telefono = request.POST.get('telefono')
            ciudad = request.POST.get('ciudad')
            direccion = request.POST.get('direccion')
            email = request.POST.get('email')
            estado_civil = request.POST.get('estado_civil')
            fecha_nacimiento = request.POST.get('fecha_nacimiento')
            gestor_capta = request.POST.get('gestor_capta')
            identificacion = request.POST.get('identificacion')
            tipo = request.POST.get('tipo_lead')
            
            obj_lead = leads.objects.get(pk=id_lead)
            verificaciones = ""
            
            verif_cel = leads.objects.filter(celular=celular).exclude(pk=id_lead)
            if verif_cel.exists():
                nombre = verif_cel[0].nombre.upper()
                mensaje = f'Ya existe otro lead con este numero de celular ({nombre})\n'
                verificaciones+=mensaje
            verif_email = leads.objects.filter(email=email).exclude(pk=id_lead)
            if verif_email.exists():
                nombre = verif_email[0].nombre.upper()
                mensaje = f'Ya existe otro lead con este email ({nombre})\n'
                verificaciones+=mensaje
            verif_id = leads.objects.filter(cedula=identificacion).exclude(pk=id_lead)
            if verif_id.exists() and identificacion!='':
                nombre = verif_id[0].nombre.upper()
                mensaje = f'Ya existe otro lead con este numero de identificacion ({nombre})\n'
                verificaciones+=mensaje
            if verificaciones!="":
                data={
                    'success':False,
                    'errors':verificaciones
                }
                return JsonResponse(data)
            else:
                obj_lead.nombre = nombre
                obj_lead.celular = celular
                obj_lead.telefono = telefono
                obj_lead.ciudad = ciudad
                obj_lead.direccion = direccion
                obj_lead.email = email
                obj_lead.estado_civil =  estado_civil
                if fecha_nacimiento!="": obj_lead.fecha_nacimiento = fecha_nacimiento
                obj_lead.gestor_aseginado = asesores.objects.get(pk=gestor_capta)
                obj_lead.cedula = identificacion
                obj_lead.tipo = tipo
                obj_lead.save()
                msj = f'Actualizó los datos del lead'
                historyline_lead.objects.create(
                    lead=obj_lead,
                    observacion=msj,
                    usuario=request.user,
                    fecha=timezone.now()
                )
                return JsonResponse({'success':True})
            
def ajax_gestoresactivos(request):
    if request.method == 'GET':
        if request.is_ajax():
            obj_asesores = asesores.objects.filter(estado='Activo').order_by('nombre').values_list()
            data = {
                'asesores':list(obj_asesores)
            }
            return JsonResponse(data)

def ajax_cerrarEvento(request):
    
    if request.method=='POST':
        if request.is_ajax():
            evento = request.POST.get('evento')
            obj_asisteventos = asistentes_evento.objects.filter(evento__pk=evento)
            error=False
            permiso = check_perms(request,('crm.change_eventos',),raise_exception=False)
            for asistente in obj_asisteventos:
                if asistente.estado_cliente=='Pendiente':
                    error=True
                    msj='No se puede cerrar el evento si hay algun lead en estado pendiente'
                    break
            if not permiso:
                error = True
                msj='No tienes permisos suficientes para cerrar un evento.'
            if error:
                data={
                    'error':error,
                    'msj':msj
                }
            
                
            else:
                obj_evento = eventos.objects.get(pk=evento)
                obj_evento.estado_evento = 'Cerrado'
                obj_evento.usuario_cierra = request.user
                obj_evento.save()
                for asist in obj_asisteventos:
                    id_asist = asist.asistente.pk
                    obj_lead = leads.objects.get(pk=id_asist)
                    obj_lead.estado = 'Activo'
                    obj_lead.save()
                data={
                    'error':error,
                    'msj':'El evento fue cerrado con exito'
                }
            return JsonResponse(data)
   
def ajax_newEvento(request):
    if request.method == 'POST':
        if request.is_ajax():
            operacion = request.POST.get('operacion')
            fecha = request.POST.get('fecha')
            hora = request.POST.get('hora')
            obj_op = Operaciones.objects.get(pk=operacion)
            is_supervisor = check_groups(request,('Supervisor TLMK',),raise_exception=False)
            if is_supervisor:
                try:
                    eventos.objects.create(
                        hora_evento=hora,fecha_evento=fecha,
                        usuario_crea=request.user,operacion=obj_op,
                        estado_evento='Abierto'
                    )
                    data = {
                        'error':False,
                        'title':'Listo',
                        'msj':'Se creo el evento con exito',
                        'type':'alert-success'
                    }
                except IntegrityError:
                    data={
                        'error':True,
                        'title':'Error',
                        'msj':'Ya existe un evento en esta fecha y hora para la operacion seleccionada',
                        'type':'alert-danger'
                    }
                except:
                    data={
                        'error':True,
                        'tile':'Error',
                        'msj':traceback.format_exc()[:200],
                        'type':'alert-danger'
                    }
            else:
                data = {
                    'error':True,
                    'tile':'Error',
                    'msj':'No tienes permisos para crear un nuevo evento',
                    'type':'alert-danger'
                }
            return JsonResponse(data)

def ajax_adminEventos(request):
    if request.method == 'GET':
        if request.is_ajax():
            obj_eventos = eventos.objects.all()
            event_list = []
            i=1
            for event in obj_eventos:
                programados=asistentes_evento.objects.filter(evento=event.pk).aggregate(Count('pk'))
                pendientes=asistentes_evento.objects.filter(evento=event.pk,estado_cliente="Pendiente").aggregate(Count('pk'))
                asistentes=asistentes_evento.objects.filter(evento=event.pk,estado_cliente="Asistio").aggregate(Count('pk'))
                no_asistio=asistentes_evento.objects.filter(evento=event.pk,estado_cliente="No Asistio").aggregate(Count('pk'))
                
                event_list.append(
                    {
                    'id':i,
                    'pk':event.pk,
                    'operacion':str(event.operacion),
                    'id_operacion':event.operacion.pk,
                    'fecha':event.fecha_evento,
                    'hora':event.hora_evento,
                    'programados':programados.get('pk__count'),
                    'pendientes':pendientes.get('pk__count'),
                    'asistio':asistentes.get('pk__count'),
                    'no_asistio':no_asistio.get('pk__count'),
                    'estado':event.estado_evento,
                    }
                )
                i+=1
            data={
                'data':event_list
            }
            return JsonResponse(data)
           
                

urls=[
    path('principal',principal),
    path('leads',leads_view),
    path('manage_leads',admin_leads),
    path('events',eventos_leads),
    path('adminevents',admin_eventos),
    path('ajax/leads',ajax_leads),
    path('ajax/get_comments',ajax_history_lead),
    path('ajax/events',ajax_eventos),
    path('ajax/new_obs/<id_lead>',ajax_newObs),
    path('ajax/changeleadtype',ajax_changeTipo),
    path('ajax/storelead',ajax_changeEstado),
    path('ajax/eventleads',ajax_asistentes_evento),
    path('ajax/changeAsist',ajax_estadoEvento),
    path('ajax/changeOP',ajax_changeOP),
    path('ajax/updateLead',ajax_actualizarLead),
    path('ajax/getasesores',ajax_gestoresactivos),
    path('ajax/close_event',ajax_cerrarEvento),
    path('ajax/new_event',ajax_newEvento),
    path('ajax/admin_event',ajax_adminEventos),
]
