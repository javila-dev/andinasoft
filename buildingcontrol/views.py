from django import forms as django_forms
from django.shortcuts import render
from django.http import HttpResponseRedirect, JsonResponse, HttpResponse, FileResponse
from django.urls import path
from django.core.exceptions import PermissionDenied
from django.db import models
from django.db.models import Avg, Max, Min, Sum, Q, F, Case, When, Value, Subquery, OuterRef, Func
from django.db.models.functions import Coalesce
from django.core import serializers
from django.conf import settings
from django.template.loader import render_to_string
from crispy_forms.layout import Layout, Fieldset, ButtonHolder, Submit, Row, Column, Field, Div, HTML
from crispy_forms.bootstrap import FieldWithButtons, StrictButton, FormActions, PrependedText, PrependedAppendedText, TabHolder, Tab
from buildingcontrol import forms
from buildingcontrol.models import (contratos,items_contrato,productos_servicios,proveedores,
                                    proveedores,tiposobra,actas_contratos,items_recibidos,unidades_medida,
                                    otrosi,pagos_obras, bitacora, fotos_bitacora,retenciones,requisiciones,
                                    items_requisiciones,parametros)
from andina.decorators import check_perms
from andinasoft.models import proyectos, Pagos, Facturas, empresas, notificaciones_correo, ItemsInforme
from andinasoft.forms import form_pagar
from andinasoft.handlers_functions import envio_notificacion
from andina.decorators import group_perm_required, check_project
import datetime
import json
import math
from decimal import Decimal


# Create your views here.

@group_perm_required(('buildingcontrol.add_contratos',),raise_exception=True)
def crear_contrato(request):
    if request.method == 'POST':
        proveedor = request.POST.get('proveedorid')
        proyecto = request.POST.get('proyecto')
        empresa_contrata = request.POST.get('empresa_contrata')
        fecha_inicio = request.POST.get('fecha_inicio')
        fecha_fin = request.POST.get('fecha_fin')
        valor_contrato = request.POST.get('valor')
        porcentaje_canje = request.POST.get('canje')
        anticipo = request.POST.get('anticipo')
        descripcion = request.POST.get('descripcion_contrato')
        retencion = request.POST.get('retenciones')
        items_list = request.POST.getlist('item_obra')
        cantidad_list = request.POST.getlist('cantidad_item')
        valor_list = request.POST.getlist('valor_item')
        total_list = request.POST.getlist('total_item')
        tipos_obra= request.POST.getlist('obraItem')
        obj_proyecto = proyectos.objects.get(pk=proyecto)
        a = request.POST.get('a')
        i = request.POST.get('i')
        u = request.POST.get('u')
        
        aiu = request.POST.get('aiu')
        iva = request.POST.get('iva')
        costo_total = request.POST.get('total_acta')
        costo_total = costo_total.replace(',','')
        costo_total = float(costo_total)
        req_cruce = request.POST.get('req_cruce')
        valor_total = 0
        for total in total_list:
            valor_total += float(total.replace(',',''))
                
        contratos.objects.create(
            proveedor=proveedores.objects.get(pk=proveedor),
            proyecto=proyectos.objects.get(pk=proyecto),
            fecha_creacion=datetime.date.today(),
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            usuario_crea=request.user,
            porcentaje_canje=porcentaje_canje,
            anticipo=anticipo,
            valor=valor_total,
            estado='Pendiente',
            descripcion=descripcion,
            empresa_contrata=empresas.objects.get(Nit=empresa_contrata),
            retencion=retenciones.objects.get(valor=retencion),
            a=a,
            i=i,
            u=u,
            aiu = aiu,
            iva = iva,
            total_costo=costo_total
        )
        obj_contrato = contratos.objects.last()
        for i in range(0,len(items_list)):
            items_contrato.objects.create(
                item=productos_servicios.objects.get(pk=items_list[i]),
                cantidad=cantidad_list[i],
                valor=valor_list[i],
                total=total_list[i].replace(',',''),
                contrato=obj_contrato,
                tipo_obra=tiposobra.objects.get(pk=tipos_obra[i])
        )
        
        if req_cruce != "":
            obj_req = requisiciones.objects.get(pk=req_cruce)
            obj_req.orden_cruce = obj_contrato
            obj_req.save()
        
        notificaciones = notificaciones_correo.objects.get(identificador='Creacion de orden proyectos')
        
        for usuario in notificaciones.users_to_send.all():
            if check_project(request,obj_proyecto.proyecto,raise_exception=False):
                mensaje = f'''Hola {usuario.first_name}, te informamos que {request.user.first_name} ha creado una orden en 
                el modulo de proyectos al proveedor {proveedores.objects.get(pk=proveedor).nombre.upper()} por ${valor_total:,.02f}'''
                asunto = 'Se ha creado una nueva Orden | Proyectos'
                correo = [usuario.email,]
                envio_notificacion(mensaje,asunto,correo)
            else: pass
        
        return HttpResponseRedirect('/buildingcontrol/unaprovedcontracts')
    obj_productos = productos_servicios.objects.all()
    obj_proveedores = proveedores.objects.all().order_by('nombre')
    contract_number = contratos.objects.last()
    if contract_number is None: contract_number=1
    else: contract_number = contract_number.pk+1
    context={
        'form':forms.formContrato(initial={
            'idcontrato':contract_number
            }),
        'productos':obj_productos,
        'proveedores':obj_proveedores,
        'tipos_obra': tiposobra.objects.all().order_by('nombre_tipo'),
        'requisiciones':requisiciones.objects.filter(estado='Aprobado',orden_cruce__isnull=True)
    }
    return render(request,'building/nuevo_contrato.html',context)

@group_perm_required(('buildingcontrol.add_actas_contratos',),raise_exception=True)
def crear_acta(request,contrato):
    if request.method == 'POST':
        nro_acta = request.POST.get('idacta')
        anticipo_amortizado = request.POST.get('vr_anticipo')
        anticipo_amortizado=anticipo_amortizado.replace(',','')
        canje_efectuado = request.POST.get('vr_canje')
        canje_efectuado = canje_efectuado.replace(',','')
        
        aiu = request.POST.get('vr_aiu')
        aiu = aiu.replace(',','')
        iva = request.POST.get('vr_iva')
        iva = iva.replace(',','')
        retefte = request.POST.get('vr_retenciones')
        retefte = retefte.replace(',','')
        
        items_list = request.POST.getlist('item_obra')
        cantidad_list = request.POST.getlist('cantidad_item')
        valor_list = request.POST.getlist('valor_item')
        total_list = request.POST.getlist('total_item')
                
        actas_contratos.objects.create(
            contrato=contratos.objects.get(pk=contrato),
            num_acta=nro_acta,
            canje_efectuado=canje_efectuado,
            anticipo_amortizado=anticipo_amortizado,
            usuario_crea=request.user,
            fecha_acta=datetime.date.today(),
            retencion_efectuada=retefte,
            aiu = aiu,
            iva = iva
        )
        
        obj_acta = actas_contratos.objects.last()
        
        for i in range (0,len(items_list)):
            items_recibidos.objects.create(
                acta=obj_acta,
                item=items_contrato.objects.get(contrato=contrato,
                                                pk=items_list[i]),
                cantidad=cantidad_list[i]
            )
        notificaciones = notificaciones_correo.objects.get(identificador='Creacion acta de recibido')
        
        for usuario in notificaciones.users_to_send.all():
            if check_project(request,obj_acta.contrato.proyecto.proyecto,raise_exception=False):
                mensaje = f'''Hola {usuario.first_name}, te informamos que {request.user.first_name} ha creado una acta de recibido en 
                el modulo de proyectos al contrato {contrato} del proveedor {obj_acta.contrato.proveedor.nombre.upper()}'''
                asunto = 'Se ha creado una nueva Acta de recibido | Proyectos'
                correo = [usuario.email,]
                envio_notificacion(mensaje,asunto,correo)
            else: pass
        
        return HttpResponseRedirect('/buildingcontrol/allcontractprogress')
        
    obj_contrato=contratos.objects.get(pk=contrato)
    obj_actas=actas_contratos.objects.filter(contrato=contrato).count()
    recibidos = items_recibidos.objects.filter(item=OuterRef('pk'),
                                    acta__contrato=contrato,acta__estado='Aprobado'
                                ).values('item')
    total_recibidos = recibidos.annotate(total=Sum('cantidad')).values('total')
    items = items_contrato.objects.filter(
                Q(otrosi__estado='Aprobado')|Q(otrosi__isnull=True),contrato=contrato
                ).annotate(contratados=Sum('cantidad',
                    )
                ).annotate(
                    recibidos=Sum(Subquery(total_recibidos[:1],
                                output_field=models.DecimalField(decimal_places=2)))
                )
    form = forms.formActaRecibido(initial={
        'idacta':obj_actas+1,
        'proveedorid':obj_contrato.proveedor.pk,
        'nombreproveedor':obj_contrato.proveedor.nombre,
        'proyecto':obj_contrato.proyecto.proyecto,
        'canje':obj_contrato.porcentaje_canje,
        'anticipo':obj_contrato.anticipo,
        'fecha_contrato':obj_contrato.fecha_creacion,
        'descripcion_contrato':obj_contrato.descripcion,
        'retenciones':obj_contrato.retencion,
        'empresa_contrata':obj_contrato.empresa_contrata.nombre,
        'iva':obj_contrato.iva,
        'a':obj_contrato.a,
        'i':obj_contrato.i,
        'u':obj_contrato.u,
        'aiu':obj_contrato.aiu
    })
    alerta={}
    actas_del_contrato = actas_contratos.objects.filter(contrato=contrato)
    for acta in actas_del_contrato: 
        if acta.estado == 'Pendiente':
            alerta = {
                'show':1,
                'redirect':1,
                'href':'/buildingcontrol/allcontractprogress',
                'title':'Error',
                'message':'Este contrato tiene un acta pendiente por aprobar, no puedes crear una nueva hasta que todo se encuentre aprobado.'
            }
            break
    if obj_contrato.estado!='Aprobado':
        alerta = {
            'show':1,
            'redirect':1,
            'href':'/buildingcontrol/allcontractprogress',
            'title':'Error',
            'message':'Esta orden no se encuentra aprobada, por lo tanto no se pueden agregar actas de avance'
        }
    
    context={
        'form':form,
        'contrato':obj_contrato,
        'nro_acta':obj_actas+1,
        'items_contrato':items,
        'alerta':alerta
    }
    return render(request,'building/acta_recibido.html',context)

