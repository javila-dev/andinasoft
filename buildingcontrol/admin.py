from django.contrib import admin
from buildingcontrol import models

# Register your models here.
@admin.register(models.unidades_medida)
class adminUnidadesMedida(admin.ModelAdmin):
    fields=('nombre',)
    list_display=['nombre']
    list_filter=['id_unid','nombre']

@admin.register(models.tiposobra)
class tiposobrasAdmin(admin.ModelAdmin):
    list_display=['nombre_tipo']

@admin.register(models.proveedores)
class proveedoresAdmin(admin.ModelAdmin):
    list_display=['id_proveedor','nombre','telefono','doc_rut','doc_cert_bancaria']

@admin.register(models.productos_servicios)
class productosAdmin(admin.ModelAdmin):
    list_display=['id_producto','nombre','tipo','unidad']
    list_filter=['tipo','unidad']

@admin.register(models.contratos)
class contratosAdmin(admin.ModelAdmin):
    list_display=['id_contrato','proveedor','proyecto','valor','estado'] 
    list_filter=['fecha_creacion','proyecto','estado']

@admin.register(models.otrosi)
class otrosiAdmin(admin.ModelAdmin):
    list_display=['id_otrosi','num_otrosi','contrato','estado','fecha_crea']
    list_filter=['fecha_crea']

@admin.register(models.items_contrato)
class itemscontratosAdmin(admin.ModelAdmin):
    list_display=['id_item','item','tipo_obra','cantidad','valor','contrato','otrosi']
    list_filter=['cantidad']

@admin.register(models.actas_contratos)
class actasAdmin(admin.ModelAdmin):
    list_display=['id_acta','num_acta','contrato','estado','usuario_crea']
    list_filter=['fecha_acta']

@admin.register(models.items_recibidos)
class itemrecibidoAdmin(admin.ModelAdmin):
    list_display=['id_recibido','acta','item','cantidad']
    
@admin.register(models.pagos_obras)
class pagosObraAdmin(admin.ModelAdmin):
    list_display=['pago','contrato_asociado']
    
@admin.register(models.bitacora)
class pagosObraAdmin(admin.ModelAdmin):
    list_display=['id_registro','usuario','fecha_bitacora','fecha_registro','proyecto']
    list_filter=['proyecto','fecha_bitacora']
    
@admin.register(models.retenciones)
class RetencionesAdmin(admin.ModelAdmin):
    list_display=['descripcion','valor']

@admin.register(models.requisiciones)
class RequisicionesAdmin(admin.ModelAdmin):
    list_display=['id_req','proyecto','fecha','usuario_crea']
    list_filter=['proyecto','fecha']
    
@admin.register(models.items_requisiciones)
class ItemsRequisicionesAdmin(admin.ModelAdmin):
    list_display=['id_item','item','requisicion','tipo_obra']
    list_filter=['tipo_obra']
    
@admin.register(models.parametros)
class ParametrosAdmin(admin.ModelAdmin):
    list_display=['parametro','check','valor']