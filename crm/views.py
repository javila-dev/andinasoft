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
from andinasoft.models import clientes, proyectos, empresas, notificaciones_correo, Profiles, asesores
from andinasoft.handlers_functions import envio_notificacion
from andinasoft.shared_models import Adjudicacion, Inmuebles, Vista_Adjudicacion, saldos_adj, titulares_por_adj, timeline, seguimientos
from andina.decorators import group_perm_required, check_project
from crm.models import leads, historyline_lead, Operaciones, eventos, asistentes_evento, historyline_lead, usuario_gestor, ActaReunion, ActaParticipante, CompromisoActa, AdjuntoActa
from crm import forms as crm_forms
import datetime
import json
import math
import traceback
from decimal import Decimal



def _build_reunion_contexto(acta):
    contexto = {
        'reuniones_anteriores': ActaReunion.objects.filter(
            cliente=acta.cliente,
            proyecto=acta.proyecto,
        ).exclude(pk=acta.pk).order_by('-fecha_reunion', '-id_acta')[:10]
        if acta.cliente_id and acta.proyecto_id else []
    }

    if not acta.cliente_id or not acta.proyecto_id:
        contexto['detalle_proyecto_error'] = 'Asocia cliente y proyecto para ver cartera, lote y antecedentes.'
        return contexto

    proyecto_alias = acta.proyecto_id
    cliente_id = acta.cliente_id

    try:
        adjudicaciones = list(
            titulares_por_adj.objects.using(proyecto_alias).filter(
                Q(IdTercero1=cliente_id) |
                Q(IdTercero2=cliente_id) |
                Q(IdTercero3=cliente_id) |
                Q(IdTercero4=cliente_id)
            ).values_list('adj', flat=True)
        )
    except Exception as exc:
        contexto['detalle_proyecto_error'] = f'No fue posible consultar la cartera del proyecto: {exc}'
        return contexto

    if not adjudicaciones:
        contexto['detalle_proyecto_error'] = 'No se encontraron adjudicaciones de este cliente en el proyecto seleccionado.'
        return contexto

    if len(adjudicaciones) > 1:
        contexto['detalle_proyecto_warning'] = 'Este cliente tiene varias adjudicaciones en el proyecto. Se requiere asociar la reunión a una adjudicación específica para mostrar cartera exacta.'
        contexto['adjudicaciones_relacionadas'] = adjudicaciones
        return contexto

    adj_id = adjudicaciones[0]
    vista_adj = Vista_Adjudicacion.objects.using(proyecto_alias).filter(IdAdjudicacion=adj_id).first()
    obj_adj = Adjudicacion.objects.using(proyecto_alias).filter(pk=adj_id).first()
    saldos = saldos_adj.objects.using(proyecto_alias).filter(adj=adj_id)
    inmueble = Inmuebles.objects.using(proyecto_alias).filter(pk=obj_adj.idinmueble).first() if obj_adj else None

    capital_pagado = saldos.aggregate(total=Sum('rcdocapital')).get('total') or 0
    capital_pendiente = saldos.aggregate(total=Sum('saldocapital')).get('total') or 0
    saldos_mora = saldos.filter(saldocuota__gt=0)
    agg_mora = saldos_mora.aggregate(
        dias=Max('diasmora'),
        int_mora=Sum('saldomora'),
        saldo_cuotas=Sum('saldocuota'),
    )
    dias_mora = agg_mora.get('dias') or 0
    int_mora = agg_mora.get('int_mora') or 0
    saldo_cuotas_mora = agg_mora.get('saldo_cuotas') or 0
    total_mora = saldo_cuotas_mora + int_mora
    cuotas_en_mora = saldos_mora.count()
    fecha_sin_pago = saldos_mora.order_by('fecha').values_list('fecha', flat=True).first()

    contexto['detalle_proyecto'] = {
        'adj_id': adj_id,
        'estado': getattr(vista_adj, 'Estado', None),
        'inmueble': getattr(vista_adj, 'Inmueble', None),
        'capital_pagado': capital_pagado,
        'capital_pendiente': capital_pendiente,
        'dias_mora': dias_mora,
        'total_mora': total_mora,
        'cuotas_en_mora': cuotas_en_mora,
        'fecha_sin_pago': fecha_sin_pago,
        'fecha_contrato': getattr(vista_adj, 'FechaContrato', None),
        'proyecto_alias': proyecto_alias,
        'estado_cuenta_url': f'/andinasoftajx/estadodecuenta?proyecto={proyecto_alias}&adj={adj_id}',
    }
    return contexto

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
        if request.POST.get('guardar_resultado'):
            check_perms(request, ('crm.change_actareunion',))
            resultado_form = crm_forms.ActaResultadoForm(request.POST, instance=acta, prefix='resultado')
            if resultado_form.is_valid():
                resultado_form.save()
                return HttpResponseRedirect(f'/crm/actas/{acta.pk}')
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
                avatar = avatar.avatar.image.url if avatar.avatar.image else ''
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
                avatar = avatar.avatar.image.url if avatar.avatar.image else ''
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


