from django.contrib import admin
from crm import models


class ActaParticipanteInline(admin.TabularInline):
    model = models.ActaParticipante
    extra = 0


class CompromisoActaInline(admin.TabularInline):
    model = models.CompromisoActa
    extra = 0
    fields = ['titulo', 'responsable', 'fecha_compromiso', 'prioridad', 'estado']


class SeguimientoCompromisoInline(admin.TabularInline):
    model = models.SeguimientoCompromiso
    extra = 0
    fields = ['usuario', 'estado_nuevo', 'fecha_proxima', 'comentario', 'created_at']
    readonly_fields = ['created_at']


class AdjuntoActaInline(admin.TabularInline):
    model = models.AdjuntoActa
    extra = 0
    fields = ['tipo', 'descripcion', 'archivo', 'cargado_por', 'created_at']
    readonly_fields = ['created_at']


@admin.register(models.Operaciones)
class adminOperaciones(admin.ModelAdmin):
    list_display = ['proyecto', 'descripcion', 'lider']
    list_filter = ['proyecto']


@admin.register(models.eventos)
class adminEventos(admin.ModelAdmin):
    list_display = ['id_evento', 'operacion', 'fecha_evento', 'hora_evento']
    list_filter = ['operacion', 'fecha_evento', 'hora_evento']


@admin.register(models.usuario_gestor)
class adminUsuarioGestor(admin.ModelAdmin):
    list_display = ['asesor', 'usuario']


@admin.register(models.leads)
class adminLeads(admin.ModelAdmin):
    list_display = ['nombre', 'celular', 'email', 'gestor_capta', 'gestor_aseginado', 'estado', 'fecha_capta']
    list_filter = ['gestor_capta', 'gestor_aseginado', 'fecha_capta']


@admin.register(models.ActaReunion)
class adminActaReunion(admin.ModelAdmin):
    list_display = ['id_acta', 'fecha_reunion', 'hora_reunion', 'duracion_minutos', 'tipo_reunion', 'cliente', 'proyecto', 'lider_reunion', 'estado']
    list_filter = ['tipo_reunion', 'canal', 'estado', 'proyecto', 'fecha_reunion']
    search_fields = ['asunto', 'cliente__nombrecompleto', 'cliente__idTercero', 'lider_reunion__username']
    autocomplete_fields = ['cliente', 'proyecto', 'creado_por', 'lider_reunion']
    inlines = [ActaParticipanteInline, CompromisoActaInline, AdjuntoActaInline]
    date_hierarchy = 'fecha_reunion'


@admin.register(models.CompromisoActa)
class adminCompromisoActa(admin.ModelAdmin):
    list_display = ['id_compromiso', 'titulo', 'acta', 'responsable', 'fecha_compromiso', 'prioridad', 'estado']
    list_filter = ['estado', 'prioridad', 'fecha_compromiso', 'acta__proyecto']
    search_fields = ['titulo', 'descripcion', 'responsable__username', 'responsable__first_name', 'responsable__last_name']
    autocomplete_fields = ['acta', 'responsable', 'creado_por']
    inlines = [SeguimientoCompromisoInline]
    date_hierarchy = 'fecha_compromiso'


@admin.register(models.SeguimientoCompromiso)
class adminSeguimientoCompromiso(admin.ModelAdmin):
    list_display = ['id_seguimiento', 'compromiso', 'usuario', 'estado_nuevo', 'fecha_proxima', 'created_at']
    list_filter = ['estado_nuevo', 'fecha_proxima', 'created_at']
    search_fields = ['compromiso__titulo', 'usuario__username', 'comentario']
    autocomplete_fields = ['compromiso', 'usuario']


@admin.register(models.ActaParticipante)
class adminActaParticipante(admin.ModelAdmin):
    list_display = ['id_participante', 'acta', 'usuario', 'nombre_externo', 'rol']
    list_filter = ['rol']
    search_fields = ['acta__asunto', 'usuario__username', 'nombre_externo', 'email_externo']
    autocomplete_fields = ['acta', 'usuario']


@admin.register(models.AdjuntoActa)
class adminAdjuntoActa(admin.ModelAdmin):
    list_display = ['id_adjunto', 'acta', 'tipo', 'descripcion', 'cargado_por', 'created_at']
    list_filter = ['tipo', 'created_at']
    search_fields = ['acta__asunto', 'descripcion', 'cargado_por__username']
    autocomplete_fields = ['acta', 'cargado_por']
