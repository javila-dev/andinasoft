import os
import traceback
import datetime
import base64
import andinasoft.shared_models as sm
import openpyxl
from decimal import Decimal
from django.conf import settings
from django.template.loader import get_template
from django.template import Context, Template
from django.shortcuts import render
from django.core.mail import EmailMultiAlternatives
from django.db.models import Avg, Max, Min, Sum
from django.db import IntegrityError
from andina.storage import media_service


#cambiar ruta a public_html

def _to_storage_key(path):
    normalized = os.path.normpath(path)
    media_root = os.path.normpath(settings.MEDIA_ROOT)
    if normalized.startswith(media_root):
        return os.path.relpath(normalized, media_root).replace("\\", "/")
    return normalized.lstrip("/").replace("\\", "/")


def upload_docs_asesores(file,id_asesor,name_doc):
    file_dir=f'{settings.DIR_DOCS}/doc_asesores/{id_asesor}'
    file_path = f'{file_dir}/{name_doc}.pdf'
    media_service.save_private(_to_storage_key(file_path), file)
            
def upload_docs_contratos(file,adj,proyecto,name_doc):
    file_dir=f'{settings.DIR_DOCS}/doc_contratos/{proyecto}/{adj}/'
    file_path = f'{file_dir}{name_doc}.pdf'
    media_service.save_private(_to_storage_key(file_path), file)
            
def upload_docs_radicados(file,tipo,name_doc):
    file_dir=f'{settings.DIR_DOCS}/docs_radicados/{tipo}/'
    file_path = f'{file_dir}{name_doc}.pdf'
    media_service.save_private(_to_storage_key(file_path), file)
            
def upload_docs(file,dir_destino,name_doc, doctype='pdf'):
    #La dir de destino debe finalizar en /
    #el name_doc no puede iniciar en /
    file_dir = dir_destino
    file_path = f'{file_dir}{name_doc}.{doctype}'
    media_service.save_private(_to_storage_key(file_path), file)

def aplicar_pago(request,adj,fecha,forma_pago,valor_pagado,concepto,valor_recibo,porcentaje_condonado,
                 saldo_cuotas:list,consecutivo,Recaudos:object,Recaudos_general:object,titulares:object,
                 proyecto:str, crear_recibo:bool=True, cobrar_mora:bool=True):
    total_cap=0
    total_intcte=0
    total_intmora=0
    count_cuota=0
    es_ci=False
    es_fn=False
    es_co=False
    es_ce=False
    if porcentaje_condonado==None or porcentaje_condonado=='':
        cobro_mora=1
    else:
        cobro_mora=Decimal(1-(porcentaje_condonado/100))
    if not cobrar_mora:
        cobro_mora = 0
    recaudo=[]               
    for cuota in saldo_cuotas:
        if valor_pagado==0:
            break
        else:
            if cuota.idcta[:2]=='CI':
                es_ci=True
            elif cuota.idcta[:2]=='FN':
                es_fn=True
            elif cuota.idcta[:2]=='CE':
                es_ce=True
            elif cuota.idcta[:2]=='CO':
                es_co=True
            capital=cuota.saldocapital
            intcte=cuota.saldointcte
            intmora=round(cuota.saldomora*cobro_mora,0)
            if valor_pagado>=intmora:
                mora_pagada=intmora
                valor_pagado-=intmora
            else:
                mora_pagada=valor_pagado
                valor_pagado-=valor_pagado
            if valor_pagado>=intcte:
                intcte_pagado=intcte
                valor_pagado-=intcte
            else:
                intcte_pagado=valor_pagado
                valor_pagado-=valor_pagado
            if valor_pagado>=capital:
                capital_pagado=capital
                valor_pagado-=capital
            else:
                capital_pagado=valor_pagado
                valor_pagado-=valor_pagado
            total_cap+=capital_pagado
            total_intcte+=intcte_pagado
            total_intmora+=mora_pagada
            nro_recibo=f'{consecutivo}'
            Recaudos.objects.using(proyecto).create(recibo=nro_recibo,
                                                    fecha=fecha,
                                                    idcta=cuota.idcta,
                                                    idadjudicacion=adj,
                                                    capital=capital_pagado,
                                                    interescte=intcte_pagado,
                                                    interesmora=mora_pagada,
                                                    moralqd=cuota.saldomora,
                                                    fechaoperacion=datetime.datetime.today(),
                                                    usuario=request.user,
                                                    estado='Aprobado')
    if es_ci:
        operacion='Cuota Inicial'
    elif es_fn:
        operacion='Financiacion'
    elif es_ce:
        operacion='Extraordinaria'
    elif es_co:
        operacion='Contado'
    else:
        operacion='Ninguna'
    if crear_recibo:
        Recaudos_general.objects.using(proyecto).create(idadjudicacion=adj,
                                                        fecha=fecha,
                                                        numrecibo=nro_recibo,
                                                        idtercero=titulares.IdTercero1,
                                                        operacion=operacion,
                                                        valor=valor_recibo,
                                                        formapago=str(forma_pago))

    obj_saldos=sm.saldos_adj.objects.using(proyecto).filter(adj=adj)
    saldos=obj_saldos.aggregate(Sum('saldocuota'))
    saldos=saldos['saldocuota__sum']
    if saldos<=0:
        obj_adj=sm.Adjudicacion.objects.using(proyecto).get(idadjudicacion=adj)
        obj_adj.estado='Pagado'
        obj_adj.save()

