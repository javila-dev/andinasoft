from django.contrib import admin
from accounting import models
# Register your models here.

@admin.register(models.egresos_contable)
class adminEgresosContable(admin.ModelAdmin):
    list_display = ['empresa','comprobante','fecha','valor']
    list_filter = ['empresa','fecha']
    date_hierarchy = 'fecha'

@admin.register(models.egresos_banco)
class adminEgresosBanco(admin.ModelAdmin):
    list_display = ['pk','cuenta','empresa','fecha','valor']
    list_filter = ['empresa','fecha','cuenta']
    date_hierarchy = 'fecha'
    
@admin.register(models.conciliaciones)
class adminConciliaciones(admin.ModelAdmin):
    list_display = ['pk','empresa','cuenta_asociada','usuario_crea','fecha_crea']
    list_filter = ['empresa','cuenta_asociada','usuario_crea']
    date_hierarchy = 'fecha_crea'
    
@admin.register(models.GastoAprobador)
class adminGastoAprobador(admin.ModelAdmin):
    list_display = ['pk', 'user', 'empresa', 'telefono', 'activo']
    list_filter = ['activo', 'empresa']
    search_fields = ['user__username', 'user__email', 'empresa__pk', 'telefono']
    autocomplete_fields = ['user']


@admin.register(models.GastoContableNotificacion)
class adminGastoContableNotificacion(admin.ModelAdmin):
    list_display = ['pk', 'user', 'empresa', 'activo']
    list_filter = ['activo', 'empresa']
    search_fields = ['user__username', 'user__email', 'empresa__pk']
    autocomplete_fields = ['user']


@admin.register(models.GastoNotificacionOficina)
class adminGastoNotificacionOficina(admin.ModelAdmin):
    list_display = ['codigo', 'etiqueta']
    search_fields = ['codigo', 'etiqueta']


@admin.register(models.GastoTesoreriaNotificacion)
class adminGastoTesoreriaNotificacion(admin.ModelAdmin):
    list_display = ['pk', 'user', 'activo', 'empresas_list', 'oficinas_list']
    list_filter = ['activo']
    search_fields = ['user__username', 'user__email']
    autocomplete_fields = ['user']
    filter_horizontal = ['empresas', 'oficinas']

    def empresas_list(self, obj):
        return ', '.join(str(e.pk) for e in obj.empresas.all()[:8])

    empresas_list.short_description = 'Empresas'

    def oficinas_list(self, obj):
        return ', '.join(o.codigo for o in obj.oficinas.all())

    oficinas_list.short_description = 'Oficinas'


@admin.register(models.Facturas)
class adminFacts(admin.ModelAdmin):
    list_display = [
        'pk', 'fecharadicado', 'nombretercero', 'nrofactura', 'empresa', 'valor',
        'origen', 'oficina', 'gasto_aprobacion_estado', 'gasto_aprobado',
    ]
    list_filter = ['empresa', 'oficina', 'origen', 'gasto_aprobacion_estado', 'gasto_aprobado']
    search_fields = ['pk', 'nombretercero', 'nrofactura', 'alegra_bill_id']
    date_hierarchy = 'fecharadicado'
    
@admin.register(models.info_interfaces)
class adminInterfaces(admin.ModelAdmin):
    list_display = ['pk','empresa','descripcion','tipo_doc','cuenta_debito_1','cuenta_credito_1']
    list_filter = ['empresa']
    
@admin.register(models.docs_cuentas_oficinas)
class adminDocsOfic(admin.ModelAdmin):
    list_display = ['pk','empresa','documento']
    list_filter = ['empresa']
    
@admin.register(models.cuentas_intercompanias)
class adminIntercomp(admin.ModelAdmin):
    list_display = ['pk','empresa_desde','empresa_hacia','documento']
    list_filter = ['empresa_desde','empresa_hacia']
    
@admin.register(models.Pagos)   
class adminPagos(admin.ModelAdmin):
    list_display = ['pk', 'fecha_pago', 'nroradicado', 'valor', 'alegra_payment_id', 'usuario']
    list_filter = ['empresa', 'cuenta']
    search_fields = ['nroradicado__pk', 'nroradicado__nombretercero', 'alegra_payment_id']
    readonly_fields = ['alegra_payment_id']
    date_hierarchy = 'fecha_pago'
    
@admin.register(models.Anticipos)
class adminAnticipos(admin.ModelAdmin):
    list_display = ['pk','fecha_pago','nombre_tercero','valor','empresa','cuenta','usuario']
    list_filter = ['empresa','cuenta','usuario']
    date_hierarchy = 'fecha_pago'

@admin.register(models.transferencias_companias)
class adminTransferencias(admin.ModelAdmin):
    list_display = ['pk','fecha','cuenta_sale','cuenta_entra','valor']
    list_filter = ['oficina','empresa_entra','empresa_sale']
    date_hierarchy = 'fecha'

@admin.register(models.distribucion_centros_costos)
class adminDistCC(admin.ModelAdmin):
    list_display = ['pk','cedula','centro','subcentro','porcentaje']
    list_filter = ['cedula']
    
@admin.register(models.conceptos_legalizacion)
class adminConceptos_legalizacion(admin.ModelAdmin):
    list_display = ['descripcion','activo']
    search_fields = ['descripcion','cuenta_contable']

@admin.register(models.solicitud_anticipos)
class adminSolicitudAnticipos(admin.ModelAdmin):
    list_display = ['usuario_solicita','fecha','valor']
    list_filter = ['empresa']
    search_fields = ['pk']
    date_hierarchy = 'fecha'
    

admin.site.site_header = "Administación de Andinasoft"
admin.site.site_title = "Administación de Andinasoft"