@group_perm_required(('buildingcontrol.view_contratos',),raise_exception=True)
def contratos_aprobados(request):
    obj_contratos = contratos.objects.all()
    
    recibidos = items_recibidos.objects.filter(acta__contrato=OuterRef('pk'),acta__estado='Aprobado' 
                                        ).values('acta__contrato')
    
    total_recibidos = recibidos.annotate(total=Sum(F('cantidad')*F('item__valor'),output_field=models.DecimalField())
                                         ).values('total')
    adicionales = otrosi.objects.filter(contrato=OuterRef('pk'),estado='Aprobado').values('contrato')
    total_adicionales = adicionales.annotate(total=Sum('total_otrosi')).values('total')
    rte_adicionales = adicionales.annotate(total=Sum(F('valor')*(1+F('aiu')/100)*F('rte')/100,
                                           output_field=models.DecimalField())).values('total')
    canje_adicionales = adicionales.annotate(total=Sum(F('total_otrosi')*F('canje')/100,
                                                       output_field=models.DecimalField())).values('total')
    valor_pagado = pagos_obras.objects.filter(contrato_asociado=OuterRef('pk')).values('contrato_asociado')
    total_pagado = valor_pagado.annotate(total=Sum('pago__valor')).values('total')
    print('entra')
    
    obj_contratos_activos = contratos.objects.filter(estado='Aprobado',
        ).annotate(recibido=Subquery(total_recibidos[:1])+Sum(F('actas_contratos__aiu')+F('actas_contratos__iva'),
                                                              output_field=models.DecimalField()),
                   adicionales=Subquery(total_adicionales[:1]),
                   canje_adicionales=Coalesce(Subquery(canje_adicionales[:1]),0),
                   rte_adicionales=Coalesce(Subquery(rte_adicionales[:1]),0),
                   pagado=Subquery(total_pagado[:1]),
                   total_orden=Coalesce(Subquery(total_adicionales[:1],output_field=models.DecimalField()),
                                        0)+Coalesce(F('total_costo'),0,output_field=models.DecimalField()),
                   pago_efectivo=Coalesce(
                       F('total_orden')-
                       ((F('valor')*(1+(F('aiu')/100)))*F('retencion__valor')/100)-
                       F('rte_adicionales')-
                       F('canje_adicionales')-
                       Coalesce(F('porcentaje_canje')*F('total_costo')/100,0,output_field=models.DecimalField()), 
                       0,output_field=models.DecimalField())
            )
    form=forms.formSoporteContratos
    context = {
        'contratos_activos':obj_contratos_activos,
        'form':form,
        'form_pagos':form_pagar
    }
    if request.method == 'POST':
        form = forms.formSoporteContratos(request.POST,request.FILES)
        if form.is_valid():
            check_perms(request,('buildingcontrol.add_contratos',))
            contrato = request.POST.get('contrato')
            docs = request.FILES.get('soporte_contrato')    
            obj_contrato = contratos.objects.get(pk=contrato)
            obj_contrato.contrato_docs = docs
            obj_contrato.save()
            
            alert = {
                'alert':1,
                'title':'!Hecho!',
                'message':f'Los soportes del Contrato {contrato} fueron cargados con exito',
                'class':'alert-success'
            }
            
            context['topalert']=alert
        else:
            alert = {
                'alert':1,
                'title':'!Error!',
                'message':'El archivo a cargar debe ser pdf',
                'class':'alert-danger'
            }
            
            context['topalert']=alert
        if request.POST.get('btnAbono'):
            fecha = request.POST.get('fecha_causacion')
            valor = request.POST.get('valorpago')
            empresa = request.POST.get('empresapago')
            cuenta = request.POST.get('formapago')
            contrato = request.POST.get('contrato')
            
            obj_contrato = contratos.objects.get(pk=contrato)
            obj_contratos_activos.filter(pk=contrato)
            obj_adicionales = otrosi.objects.filter(contrato=contrato
                        ).aggregate(Total=Coalesce(
                    Sum(F('valor')*F('canje')/100,output_field=models.DecimalField()),0))
            canje_adicionales = obj_adicionales['Total']
            recibido = obj_contratos_activos.filter(pk=contrato)[0].recibido
            pagado = obj_contratos_activos.filter(pk=contrato)[0].pagado
            if recibido is None: recibido = 0
            if pagado is None: pagado = 0
            valor_control = Decimal(obj_contrato.valor*obj_contrato.porcentaje_canje/100)+canje_adicionales+Decimal(obj_contrato.valor*obj_contrato.anticipo/100)
            diferencia_control = pagado + int(valor) - recibido
            override_control = parametros.objects.get(parametro='Override abonar a orden')
            
            if (diferencia_control > valor_control) and override_control.check==0:
                alert = {
                'alert':1,
                'title':'!Error!',
                'message':f'El valor pagado supera el tope permitido ({obj_contrato.porcentaje_canje}%), con relación al monto recibido de la orden',
                'class':'alert-danger'
                }
                
                context['topalert']=alert
            else:
                obj_contrato = contratos.objects.get(pk=contrato)
                obj_pagos = pagos_obras.objects.filter(contrato_asociado=contrato)
                fact_anticip = f'AN-OP{contrato}-{obj_pagos.count()+1}'
                today=datetime.date.today()
                Facturas.objects.create(estado='Tesoreria',valor=valor,empresa=empresa,
                                        fecharadicado=today,nrofactura=fact_anticip,
                                        fechafactura=today,idtercero=obj_contrato.proveedor.pk,
                                        nombretercero=obj_contrato.proveedor.nombre,pago_neto=valor,
                                        fechavenc=today,nrocausa=fact_anticip,fechacausa=today,
                                        origen='Proyectos')
                obj_factura = Facturas.objects.last()
                Pagos.objects.create(valor=valor,nroradicado=obj_factura.pk,empresapago=empresa,
                                    fechapago=fecha,formapago=cuenta)
                obj_pago = Pagos.objects.last()
                pagos_obras.objects.create(pago=obj_pago,contrato_asociado=obj_contrato)
                if override_control.check==1:
                    override_control.check=0
                    override_control.save()
                alert = {
                    'alert':1,
                    'title':'!Listo!',
                    'message':'El pago fue adicionado con exito',
                    'class':'alert-success'
                }
                
                context['topalert']=alert
        if request.POST.get('btnAsociar'):
            contrato = request.POST.get('contrato')
            idpago = request.POST.get('idpago')
            
            obj_contrato = contratos.objects.get(pk=contrato)
            obj_contratos_activos.filter(pk=contrato)
            obj_adicionales = otrosi.objects.filter(contrato=contrato
                        ).aggregate(Total=Coalesce(
                    Sum(F('valor')*F('canje')/100,output_field=models.DecimalField()),0))
            canje_adicionales = obj_adicionales['Total']
            recibido = obj_contratos_activos.filter(pk=contrato)[0].recibido
            pagado = obj_contratos_activos.filter(pk=contrato)[0].pagado
            if recibido is None: recibido = 0
            if pagado is None: pagado = 0
            valor = Pagos.objects.get(pk=idpago).valor
            valor_control = Decimal(obj_contrato.valor*obj_contrato.porcentaje_canje/100)+canje_adicionales+Decimal(obj_contrato.valor*obj_contrato.anticipo/100)
            diferencia_control = pagado + valor - recibido
            if diferencia_control > valor_control:
                alert = {
                'alert':1,
                'title':'!Error!',
                'message':f'El valor pagado supera el tope permitido ({obj_contrato.porcentaje_canje}%), con relación al monto recibido de la orden',
                'class':'alert-danger'
                }
                
                context['topalert']=alert
            
            else:
                pagos_obras.objects.create(
                    pago=Pagos.objects.get(pk=idpago),
                    contrato_asociado=contratos.objects.get(pk=contrato))
                alert = {
                    'alert':1,
                    'title':'!Listo!',
                    'message':f'El pago fue relacionado al contrato {contrato}',
                    'class':'alert-success'
                }
                
                context['topalert']=alert
        
          
    elif request.method == 'GET':
        if request.is_ajax():
            idpago = request.GET.get('idpago')
            info_pago = Pagos.objects.get(pk=idpago)
            info_factura = Facturas.objects.get(pk=info_pago.nroradicado)
            text = f"Pago realizado a {info_factura.nombretercero} el {info_pago.fechapago} por ${info_pago.valor:,}" 
            if pagos_obras.objects.filter(pago=idpago).exists():
                text='Este pago ya se encuentra asociado'
            data = {'pago':text}
            return JsonResponse(data)
        
    return render(request,'building/contratos_aprobados.html',context)