def ajax_clientes_proyecto(request):
    if request.method == 'GET':
        proyecto_alias = request.GET.get('proyecto')
        search = (request.GET.get('search') or '').strip()
        if not proyecto_alias:
            return JsonResponse({'error': 'Debes seleccionar un proyecto.'}, status=400)
        if len(search) < 2:
            return JsonResponse({'terceros': []})

        clientes_qs = clientes.objects.filter(
            Q(nombrecompleto__icontains=search) | Q(idTercero__icontains=search)
        ).order_by('nombrecompleto')[:25]
        clientes_map = {cliente.pk: cliente for cliente in clientes_qs}
        if not clientes_map:
            return JsonResponse({'terceros': []})

        relaciones = titulares_por_adj.objects.using(proyecto_alias).filter(
            Q(IdTercero1__in=clientes_map.keys()) |
            Q(IdTercero2__in=clientes_map.keys()) |
            Q(IdTercero3__in=clientes_map.keys()) |
            Q(IdTercero4__in=clientes_map.keys())
        ).values('IdTercero1', 'IdTercero2', 'IdTercero3', 'IdTercero4')

        asociados = set()
        for row in relaciones:
            for field in ('IdTercero1', 'IdTercero2', 'IdTercero3', 'IdTercero4'):
                tercero_id = row.get(field)
                if tercero_id in clientes_map:
                    asociados.add(tercero_id)

        terceros = []
        for tercero_id in sorted(asociados, key=lambda pk: clientes_map[pk].nombrecompleto):
            cliente = clientes_map[tercero_id]
            terceros.append({
                'id': cliente.idTercero,
                'nombre_completo': cliente.nombrecompleto,
                'celular': cliente.celular1,
                'email': cliente.email,
                'ciudad': cliente.ciudad,
            })

        return JsonResponse({'terceros': terceros})

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
           
                


@group_perm_required(('crm.view_actareunion',), raise_exception=True)
def actas_list(request):
    actas = ActaReunion.objects.select_related('cliente', 'proyecto', 'lider_reunion').all()
    filtros = {
        'estado': request.GET.get('estado', ''),
        'responsable': request.GET.get('responsable', ''),
        'proyecto': request.GET.get('proyecto', ''),
    }
    if filtros['estado']:
        actas = actas.filter(estado=filtros['estado'])
    if filtros['responsable']:
        actas = actas.filter(compromisos__responsable_id=filtros['responsable']).distinct()
    if filtros['proyecto']:
        actas = actas.filter(proyecto_id=filtros['proyecto'])
    context = {
        'actas': actas,
        'estados': ActaReunion.ESTADOS,
        'proyectos': proyectos.objects.filter(activo=True).order_by('proyecto'),
        'usuarios': User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username'),
        'filtros': filtros,
    }
    return render(request, 'crm/actas.html', context)


