from django.contrib import admin

from telefonia.models import LineaSaliente, Llamada


@admin.register(LineaSaliente)
class LineaSalienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero', 'activa', 'orden', 'ultimo_uso')
    list_editable = ('activa', 'orden')
    readonly_fields = ('ultimo_uso',)


@admin.register(Llamada)
class LlamadaAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'numero', 'fuente', 'linea_nombre', 'estado', 'duracion', 'grabada',
                    'nota_privada', 'chatwoot_conversation_id')
    list_filter = ('estado', 'linea_nombre', 'grabada')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'numero', 'cliente_id',
                     'chatwoot_conversation_id', 'call_sid', 'dial_sid')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in Llamada._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