@group_perm_required(('buildingcontrol.view_contratos',),raise_exception=True)
def contratos_sin_aprobar(request):
    obj_contratos = contratos.objects.filter(estado='Pendiente')
    context={
        'contratos_sinaprobar':obj_contratos
    }
    return render(request,'building/contratos_sinaprobar.html',context)

@group_perm_required(('buildingcontrol.change_contratos',),raise_exception=True)
def ver_contrato(request,contrato):
    alert={}
    context={}
    obj_contrato = contratos.objects.get(pk=contrato)
    detalle_contrato = items_contrato.objects.filter(contrato=contrato)
    if request.method == 'POST':
        if request.POST.get('btnModificar'):
            proveedor = request.POST.get('proveedorid')
            empresa_contrata = request.POST.get('empresa_contrata')
            proyecto = request.POST.get('proyecto')
            fecha_inicio = request.POST.get('fecha_inicio')
            fecha_fin = request.POST.get('fecha_fin')
            valor_contrato = request.POST.get('valor')
            porcentaje_canje = request.POST.get('canje')
            anticipo = request.POST.get('anticipo')
            descripcion = request.POST.get('descripcion_contrato')
            retencion = request.POST.get('retenciones')
            items_list = request.POST.getlist('item_obra')
            cantidad_list = request.POST.getlist('cantidad_item')
            valor_list = request.POST.getlist('valor_item')
            total_list = request.POST.getlist('total_item')
            tipos_obra = request.POST.getlist('obraItem')
            iva = request.POST.get('iva')
            a = request.POST.get('a')
            i = request.POST.get('i')
            u = request.POST.get('u')
            aiu = request.POST.get('aiu')
            costo_total = request.POST.get('total_acta')
            costo_total = float(costo_total.replace(',',''))
            
            valor_total = 0
            for total in total_list:
                valor_total += float(total.replace(',',''))

            obj_contrato.proveedor=proveedores.objects.get(pk=proveedor)
            obj_contrato.proyecto=proyectos.objects.get(pk=proyecto)
            obj_contrato.fecha_inicio=fecha_inicio
            obj_contrato.fecha_fin=fecha_fin
            obj_contrato.usuario_crea=request.user
            obj_contrato.porcentaje_canje=porcentaje_canje
            obj_contrato.anticipo=anticipo
            obj_contrato.valor=valor_total
            obj_contrato.descripcion=descripcion
            obj_contrato.empresa_contrata=empresas.objects.get(Nit=empresa_contrata)
            obj_contrato.retencion=retenciones.objects.get(valor=retencion)
            obj_contrato.aiu = aiu
            obj_contrato.a=a
            obj_contrato.i=i
            obj_contrato.u=u
            obj_contrato.iva = iva
            obj_contrato.total_costo=costo_total
            obj_contrato.save()
            
            for item in detalle_contrato:
                item.delete()
                
            for i in range(0,len(items_list)):
                items_contrato.objects.create(
                    item=productos_servicios.objects.get(pk=items_list[i]),
                    cantidad=cantidad_list[i],
                    valor=valor_list[i],
                    total=total_list[i].replace(',',''),
                    contrato=obj_contrato,
                    tipo_obra=tiposobra.objects.get(pk=tipos_obra[i])
            )
            alert = {
                'alert':1,
                'title':'!Hecho!',
                'message':f'El contrato {contrato} fué modificado con exito',
                'class':'alert-success'
            }
            obj_contrato = contratos.objects.get(pk=contrato)
            detalle_contrato = items_contrato.objects.filter(contrato=contrato)
        if request.POST.get('btnAprobar'):
            check_perms(request,('buildingcontrol.delete_contratos',))
            obj_contrato.estado='Aprobado'
            obj_contrato.usuario_aprueba=request.user
            obj_contrato.save()
            
            notificaciones = notificaciones_correo.objects.get(identificador='Aprobar orden')
            for usuario in notificaciones.users_to_send.all():
                if check_project(request,obj_contrato.proyecto.proyecto,raise_exception=False):
                    mensaje = f'''Hola {usuario.first_name}, te informamos que {request.user.first_name} ha aprobado la orden {contrato} en 
                    el modulo de proyectos, del proveedor {obj_contrato.proveedor.nombre.upper()} por valor de ${obj_contrato.valor:,.02f}'''
                    asunto = 'Se ha Aprobado una orden | Proyectos'
                    correo = [usuario.email,]
                    envio_notificacion(mensaje,asunto,correo)
                else: pass
            return HttpResponseRedirect('/buildingcontrol/aprovedcontracts')
        
    obj_productos = productos_servicios.objects.all()
    obj_proveedores = proveedores.objects.all().order_by('nombre')
    
    lista_detalle = []
    for item in detalle_contrato:
        recibidos = items_recibidos.objects.filter(item=item
                            ).aggregate(total=Sum('cantidad'))
        recibidos = recibidos['total']
        if recibidos is None: recibidos=0
        lista_detalle.append(
            {
                'item':item.item.pk,
                'nombre':item.item.nombre,
                'unidad':item.item.unidad.nombre,
                'cantidad':float(item.cantidad),
                'vr_unit':float(item.valor),
                'vr_total':f'{float(item.total):,}',
                'recibidos':float(recibidos),
                'obra':item.tipo_obra.pk,
                'nombre_obra':item.tipo_obra.nombre_tipo
            }
        )
    json_detalle = json.dumps(lista_detalle)
    fecha_ini=datetime.datetime.strftime(obj_contrato.fecha_inicio,'%Y-%m-%d')
    fecha_fin=datetime.datetime.strftime(obj_contrato.fecha_fin,'%Y-%m-%d')
    form = forms.formContrato(initial={
        'idcontrato':contrato,
        'proveedorid' : obj_contrato.proveedor.pk,
        'nombreproveedor' : obj_contrato.proveedor.nombre,
        'proyecto' : obj_contrato.proyecto.proyecto,
        'fecha_inicio' : fecha_ini,
        'fecha_fin' : fecha_fin,
        'valor' : f'{obj_contrato.valor:,}',
        'canje' : obj_contrato.porcentaje_canje,
        'anticipo' : obj_contrato.anticipo,
        'descripcion_contrato':obj_contrato.descripcion,
        'empresa_contrata':obj_contrato.empresa_contrata,
        'retenciones':obj_contrato.retencion.valor,
        'a':obj_contrato.a,
        'i':obj_contrato.i,
        'u':obj_contrato.u,
        'aiu':obj_contrato.aiu,
        'iva':obj_contrato.iva
    })
    if obj_contrato.estado == 'Aprobado':
        form.helper[2].update_attributes(css_class='col-1 m-0 p-0')
        form.helper.layout[2][1]=Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Descripcion</p>'),
                    css_class='col-4 m-0'
                )
        form.helper.layout[2][3]=Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Cantidades</p>'),
                    css_class='col-2 m-0'
                )
        form.helper.layout.pop(7)
        form.helper.layout.pop(4)
        form.helper['proyecto'].update_attributes(readonly=True,disabled=True)
        form.helper['empresa_contrata'].update_attributes(readonly=True,disabled=True)
        form.helper['iva'].update_attributes(readonly=True,disabled=True)
        form.helper['aiu'].update_attributes(readonly=True,disabled=True)
        form.helper['a'].update_attributes(readonly=True,disabled=True)
        form.helper['i'].update_attributes(readonly=True,disabled=True)
        form.helper['u'].update_attributes(readonly=True,disabled=True)
        form.helper['tipo_obra'].update_attributes(readonly=True,disabled=True)
        form.helper['fecha_inicio'].update_attributes(readonly=True,disabled=True)
        form.helper['fecha_fin'].update_attributes(readonly=True,disabled=True)
        form.helper['anticipo'].update_attributes(readonly=True,disabled=True)
        form.helper['canje'].update_attributes(readonly=True,disabled=True)
        form.helper['descripcion_contrato'].update_attributes(readonly=True,disabled=True)
        obj_actas = actas_contratos.objects.filter(contrato=contrato).annotate(total=Sum(
                                F('items_recibidos__cantidad')*F('items_recibidos__item__valor')
                            ))
        actas_html = ''
        total_recibido =0
        for acta in obj_actas:
            actas_html+=f'''<tr class="text-center">
                    <td><a href="/buildingcontrol/viewprogress/{acta.pk}">
                        {acta.num_acta}</td>
                    <td>{acta.fecha_acta}</td>
                    <td>{acta.usuario_crea.username}</td>
                    <td>{acta.estado}</td>
                    <td>{(acta.total+acta.aiu+acta.iva):,.0f}</td>
                </tr>'''
            total_recibido += acta.total+acta.aiu+acta.iva
        total_recibido = f'{total_recibido:,.0f}'
        adicionales = ''
        total_adicionales = 0
        canje_adicionales = 0
        rte_adicionales = 0
        aiu_adicionales = 0
        iva_adicionales = 0
        subtotal_adicionales= 0
        obj_adicionales = otrosi.objects.filter(contrato=contrato)
        for adicional in obj_adicionales:
            adicionales+=f'''<tr class="text-center">
                    <td><a href="/buildingcontrol/viewotrosi/{adicional.pk}">
                        {adicional.num_otrosi}</td>
                    <td>{adicional.fecha_crea}</td>
                    <td>{adicional.usuario_crea.username}</td>
                    <td>{adicional.estado}</td>
                    <td>{adicional.canje:,.2f}</td>
                    <td>{adicional.total_otrosi:,.0f}</td>
                </tr>'''
            total_adicionales+=adicional.total_otrosi
            subtotal_adicionales+=adicional.valor
            aiu_adicionales += adicional.valor*adicional.aiu/100
            if aiu_adicionales==0: iva_adicionales += adicional.valor*adicional.iva/100
            else: iva_adicionales += aiu_adicionales*adicional.iva/100 
            canje_adicionales+=adicional.canje*adicional.total_otrosi/Decimal(100)
            rte_adicionales+=adicional.valor*(1+adicional.aiu/100)*adicional.rte/100
        pagos_html=''
        pagos_efectuados = 0
        obj_pagos = pagos_obras.objects.filter(contrato_asociado=contrato)
        for pago in obj_pagos:
            pagos_html+=f'''<tr class="text-center">
                    <td>{pago.pago.pk}</td>
                    <td>{pago.pago.fechapago}</td>
                    <td><a href="/docs_andinasoft/docs_radicados/Soportes_Pago/Soporte_Pago_{pago.pago.pk}_Radicado_{pago.pago.nroradicado}.pdf">Soporte</a> </td>
                    <td>{pago.pago.valor:,.0f}</td>
                </tr>'''
            pagos_efectuados+=pago.pago.valor
        pagos_efectuados=f'{pagos_efectuados:,.0f}'
        
        subtotal_inicial = obj_contrato.valor
        total_inicial = obj_contrato.total_costo
        aiu_inicial = obj_contrato.aiu*obj_contrato.valor/100
        u_inicial = obj_contrato.u*obj_contrato.valor/100
        if u_inicial == 0: iva_inicial = obj_contrato.valor*obj_contrato.iva/100
        else: iva_inicial = u_inicial*obj_contrato.iva/100
        canje_inicial = obj_contrato.porcentaje_canje*obj_contrato.total_costo/Decimal(100)
        retencion_inicial = int(obj_contrato.valor*(1+obj_contrato.aiu/100)*obj_contrato.retencion.valor/100)
        
        subtotales = subtotal_inicial + subtotal_adicionales
        aiu_total=aiu_inicial+aiu_adicionales
        iva_total=iva_inicial + iva_adicionales
        total_orden=total_inicial + total_adicionales
        canje_total = canje_inicial + canje_adicionales
        rte_total = retencion_inicial + rte_adicionales
        anticipo = total_inicial*obj_contrato.anticipo/100
        
        porc_aiu = aiu_total*100/subtotales
        porc_canje = canje_total*100/total_orden
        
        
        pago_efectivo_total = total_orden-canje_total-rte_total
        
        form.initial.update({
            'vr_aiu':f'{aiu_total:,.0f}',
            'vr_iva':f'{iva_total:,.0f}',
            'pago_efectivo':f'{pago_efectivo_total:,.0f}',
            'vr_anticipo':f'{anticipo:,.0f}',
            'vr_retenciones':f'{rte_total:,.0f}',
            'total_acta':f'{total_orden:,.0f}',
            'valor':f'{subtotales:,.0f}',
            'aiu':f'{porc_aiu:.02f}',
            'canje':f'{porc_canje:.02f}'
        })
        canje_contrato = f'{canje_adicionales+canje_inicial:,.0f}'
        context['total_canje'] = canje_contrato
        total_adicionales = f'{total_adicionales:,.0f}'
        form.helper.layout[5].append(
            Div(
                TabHolder(
                    Tab('Adicionales',
                        HTML(
                            '<table id="tablaAdicionales" class="table table-sm table-hover">'+
                                    '<thead class="thead thead-dark">'+
                                        '<tr><th colspan="6">Adicionales</th><tr>'
                                        '<tr>'+
                                            '<th>Id</th>'+
                                            '<th>Fecha</th>'+
                                            '<th>Usuario</th>'+
                                            '<th>Estado</th>'+
                                            '<th>Canje</th>'+
                                            '<th>Total</th>'+
                                        '</tr>'+
                                    '</thead>'+
                                    '<tbody>'+
                                        adicionales+
                                    '</tbody>'+
                                    '<tfooter>'+
                                        '<tr>'+
                                            '<th colspan="5" class="text-right">Total</th>'+
                                            '<th>'+total_adicionales+'</th>'+
                                        '</tr>'+
                                    '</tfooter>'+
                                '</table><br/>')
                    ),
                    Tab('Actas',
                        HTML(
                            '<table id="tablaActas" class="table table-sm table-hover">'+
                                '<thead class="thead thead-dark">'+
                                    '<tr><th colspan="5">Actas de recibido</th><tr>'
                                    '<tr>'+
                                        '<th>Acta</th>'+
                                        '<th>Fecha</th>'+
                                        '<th>Usuario</th>'+
                                        '<th>Estado</th>'+
                                        '<th>Valor</th>'+
                                    '</tr>'+
                                '</thead>'+
                                '<tbody>'+
                                    actas_html+
                                '</tbody>'+
                                '<tfooter>'+
                                    '<tr>'+
                                        '<th colspan="4" class="text-right">Total</th>'+
                                        '<th>'+total_recibido+'</th>'+
                                    '</tr>'+
                                '</tfooter>'+
                            '</table>')
                    ),
                    Tab('Pagos',
                        HTML(
                            '<table id="tablaActas" class="table table-sm table-hover">'+
                                '<thead class="thead thead-dark">'+
                                    '<tr><th colspan="4">Pagos realizados</th><tr>'
                                    '<tr>'+
                                        '<th>Id</th>'+
                                        '<th>Fecha</th>'+
                                        '<th>Soporte</th>'+
                                        '<th>Valor</th>'+
                                    '</tr>'+
                                '</thead>'+
                                '<tbody>'+
                                    pagos_html+
                                '</tbody>'+
                                '<tfooter>'+
                                    '<tr>'+
                                        '<th colspan="3" class="text-right">Total</th>'+
                                        '<th>'+pagos_efectuados+'</th>'+
                                    '</tr>'+
                                '</tfooter>'+
                            '</table>')
                    )
                ),
                css_class="col-xl-6 col-lg-6 order-lg-1 table-responsive"
            )
        )
    else:
        form.helper.layout[7][0][0] =  Submit('btnModificar','Modificar Orden',css_class='ml-auto')
        if check_perms(request,('buildingcontrol.delete_actas_contratos',),raise_exception=False):
            form.helper.layout[7][0].append(Submit('btnAprobar','Aprobar orden',css_class='btn-success'))
    context.update({
        'form':form,
        'contrato':obj_contrato,
        'items_contrato': json_detalle,
        'productos':obj_productos,
        'proveedores':obj_proveedores,
        'tipos_obra': tiposobra.objects.all().order_by('nombre_tipo'),
        'topalert':alert,
    })
    return render(request,'building/modificar_contrato.html',context)

