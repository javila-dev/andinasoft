from django.contrib import admin

from telefonia.models import LineaSaliente, Llamada, NumeroDescartado


@admin.register(LineaSaliente)
class LineaSalienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'numero', 'activa', 'orden', 'ultimo_uso')
    list_editable = ('activa', 'orden')
    readonly_fields = ('ultimo_uso',)


@admin.register(Llamada)
class LlamadaAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'numero', 'fuente', 'linea_nombre', 'estado', 'duracion', 'resultado',
                    'proyecto', 'adj', 'nota_privada', 'chatwoot_conversation_id')
    list_filter = ('estado', 'resultado', 'linea_nombre', 'grabada')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'numero', 'cliente_id', 'adj',
                     'chatwoot_conversation_id', 'call_sid', 'dial_sid')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in Llamada._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NumeroDescartado)
class NumeroDescartadoAdmin(admin.ModelAdmin):
    """Para volver a ofrecer un número, se borra de aquí."""

    list_display = ('created_at', 'numero', 'cliente_id', 'chatwoot_contact_id', 'user')
    search_fields = ('numero', 'cliente_id', 'chatwoot_contact_id')
    readonly_fields = ('numero', 'cliente_id', 'chatwoot_contact_id', 'llamada', 'user', 'created_at')

    def has_add_permission(self, request):
        return False
