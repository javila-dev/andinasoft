from django.contrib import admin
from crm import models

# Register your models here.
@admin.register(models.Operaciones)
class adminOperaciones(admin.ModelAdmin):
    list_display=['proyecto','descripcion','lider']
    list_filter=['proyecto']
    
@admin.register(models.eventos)
class adminEventos(admin.ModelAdmin):
    list_display=['id_evento','operacion','fecha_evento','hora_evento']
    list_filter=['operacion','fecha_evento','hora_evento']
    
@admin.register(models.usuario_gestor)
class adminUsuarioGestor(admin.ModelAdmin):
    list_display=['asesor','usuario']
    
@admin.register(models.leads)
class adminLeads(admin.ModelAdmin):
    list_display=['nombre','celular','email','gestor_capta','gestor_aseginado','estado','fecha_capta']   
    list_filter = ['gestor_capta','gestor_aseginado','fecha_capta']
    