@group_perm_required(('crm.add_actareunion',), raise_exception=True)
def acta_create(request):
    initial = {}
    fecha = request.GET.get('date')
    hora = request.GET.get('time')
    if fecha:
        initial['fecha_reunion'] = fecha
    if hora:
        initial['hora_reunion'] = hora
    form = crm_forms.ProgramarReunionForm(request.POST or None, initial=initial if request.method == 'GET' else None)
    if request.method == 'POST' and form.is_valid():
        acta = form.save(commit=False)
        acta.creado_por = request.user
        acta.estado = 'Programada'
        acta.save()
        return HttpResponseRedirect(f'/crm/actas/{acta.pk}')
    return render(request, 'crm/acta_form.html', {'form': form, 'modo': 'crear'})


@group_perm_required(('crm.change_actareunion',), raise_exception=True)
def acta_edit(request, acta_id):
    acta = ActaReunion.objects.get(pk=acta_id)
    form = crm_forms.ProgramarReunionForm(request.POST or None, instance=acta)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return HttpResponseRedirect(f'/crm/actas/{acta.pk}')
    return render(request, 'crm/acta_form.html', {'form': form, 'modo': 'editar', 'acta': acta})


@group_perm_required(('crm.view_actareunion',), raise_exception=True)
def acta_detail(request, acta_id):
    acta = ActaReunion.objects.select_related('cliente', 'proyecto', 'lider_reunion', 'creado_por').get(pk=acta_id)
    resultado_form = crm_forms.ActaResultadoForm(instance=acta, prefix='resultado')
    compromiso_form = crm_forms.CompromisoActaForm(prefix='compromiso')
    seguimiento_form = crm_forms.SeguimientoCompromisoForm(prefix='seguimiento')
    participante_form = crm_forms.ActaParticipanteForm(prefix='participante')
    adjunto_form = crm_forms.AdjuntoActaForm(prefix='adjunto')

    if request.method == 'POST':
        if request.POST.get('guardar_compromiso'):
            check_perms(request, ('crm.add_compromisoacta',))
            compromiso_form = crm_forms.CompromisoActaForm(request.POST, prefix='compromiso')
            if compromiso_form.is_valid():
                compromiso = compromiso_form.save(commit=False)
                compromiso.acta = acta
                compromiso.creado_por = request.user
                if acta.estado == 'Programada':
                    acta.estado = 'En curso'
                    acta.save(update_fields=['estado'])
                compromiso.save()
                return HttpResponseRedirect(f'/crm/actas/{acta.pk}')
        if request.POST.get('guardar_seguimiento'):
            check_perms(request, ('crm.add_seguimientocompromiso',))
            compromiso_id = request.POST.get('compromiso_id')
            compromiso = CompromisoActa.objects.get(pk=compromiso_id, acta=acta)
            seguimiento_form = crm_forms.SeguimientoCompromisoForm(request.POST, prefix='seguimiento')
            if seguimiento_form.is_valid():
                seguimiento = seguimiento_form.save(commit=False)
                seguimiento.compromiso = compromiso
                seguimiento.usuario = request.user
                seguimiento.save()
                if seguimiento.estado_nuevo:
                    compromiso.estado = seguimiento.estado_nuevo
                if seguimiento.fecha_proxima:
                    compromiso.fecha_compromiso = seguimiento.fecha_proxima
                compromiso.save()
                if acta.estado == 'Programada':
                    acta.estado = 'En curso'
                    acta.save(update_fields=['estado'])
                return HttpResponseRedirect(f'/crm/actas/{acta.pk}#compromiso-{compromiso.pk}')
        if request.POST.get('guardar_participante'):
            check_perms(request, ('crm.add_actaparticipante',))
            participante_form = crm_forms.ActaParticipanteForm(request.POST, prefix='participante')
            if participante_form.is_valid():
                participante = participante_form.save(commit=False)
                participante.acta = acta
                participante.save()
                return HttpResponseRedirect(f'/crm/actas/{acta.pk}#participantes')
        if request.POST.get('guardar_adjunto'):
            check_perms(request, ('crm.add_adjuntoacta',))
            adjunto_form = crm_forms.AdjuntoActaForm(request.POST, request.FILES, prefix='adjunto')
            if adjunto_form.is_valid():
                adjunto = adjunto_form.save(commit=False)
                adjunto.acta = acta
                adjunto.cargado_por = request.user
                adjunto.save()
                return HttpResponseRedirect(f'/crm/actas/{acta.pk}#adjuntos')

    compromisos = acta.compromisos.select_related('responsable', 'creado_por').prefetch_related('seguimientos__usuario').all()
    participantes = acta.participantes.select_related('usuario').all()
    adjuntos = acta.adjuntos.select_related('cargado_por').all()
    contexto_relacion = _build_reunion_contexto(acta)
    context = {
        'acta': acta,
        'compromisos': compromisos,
        'participantes': participantes,
        'adjuntos': adjuntos,
        'resultado_form': resultado_form,
        'compromiso_form': compromiso_form,
        'seguimiento_form': seguimiento_form,
        'participante_form': participante_form,
        'adjunto_form': adjunto_form,
        **contexto_relacion,
    }
    return render(request, 'crm/acta_detail.html', context)