@group_perm_required(('buildingcontrol.view_actas_contratos',),raise_exception=True)
def lista_actas(request):
    obj_actas_pdtes = actas_contratos.objects.all().annotate(total=Sum(
                                F('items_recibidos__cantidad')*F('items_recibidos__item__valor')
                            ))
    context = {
        'actas_pendientes':obj_actas_pdtes
    }
    return render(request,'building/lista_actas.html',context)

@group_perm_required(('buildingcontrol.change_actas_contratos',),raise_exception=True)
def ver_acta(request,acta):
    alerta={}
    obj_acta = actas_contratos.objects.filter(pk=acta).annotate(total=Sum(
                    F('items_recibidos__cantidad')*F('items_recibidos__item__valor')
                        ))
    obj_acta = obj_acta[0]
    obj_productos = productos_servicios.objects.all()
    obj_proveedores = proveedores.objects.all().order_by('nombre')
    items_acta = items_recibidos.objects.filter(acta=acta
                    )
    if request.method == 'POST':
        if request.POST.get('btnModificar'):
            fecha_corte = request.POST.get('fecha_corte')
            canje_efectuado = request.POST.get('vr_canje')
            canje_efectuado = canje_efectuado.replace(",","")
            anticipo_amortizado = request.POST.get('vr_anticipo')
            anticipo_amortizado = anticipo_amortizado.replace(',','')
            aiu = request.POST.get('vr_aiu')
            aiu = aiu.replace(',','')
            iva = request.POST.get('vr_iva')
            iva = iva.replace(',','')
            retefuente = request.POST.get('vr_retenciones')
            retefuente = retefuente.replace(',','')
            
            items_list = request.POST.getlist('item_obra')
            cantidad_list = request.POST.getlist('cantidad_item')
            valor_list = request.POST.getlist('valor_item')
            total_list = request.POST.getlist('total_item')
            
            obj_acta.fecha_acta = fecha_corte
            obj_acta.canje_efectuado = canje_efectuado
            obj_acta.anticipo_amortizado = anticipo_amortizado
            obj_acta.retencion_efectuada = retefuente
            obj_acta.aiu=aiu
            obj_acta.iva=iva
            obj_acta.save()
            
            for item in items_acta:
                item.delete()
            contrato = obj_acta.contrato.pk
            for i in range (0,len(items_list)):
                items_recibidos.objects.create(
                    acta=obj_acta,
                    item=items_contrato.objects.get(contrato=contrato,
                                                    pk=items_list[i]),
                    cantidad=cantidad_list[i]
                )
            alerta = {
                'alert':1,
                'title':'¡Listo!',
                'message':'El acta fue modificada con exito',
                'class':'alert-success'
            }
            
            obj_acta = actas_contratos.objects.filter(pk=acta).annotate(total=Sum(
                    F('items_recibidos__cantidad')*F('items_recibidos__item__valor')
                        ))[0]
            items_acta = items_recibidos.objects.filter(acta=acta
                    ).annotate(total_recibido=Sum('cantidad'))
        if request.POST.get('btnAprobar'):
            check_perms(request,('buildingcontrol.delete_actas_contratos',))
            obj_acta.estado='Aprobado'
            obj_acta.usuario_aprueba = request.user
            obj_acta.fecha_aprueba = datetime.date.today()
            obj_acta.save()
            
            notificaciones = notificaciones_correo.objects.get(identificador='Aprobar acta recibido')
            
            for usuario in notificaciones.users_to_send.all():
                if check_project(request,obj_acta.contrato.proyecto.proyecto,raise_exception=False):
                    obj_acta.contrato.pk
                    mensaje = f'''Hola {usuario.first_name}, te informamos que {request.user.first_name} ha aprobado el acta de recibido {obj_acta.num_acta} en 
                    el modulo de proyectos, correspondiente al contrato {obj_acta.contrato.pk} del proveedor {obj_acta.contrato.proveedor.nombre.upper()}'''
                    asunto = 'Se ha Aprobado una Acta de recibido | Proyectos'
                    correo = [usuario.email,]
                    envio_notificacion(mensaje,asunto,correo)
                else: pass
            
            return HttpResponseRedirect('/buildingcontrol/allcontractprogress')
    fecha_corte = datetime.datetime.strftime(obj_acta.fecha_acta,'%Y-%m-%d')
    form = forms.formActaRecibido(
        initial={
            'idacta':obj_acta.num_acta,
            'proveedorid':obj_acta.contrato.proveedor.pk,
            'nombreproveedor':obj_acta.contrato.proveedor.nombre,
            'proyecto':obj_acta.contrato.proyecto.proyecto,
            'valor':f'{obj_acta.total:,.2f}',
            'vr_canje':f'{obj_acta.canje_efectuado:,}',
            'canje':math.ceil(obj_acta.canje_efectuado*100/(obj_acta.total+obj_acta.iva+obj_acta.aiu)),
            'vr_anticipo':f'{obj_acta.anticipo_amortizado:,}',
            'anticipo':math.ceil(obj_acta.anticipo_amortizado*100/(obj_acta.total+obj_acta.iva+obj_acta.aiu)),
            'fecha_corte':fecha_corte,
            'fecha_contrato':obj_acta.contrato.fecha_creacion,
            'descripcion_contrato':obj_acta.contrato.descripcion,
            'retenciones':obj_acta.contrato.retencion.valor,
            'vr_retenciones':obj_acta.retencion_efectuada,
            'empresa_contrata':obj_acta.contrato.empresa_contrata.nombre,
            'iva':obj_acta.contrato.iva,
            'aiu':obj_acta.contrato.aiu,
            'a':obj_acta.contrato.a,
            'i':obj_acta.contrato.i,
            'u':obj_acta.contrato.u
        }
    )
    if obj_acta.estado == 'Aprobado':
        form.helper.layout.pop(7)
        form.helper.layout.pop(4)
        form.helper['fecha_corte'].update_attributes(readonly=True,disabled=True)
    else:
        form.helper.layout[7][0][0] =  Submit('btnModificar','Modificar acta',css_class='ml-auto')
        if check_perms(request,('buildingcontrol.delete_actas_contratos',),raise_exception=False):
            form.helper.layout[7][0].append(Submit('btnAprobar','Aprobar acta',css_class='btn-success'))
    lista_detalle = []
    for item in items_acta:
        cantidad = float(item.cantidad)
        vr_unit = float(item.item.valor)
        total = float(item.cantidad)*float(item.item.valor)
        contratado = float(item.item.cantidad)
        recibido = items_recibidos.objects.filter(acta__contrato=obj_acta.contrato,
                                            acta__estado='Aprobado',item=item.item
                                ).aggregate(total=Sum('cantidad'))
        if recibido['total'] is None: recibido['total']=0
        recibido = float(recibido['total'])
        pendiente = contratado-recibido
        lista_detalle.append(
            {
                'item':item.item.pk,
                'nombre':item.item.item.nombre,
                'unidad':item.item.item.unidad.nombre,
                'cantidad':cantidad,
                'vr_unit':vr_unit,
                'vr_total':f'{total:,}',
                'cantidad_contratada':contratado,
                'total_recibido':recibido,
                'pendiente':pendiente,
            }
        )
    contrato = obj_acta.contrato.pk
    recibidos = items_recibidos.objects.filter(item=OuterRef('pk'),
                                    acta__contrato=contrato,acta__estado='Aprobado' 
                                        ).values('item')
    total_recibidos = recibidos.annotate(total=Sum('cantidad')).values('total')
    items = items_contrato.objects.filter(contrato=contrato
                ).annotate(contratados=Sum('cantidad',
                    )
                ).annotate(
                    recibidos=Sum(Subquery(total_recibidos[:1],
                                output_field=models.DecimalField(decimal_places=2)))
                )
    json_detalle = json.dumps(lista_detalle)
    context = {
        'form':form,
        'acta':obj_acta,
        'items_acta':json_detalle,
        'productos':obj_productos,
        'proveedores':obj_proveedores,
        'items_contrato':items,
        'topalert':alerta
    }
    
    return render(request,'building/ver_acta.html',context)

