from django.contrib import admin

from conciliacion_terceros.models import (
    AjusteConciliacion,
    Conciliacion,
    ConciliacionLinea,
    ConfigEmpresa,
    ConfigFacturacion,
    CorreccionIdentificacion,
    FacturaConciliacion,
    FuenteConciliacion,
)


@admin.register(ConfigFacturacion)
class ConfigFacturacionAdmin(admin.ModelAdmin):
    list_display = ('proyecto', 'empresa', 'modo', 'emision', 'numeracion_nombre', 'cuenta_cxc_codigo', 'updated_at')


@admin.register(FacturaConciliacion)
class FacturaConciliacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'conciliacion', 'tipo', 'empresa', 'proyecto', 'negocio_ref', 'identificacion', 'numero', 'total', 'estado', 'cruce_estado', 'created_at')
    list_filter = ('tipo', 'estado', 'cruce_estado', 'empresa')
    search_fields = ('identificacion', 'numero', 'negocio_ref', 'alegra_invoice_id')
    readonly_fields = ('respuesta',)


@admin.register(CorreccionIdentificacion)
class CorreccionIdentificacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'id_errado', 'id_correcto', 'modo', 'estado', 'created_by', 'created_at', 'revertido_en')
    list_filter = ('estado', 'modo')
    search_fields = ('id_errado', 'id_correcto')
    readonly_fields = ('vista_previa', 'detalle', 'alegra')


@admin.register(AjusteConciliacion)
class AjusteConciliacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'conciliacion', 'tipo', 'origen_identificacion', 'origen_cuenta', 'destino_identificacion',
                    'destino_cuenta', 'valor', 'misma_empresa', 'anulado', 'journal_estado', 'created_by', 'created_at')
    list_filter = ('tipo', 'anulado', 'journal_estado', 'misma_empresa')
    search_fields = ('origen_identificacion', 'destino_identificacion', 'grupo')


@admin.register(ConfigEmpresa)
class ConfigEmpresaAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'cuentas', 'updated_at')


class FuenteInline(admin.TabularInline):
    model = FuenteConciliacion
    extra = 0
    fields = ('empresa', 'formato', 'archivo_nombre', 'fecha_corte_archivo', 'cuentas_usadas', 'confirmada', 'created_by', 'created_at')
    readonly_fields = fields


@admin.register(Conciliacion)
class ConciliacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha_corte', 'estado', 'tolerancia', 'created_by', 'created_at')
    list_filter = ('estado',)
    inlines = [FuenteInline]


@admin.register(ConciliacionLinea)
class ConciliacionLineaAdmin(admin.ModelAdmin):
    list_display = ('conciliacion', 'identificacion', 'nombre', 'saldo_andina', 'saldo_contable', 'diferencia', 'estado', 'revision')
    list_filter = ('estado', 'revision')
    search_fields = ('identificacion', 'nombre')