@group_perm_required(('crm.view_actareunion',), raise_exception=True)
def agenda_reuniones(request):
    return render(request, 'crm/agenda_reuniones.html')


@group_perm_required(('crm.view_actareunion',), raise_exception=True)
def ajax_reuniones_calendario(request):
    start = request.GET.get('start')
    end = request.GET.get('end')
    reuniones = ActaReunion.objects.select_related('cliente', 'proyecto', 'lider_reunion').exclude(hora_reunion__isnull=True)
    if start:
        reuniones = reuniones.filter(fecha_reunion__gte=start[:10])
    if end:
        reuniones = reuniones.filter(fecha_reunion__lte=end[:10])

    colors = {
        'Programada': '#2563eb',
        'En curso': '#d97706',
        'Realizada': '#15803d',
        'Cancelada': '#b91c1c',
    }
    eventos = []
    for reunion in reuniones:
        inicio = reunion.inicio_programado()
        fin = reunion.fin_programado()
        if not inicio or not fin:
            continue
        eventos.append({
            'id': reunion.pk,
            'title': reunion.titulo_calendario(),
            'start': inicio.isoformat(),
            'end': fin.isoformat(),
            'url': f'/crm/actas/{reunion.pk}',
            'backgroundColor': colors.get(reunion.estado, '#475569'),
            'borderColor': colors.get(reunion.estado, '#475569'),
            'extendedProps': {
                'estado': reunion.estado,
                'asunto': reunion.asunto,
                'lider': reunion.lider_reunion.get_full_name() or reunion.lider_reunion.username,
            }
        })
    return JsonResponse(eventos, safe=False)

@group_perm_required(('crm.view_actareunion',), raise_exception=True)
def ajax_adjudicacion_historial(request, acta_id):
    acta = ActaReunion.objects.select_related('cliente', 'proyecto').get(pk=acta_id)
    contexto_relacion = _build_reunion_contexto(acta)
    detalle = contexto_relacion.get('detalle_proyecto')
    if not detalle:
        mensaje = contexto_relacion.get('detalle_proyecto_warning') or contexto_relacion.get('detalle_proyecto_error') or 'No hay una adjudicacion unica asociada a esta reunion.'
        return JsonResponse({'ok': False, 'message': mensaje}, status=400)

    proyecto_alias = detalle['proyecto_alias']
    adj_id = detalle['adj_id']
    timeline_adj = timeline.objects.using(proyecto_alias).filter(adj=adj_id).order_by('-fecha', '-id_line')[:50]
    seguimientos_adj = seguimientos.objects.using(proyecto_alias).filter(adj=adj_id).order_by('-fecha', '-id_seg')[:50]

    return JsonResponse({
        'ok': True,
        'adj': adj_id,
        'timeline': [
            {
                'fecha': item.fecha.strftime('%Y-%m-%d') if item.fecha else '',
                'usuario': item.usuario or '',
                'accion': item.accion or '',
            }
            for item in timeline_adj
        ],
        'seguimientos': [
            {
                'fecha': item.fecha.strftime('%Y-%m-%d') if item.fecha else '',
                'usuario': item.usuario or '',
                'tipo_seguimiento': item.tipo_seguimiento or '',
                'forma_contacto': item.forma_contacto or '',
                'respuesta_cliente': item.respuesta_cliente or '',
                'valor_compromiso': item.valor_compromiso or 0,
                'fecha_compromiso': item.fecha_compromiso or '',
            }
            for item in seguimientos_adj
        ],
    })