@group_perm_required(('buildingcontrol.view_proveedores',),raise_exception=True)
def suppliers(request):
    form = forms.formProveedores
    obj_proveedores = proveedores.objects.all()
    context ={
        'proveedores':obj_proveedores,
        'form':form
    }
    
    if request.method == 'POST':
        form = forms.formProveedores(request.POST)
        if form.is_valid():
            nit = request.POST.get('Nit')
            nombre=request.POST.get('Nombre')
            telefono=request.POST.get('Telefono')
            direccion=request.POST.get('Direccion')
            rut=request.FILES.get('Rut')
            certificado=request.FILES.get('Certificacion_bancaria')
            if proveedores.objects.filter(pk=nit).exists():
                check_perms(request,('buildingcontrol.change_proveedores',))
                proveedor = proveedores.objects.get(pk=nit)
                proveedor.nombre = nombre
                proveedor.telefono = telefono
                proveedor.direccion = direccion
                proveedor.doc_rut = rut
                proveedor.doc_cert_bancaria = certificado
                proveedor.save()
                alert = {
                    'alert':1,
                    'title':'!Hecho!',
                    'message':f'El proveedor fué modificado con exito',
                    'class':'alert-success'
                }
            else:
                check_perms(request,('buildingcontrol.add_proveedores',))
                proveedores.objects.create(
                    id_proveedor=nit,
                    nombre=nombre,
                    telefono=telefono,
                    direccion=direccion,
                    doc_rut=rut,
                    doc_cert_bancaria=certificado
                )
                alert = {
                    'alert':1,
                    'title':'!Hecho!',
                    'message':f'El proveedor fué creado con exito',
                    'class':'alert-success'
                }
            context['topalert']=alert
        else:
            context['form']=form
            
    
    return render(request,'building/proveedores.html',context)

