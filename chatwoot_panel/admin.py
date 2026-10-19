from django import forms
from django.contrib import admin, messages
from django.utils import timezone

from andinasoft.models import proyectos
from chatwoot_panel.models import (
    ChatwootPanelAudit, ChatwootPanelToken, ComercioWompi, LinkPagoWompi, ProyectoWompi,
)
from chatwoot_panel.pagos_wompi import bucket_publico_configurado, llave_de, logo_url, logo_visible


class ProyectoWompiForm(forms.ModelForm):
    """El proyecto se elige de la lista: el nombre tiene que ser idéntico al de `proyectos`."""

    proyecto = forms.ChoiceField(choices=())

    class Meta:
        model = ProyectoWompi
        fields = ('proyecto', 'logo')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nombres = list(proyectos.objects.order_by('proyecto').values_list('proyecto', flat=True))
        actual = self.instance.proyecto if self.instance and self.instance.pk else ''
        if actual and actual not in nombres:
            nombres.insert(0, actual)  # no perder uno que ya no esté en la lista
        self.fields['proyecto'].choices = [('', '---------')] + [(n, n) for n in nombres]


class ProyectoWompiInline(admin.TabularInline):
    model = ProyectoWompi
    form = ProyectoWompiForm
    extra = 1


@admin.register(ComercioWompi)
class ComercioWompiAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'alias', 'activo', 'llave_configurada', 'lista_proyectos')
    inlines = (ProyectoWompiInline,)

    @admin.display(boolean=True, description='Llave en el entorno')
    def llave_configurada(self, obj):
        return bool(llave_de(obj))

    @admin.display(description='Proyectos')
    def lista_proyectos(self, obj):
        return ', '.join(obj.proyectos.values_list('proyecto', flat=True))

    def save_formset(self, request, form, formset, change):
        """Tras subir logos, confirma que Wompi podrá verlos (URL pública, sin credenciales)."""
        super().save_formset(request, form, formset, change)
        if formset.model is not ProyectoWompi:
            return
        if not bucket_publico_configurado():
            messages.error(request, 'Falta AWS_PUBLIC_BUCKET_NAME (o es el bucket privado): los links saldrán sin logo.')
            return
        for asignacion in formset.queryset.exclude(logo=''):
            url = logo_url(asignacion.proyecto)
            if not url:
                messages.warning(request, f'{asignacion.proyecto}: el logo no tiene una URL pública https; '
                                          'el link saldrá sin logo.')
            elif not logo_visible(url):
                messages.warning(request, f'{asignacion.proyecto}: el logo no se puede ver sin credenciales ({url}); '
                                          'Wompi no podrá mostrarlo.')


@admin.register(LinkPagoWompi)
class LinkPagoWompiAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'proyecto', 'adj', 'valor', 'link_id', 'enviado', 'vence', 'created_by')
    list_filter = ('enviado', 'comercio')
    search_fields = ('adj', 'proyecto', 'link_id', 'chatwoot_conversation_id')
    date_hierarchy = 'created_at'
    readonly_fields = [f.name for f in LinkPagoWompi._meta.fields]

    def has_add_permission(self, request):
        return False


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
