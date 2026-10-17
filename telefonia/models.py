from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class LineaSaliente(models.Model):
    """Número que ve el cliente (caller ID): comprado en Twilio o verificado en «Verified Caller IDs».

    En modo automático se usa la línea activa que lleva más tiempo sin usarse.
    """

    nombre = models.CharField(max_length=60, help_text='Cómo la ve el agente, p. ej. «Oficina Medellín».')
    numero = models.CharField(
        max_length=20, unique=True,
        validators=[RegexValidator(r'^\+\d{8,15}$', 'Usa formato E.164, p. ej. +576041234567.')],
        help_text='E.164 (+57…). Debe estar comprado o verificado en Twilio; si no, Twilio rechaza la llamada.',
    )
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0, help_text='Orden en la lista del softphone.')
    ultimo_uso = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        verbose_name = 'Línea saliente'
        verbose_name_plural = 'Líneas salientes'
        ordering = ('orden', 'nombre')

    def __str__(self):
        return f'{self.nombre} ({self.numero})'


class Llamada(models.Model):
    """Llamada saliente hecha desde el softphone del panel de Chatwoot.

    Se crea antes de marcar (estado `iniciando`); Twilio la completa con sus webhooks.
    El número lo resuelve el servidor: el navegador solo dice de qué campo sale.
    """

    INICIANDO = 'iniciando'
    EN_CURSO = 'en_curso'
    COMPLETADA = 'completada'
    OCUPADO = 'ocupado'
    SIN_RESPUESTA = 'sin_respuesta'
    FALLIDA = 'fallida'
    CANCELADA = 'cancelada'
    ESTADOS = (
        (INICIANDO, 'Iniciando'),
        (EN_CURSO, 'En curso'),
        (COMPLETADA, 'Completada'),
        (OCUPADO, 'Ocupado'),
        (SIN_RESPUESTA, 'Sin respuesta'),
        (FALLIDA, 'Fallida'),
        (CANCELADA, 'Cancelada'),
    )
    FINALES = {COMPLETADA, OCUPADO, SIN_RESPUESTA, FALLIDA, CANCELADA}

    # auth_user es MyISAM: sin constraint en la BD.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='llamadas', db_constraint=False,
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default=INICIANDO, db_index=True)
    numero = models.CharField(max_length=20, help_text='Destino en E.164 (+57…).')
    fuente = models.CharField(max_length=20, help_text='De dónde salió el número: chatwoot, celular1, telefono2…')
    caller_id = models.CharField(max_length=20, blank=True, default='', help_text='Número que vio el cliente.')
    linea_nombre = models.CharField(max_length=60, blank=True, default='')
    cliente_id = models.CharField(max_length=255, blank=True, default='', help_text='idTercero del cliente, si aplica.')
    chatwoot_account_id = models.CharField(max_length=20)
    chatwoot_conversation_id = models.CharField(max_length=20)
    chatwoot_contact_id = models.CharField(max_length=20, blank=True, default='')
    call_sid = models.CharField(max_length=64, blank=True, default='', db_index=True,
                                help_text='Llamada del navegador a Twilio.')
    dial_sid = models.CharField(max_length=64, blank=True, default='', db_index=True,
                                help_text='Llamada de Twilio al cliente.')
    duracion = models.PositiveIntegerField(default=0, help_text='Segundos hablados con el cliente.')
    grabada = models.BooleanField(default=False)
    grabacion_sid = models.CharField(max_length=64, blank=True, default='')
    nota_privada = models.BooleanField(default=False, help_text='Se anotó en la conversación de Chatwoot.')
    detalle = models.CharField(max_length=255, blank=True, default='')
    ip = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    contestada_at = models.DateTimeField(null=True, blank=True)
    finalizada_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Llamada'
        verbose_name_plural = 'Llamadas'
        ordering = ('-created_at',)
        permissions = (
            ('llamar', 'Puede hacer llamadas desde el panel de Chatwoot'),
        )

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.user} → {self.numero} ({self.estado})'

    @property
    def finalizada(self):
        return self.estado in self.FINALES
