from django.conf import settings
from django.db import models
from django.utils import timezone

from andinasoft.models import empresas, proyectos


class AlegraMapping(models.Model):
    BANK_ACCOUNT = 'bank_account'
    CATEGORY = 'category'
    CONTACT = 'contact'
    COST_CENTER = 'cost_center'
    NUMERATION = 'numeration'
    RETENTION = 'retention'
    PAYMENT_METHOD = 'payment_method'
    BILL = 'bill'

    MAPPING_TYPES = (
        (BANK_ACCOUNT, 'Cuenta bancaria'),
        (CATEGORY, 'Cuenta/categoria contable'),
        (CONTACT, 'Contacto'),
        (COST_CENTER, 'Centro de costo'),
        (NUMERATION, 'Numeracion'),
        (RETENTION, 'Retencion'),
        (PAYMENT_METHOD, 'Metodo de pago'),
        (BILL, 'Factura/documento proveedor'),
    )

    empresa = models.ForeignKey(empresas, on_delete=models.CASCADE, related_name='alegra_mappings', db_constraint=False)
    proyecto = models.ForeignKey(proyectos, on_delete=models.CASCADE, null=True, blank=True, related_name='alegra_mappings', db_constraint=False)
    mapping_type = models.CharField(max_length=40, choices=MAPPING_TYPES)
    local_model = models.CharField(max_length=120, blank=True, default='')
    local_pk = models.CharField(max_length=255, blank=True, default='')
    local_code = models.CharField(max_length=255, blank=True, default='')
    alegra_id = models.CharField(max_length=255)
    alegra_payload = models.JSONField(default=dict, blank=True)
    description = models.CharField(max_length=255, blank=True, default='')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Mapeo Alegra'
        verbose_name_plural = 'Mapeos Alegra'
        indexes = [
            models.Index(
                fields=['empresa', 'proyecto', 'mapping_type', 'local_model', 'local_pk'],
                name='alegra_mapping_local_pk_idx',
            ),
            models.Index(
                fields=['empresa', 'proyecto', 'mapping_type', 'local_code'],
                name='alegra_mapping_code_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'proyecto', 'mapping_type', 'local_model', 'local_pk', 'local_code'],
                name='unique_alegra_mapping'
            )
        ]

    def __str__(self):
        project = self.proyecto_id or 'empresa'
        key = self.local_pk or self.local_code or self.local_model
        return f'{self.empresa_id}|{project}|{self.mapping_type}|{key}->{self.alegra_id}'


class AlegraSyncBatch(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_PREVIEW = 'preview'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE = 'done'
    STATUS_FAILED = 'failed'
    STATUS_PARTIAL = 'partial'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_PREVIEW, 'Preview'),
        (STATUS_PROCESSING, 'Procesando'),
        (STATUS_DONE, 'Completado'),
        (STATUS_FAILED, 'Fallido'),
        (STATUS_PARTIAL, 'Parcial'),
    )

    DOC_RECEIPT = 'receipt'
    DOC_COMMISSION = 'commission'
    DOC_EXPENSE = 'expense'

    DOCUMENT_TYPES = (
        (DOC_RECEIPT, 'Recibos de caja'),
        (DOC_COMMISSION, 'Comisiones'),
        (DOC_EXPENSE, 'Egresos'),
    )

    empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='alegra_batches', db_constraint=False)
    proyecto = models.ForeignKey(proyectos, on_delete=models.PROTECT, null=True, blank=True, related_name='alegra_batches', db_constraint=False)
    document_type = models.CharField(max_length=40, choices=DOCUMENT_TYPES)
    fecha_desde = models.DateField()
    fecha_hasta = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    summary = models.JSONField(default=dict, blank=True)
    total_documents = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Lote Alegra'
        verbose_name_plural = 'Lotes Alegra'
        ordering = ['-created_at']

    def finish(self, status):
        self.status = status
        self.completed_at = timezone.now()
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def __str__(self):
        return f'{self.document_type} {self.empresa_id} {self.fecha_desde}..{self.fecha_hasta}'


class AlegraDocument(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Pendiente'),
        (STATUS_VALID, 'Valido'),
        (STATUS_INVALID, 'Invalido'),
        (STATUS_SENT, 'Enviado'),
        (STATUS_FAILED, 'Fallido'),
        (STATUS_SKIPPED, 'Omitido'),
    )

    ALEGRA_TOOL = 'mcp_tool'
    ALEGRA_REST = 'rest'

    batch = models.ForeignKey(AlegraSyncBatch, on_delete=models.CASCADE, null=True, blank=True, related_name='documents')
    empresa = models.ForeignKey(empresas, on_delete=models.PROTECT, related_name='alegra_documents', db_constraint=False)
    proyecto = models.ForeignKey(proyectos, on_delete=models.PROTECT, null=True, blank=True, related_name='alegra_documents', db_constraint=False)
    document_type = models.CharField(max_length=40)
    alegra_operation = models.CharField(max_length=120, blank=True, default='')
    transport = models.CharField(max_length=20, blank=True, default='')
    source_model = models.CharField(max_length=120)
    source_pk = models.CharField(max_length=255)
    local_key = models.CharField(max_length=255)
    payload = models.JSONField(default=dict, blank=True)
    response = models.JSONField(default=dict, blank=True)
    alegra_id = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error = models.TextField(blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, db_constraint=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Documento Alegra'
        verbose_name_plural = 'Documentos Alegra'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['empresa', 'document_type', 'local_key'],
                name='unique_alegra_document_local_key'
            )
        ]

    def __str__(self):
        return f'{self.document_type}|{self.local_key}|{self.status}'


