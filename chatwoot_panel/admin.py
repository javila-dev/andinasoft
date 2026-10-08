from django.contrib import admin
from django.utils import timezone

from chatwoot_panel.models import ChatwootPanelAudit, ChatwootPanelToken


@admin.register(ChatwootPanelToken)
class ChatwootPanelTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'last_used_at', 'expires_at', 'revoked_at', 'ip')
    list_filter = ('revoked_at',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'ip')
    readonly_fields = ('user', 'created_at', 'expires_at', 'last_used_at', 'revoked_at', 'ip', 'user_agent')
    exclude = ('jti',)
    actions = ('revocar',)

    def has_add_permission(self, request):
        return False

    @admin.action(description='Revocar las conexiones seleccionadas')
    def revocar(self, request, queryset):
        n = queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
        self.message_user(request, f'{n} conexión(es) revocada(s).')


@admin.register(ChatwootPanelAudit)
class ChatwootPanelAuditAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'user', 'accion', 'proyecto', 'adj', 'chatwoot_conversation_id', 'ip')
    list_filter = ('accion',)
    search_fields = ('user__username', 'proyecto', 'adj', 'chatwoot_contact_id', 'chatwoot_conversation_id')
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
