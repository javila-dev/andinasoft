from django.contrib import admin
from finance import models
# Register your models here.

@admin.register(models.recibos_internos)
class adminrecibosint(admin.ModelAdmin):
    list_display = ['pk','fecha','cliente','valor']
    list_filter = ['proyecto']
    date_hierarchy = 'fecha'