class AlegraContactIndex(models.Model):
    """
    Simple relational index of Alegra contacts by identification (NIT/CC) and type.
    This is used as a lightweight resolver when the local system does not have a dedicated third-party table.
    """
    TYPE_CLIENT = 'client'
    TYPE_PROVIDER = 'provider'
    TYPE_CHOICES = (
        (TYPE_CLIENT, 'Cliente'),
        (TYPE_PROVIDER, 'Proveedor'),
    )

    empresa = models.ForeignKey(empresas, on_delete=models.CASCADE, related_name='alegra_contact_index', db_constraint=False)
    identification = models.CharField(max_length=255, db_index=True)  # normalized (no separators)
    contact_type = models.CharField(max_length=20, choices=TYPE_CHOICES, db_index=True)
    alegra_id = models.CharField(max_length=255)
    name = models.CharField(max_length=255, blank=True, default='')
    raw = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Índice de contactos Alegra'
        verbose_name_plural = 'Índice de contactos Alegra'
        indexes = [
            models.Index(fields=['empresa', 'contact_type', 'identification'], name='alegra_contact_idx_key'),
        ]
        constraints = [
            models.UniqueConstraint(fields=['empresa', 'contact_type', 'identification'], name='unique_alegra_contact_index'),
        ]

    def __str__(self):
        return f'{self.empresa_id}|{self.contact_type}|{self.identification}->{self.alegra_id}'


class AlegraWebhookSubscriptionLog(models.Model):
    """
    Registro de intentos de suscripción a webhooks de Alegra (POST /webhooks/subscriptions).
    Guarda la respuesta de Alegra para verificación y auditoría.
    """
    empresa = models.ForeignKey(empresas, on_delete=models.CASCADE, related_name='alegra_webhook_logs', db_constraint=False)
    event = models.CharField(max_length=40, db_index=True)
    callback_url = models.TextField()
    request_json = models.JSONField(default=dict, blank=True)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_json = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alegra_webhook_subscription_logs',
        db_constraint=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log suscripción webhook Alegra'
        verbose_name_plural = 'Logs suscripción webhooks Alegra'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['empresa', 'created_at'], name='alegra_whk_log_empresa_idx'),
        ]

    def __str__(self):
        return f'{self.empresa_id}|{self.event}|{self.response_status}|ok={self.success}'


class AlegraWebhookInboundLog(models.Model):
    """
    POST/GET recibidos en el endpoint de ingesta de webhooks (desde Alegra hacia AndinaSoft).
    Sirve para inspeccionar la estructura del payload antes de mapear a modelos locales.
    """
    http_method = models.CharField(max_length=16, db_index=True)
    content_type = models.CharField(max_length=255, blank=True, default='')
    remote_addr = models.CharField(max_length=255, blank=True, default='')
    query_string = models.TextField(blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    raw_body = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log webhook entrante Alegra'
        verbose_name_plural = 'Logs webhooks entrantes Alegra'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at'], name='alegra_whk_in_created_idx'),
        ]

    def __str__(self):
        return f'{self.http_method}|{self.created_at}|id={self.pk}'


class AlegraBillGetLog(models.Model):
    """
    Respuesta cruda de GET /bills/{id} tras procesar webhook (descarga PDF).
    Sirve para depurar la forma real del JSON (stampFiles, attachments, etc.).
    """

    empresa = models.ForeignKey(
        empresas,
        on_delete=models.CASCADE,
        related_name='alegra_bill_get_logs',
        db_constraint=False,
    )
    alegra_bill_id = models.CharField(max_length=64, db_index=True)
    factura = models.ForeignKey(
        'accounting.Facturas',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='alegra_bill_get_logs',
        db_constraint=False,
    )
    fields = models.CharField(max_length=255, blank=True, default='', verbose_name='fields (query)')
    response_json = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='', verbose_name='notas / error')
    pdf_saved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log GET /bills Alegra (debug)'
        verbose_name_plural = 'Logs GET /bills Alegra (debug)'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['empresa', 'created_at'], name='alegra_bill_get_emp_ct_idx'),
        ]

    def __str__(self):
        return f'{self.empresa_id}|bill={self.alegra_bill_id}|pdf={self.pdf_saved}|{self.created_at}'
