from django.contrib import admin
from django.contrib.admin import register,ModelAdmin
from django.db import connections
from django.utils.http import urlencode
from django.core.exceptions import PermissionDenied
from andinasoft.models import (asesores, clientes, Facturas, Pagos, timeline_radicados, Usuarios_Proyectos, 
                                Avatars, Profiles, empresas,notificaciones_correo, parametros, proyectos)
from andinasoft.shared_models import Inmuebles, ventas_nuevas, Parametros_Operaciones

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

class adminProyecto(admin.ModelAdmin):
    list_display=['proyecto','activo']
    list_filter=['activo']
    search_fields=['proyecto']

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


class MultiDBModelAdmin(admin.ModelAdmin):
    db_param = '_db'
    change_list_template = 'admin/andinasoft/multi_db_change_list.html'
    change_form_template = 'admin/andinasoft/multi_db_change_form.html'

    def _get_db_choices(self, request):
        aliases = []
        for alias in proyectos.objects.values_list('proyecto', flat=True):
            if alias in connections.databases:
                aliases.append(alias)

        if not request.user.is_superuser:
            allowed = set(
                Usuarios_Proyectos.objects
                .filter(usuario=request.user)
                .values_list('proyecto__proyecto', flat=True)
            )
            aliases = [alias for alias in aliases if alias in allowed]

        if not aliases:
            aliases = [alias for alias in connections.databases.keys() if alias != 'default']
        return aliases

    def _get_session_key(self):
        return f'admin_db_{self.opts.app_label}_{self.opts.model_name}'

    def _get_current_db(self, request):
        db_choices = self._get_db_choices(request)
        if not db_choices:
            raise PermissionDenied('No hay bases de datos de proyecto disponibles para este usuario.')
        current = (
            request.GET.get(self.db_param)
            or request.POST.get(self.db_param)
            or request.session.get(self._get_session_key())
        )
        if current in db_choices:
            request.session[self._get_session_key()] = current
            return current
        current = db_choices[0]
        request.session[self._get_session_key()] = current
        return current

    def _db_query_suffix(self, request):
        return urlencode({self.db_param: self._get_current_db(request)})

    def get_preserved_filters(self, request):
        preserved = super().get_preserved_filters(request)
        current_db = self._get_current_db(request)
        db_filter = urlencode({self.db_param: current_db})
        if not preserved:
            return db_filter
        if f'{self.db_param}=' in preserved:
            return preserved
        return f'{preserved}&{db_filter}'

    def get_queryset(self, request):
        return super().get_queryset(request).using(self._get_current_db(request))

    def get_form(self, request, obj=None, change=False, **kwargs):
        base_form = super().get_form(request, obj=obj, change=change, **kwargs)
        selected_db = self._get_current_db(request)

        class MultiDBAdminForm(base_form):
            def __init__(self, *args, **inner_kwargs):
                super().__init__(*args, **inner_kwargs)
                if self.instance is not None:
                    self.instance._state.db = selected_db

        return MultiDBAdminForm

    def save_model(self, request, obj, form, change):
        obj.save(using=self._get_current_db(request))

    def delete_model(self, request, obj):
        obj.delete(using=self._get_current_db(request))

    def delete_queryset(self, request, queryset):
        queryset.using(self._get_current_db(request)).delete()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        kwargs['using'] = self._get_current_db(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        kwargs['using'] = self._get_current_db(request)
        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'available_databases': self._get_db_choices(request),
            'current_db': self._get_current_db(request),
            'db_param': self.db_param,
            'db_query_suffix': self._db_query_suffix(request),
        })
        return super().changelist_view(request, extra_context=extra_context)

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'available_databases': self._get_db_choices(request),
            'current_db': self._get_current_db(request),
            'db_param': self.db_param,
            'db_query_suffix': self._db_query_suffix(request),
        })
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'available_databases': self._get_db_choices(request),
            'current_db': self._get_current_db(request),
            'db_param': self.db_param,
            'db_query_suffix': self._db_query_suffix(request),
        })
        return super().add_view(request, form_url=form_url, extra_context=extra_context)

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue=post_url_continue)
        location = response.get('Location')
        if location and self.db_param not in location:
            separator = '&' if '?' in location else '?'
            response['Location'] = f'{location}{separator}{self._db_query_suffix(request)}'
        return response

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        location = response.get('Location')
        if location and self.db_param not in location:
            separator = '&' if '?' in location else '?'
            response['Location'] = f'{location}{separator}{self._db_query_suffix(request)}'
        return response


class adminInmuebles(MultiDBModelAdmin):
    list_display = [
        'idinmueble', 'etapa', 'manzananumero', 'lotenumero', 'estado',
        'vrmetrocuadrado', 'areaprivada', 'meses'
    ]
    list_filter = ['estado', 'etapa']
    search_fields = ['idinmueble', 'manzananumero', 'lotenumero', 'matricula']


class adminVentasNuevas(MultiDBModelAdmin):
    list_display = [
        'id_venta', 'inmueble', 'id_t1', 'valor_venta', 'cuota_inicial',
        'fecha_contrato', 'estado', 'usuario'
    ]
    list_filter = ['estado', 'tipo_venta', 'fecha_contrato']
    search_fields = ['id_venta', 'inmueble', 'id_t1', 'usuario', 'grupo']


class adminParametrosOperaciones(MultiDBModelAdmin):
    list_display = ['descripcion', 'estado']
    list_filter = ['estado']
    search_fields = ['descripcion']

admin.site.register(asesores,adminAsesores)
admin.site.register(clientes,adminClientes)
admin.site.register(Facturas,adminFacturas)
admin.site.register(Pagos,adminPagos)
admin.site.register(timeline_radicados,adminTimeline)
admin.site.register(Usuarios_Proyectos,adminProyectos)
admin.site.register(proyectos,adminProyecto)
admin.site.register(Avatars,adminAvatars)
admin.site.register(Profiles,adminProfiles)
admin.site.register(empresas,adminEmpresas)
admin.site.register(parametros,adminParametros)
admin.site.register(notificaciones_correo,adminNotificacionesEmail)
admin.site.register(Inmuebles,adminInmuebles)
admin.site.register(ventas_nuevas,adminVentasNuevas)
admin.site.register(Parametros_Operaciones,adminParametrosOperaciones)
