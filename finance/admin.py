from django.contrib import admin
from finance import models
# Register your models here.

@admin.register(models.recibos_internos)
class adminrecibosint(admin.ModelAdmin):
    list_display = ['pk','fecha','cliente','valor']
    list_filter = ['proyecto']
    date_hierarchy = 'fecha'


@admin.register(models.SaldoFavorCliente)
class adminSaldoFavorCliente(admin.ModelAdmin):
    list_display = ['pk', 'proyecto', 'adjudicacion', 'recibo', 'valor', 'fecha', 'usuario']
    list_filter = ['proyecto']
    search_fields = ['adjudicacion', 'recibo']
    date_hierarchy = 'fecha'
    readonly_fields = ['fecha']