@group_perm_required(('buildingcontrol.view_productos_servicios',),raise_exception=True)
def productosservicios(request):
    form=forms.formProductos
    obj_productos=productos_servicios.objects.all()
    context={
        'form':form,
        'productos':obj_productos
    }
    if request.method == 'POST':
        codigo = request.POST.get('id_producto')
        nombre = request.POST.get('nombre')
        tipo = request.POST.get('tipo')
        unidad = request.POST.get('unidad')
        
        if codigo == 'Nuevo':
            check_perms(request,('buildingcontrol.add_productos_servicios',))
            productos_servicios.objects.create(
                nombre = nombre,
                tipo=tipo,
                unidad=unidades_medida.objects.get(pk=unidad)
            )
            alert = {
                    'alert':1,
                    'title':'!Hecho!',
                    'message':f'El producto fué creado con exito',
                    'class':'alert-success'
                }
        else:
            check_perms(request,('buildingcontrol.change_productos_servicios',))
            producto = productos_servicios.objects.get(pk=codigo)
            producto.nombre = nombre
            producto.tipo = tipo
            producto.unidad = unidades_medida.objects.get(pk=unidad)
            producto.save()
            
            alert = {
                    'alert':1,
                    'title':'!Hecho!',
                    'message':f'El producto fué modificado con exito',
                    'class':'alert-success'
                }
        context['topalert']=alert
        
    return render(request,'building/productos_servicios.html',context)

@group_perm_required(('buildingcontrol.add_otrosi',),raise_exception=True)
def adicionales_orden(request,contrato):
    obj_contrato = contratos.objects.get(pk=contrato)
    obj_productos = productos_servicios.objects.all()
    form = forms.formContrato(
        initial={
            'idcontrato':contrato,
            'proveedorid':obj_contrato.proveedor.pk,
            'nombreproveedor':obj_contrato.proveedor.nombre,
            'proyecto':obj_contrato.proyecto.pk,
            'fecha_inicio':obj_contrato.fecha_inicio,
            'fecha_fin':obj_contrato.fecha_fin,
            'descripcion_contrato':obj_contrato.descripcion,
            'empresa_contrata':obj_contrato.empresa_contrata,
            'aiu':obj_contrato.aiu,
            'iva':obj_contrato.iva,
            'a':obj_contrato.a,
            'i':obj_contrato.i,
            'u':obj_contrato.u
        }
    )
    form.helper.layout[6][0][0]=PrependedText('valor', '<strong>Subtotal</strong>',css_class='text-right',readonly=True)
    form.helper.layout[7][0][0]=Submit('btnCrear','Crear adicion')
    form.helper.layout[1][4]=Div(Field('descripcion_contrato',readonly=True),css_class='col-md-6')
    form.helper.layout[1].append(Div(Field('descripcion_adicionales'),css_class='col-md-6'))
    form.helper.layout[6][0][8]=Row(
                        Column(PrependedText('anticipo', '<strong>Anticipo</strong>',css_class='text-center')),
                        Column(Field('vr_anticipo',css_class='text-right',readonly=True)),
                    hidden=True)
    context = {
        'form':form,
        'contrato':obj_contrato,
        'productos':obj_productos,
        'tipos_obra': tiposobra.objects.all().order_by('nombre_tipo'),
    }
    if request.method == 'POST':
        porcentaje_canje = request.POST.get('canje')
        descripcion = request.POST.get('descripcion_adicionales')
        items_list = request.POST.getlist('item_obra')
        valor_contrato = request.POST.get('valor').replace(',','')
        cantidad_list = request.POST.getlist('cantidad_item')
        valor_list = request.POST.getlist('valor_item')
        total_list = request.POST.getlist('total_item')
        tipos_obra = request.POST.getlist('obraItem')
        iva = request.POST.get('iva')
        aiu = request.POST.get('aiu')
        rte = request.POST.get('retenciones')
        total = request.POST.get('total_acta')
        total = total.replace(',','')
        
        if request.POST.get('btnCrear'):
            nro_otrosi = otrosi.objects.filter(contrato=contrato).count()+1
            obj_contrato = contratos.objects.get(pk=contrato)
            otrosi.objects.create(
                usuario_crea=request.user,
                estado='Pendiente',
                num_otrosi=nro_otrosi,
                contrato=obj_contrato,
                canje=porcentaje_canje,
                fecha_crea=datetime.datetime.today(),
                valor=valor_contrato,
                descripcion = descripcion,
                aiu=aiu,
                rte=rte,
                iva=iva,
                total_otrosi=total
            )
            obj_otrosi = otrosi.objects.last()
            for i in range(0,len(items_list)):
                items_contrato.objects.create(
                    item=productos_servicios.objects.get(pk=items_list[i]),
                    cantidad=cantidad_list[i],
                    valor=valor_list[i],
                    total=total_list[i].replace(',',''),
                    contrato=obj_contrato,
                    otrosi=obj_otrosi,
                    tipo_obra=tiposobra.objects.get(pk=tipos_obra[i])
                )
            return HttpResponseRedirect('/buildingcontrol/allotrosi')
            
            
    return render(request,'building/adicionales_orden.html',context)