@group_perm_required(('crm.add_adjuntoacta',), raise_exception=True)
def ajax_subir_audio_acta(request, acta_id):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'message': 'Metodo no permitido.'}, status=405)

    acta = ActaReunion.objects.get(pk=acta_id)
    archivo = request.FILES.get('audio')
    if not archivo:
        return JsonResponse({'ok': False, 'message': 'Debes adjuntar un archivo de audio.'}, status=400)

    descripcion = (request.POST.get('descripcion') or '').strip()
    form = crm_forms.AdjuntoActaForm(
        data={'tipo': 'Audio', 'descripcion': descripcion or 'Grabacion de reunion'},
        files={'archivo': archivo},
    )
    if not form.is_valid():
        return JsonResponse({'ok': False, 'message': 'No fue posible guardar el audio.', 'errors': form.errors}, status=400)

    adjunto = form.save(commit=False)
    adjunto.acta = acta
    adjunto.cargado_por = request.user
    adjunto.save()

    return JsonResponse({
        'ok': True,
        'adjunto': {
            'id': adjunto.pk,
            'tipo': adjunto.tipo,
            'descripcion': adjunto.descripcion or 'Sin descripcion',
            'archivo_url': adjunto.archivo.url,
            'cargado_por': request.user.get_full_name() or request.user.username,
            'created_at': timezone.localtime(adjunto.created_at).strftime('%Y-%m-%d %H:%M'),
        }
    })


@group_perm_required(('crm.view_compromisoacta',), raise_exception=True)
def mis_compromisos(request):
    compromisos = CompromisoActa.objects.select_related('acta', 'responsable', 'acta__cliente', 'acta__proyecto')
    vista = request.GET.get('vista', 'mios')
    if not request.user.is_superuser and vista == 'mios':
        compromisos = compromisos.filter(responsable=request.user)
    estado = request.GET.get('estado', '')
    if estado:
        compromisos = compromisos.filter(estado=estado)
    if vista == 'vencidos':
        compromisos = compromisos.filter(fecha_compromiso__lt=timezone.localdate()).exclude(estado__in=['Cumplido', 'Cancelado'])
    context = {
        'compromisos': compromisos.order_by('fecha_compromiso', 'estado'),
        'estados': CompromisoActa.ESTADOS,
        'estado_actual': estado,
        'vista': vista,
        'hoy': timezone.localdate(),
    }
    return render(request, 'crm/mis_compromisos.html', context)


urls=[
    path('principal',principal),
    path('leads',leads_view),
    path('manage_leads',admin_leads),
    path('events',eventos_leads),
    path('adminevents',admin_eventos),
    path('actas', actas_list, name='crm_actas'),
    path('agenda-reuniones', agenda_reuniones, name='crm_agenda_reuniones'),
    path('actas/nueva', acta_create, name='crm_acta_nueva'),
    path('actas/<int:acta_id>/editar', acta_edit, name='crm_acta_editar'),
    path('actas/<int:acta_id>', acta_detail, name='crm_acta_detalle'),
    path('compromisos/mios', mis_compromisos, name='crm_mis_compromisos'),
    path('ajax/leads',ajax_leads),
    path('ajax/clientes-proyecto', ajax_clientes_proyecto, name='crm_ajax_clientes_proyecto'),
    path('ajax/reuniones-calendario', ajax_reuniones_calendario, name='crm_ajax_reuniones_calendario'),
    path('ajax/actas/<int:acta_id>/adjudicacion-historial', ajax_adjudicacion_historial, name='crm_ajax_adjudicacion_historial'),
    path('ajax/actas/<int:acta_id>/subir-audio', ajax_subir_audio_acta, name='crm_ajax_subir_audio_acta'),
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