def envio_notificacion(mensaje,subject,destinatarios):
    
    template=get_template('emails/notificacion_aplicacion.html')
    content=template.render({'mensaje':mensaje})
    message=EmailMultiAlternatives(subject,'',settings.EMAIL_HOST_USER,destinatarios)
    message.attach_alternative(content,'text/html')
    message.send()

def envio_email_template(subject:str,sender:str,destinatarios:list,template:str,campos:dict):
    """
    Envia correos genericamente pasando el template, destinatarios, campos, etc.
    """
    template=get_template(template)
    content=template.render(campos)
    message=EmailMultiAlternatives(subject=subject,body='',from_email=sender,to=destinatarios)
    message.attach_alternative(content,'text/html')
    message.send()

def respuesta_reestructuracion(proyecto,lote,manzana,forma_ci,forma_saldo,destinatarios):
    encabezados={
        'Sandville Beach':'Header-Sandville-Andina.jpg',
        'Perla del Mar':'Header-Sandville-Andina.jpg',
        'Sandville del Sol':'Header-Sandville-Andina.jpg',
        'Tesoro Escondido':'Header-Tesoro-Escondido.jpg',
        'Vegas de Venecia':'Header-Vegas-de-Venecia.jpg',
        'Sotavento':'Header-Sotavento.jpg',
    }
    subject=f'Tu solicitud de reestructuracion en {proyecto} ha sido Aprobada!'
    template=get_template('emails/respuesta_reestructuracion.html')
    direccion=f'https://andinasoft.com.co/public_images/{encabezados[proyecto]}'
    content=template.render({
        'proyecto':proyecto,
        'lote':lote,
        'manzana':manzana,
        'forma_ci':forma_ci,
        'forma_saldo':forma_saldo,
        'dir_encabezado':direccion,
    })
    message=EmailMultiAlternatives(subject,'',settings.EMAIL_HOST_USER,destinatarios)
    message.attach_alternative(content,'text/html')
    message.send()

def cargar_gastos_informe(empresa,file,ultima_linea:int,object_gastos:object,object_cc:object,object_cuentas:object):
    """
    Esta funcion carga a la tabla de gastos de informe el archivo xlsx que exporta SIIGO del movimiento de cuentas de gastos.
    Esta funcion reclasifica segun las asociaciones de cuentas y centros de costos para lo cual se pasan los objetos de gastos, centros de costo y cuentas asociadas.
    """
    file_server=settings.DIR_EXPORT+'gastos_file.xlsx'
    with open(file_server,'wb+') as destination:
        for chunk in file.chunks():
            destination.write(chunk)
    documento=openpyxl.load_workbook(file_server)
    hoja=documento.get_sheet_names()
    sheet=documento.get_sheet_by_name(hoja[0])
    errores=0
    for fila in range(8,ultima_linea+1):
        manage=sheet[f'E{fila}'].value
        if manage=='  000 00000000000 000' or manage=='' or manage==None:
            pass
        else:
            cuenta=sheet[f'B{fila}'].value
            descrip_cta=sheet[f'C{fila}'].value
            comprobante=sheet[f'E{fila}'].value
            fecha=sheet[f'F{fila}'].value
            tercero=sheet[f'H{fila}'].value
            descripcion=sheet[f'I{fila}'].value
            centro_costo=sheet[f'L{fila}'].value
            debito=sheet[f'M{fila}'].value
            credito=sheet[f'N{fila}'].value
            if debito=='                 ' or debito==None:
                debito=0
            else:
                debito=(debito)
            if credito=='                 ' or credito==None:
                credito=0
            else:
                credito=(credito)
            valor=Decimal(debito-credito)
            proyecto=object_cc.filter(empresa=empresa,idcentrocosto=centro_costo)
            if proyecto.exists(): proyecto=proyecto[0].proyecto
            else: proyecto=''
            item=object_cuentas.filter(empresa=empresa,cuenta=cuenta)
            if item.exists(): item=item[0].item_asociado
            else: item=''
            try:
                object_gastos.create(empresa=empresa,
                                    cuenta=cuenta,
                                    descrip_cuenta=descrip_cta,
                                    fecha=fecha,
                                    comprobante=comprobante,
                                    tercero=tercero,
                                    descrip_gasto=descripcion,
                                    valor=valor,
                                    proyecto=proyecto,
                                    centro_costo=centro_costo,
                                    item_asociado=item
                                    )
            except IntegrityError:
                if errores==0:
                    file = open(settings.DIR_EXPORT+'comprobantes_no_cargados.txt','w')
                    file.write('Los siguientes comprobantes ya estan cargados en la base de datos para esta empresa:'+'\n')
                file.write(comprobante+'\n')
                errores+=1
    if errores>0:
        file.close()
    return errores

    def check_project(user):
        user=request.user.pk
        user_projects=Usuarios_Proyectos.objects.filter(usuario=user)
        if user_projects.exists():
            user_projects=user_projects[0].proyecto.all()
            for p in user_projects:
                if p==proyecto:
                    return True
        else:
            if raise_exception:
                raise PermissionDenied
            else:
                return False
        return False
    return user_passes_test(check_project, login_url=login_url)    