@group_perm_required(('buildingcontrol.view_otrosi',),raise_exception=True)
def lista_otrosi(request):
    obj_otrosi = otrosi.objects.all()
    context ={
        'otrosis':obj_otrosi
    }
    return render(request,'building/lista_otrosi.html',context)

@group_perm_required(('buildingcontrol.change_otrosi',),raise_exception=True)
def ver_adicional(request,adicional):
    alert={}
    obj_proveedores=proveedores.objects.all()
    obj_adicional = otrosi.objects.get(pk=adicional)
    contrato = obj_adicional.contrato.pk
    items_adicional = items_contrato.objects.filter(otrosi=adicional)
    obj_contrato = contratos.objects.get(pk=contrato)
    obj_productos = productos_servicios.objects.all()
    if request.method == 'POST':
        if request.POST.get('btnModificar'):
            descripcion = request.POST.get('descripcion_adicionales')
            canje = request.POST.get('canje')
            items_list = request.POST.getlist('item_obra')
            cantidad_list = request.POST.getlist('cantidad_item')
            valor_list = request.POST.getlist('valor_item')
            total_list = request.POST.getlist('total_item')
            tipos_obra = request.POST.getlist('obraItem')
            total = request.POST.get('total_acta')
            total = total.replace(',','')
            valor = request.POST.get('valor')
            valor = valor.replace(',','')
            retencion = request.POST.get('retenciones')
            
            obj_adicional.descripcion=descripcion
            obj_adicional.canje=canje
            obj_adicional.total_otrosi = total
            obj_adicional.valor = valor
            obj_adicional.rte = retencion
            obj_adicional.save()
            
            for item in items_adicional:
                item.delete()
                
            for i in range(0,len(items_list)):
                items_contrato.objects.create(
                    item=productos_servicios.objects.get(pk=items_list[i]),
                    cantidad=cantidad_list[i],
                    valor=valor_list[i],
                    total=total_list[i].replace(',',''),
                    contrato=obj_contrato,
                    otrosi=otrosi.objects.get(pk=adicional),
                    tipo_obra=tiposobra.objects.get(pk=tipos_obra[i])
            )
            alert = {
                'alert':1,
                'title':'!Hecho!',
                'message':f'El contrato {contrato} fué modificado con exito',
                'class':'alert-success'
            }
            contrato = obj_adicional.contrato.pk
            items_adicional = items_contrato.objects.filter(otrosi=adicional)
            obj_contrato = contratos.objects.get(pk=contrato)
        if request.POST.get('btnAprobar'):
            check_perms(request,('buildingcontrol.delete_otrosi',))
            obj_adicional.estado='Aprobado'
            obj_adicional.usuario_aprueba=request.user
            obj_adicional.fecha_aprueba=datetime.date.today()
            obj_adicional.save()
            
            return HttpResponseRedirect('/buildingcontrol/allotrosi')
        obj_adicional = otrosi.objects.get(pk=adicional)
        
    form = forms.formContrato(
        initial={
            'idcontrato':contrato,
            'proveedorid':obj_contrato.proveedor.pk,
            'nombreproveedor':obj_contrato.proveedor.nombre,
            'proyecto':obj_contrato.proyecto.pk,
            'fecha_inicio':datetime.datetime.strftime(obj_contrato.fecha_inicio,"%Y-%m-%d"),
            'fecha_fin':datetime.datetime.strftime(obj_contrato.fecha_fin,"%Y-%m-%d"),
            'descripcion_contrato':obj_contrato.descripcion,
            'descripcion_adicionales':obj_adicional.descripcion,
            'valor':f'{obj_adicional.valor:,.0f}',
            'canje':obj_adicional.canje,
            'vr_canje':f'{obj_adicional.valor*obj_adicional.canje/100:,.0f}',
            'pago_efectivo':f'{obj_adicional.valor*(100-obj_adicional.canje)/100:,.0f}',
            'empresa_contrata':obj_contrato.empresa_contrata.pk,
            'retenciones':obj_adicional.rte,
            'iva':obj_adicional.iva,
            'aiu':obj_adicional.aiu
        }
    )
   
    form.helper.layout[6][0][0]=PrependedText('valor', '<strong>Subtotal</strong>',css_class='text-right',readonly=True)
    form.helper.layout[6][0][8]=Row(
                        Column(PrependedText('anticipo', '<strong>Anticipo</strong>',css_class='text-center')),
                        Column(Field('vr_anticipo',css_class='text-right',readonly=True)),
                    hidden=True)
    form.helper.layout[1][4]=Div(Field('descripcion_contrato',readonly=True),css_class='col-md-6')
    form.helper.layout[1].append(Div(Field('descripcion_adicionales'),css_class='col-md-6'))
    form.helper.layout[7][0][0] =  Submit('btnModificar','Modificar adicional',css_class='ml-auto')
    if obj_adicional.estado=='Aprobado':
        form.helper.layout[2][1]=Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Descripcion</p>'),
                    css_class='col-4 m-0'
                )
        form.helper.layout[2][3]=Div(
                    HTML('<p class="text-center mb-0 px-0 h-100">Cantidades</p>'),
                    css_class='col-2 m-0'
                )
        form.helper.layout.pop(7)
        form.helper.layout.pop(4)
        form.helper['descripcion_adicionales'].update_attributes(readonly=True,disabled=True)
        form.helper['fecha_fin'].update_attributes(readonly=True,disabled=True)
        form.helper['fecha_inicio'].update_attributes(readonly=True,disabled=True)
        form.helper['tipo_obra'].update_attributes(readonly=True,disabled=True)
        form.helper['proyecto'].update_attributes(readonly=True,disabled=True)
        form.helper['canje'].update_attributes(readonly=True,disabled=True)
        
        
    else:
        if check_perms(request,('buildingcontrol.delete_otrosi',),raise_exception=False):
            form.helper.layout[7][0].append(Submit('btnAprobar','Aprobar adicional',css_class='btn-success'))
    lista_detalle = []
    for item in items_adicional:
        recibidos = items_recibidos.objects.filter(item=item
                            ).aggregate(total=Sum('cantidad'))
        recibidos = recibidos['total']
        if recibidos is None: recibidos=0
        lista_detalle.append(
            {
                'item':item.item.pk,
                'nombre':item.item.nombre,
                'unidad':item.item.unidad.nombre,
                'cantidad':float(item.cantidad),
                'vr_unit':float(item.valor),
                'vr_total':f'{float(item.total):,}',
                'recibidos':float(recibidos),
                'obra':item.tipo_obra.pk,
                'nombre_obra':item.tipo_obra.nombre_tipo
            }
        )
    json_detalle = json.dumps(lista_detalle)
    context = {
        'form':form,
        'contrato':obj_contrato,
        'proveedores':obj_proveedores,
        'productos':obj_productos,
        'items_contrato': json_detalle,
        'adicional':obj_adicional,
        'tipos_obra': tiposobra.objects.all(),
        'topalert':alert
    }
    
            
    return render(request,'building/ver_adicional.html',context)

@group_perm_required(('buildingcontrol.view_bitacora',),raise_exception=True)
def info_bitacora(request):
    
    form = forms.formBitacora
    context = {
        'form':form,
    }
    
    if request.method == 'POST':
        check_perms(request,('buildingcontrol.add_bitacora',))
        id_bitacora = request.POST.get('id_bitacora')
        fecha = request.POST.get('fecha')
        proyecto = request.POST.get('proyecto')
        observaciones = request.POST.get('Observaciones')
        fotos = request.FILES.getlist('registro_foto')
        if id_bitacora !='Nuevo':
            obj_bitacora = bitacora.objects.filter(pk=id_bitacora)
            obj_bitacora=obj_bitacora[0]
            if request.user == obj_bitacora.usuario:
                obj_bitacora.fecha_bitacora = fecha
                obj_bitacora.proyecto = proyectos.objects.get(pk=proyecto)
                obj_bitacora.observaciones = observaciones
                obj_bitacora.save()
                alert = {
                    'alert':1,
                    'title':'!Hecho!',
                    'message':f'El registro de la bitacora fué modificado con exito',
                    'class':'alert-success'
                }
            else:
                alert = {
                    'alert':1,
                    'title':'!Error!',
                    'message':'No puedes modificar la bitacora de otro usuario',
                    'class':'alert-danger'
                }
        else:
            bitacora.objects.create(
                usuario = request.user,
                fecha_bitacora=fecha,
                proyecto = proyectos.objects.get(pk=proyecto),
                observaciones = observaciones,
            )
            bit = bitacora.objects.last()
            for foto in fotos:
                fotos_bitacora.objects.create(
                    bitacora=bit,
                    foto = foto
                )
            alert = {
                'alert':1,
                'title':'!Hecho!',
                'message':f'El registro fué anexado a la bitacora con exito',
                'class':'alert-success'
            }
        context['topalert']=alert
    if request.method == 'GET':
        if request.is_ajax():
            id_bit = request.GET.get('id_bit')
            obj_fotos = fotos_bitacora.objects.filter(bitacora=id_bit)
            json_fotos = serializers.serialize('json',obj_fotos)
            data = {
                'fotos':json_fotos
            }
            return JsonResponse(data)
            
            
    obj_bitacora = bitacora.objects.all()
    
    context['bitacora'] = obj_bitacora
        
    
    return render(request,'building/bitacora.html',context)

