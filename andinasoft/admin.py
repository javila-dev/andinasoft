from django.contrib import admin
from django.contrib.admin import register,ModelAdmin
from andinasoft.models import (asesores, clientes, Facturas, Pagos, timeline_radicados, Usuarios_Proyectos, 
                                Avatars, Profiles, empresas,notificaciones_correo, parametros)

# Register your models here.

class adminAsesores(admin.ModelAdmin):
    list_display=['cedula','nombre','email','banco','cuenta','rut','cc','direccion',
    'fecha_nacimiento','estado_civil','nivel_educativo','equipo','estado',
    'fecha_registro','fecha_baja']
    
    list_filter=['equipo','estado']
    search_fields=['nombre','banco']

class adminClientes(admin.ModelAdmin):
    list_display = ['idTercero','nombrecompleto','celular1','telefono1','ciudad','email','fecha_actualizacion']
    list_filter=['fecha_actualizacion','estado_civil']
    search_fields=['idTercero','nombrecompleto']
    
class adminFacturas(admin.ModelAdmin):
    list_display=['nroradicado','fecharadicado','nrofactura','nombretercero','valor','nrocausa','estado']
    list_filter=['empresa','estado']
    search_fields=['nroradicado','nrofactura','nombretercero']

class adminPagos(admin.ModelAdmin):
    list_display=['nroradicado','valor','empresapago','fechapago','formapago']
    list_filter=['empresapago','formapago']
    search_fields=['nroradicado','empresapago']
    
class adminTimeline(admin.ModelAdmin):
    list_display=['id_flow','fecha','tiporadicado','nroradicado','usuario','accion']
    list_filter=['tiporadicado']
    search_fields=['tiporadicado','nroradicado','usuario']

class adminProyectos(admin.ModelAdmin):
    list_display=['usuario']

class adminAvatars(admin.ModelAdmin):
    list_display=['name','image']

class adminProfiles(admin.ModelAdmin):
    list_display=['user']

class adminEmpresas(admin.ModelAdmin):
    list_display=['Nit','nombre','logo']
    
class adminNotificacionesEmail(admin.ModelAdmin):
    list_display=['id_notificacion','identificador']

class adminParametros(admin.ModelAdmin):
    list_display=['pk','parametro','valor']

admin.site.register(asesores,adminAsesores)
admin.site.register(clientes,adminClientes)
admin.site.register(Facturas,adminFacturas)
admin.site.register(Pagos,adminPagos)
admin.site.register(timeline_radicados,adminTimeline)
admin.site.register(Usuarios_Proyectos,adminProyectos)
admin.site.register(Avatars,adminAvatars)
admin.site.register(Profiles,adminProfiles)
admin.site.register(empresas,adminEmpresas)
admin.site.register(parametros,adminParametros)
admin.site.register(notificaciones_correo,adminNotificacionesEmail)