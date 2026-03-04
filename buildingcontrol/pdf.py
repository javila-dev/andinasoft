from django.shortcuts import render
from django.http import HttpResponse,FileResponse, JsonResponse
from django.template.loader import render_to_string, get_template
from django.urls import path
from django.db.models import Avg, Max, Min, Sum, Q, F, Case, When, Value, Subquery, OuterRef, Func
from django.db.models.functions import Coalesce
from django.core import serializers
from buildingcontrol import models as building_models
from django.conf import settings
from andinasoft.create_pdf import GenerarPDF
import traceback

       
def ordenCompra(request):
    
    if request.method == 'GET':
        if request.is_ajax():
            contrato = request.GET.get('contrato')
            try:
                obj_contrato = building_models.contratos.objects.get(pk=contrato)
                items = building_models.items_contrato.objects.filter(contrato=contrato,otrosi__isnull=True).order_by('tipo_obra')
                nombre_doc = f'Orden_{contrato}.pdf'
                ruta = settings.MEDIA_ROOT+'/tmp/pdf/'+nombre_doc
                pdf = GenerarPDF()
                pdf.ordenCompra(obj_contrato,items,ruta)
                
                data = {
                    'href': settings.MEDIA_URL + 'tmp/pdf/' + nombre_doc,
                    'valid':True
                }
            except:
                data={
                    'valid':False,
                    'error':traceback.format_exc()[:450]
                }
            return JsonResponse(data)
                                   
            
def actaRecibido(request):
    
    if request.method == 'GET':
        if request.is_ajax():
            acta = request.GET.get('acta')
            
            obj_acta = building_models.actas_contratos.objects.filter(pk=acta
                            ).annotate(total=Sum(
                                        F('items_recibidos__cantidad')*F('items_recibidos__item__valor')
                        ))
            obj_contrato = building_models.contratos.objects.get(pk=obj_acta[0].contrato.pk)
            items = building_models.items_recibidos.objects.filter(acta=acta)
            nombre_doc = f'Acta_{obj_acta[0].num_acta}_Orden_{obj_acta[0].contrato.pk}.pdf'
            ruta = settings.MEDIA_ROOT+'/tmp/pdf/'+nombre_doc
            pdf = GenerarPDF()
            pdf.actaRecibido(obj_contrato,obj_acta[0],items,ruta)
            
            data = {
                'href': settings.MEDIA_URL + 'tmp/pdf/' + nombre_doc,
                'valid':True
            }
            
            return JsonResponse(data)

def adicionalesOrden(request):
    
    if request.method == 'GET':
        if request.is_ajax():
            adicional = request.GET.get('adicional')
            print(adicional)
            try:
                obj_adicional = building_models.otrosi.objects.get(pk=adicional)
                contrato = obj_adicional.contrato.pk
                obj_contrato = building_models.contratos.objects.get(pk=contrato)
                items = building_models.items_contrato.objects.filter(contrato=contrato,otrosi=adicional)
                nombre_doc = f'Adicional_{obj_adicional.num_otrosi}_Orden_{contrato}.pdf'
                ruta = settings.MEDIA_ROOT+'/tmp/pdf/'+nombre_doc
                pdf = GenerarPDF()
                pdf.adicionalOrden(obj_contrato,obj_adicional,items,ruta)
                
                data = {
                    'href': settings.MEDIA_URL + 'tmp/pdf/' + nombre_doc,
                    'valid':True
                }
            except:
                data={
                    'valid':False,
                    'error':traceback.format_exc()[:550]
                }
            return JsonResponse(data)

urls=[
    path('orderspdf',ordenCompra),
    path('progressdoc',actaRecibido),
    path('adicionales',adicionalesOrden),
]