@group_perm_required(('buildingcontrol.view_requisiciones',),raise_exception=True)
def requisiciones_obra(request):
    obj_requisiciones = requisiciones.objects.filter(orden_cruce__isnull=True)
    context = {
        'requisiciones':obj_requisiciones,
        'form':forms.formRequisicion,
        'tipos_obra':tiposobra.objects.all(),
        'productos':productos_servicios.objects.all()
    }
    if request.method == 'POST':
        proyecto = request.POST.get('proyecto')
        descripcion = request.POST.get('descripcion')
        items = request.POST.getlist('item_obra')
        cantidades = request.POST.getlist('cantidad_item')
        obras = request.POST.getlist('obraItem')
        idReq = request.POST.get('idReq')
        obj_proyecto = proyectos.objects.get(proyecto=proyecto)
        if idReq == "":
            check_perms(request,('buildingcontrol.add_requisiciones',))
            requisiciones.objects.create(descripcion=descripcion,proyecto=obj_proyecto,
                                        usuario_crea=request.user,estado='Pendiente',
                                        fecha=datetime.date.today())
            obj_req=requisiciones.objects.last()
            for i in range(0,len(items)):
                items_requisiciones.objects.create(
                    item=productos_servicios.objects.get(pk=items[i]),
                    cantidad=cantidades[i],
                    tipo_obra=tiposobra.objects.get(pk=obras[i]),
                    requisicion=obj_req
                )
            alert = {
                    'alert':1,
                    'title':'!Hecho!',
                    'message':f'La requisicion fue creada con exito',
                    'class':'alert-success'
                    }
        else:
            if request.POST.get('btnCrear'):
                check_perms(request,('buildingcontrol.change_requisiciones',))
                obj_req = requisiciones.objects.get(pk=idReq)
                obj_req.proyecto = obj_proyecto
                obj_req.descripcion = descripcion
                obj_req.save()
                
                items_req = items_requisiciones.objects.filter(requisicion=idReq)
                
                for item in items_req:
                    item.delete()
                    
                for i in range(0,len(items)):
                    items_requisiciones.objects.create(
                        item=productos_servicios.objects.get(pk=items[i]),
                        cantidad=cantidades[i],
                        tipo_obra=tiposobra.objects.get(pk=obras[i]),
                        requisicion=obj_req
                    )
                alert = {
                        'alert':1,
                        'title':'!Hecho!',
                        'message':f'La requisicion fue modificada con exito',
                        'class':'alert-success'
                        }
                
            elif request.POST.get('btnAprobar'):
                check_perms(request,('buildingcontrol.delete_requisiciones',))
                obj_requisicion = requisiciones.objects.get(pk=idReq)
                obj_requisicion.estado = 'Aprobado'
                obj_requisicion.usuario_aprueba = request.user
                obj_requisicion.fecha_aprueba = datetime.datetime.now()
                obj_requisicion.save()
                
                alert = {
                        'alert':1,
                        'title':'!Hecho!',
                        'message':f'La requisicion fue aprobada con exito',
                        'class':'alert-success'
                        }
        
        obj_requisiciones = requisiciones.objects.filter(orden_cruce__isnull=True)
        context['requisiciones']=obj_requisiciones 
        context['topalert']=alert
            
    return render(request,'building/requisiciones.html',context)

def payments(request):
    
    if request.method == 'POST':
        if request.is_ajax():
            idpago = request.POST.get('idpago')
            item = request.POST.get('item')
            proyecto = request.POST.get('proyecto')
            obj_pago = pagos_obras.objects.get(pk=idpago)
            obj_pago.item_informe = ItemsInforme.objects.get(pk=item)
            obj_pago.proyecto_asume = proyectos.objects.get(pk=proyecto)
            obj_pago.save()
            
    obj_pagos = pagos_obras.objects.all()
    items_proyectos = ItemsInforme.objects.filter(grupo='GASTO PROYECTOS')
    obj_proyectos = proyectos.objects.all()
    context = {
        'pagos':obj_pagos,
        'items':items_proyectos,
        'proyectos':obj_proyectos,
    }

    
    return render(request,'building/payments.html',context)

def ajax_requisiciones(request):

    if request.method == 'GET':
        if request.is_ajax():
            id_req = request.GET.get('id_req')
            obj_req = requisiciones.objects.filter(pk=id_req)
            json_req = serializers.serialize('json',obj_req)
            obj_items = items_requisiciones.objects.filter(requisicion=id_req)
            data_items=[]
            for item in obj_items:
                data_items.append({
                    'item':item.item.pk,
                    'descripcion':item.item.nombre,
                    'unidad':item.item.unidad.nombre,
                    'cantidad':float(item.cantidad),
                    'item_obra':item.tipo_obra.pk,
                    'obra':item.tipo_obra.nombre_tipo
                })
            json_items = json.dumps(data_items)
            data = {
                'requisicion':json_req,
                'items':json_items,
            }
            return JsonResponse(data)

def ajax_productos(request):
    obj_productos = productos_servicios.objects.all().order_by('nombre')
    productos = []
    i=1
    for item in obj_productos:
        productos.append(
            [item.pk,item.nombre,item.unidad.nombre,item.tipo]
        )
        i+=1
    data_productos = {'data':productos}
    json_productos = json.dumps(data_productos)
    return JsonResponse(data_productos)

def ajax_pagos(request):
    pagos_list = []
    obj_pagos = pagos_obras.objects.all()
    for pago in obj_pagos:
        fecha = datetime.datetime.strftime(pago.pago.fechapago,
                                           '%d/%m/%Y')
        dir_sop = f'/docs_andinasoft/docs_radicados/Soportes_Pago/Soporte_Pago_{pago.pago.pk}_Radicado_{pago.pago.nroradicado}'
        if pago.item_informe is None: item = ''
        else: item = pago.item_informe.pk
        if pago.proyecto_asume is None: proy_asum = ''
        else: proy_asum = pago.proyecto_asume.pk
        pagos_list.append({
            'pk':pago.pago.pk,
            'fecha':fecha,
            'proveedor':pago.contrato_asociado.proveedor.nombre,
            'orden':pago.contrato_asociado.pk,
            'proyecto':pago.contrato_asociado.proyecto.proyecto,
            'valor':f'{pago.pago.valor:,}',
            'item':item,
            'proy_asum':proy_asum,
        })
    return JsonResponse({'data':pagos_list})

urls=[
    path('newcontract',crear_contrato,name='crear contrato'),
    path('viewcontract/<contrato>',ver_contrato),
    path('newprogress/<contrato>',crear_acta),
    path('viewprogress/<acta>',ver_acta),
    path('aprovedcontracts',contratos_aprobados),
    path('unaprovedcontracts',contratos_sin_aprobar),
    path('allcontractprogress',lista_actas),
    path('suppliers',suppliers),
    path('productsandservices',productosservicios),
    path('addotrosi/<contrato>',adicionales_orden),
    path('allotrosi',lista_otrosi),
    path('viewotrosi/<adicional>',ver_adicional),    
    path('logbook',info_bitacora),
    path('payments',payments),
    path('requirements',requisiciones_obra),
    path('ajax/requisiciones',ajax_requisiciones),
    path('ajax/productos',ajax_productos),
    path('ajax/paymentsdata',ajax_pagos),
]