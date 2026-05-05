from django.contrib import admin

from alegra_integration.models import (
    AlegraBillGetLog,
    AlegraDocument,
    AlegraMapping,
    AlegraSyncBatch,
    AlegraWebhookInboundLog,
    AlegraWebhookSubscriptionLog,
)


@admin.register(AlegraMapping)
class AlegraMappingAdmin(admin.ModelAdmin):
    list_display = ['empresa', 'proyecto', 'mapping_type', 'local_model', 'local_pk', 'local_code', 'alegra_id', 'active']
    list_filter = ['empresa', 'proyecto', 'mapping_type', 'active']
    search_fields = ['local_model', 'local_pk', 'local_code', 'alegra_id', 'description']


class AlegraDocumentInline(admin.TabularInline):
    model = AlegraDocument
    extra = 0
    fields = ['document_type', 'local_key', 'status', 'alegra_id', 'error']
    readonly_fields = fields
    can_delete = False


@admin.register(AlegraSyncBatch)
class AlegraSyncBatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'empresa', 'proyecto', 'document_type', 'fecha_desde', 'fecha_hasta', 'status', 'success_count', 'error_count']
    list_filter = ['empresa', 'proyecto', 'document_type', 'status']
    date_hierarchy = 'created_at'
    inlines = [AlegraDocumentInline]


@admin.register(AlegraBillGetLog)
class AlegraBillGetLogAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'created_at',
        'empresa',
        'alegra_bill_id',
        'factura',
        'pdf_saved',
        'error_short',
    ]
    list_filter = ['pdf_saved', 'empresa']
    search_fields = ['alegra_bill_id', 'error', 'fields']
    readonly_fields = [
        'empresa',
        'alegra_bill_id',
        'factura',
        'fields',
        'response_json',
        'error',
        'pdf_saved',
        'created_at',
    ]
    date_hierarchy = 'created_at'

    def error_short(self, obj):
        t = (obj.error or '')[:80]
        return t or '—'

    error_short.short_description = 'Error (inicio)'


@admin.register(AlegraWebhookInboundLog)
class AlegraWebhookInboundLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'created_at', 'http_method', 'remote_addr', 'content_type', 'payload_preview']
    list_filter = ['http_method']
    search_fields = ['remote_addr', 'raw_body']
    readonly_fields = ['http_method', 'content_type', 'remote_addr', 'query_string', 'payload', 'raw_body', 'created_at']

    def payload_preview(self, obj):
        keys = list((obj.payload or {}).keys())[:8]
        return ', '.join(keys) if keys else '(vacío)'

    payload_preview.short_description = 'Claves payload'


@admin.register(AlegraWebhookSubscriptionLog)
class AlegraWebhookSubscriptionLogAdmin(admin.ModelAdmin):
    list_display = ['id', 'empresa', 'event', 'response_status', 'success', 'created_at', 'created_by']
    list_filter = ['success', 'event', 'empresa']
    search_fields = ['callback_url', 'event']
    readonly_fields = ['empresa', 'event', 'callback_url', 'request_json', 'response_status', 'response_json', 'success', 'created_by', 'created_at']


@admin.register(AlegraDocument)
class AlegraDocumentAdmin(admin.ModelAdmin):
    list_display = ['id', 'empresa', 'proyecto', 'document_type', 'local_key', 'status', 'alegra_id', 'updated_at']
    list_filter = ['empresa', 'proyecto', 'document_type', 'status', 'transport']
    search_fields = ['local_key', 'source_pk', 'alegra_id', 'error']
    readonly_fields = ['created_at', 'updated_at', 'sent_at']
