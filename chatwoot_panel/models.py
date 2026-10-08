from django.conf import settings
from django.db import models


class ChatwootPanelToken(models.Model):
    """Acceso del panel embebido en Chatwoot.

    En el navegador solo queda la cadena firmada (jti + usuario); la vigencia vive
    aquí. Vence tras CHATWOOT_PANEL_TOKEN_IDLE_DAYS sin uso: cada uso la corre.
    """

    # auth_user es MyISAM: sin constraint en la BD.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chatwoot_panel_tokens', db_constraint=False,
    )
    jti = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    ip = models.CharField(max_length=64, blank=True, default='')
    user_agent = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        verbose_name = 'Conexión del panel de Chatwoot'
        verbose_name_plural = 'Conexiones del panel de Chatwoot'
        ordering = ('-created_at',)
        permissions = (
            ('usar_panel_chatwoot', 'Puede usar el panel de Chatwoot'),
        )

    def __str__(self):
        return f'{self.user} · {self.created_at:%Y-%m-%d %H:%M}'


class ChatwootContactLink(models.Model):
    """Contacto de Chatwoot confirmado como un cliente de Andinasoft."""

    chatwoot_account_id = models.CharField(max_length=20)
    chatwoot_contact_id = models.CharField(max_length=20)
    # idTercero de andinasoft.clientes (texto, puede llevar prefijo ALT-). Tabla MyISAM: sin FK.
    cliente_id = models.CharField(max_length=255, db_index=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, db_constraint=False, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Vínculo contacto Chatwoot ↔ cliente'
        verbose_name_plural = 'Vínculos contacto Chatwoot ↔ cliente'
        constraints = [
            models.UniqueConstraint(fields=('chatwoot_account_id', 'chatwoot_contact_id'), name='chatwoot_link_unico'),
        ]

    def __str__(self):
        return f'{self.chatwoot_account_id}/{self.chatwoot_contact_id} → {self.cliente_id}'


class ChatwootSeguimientoRef(models.Model):
    """Seguimiento registrado desde el panel.

    `seguimientos` vive en la BD de cada proyecto, es MyISAM y no la administra Django:
    aquí queda la conversación de Chatwoot y la llave que evita registrarlo dos veces.
    """

    idempotency_key = models.CharField(max_length=64, unique=True)
    proyecto = models.CharField(max_length=60)
    adj = models.CharField(max_length=30)
    seguimiento_id = models.IntegerField(null=True, blank=True)
    chatwoot_account_id = models.CharField(max_length=20, blank=True, default='')
    chatwoot_conversation_id = models.CharField(max_length=20, blank=True, default='')
    nota_privada = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, db_constraint=False, related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Seguimiento desde Chatwoot'
        verbose_name_plural = 'Seguimientos desde Chatwoot'
        indexes = [models.Index(fields=('proyecto', 'adj'))]

    def __str__(self):
        return f'{self.proyecto} {self.adj} #{self.seguimiento_id}'


class ChatwootPanelAudit(models.Model):
    """Rastro de conexiones, consultas y registros hechos desde el panel."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, db_constraint=False)
    token = models.ForeignKey(ChatwootPanelToken, null=True, blank=True, on_delete=models.SET_NULL)
    accion = models.CharField(max_length=40, db_index=True)
    proyecto = models.CharField(max_length=60, blank=True, default='')
    adj = models.CharField(max_length=30, blank=True, default='')
    chatwoot_account_id = models.CharField(max_length=20, blank=True, default='')
    chatwoot_contact_id = models.CharField(max_length=20, blank=True, default='')
    chatwoot_conversation_id = models.CharField(max_length=20, blank=True, default='')
    detalle = models.CharField(max_length=500, blank=True, default='')
    ip = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Auditoría del panel de Chatwoot'
        verbose_name_plural = 'Auditoría del panel de Chatwoot'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.user} {self.accion}'
