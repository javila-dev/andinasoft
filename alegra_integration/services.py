import logging
import re
import time
from urllib.parse import quote, urlparse

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.cache import cache

from accounting.models import Anticipos, Pagos, Partners, gastos_caja, transferencias_companias
from alegra_integration.builders import (
    CajaGastoBillBuilder,
    CajaLegalizationJournalBuilder,
    CommissionBuilder,
    ExpensePaymentBuilder,
    GttBuilder,
    ReceiptPaymentBuilder,
)
from alegra_integration.bill_mapping import cxp_category_id_from_bill, cxp_category_id_from_contact
from alegra_integration.client import AlegraMCPClient
from alegra_integration.mapping import MappingResolver
from alegra_integration.pago_link import sync_pago_from_alegra_document
from alegra_integration.pago_reconcile import reconcile_expense_payment_document, should_attempt_payment_reconcile
from alegra_integration.exceptions import AlegraBuildError, AlegraConfigurationError, AlegraIntegrationError

logger = logging.getLogger(__name__)
from alegra_integration.models import (
    AlegraContactIndex,
    AlegraDocument,
    AlegraMapping,
    AlegraSyncBatch,
    AlegraWebhookSubscriptionLog,
)
from andinasoft.models import Detalle_gtt, Gtt, asesores, clientes, empresas, proyectos
from andinasoft.shared_models import Pagocomision, Recaudos_general


# Eventos admitidos por POST /webhooks/subscriptions (Alegra API v1).
ALEGRA_WEBHOOK_EVENTS = frozenset({
    'new-invoice', 'edit-invoice', 'delete-invoice',
    'new-bill', 'edit-bill', 'delete-bill',
    'new-client', 'edit-client', 'delete-client',
    'new-item', 'edit-item', 'delete-item',
})

# Ruta fija (tras el dominio) donde Alegra llamará al webhook de bills (ingesta futura).
# Nota: algunas entregas parecen descartar query params; preferimos un path con empresa embebida.
ALEGRA_WEBHOOK_BILLS_INGEST_SUFFIX = '/accounting/alegra/webhooks/bills/'


def _norm_ident(value):
    """Normalize NIT/cédula: strip non-alphanumerics, uppercase."""
    return re.sub(r'[^0-9A-Za-z]', '', str(value or '')).strip().upper()


def _ident_variants(value):
    """
    Return acceptable lookup keys for an identification.
    Handles Colombia NIT with dígito de verificación (DV) where one side may include it and the other may not.
    Example: "901560549-1" -> {"9015605491", "901560549"}
    """
    key = _norm_ident(value)
    if not key:
        return []
    variants = {key}
    # If all digits, also try without last digit (DV) for matching "NIT" vs "NIT+DV".
    if key.isdigit() and len(key) >= 6:
        variants.add(key[:-1])
    return [v for v in variants if v]


_MISSING_CONTACT_RE = re.compile(r'model=(?P<model>[^,]+),\s*pk=(?P<pk>[^)]+)\)')
_MISSING_PARTNER_IDENT_RE = re.compile(r'identification=(?P<ident>[^)]+)\)')


def _pick_local_name(obj, fields):
    if not obj:
        return ''
    for field in fields:
        value = getattr(obj, field, None)
        value = (value or '').strip() if isinstance(value, str) else (str(value).strip() if value is not None else '')
        if value:
            return value
    return ''


def _partner_display_name(partner):
    if not partner:
        return ''
    nombre_completo = getattr(partner, 'nombre_completo', None)
    if callable(nombre_completo):
        name = (nombre_completo() or '').strip()
        if name:
            return name
    nombres = _pick_local_name(partner, ['nombres'])
    apellidos = _pick_local_name(partner, ['apellidos'])
    return f'{nombres} {apellidos}'.strip() or nombres or apellidos


def _local_third_party_info(local_model, local_pk):
    """
    Returns (resolved_local_model, ident, name, contact_types) for bulk contact tools.
    """
    ident = str(local_pk or '').strip()
    if not ident:
        return (local_model, '', '', ['client'])

    if local_model == 'accounting.partners':
        partner = Partners.objects.filter(pk=ident).first()
        name = _partner_display_name(partner)
        if partner:
            return ('accounting.partners', ident, name, ['provider'])

    if local_model == 'andinasoft.profiles':
        from andinasoft.models import Profiles
        profile = Profiles.objects.filter(pk=ident).first()
        if not profile:
            profile = Profiles.objects.filter(identificacion=ident).first()
        if profile:
            return ('andinasoft.profiles', str(profile.pk), str(profile), ['provider', 'client'])

    if local_model == 'andinasoft.terceros_raw':
        return ('andinasoft.terceros_raw', ident, '', ['provider', 'client'])

    if local_model == 'andinasoft.clientes':
        obj = clientes.objects.filter(pk=ident).first()
        name = _pick_local_name(obj, ['nombrecompleto', 'nombres', 'apellidos', 'nombre', 'razon_social', 'razonSocial'])
        if obj and not name:
            n = _pick_local_name(obj, ['nombres'])
            a = _pick_local_name(obj, ['apellidos'])
            name = f'{n} {a}'.strip()
        if name:
            return ('andinasoft.clientes', ident, name, ['client'])
    elif local_model == 'andinasoft.empresas':
        obj = empresas.objects.filter(pk=ident).first()
        name = _pick_local_name(obj, ['nombre', 'razon_social', 'razonSocial', 'nombrecompleto'])
        if name:
            return ('andinasoft.empresas', ident, name, ['provider'])
    elif local_model == 'andinasoft.asesores':
        obj = asesores.objects.filter(pk=ident).first()
        name = _pick_local_name(obj, ['nombre', 'nombrecompleto'])
        if name:
            return ('andinasoft.asesores', ident, name, ['provider'])

    partner = Partners.objects.filter(pk=ident).first()
    name = _partner_display_name(partner)
    if name:
        return ('accounting.partners', ident, name, ['provider'])

    obj = empresas.objects.filter(pk=ident).first()
    name = _pick_local_name(obj, ['nombre', 'razon_social', 'razonSocial', 'nombrecompleto'])
    if name:
        return ('andinasoft.empresas', ident, name, ['provider'])

    obj = clientes.objects.filter(pk=ident).first()
    name = _pick_local_name(obj, ['nombrecompleto', 'nombres', 'apellidos', 'nombre', 'razon_social', 'razonSocial'])
    if obj and not name:
        n = _pick_local_name(obj, ['nombres'])
        a = _pick_local_name(obj, ['apellidos'])
        name = f'{n} {a}'.strip()
    if name:
        return ('andinasoft.clientes', ident, name, ['client'])

    obj = asesores.objects.filter(pk=ident).first()
    name = _pick_local_name(obj, ['nombre', 'nombrecompleto'])
    if name:
        return ('andinasoft.asesores', ident, name, ['provider'])

    return (local_model, ident, '', ['client'])


def _resolve_identification_to_local(ident):
    """
    Resuelve cédula/NIT al registro local correcto para enlazar contactos.
    Orden: Partners → Profiles (responsable caja) → asesor → cliente → empresa.
    """
    raw = str(ident or '').strip()
    if not raw:
        return None

    from andinasoft.models import Profiles

    keys = _ident_variants(raw)
    for key in keys:
        partner = Partners.objects.filter(pk=key).first()
        if partner:
            return ('accounting.partners', str(partner.pk), _partner_display_name(partner))

    for key in keys:
        profile = Profiles.objects.filter(identificacion=key).first()
        if profile:
            return ('andinasoft.profiles', str(profile.pk), str(profile))

    for key in keys:
        obj = asesores.objects.filter(pk=key).first()
        if obj:
            return ('andinasoft.asesores', str(obj.pk), (obj.nombre or '').strip())

    for key in keys:
        obj = clientes.objects.filter(pk=key).first()
        if obj:
            name = _pick_local_name(obj, ['nombrecompleto', 'nombres', 'apellidos', 'nombre'])
            return ('andinasoft.clientes', str(obj.pk), name)

    for key in keys:
        obj = empresas.objects.filter(pk=key).first()
        if obj:
            name = _pick_local_name(obj, ['nombre', 'razon_social', 'razonSocial'])
            return ('andinasoft.empresas', str(obj.pk), name)

    return ('andinasoft.terceros_raw', raw, '')


def _contact_index_ident(resolved_model, local_pk):
    """Identificación para AlegraContactIndex (puede diferir del local_pk del mapeo)."""
    if resolved_model == 'andinasoft.profiles':
        from andinasoft.models import Profiles
        profile = Profiles.objects.filter(pk=local_pk).first()
        if profile and profile.identificacion:
            return _norm_ident(profile.identificacion)
    return _norm_ident(local_pk)


def _extract_missing_contact_refs(error):
    """Parse invalid-doc errors into (local_model, local_pk) pairs."""
    err = (error or '')
    refs = []
    seen = set()

    if 'tipo "contact"' in err:
        match = _MISSING_CONTACT_RE.search(err)
        if match:
            refs.append((match.group('model').strip(), match.group('pk').strip()))

    if 'accounting.partners' in err:
        match = _MISSING_CONTACT_RE.search(err)
        if match and match.group('model').strip() == 'accounting.partners':
            refs.append((match.group('model').strip(), match.group('pk').strip()))

    if 'identification=' in err and 'índice Alegra' in err:
        match = _MISSING_PARTNER_IDENT_RE.search(err)
        if match:
            ident = match.group('ident').strip()
            resolved = _resolve_identification_to_local(ident)
            if resolved:
                refs.append((resolved[0], resolved[1]))
            else:
                refs.append(('andinasoft.terceros_raw', ident))

    if 'responsable de la caja' in err.lower() and 'identificacion=' in err.lower():
        match = re.search(r'identificacion=([^)\s,]+)', err, re.I)
        if match:
            ident = match.group(1).strip()
            resolved = _resolve_identification_to_local(ident)
            if resolved:
                refs.append((resolved[0], resolved[1]))
            else:
                refs.append(('andinasoft.terceros_raw', ident))

    out = []
    for model, pk in refs:
        key = (model, pk)
        if model and pk and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _mirror_tercero_raw_contact_mapping(empresa_id, *, local_pk, alegra_id, name=''):
    """
    Guarda alias andinasoft.terceros_raw para que egresos resuelvan idtercero/NIT
    aunque el enlace manual se haya hecho como Cliente u otro tipo.
    """
    pk = str(local_pk or '').strip()
    aid = str(alegra_id or '').strip()
    if not pk or not aid:
        return
    AlegraMapping.objects.update_or_create(
        empresa_id=empresa_id,
        proyecto=None,
        mapping_type=AlegraMapping.CONTACT,
        local_model='andinasoft.terceros_raw',
        local_pk=pk,
        local_code='',
        defaults={
            'alegra_id': aid,
            'description': (name or '')[:255],
            'active': True,
        },
    )


def _upsert_contact_index_for_mapping(empresa, *, ident, alegra_id, name, contact_types):
    ident_key = _norm_ident(ident)
    if not ident_key or not alegra_id:
        return
    for contact_type in contact_types or ['client']:
        AlegraContactIndex.objects.update_or_create(
            empresa=empresa,
            contact_type=contact_type,
            identification=ident_key,
            defaults={
                'alegra_id': str(alegra_id),
                'name': (name or '')[:255],
                'raw': {},
            },
        )


class AlegraIntegrationService:
    def __init__(self, user=None):
        self.user = user

    def preview(self, *, empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id=None, caja_id=None):
        empresa, proyecto, desde, hasta, caja_id = self._validate_input(
            empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id, caja_id=caja_id,
        )
        batch = AlegraSyncBatch.objects.create(
            empresa=empresa,
            proyecto=proyecto,
            document_type=document_type,
            fecha_desde=desde,
            fecha_hasta=hasta,
            status=AlegraSyncBatch.STATUS_PREVIEW,
            created_by=self.user if getattr(self.user, 'is_authenticated', False) else None,
        )

        built_results = self._build_documents(
            empresa, proyecto, document_type, desde, hasta, caja_id=caja_id, batch=batch,
        )
        ready_to_send = 0
        already_sent = 0
        invalid = 0
        documents = []

        for result in built_results:
            if result.get('existing_sent'):
                doc = result['existing_sent']
                doc.batch = batch
                doc.save(update_fields=['batch', 'updated_at'])
                already_sent += 1
                documents.append(self._document_summary(doc))
                continue

            if result.get('pending_journal'):
                doc = result['pending_journal']
                documents.append(self._document_summary(doc))
                continue

            if result.get('error'):
                invalid += 1
                doc = self._upsert_document(
                    batch,
                    empresa,
                    proyecto,
                    document_type=result['document_type'],
                    source_model=result['source_model'],
                    source_pk=result['source_pk'],
                    local_key=result['local_key'],
                    payload=result.get('payload') or {},
                    operation=result.get('operation') or '',
                    transport=result.get('transport') or '',
                    status=AlegraDocument.STATUS_INVALID,
                    error=result['error'],
                )
            else:
                built = result['built']
                doc_empresa = empresas.objects.get(pk=built.empresa_id) if getattr(built, 'empresa_id', None) else empresa
                doc_proyecto = proyectos.objects.get(pk=built.proyecto_id) if getattr(built, 'proyecto_id', None) else proyecto
                doc = self._upsert_document(
                    batch,
                    doc_empresa,
                    doc_proyecto,
                    document_type=built.document_type,
                    source_model=built.source_model,
                    source_pk=built.source_pk,
                    local_key=built.local_key,
                    payload=built.payload,
                    operation=built.operation,
                    transport=built.transport,
                    status=AlegraDocument.STATUS_VALID,
                    error='',
                )
                if doc.status == AlegraDocument.STATUS_SENT:
                    already_sent += 1
                elif doc.status == AlegraDocument.STATUS_VALID:
                    ready_to_send += 1
            documents.append(self._document_summary(doc))

        batch.total_documents = len(documents)
        batch.success_count = ready_to_send
        batch.error_count = invalid
        batch.summary = {
            'ready_to_send': ready_to_send,
            'already_sent': already_sent,
            'built_ok': ready_to_send + already_sent,
            'invalid': invalid,
        }
        if caja_id is not None:
            batch.summary['caja_id'] = caja_id
        batch.save(update_fields=['total_documents', 'success_count', 'error_count', 'summary', 'updated_at'])
        return self._batch_response(batch, documents)

    def send(self, *, empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id=None, caja_id=None, retry_failed=True):
        preview = self.preview(
            empresa_id=empresa_id,
            document_type=document_type,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            proyecto_id=proyecto_id,
            caja_id=caja_id,
        )
        batch = AlegraSyncBatch.objects.get(pk=preview['batch']['id'])
        return self._send_batch_documents(batch, retry_failed=retry_failed)

    def send_existing_batch(self, *, batch_id, retry_failed=True):
        """
        Envia un lote ya construido en vista previa (sin reconstruir documentos).
        Útil para: abrir un lote en preview y enviarlo directamente desde la UI.
        """
        batch = AlegraSyncBatch.objects.get(pk=int(batch_id))
        return self._send_batch_documents(batch, retry_failed=retry_failed)

    def send_one_batch_document(self, *, batch_id, document_id=None, retry_failed=True):
        """
        Envía un solo documento del lote (reinicia timeout HTTP por petición).
        Repetir hasta complete=True en la respuesta.
        """
        batch = AlegraSyncBatch.objects.get(pk=int(batch_id))
        if batch.status in (AlegraSyncBatch.STATUS_DONE,):
            totals = self._batch_send_totals(batch)
            documents = [self._document_summary(d) for d in batch.documents.order_by('id')]
            return {
                **self._batch_response(batch, documents),
                'complete': True,
                'remaining': totals['pending'],
                'document': None,
            }

        if batch.status == AlegraSyncBatch.STATUS_PREVIEW:
            batch.status = AlegraSyncBatch.STATUS_PROCESSING
            batch.save(update_fields=['status', 'updated_at'])

        if document_id:
            doc = batch.documents.filter(pk=int(document_id)).first()
            if not doc:
                raise AlegraIntegrationError(f'Documento {document_id} no pertenece al lote {batch_id}.')
        else:
            doc = self._next_sendable_batch_document(batch, retry_failed=retry_failed)

        if not doc:
            self._finalize_batch_send(batch)
            documents = [self._document_summary(d) for d in batch.documents.order_by('id')]
            totals = self._batch_send_totals(batch)
            return {
                **self._batch_response(batch, documents),
                'complete': True,
                'remaining': totals['pending'],
                'document': None,
            }

        client_by_empresa = {}
        try:
            self._prepare_caja_document_for_send(batch, doc)
        except AlegraIntegrationError as exc:
            doc.status = AlegraDocument.STATUS_FAILED
            doc.error = str(exc)
            doc.save(update_fields=['status', 'error', 'updated_at'])
            batch.refresh_from_db()
            self._finalize_batch_send(batch)
            batch.refresh_from_db()
            totals = self._batch_send_totals(batch)
            documents = [self._document_summary(d) for d in batch.documents.order_by('id')]
            return {
                **self._batch_response(batch, documents),
                'complete': True,
                'stopped_on_error': True,
                'remaining': totals['pending'],
                'document': self._document_summary(doc),
            }

        self._try_send_batch_document(batch, doc, client_by_empresa, retry_failed=retry_failed)
        doc.refresh_from_db()
        batch.refresh_from_db()

        stopped_on_error = doc.status == AlegraDocument.STATUS_FAILED
        remaining = self._count_sendable_batch_documents(batch, retry_failed=retry_failed)
        complete = stopped_on_error or remaining == 0
        if complete:
            self._finalize_batch_send(batch)
            batch.refresh_from_db()
            remaining = self._batch_send_totals(batch)['pending']

        documents = [self._document_summary(d) for d in batch.documents.order_by('id')]
        return {
            **self._batch_response(batch, documents),
            'complete': complete,
            'stopped_on_error': stopped_on_error,
            'remaining': remaining,
            'document': self._document_summary(doc),
        }

    def _batch_send_totals(self, batch):
        qs = batch.documents.all()
        return {
            'sent': qs.filter(status=AlegraDocument.STATUS_SENT).count(),
            'failed': qs.filter(status=AlegraDocument.STATUS_FAILED).count(),
            'invalid': qs.filter(status=AlegraDocument.STATUS_INVALID).count(),
            'skipped': qs.filter(status=AlegraDocument.STATUS_SKIPPED).count(),
            'pending': qs.filter(status=AlegraDocument.STATUS_VALID).count(),
        }

    def _count_sendable_batch_documents(self, batch, *, retry_failed=True):
        statuses = [AlegraDocument.STATUS_VALID]
        if retry_failed:
            statuses.append(AlegraDocument.STATUS_FAILED)
        return batch.documents.filter(status__in=statuses).count()

    def _next_sendable_batch_document(self, batch, *, retry_failed=True):
        statuses = [AlegraDocument.STATUS_VALID]
        if retry_failed:
            statuses.append(AlegraDocument.STATUS_FAILED)
        qs = batch.documents.filter(status__in=statuses)
        if batch.document_type == AlegraSyncBatch.DOC_CAJA:
            docs = sorted(qs, key=self._caja_document_sort_key)
            return docs[0] if docs else None
        return qs.order_by('id').first()

    def _finalize_batch_send(self, batch):
        totals = self._batch_send_totals(batch)
        sent = totals['sent']
        failed = totals['failed'] + totals['invalid']
        skipped = totals['skipped']
        if failed == 0:
            final_status = AlegraSyncBatch.STATUS_DONE
        elif sent > 0:
            final_status = AlegraSyncBatch.STATUS_PARTIAL
        else:
            final_status = AlegraSyncBatch.STATUS_FAILED
        batch.status = final_status
        batch.success_count = sent
        batch.error_count = failed
        batch.summary = {'sent': sent, 'failed': failed, 'skipped': skipped}
        batch.completed_at = timezone.now()
        batch.save(update_fields=['status', 'success_count', 'error_count', 'summary', 'completed_at', 'updated_at'])

    def _caja_document_sort_key(self, doc):
        type_order = {'caja_bill': 0, 'caja_journal': 1}
        return (type_order.get(doc.document_type, 9), doc.pk)

    def _prepare_caja_document_for_send(self, batch, doc):
        """Antes de enviar un journal de caja: construye (si falta) e inyecta CxP del bill."""
        if batch.document_type != AlegraSyncBatch.DOC_CAJA:
            return
        if doc.document_type != 'caja_journal':
            return
        payload = doc.payload or {}
        local = payload.get('__local') if isinstance(payload.get('__local'), dict) else {}
        pending_bills = local.get('pending_bills') or []
        entries = payload.get('entries') or []
        needs_build = bool(local.get('awaiting_bills')) or (
            pending_bills and len(entries) < len(pending_bills)
        )
        if needs_build:
            self._activate_caja_journal_doc(batch, doc)
        else:
            self._finalize_caja_journal_doc(doc)

    def _try_send_batch_document(self, batch, doc, client_by_empresa, *, retry_failed=True):
        if doc.status == AlegraDocument.STATUS_SENT:
            return 'skipped'
        if doc.status == AlegraDocument.STATUS_INVALID:
            return 'invalid'
        if doc.status == AlegraDocument.STATUS_FAILED and not retry_failed:
            return 'skipped'

        existing_sent = AlegraDocument.objects.filter(
            empresa=doc.empresa,
            document_type=doc.document_type,
            local_key=doc.local_key,
            status=AlegraDocument.STATUS_SENT,
        ).exclude(pk=doc.pk).first()
        if existing_sent:
            doc.status = AlegraDocument.STATUS_SKIPPED
            doc.response = {'skipped_reason': 'already_sent', 'existing_document_id': existing_sent.pk}
            doc.alegra_id = existing_sent.alegra_id
            doc.save(update_fields=['status', 'response', 'alegra_id', 'updated_at'])
            sync_pago_from_alegra_document(doc)
            return 'skipped'

        client = None
        try:
            emp_id = str(doc.empresa_id)
            client = client_by_empresa.get(emp_id)
            if not client:
                client = AlegraMCPClient(doc.empresa)
                client_by_empresa[emp_id] = client
            response = self._send_document(client, doc)
            doc.status = AlegraDocument.STATUS_SENT
            doc.response = response
            doc.alegra_id = self._extract_alegra_id(response)
            doc.error = ''
            doc.sent_at = timezone.now()
            doc.save(update_fields=['status', 'response', 'alegra_id', 'error', 'sent_at', 'updated_at'])
            sync_pago_from_alegra_document(doc)
            if doc.document_type == 'caja_bill':
                self._capture_caja_bill_cxp(client, doc)
                if batch.document_type == AlegraSyncBatch.DOC_CAJA:
                    self._refresh_caja_journal_progress(batch)
            return 'sent'
        except AlegraIntegrationError as exc:
            if (
                doc.alegra_operation == 'POST /payments'
                and doc.document_type == 'expense_payment'
                and should_attempt_payment_reconcile(exc)
            ):
                try:
                    reconcile_client = client or AlegraMCPClient(doc.empresa)
                    if reconcile_expense_payment_document(doc, reconcile_client, exc):
                        return 'sent'
                except Exception as reconcile_exc:
                    doc.status = AlegraDocument.STATUS_FAILED
                    doc.error = f'{exc} · Reconciliación falló: {reconcile_exc}'
                    doc.save(update_fields=['status', 'error', 'updated_at'])
                    return 'failed'
            doc.status = AlegraDocument.STATUS_FAILED
            doc.error = str(exc)
            doc.save(update_fields=['status', 'error', 'updated_at'])
            return 'failed'

    def _send_batch_documents(self, batch, *, retry_failed=True):
        batch.status = AlegraSyncBatch.STATUS_PROCESSING
        batch.save(update_fields=['status', 'updated_at'])

        client_by_empresa = {}
        stopped_on_error = False

        doc_list = list(batch.documents.order_by('id'))
        if batch.document_type == AlegraSyncBatch.DOC_CAJA:
            doc_list.sort(key=self._caja_document_sort_key)

        for doc in doc_list:
            if stopped_on_error:
                break
            if doc.status == AlegraDocument.STATUS_SENT:
                continue
            if doc.status == AlegraDocument.STATUS_INVALID:
                continue

            try:
                self._prepare_caja_document_for_send(batch, doc)
            except AlegraIntegrationError as exc:
                doc.status = AlegraDocument.STATUS_FAILED
                doc.error = str(exc)
                doc.save(update_fields=['status', 'error', 'updated_at'])
                stopped_on_error = True
                break

            outcome = self._try_send_batch_document(
                batch, doc, client_by_empresa, retry_failed=retry_failed,
            )
            if outcome == 'failed':
                stopped_on_error = True
                break

        self._finalize_batch_send(batch)
        batch.refresh_from_db()
        documents = [self._document_summary(d) for d in batch.documents.order_by('id')]
        response = self._batch_response(batch, documents)
        if stopped_on_error:
            response['stopped_on_error'] = True
        return response

    @staticmethod
    def _reference_sections_for_type(ref_type):
        """Mapeo type= del frontend → claves a consultar en Alegra (evita cargar todo en cada tab)."""
        key = (ref_type or '').strip().lower()
        if not key:
            return None
        if key in ('banks', 'categories', 'cost_centers', 'retentions', 'taxes'):
            return {key}
        if key in ('journal_numerations', 'journal_numeration', 'journals_numerations'):
            return {'journal_numerations'}
        if key in ('number_templates', 'numerations', 'numeration'):
            return {'number_templates'}
        return None

    def reference_sync(self, *, empresa_id, ref_type=None):
        empresa = empresas.objects.get(pk=empresa_id)
        client = AlegraMCPClient(empresa)
        sections = self._reference_sections_for_type(ref_type)
        return client.get_reference_data(sections=sections)

    def contact_sync(self, *, empresa_id):
        empresa = empresas.objects.get(pk=empresa_id)
        client = AlegraMCPClient(empresa)

        alegra_contacts = client.get_all_contacts()

        # Save a simple identification->id index for payload building.
        for c in alegra_contacts:
            raw_ident = c.get('identification') or ''
            if isinstance(raw_ident, dict):
                raw_ident = raw_ident.get('number') or ''
            ident = _norm_ident(raw_ident)
            if not ident:
                continue
            types = c.get('type') or []
            if isinstance(types, str):
                types = [types]
            types = [t for t in types if t in ('client', 'provider')]
            if not types:
                # default: treat as client
                types = ['client']
            name = (c.get('name') or c.get('businessName') or '').strip()
            for t in set(types):
                AlegraContactIndex.objects.update_or_create(
                    empresa=empresa,
                    contact_type=t,
                    identification=ident,
                    defaults={
                        'alegra_id': str(c.get('id') or ''),
                        'name': name[:255],
                        'raw': c or {},
                    },
                )

        # Index by normalized identification for fast lookup.
        # Handle both string and object formats: {"type":..,"number":..}
        def _ident(contact):
            raw = contact.get('identification') or ''
            if isinstance(raw, dict):
                raw = raw.get('number') or ''
            return _norm_ident(raw)

        by_ident = {}
        for c in alegra_contacts:
            key = _ident(c)
            for k in _ident_variants(key):
                if k:
                    by_ident[k] = c

        new_count = 0
        updated_count = 0
        unmatched = []

        def _upsert_contact(local_model, local_pk, local_ident, name):
            nonlocal new_count, updated_count
            match = None
            for k in _ident_variants(local_ident):
                match = by_ident.get(k)
                if match:
                    break
            if not match:
                unmatched.append({
                    'model': local_model,
                    'pk': str(local_pk),
                    'identification': str(local_ident),
                    'name': name,
                })
                return

            alegra_id = str(match['id'])
            # Safe upsert: MySQL allows multiple NULLs in unique index,
            # so filter manually instead of update_or_create.
            existing = AlegraMapping.objects.filter(
                empresa=empresa,
                proyecto__isnull=True,
                mapping_type=AlegraMapping.CONTACT,
                local_model=local_model,
                local_pk=str(local_pk),
                local_code='',
            ).first()

            if existing:
                if existing.alegra_id != alegra_id or not existing.active:
                    existing.alegra_id = alegra_id
                    existing.description = name[:255]
                    existing.active = True
                    existing.save(update_fields=['alegra_id', 'description', 'active', 'updated_at'])
                    updated_count += 1
            else:
                AlegraMapping.objects.create(
                    empresa=empresa,
                    proyecto=None,
                    mapping_type=AlegraMapping.CONTACT,
                    local_model=local_model,
                    local_pk=str(local_pk),
                    local_code='',
                    alegra_id=alegra_id,
                    description=name[:255],
                    active=True,
                )
                new_count += 1

        for c in clientes.objects.all():
            _upsert_contact('andinasoft.clientes', c.idTercero, c.idTercero, c.nombrecompleto)

        for a in asesores.objects.all():
            _upsert_contact('andinasoft.asesores', a.cedula, a.cedula, a.nombre)

        for e in empresas.objects.all():
            _upsert_contact('andinasoft.empresas', e.Nit, e.Nit, e.nombre)

        return {
            'alegra_total': len(alegra_contacts),
            'mapped_new': new_count,
            'mapped_updated': updated_count,
            'unmatched_count': len(unmatched),
            'unmatched': unmatched,
        }

    def _contact_sync_log_state(self, state, *, prefix='contact_sync'):
        by_ident = state.get('by_ident') or {}
        logger.info(
            '%s state phase=%s stage=%s alegra_type=%s alegra_start=%s alegra_loaded=%s '
            'by_ident_keys=%s processed=%s total_local=%s status=%s',
            prefix,
            state.get('phase'),
            state.get('stage'),
            state.get('alegra_type'),
            state.get('alegra_start'),
            state.get('alegra_loaded'),
            len(by_ident) if isinstance(by_ident, dict) else 0,
            state.get('processed'),
            state.get('total_local'),
            state.get('status'),
        )

    def contact_sync_progress(self, *, empresa_id, action='start', chunk_size=250):
        """
        Progressive contact sync for UI progress feedback.
        The flow is:
        - action=start: fetch Alegra contacts once, compute totals, init cache state
        - action=step: process next chunk of local third parties, update cache state
        - action=status: return current state without processing
        """
        user_id = getattr(getattr(self.user, 'pk', None), '__str__', lambda: 'anon')()
        key = f'alegra:contact_sync:{empresa_id}:{user_id}'
        state = cache.get(key) or {}
        logger.info(
            'contact_sync_progress empresa=%s action=%s chunk_size=%s cache_key=%s has_state=%s',
            empresa_id,
            action,
            chunk_size,
            key,
            bool(state),
        )

        def _ident(contact):
            raw = contact.get('identification') or ''
            if isinstance(raw, dict):
                raw = raw.get('number') or ''
            return _norm_ident(raw)

        if action == 'step' and not state:
            logger.warning(
                'contact_sync step sin estado en cache (expirado o otro worker?) empresa=%s key=%s',
                empresa_id,
                key,
            )

        if action == 'start' or not state:
            state = {
                'status': 'running',
                'empresa_id': empresa_id,
                # Phase 1: fetch Alegra contacts progressively
                'phase': 'alegra',
                'alegra_total': 0,  # unknown until finished
                'alegra_loaded': 0,
                'alegra_start': 0,
                'alegra_limit': 30,
                'alegra_type': 'client',
                # Phase 2: process local third parties progressively
                'total_local': 0,
                'processed': 0,
                'stage': 'alegra',
                'offset': 0,
                'mapped_new': 0,
                'mapped_updated': 0,
                'unmatched': [],
                'unmatched_count': 0,
                'by_ident': {},
            }
            cache.set(key, state, timeout=60 * 30)
            self._contact_sync_log_state(state, prefix='contact_sync start')
            return self._contact_sync_state_public(state)

        if action == 'status':
            if not state:
                return {'status': 'idle', 'phase': None, 'stage': None}
            return self._contact_sync_state_public(state)

        # step
        empresa = empresas.objects.get(pk=empresa_id)
        by_ident = state.get('by_ident') or {}
        phase = state.get('phase') or 'alegra'
        stage = state.get('stage') or ('alegra' if phase == 'alegra' else 'clientes')
        offset = int(state.get('offset') or 0)

        if phase == 'alegra':
            client = AlegraMCPClient(empresa)
            start = int(state.get('alegra_start') or 0)
            limit = int(state.get('alegra_limit') or 30)
            contact_type = state.get('alegra_type') or 'client'
            logger.info(
                'contact_sync alegra page empresa=%s type=%s start=%s limit=%s loaded_so_far=%s',
                empresa_id,
                contact_type,
                start,
                limit,
                state.get('alegra_loaded'),
            )
            try:
                page = client.get_contacts_page(start=start, limit=limit, contact_type=contact_type)
            except Exception as exc:
                logger.error(
                    'contact_sync get_contacts_page failed empresa=%s type=%s start=%s limit=%s: %s',
                    empresa_id,
                    contact_type,
                    start,
                    limit,
                    exc,
                    exc_info=True,
                )
                raise
            # Alegra returns list; if wrapped in metadata=true it'd be page['data']
            if isinstance(page, dict) and 'data' in page:
                page = page['data']
            page = page if isinstance(page, list) else []
            logger.info(
                'contact_sync alegra page ok empresa=%s type=%s start=%s page_len=%s page_type=%s',
                empresa_id,
                contact_type,
                start,
                len(page),
                type(page).__name__ if not isinstance(page, list) else 'list',
            )
            for c in page:
                k = _ident(c)
                for kk in _ident_variants(k):
                    if kk:
                        by_ident[kk] = {'id': str(c.get('id')), 'name': c.get('name') or c.get('businessName') or ''}
                # Also upsert the contact index as we stream pages
                if k:
                    try:
                        AlegraContactIndex.objects.update_or_create(
                            empresa=empresa,
                            contact_type=contact_type,
                            identification=k,
                            defaults={
                                'alegra_id': str(c.get('id') or ''),
                                'name': (c.get('name') or c.get('businessName') or '')[:255],
                                'raw': c or {},
                            },
                        )
                    except Exception as exc:
                        logger.error(
                            'contact_sync AlegraContactIndex upsert failed empresa=%s type=%s '
                            'ident=%s alegra_id=%s: %s',
                            empresa_id,
                            contact_type,
                            k,
                            c.get('id'),
                            exc,
                            exc_info=True,
                        )
                        raise
            state['by_ident'] = by_ident
            state['alegra_loaded'] = int(state.get('alegra_loaded') or 0) + len(page)
            state['alegra_start'] = start + limit
            state['stage'] = 'alegra'

            if len(page) < limit:
                # finished this type; switch to providers if we just finished clients
                if contact_type == 'client':
                    logger.info(
                        'contact_sync alegra finished clients empresa=%s loaded=%s -> providers',
                        empresa_id,
                        state.get('alegra_loaded'),
                    )
                    state['alegra_type'] = 'provider'
                    state['alegra_start'] = 0
                else:
                    # finished loading all Alegra contacts (client + provider)
                    logger.info(
                        'contact_sync alegra finished all empresa=%s total_loaded=%s -> local phase',
                        empresa_id,
                        state.get('alegra_loaded'),
                    )
                    state['phase'] = 'local'
                    state['alegra_total'] = int(state.get('alegra_loaded') or 0)
                    state['total_local'] = (
                        clientes.objects.count()
                        + asesores.objects.count()
                        + empresas.objects.count()
                        + Partners.objects.count()
                    )
                    state['stage'] = 'clientes'
                    state['offset'] = 0
            try:
                cache.set(key, state, timeout=60 * 30)
            except Exception as exc:
                logger.error(
                    'contact_sync cache.set failed empresa=%s by_ident_keys=%s: %s',
                    empresa_id,
                    len(by_ident),
                    exc,
                    exc_info=True,
                )
                raise
            self._contact_sync_log_state(state, prefix='contact_sync alegra step')
            return self._contact_sync_state_public(state)

        def _iter_queryset(qs, to_process):
            return list(qs.order_by('pk')[offset:offset + to_process])

        def _upsert_contact(local_model, local_pk, local_ident, name):
            match = None
            for k in _ident_variants(local_ident):
                match = by_ident.get(k)
                if match:
                    break
            if not match:
                state['unmatched_count'] += 1
                if len(state['unmatched']) < 500:
                    state['unmatched'].append({
                        'model': local_model,
                        'pk': str(local_pk),
                        'identification': str(local_ident),
                        'name': name,
                    })
                return

            alegra_id = str(match['id'])
            existing = AlegraMapping.objects.filter(
                empresa=empresa,
                proyecto__isnull=True,
                mapping_type=AlegraMapping.CONTACT,
                local_model=local_model,
                local_pk=str(local_pk),
                local_code='',
            ).first()

            if existing:
                if existing.alegra_id != alegra_id or not existing.active:
                    existing.alegra_id = alegra_id
                    existing.description = (name or '')[:255]
                    existing.active = True
                    existing.save(update_fields=['alegra_id', 'description', 'active', 'updated_at'])
                    state['mapped_updated'] += 1
            else:
                AlegraMapping.objects.create(
                    empresa=empresa,
                    proyecto=None,
                    mapping_type=AlegraMapping.CONTACT,
                    local_model=local_model,
                    local_pk=str(local_pk),
                    local_code='',
                    alegra_id=alegra_id,
                    description=(name or '')[:255],
                    active=True,
                )
                state['mapped_new'] += 1

        remaining = chunk_size
        while remaining > 0 and stage:
            if stage == 'clientes':
                batch = _iter_queryset(clientes.objects.all(), remaining)
                for c in batch:
                    _upsert_contact('andinasoft.clientes', c.idTercero, c.idTercero, c.nombrecompleto)
                state['processed'] += len(batch)
                if len(batch) < remaining:
                    stage = 'asesores'
                    offset = 0
                else:
                    offset += len(batch)
            elif stage == 'asesores':
                batch = _iter_queryset(asesores.objects.all(), remaining)
                for a in batch:
                    _upsert_contact('andinasoft.asesores', a.cedula, a.cedula, a.nombre)
                state['processed'] += len(batch)
                if len(batch) < remaining:
                    stage = 'empresas'
                    offset = 0
                else:
                    offset += len(batch)
            elif stage == 'empresas':
                batch = _iter_queryset(empresas.objects.all(), remaining)
                for e in batch:
                    _upsert_contact('andinasoft.empresas', e.Nit, e.Nit, e.nombre)
                state['processed'] += len(batch)
                if len(batch) < remaining:
                    stage = 'partners'
                    offset = 0
                else:
                    offset += len(batch)
            elif stage == 'partners':
                batch = _iter_queryset(Partners.objects.all(), remaining)
                for partner in batch:
                    _upsert_contact(
                        'accounting.partners',
                        partner.idTercero,
                        partner.idTercero,
                        _partner_display_name(partner),
                    )
                state['processed'] += len(batch)
                if len(batch) < remaining:
                    stage = None
                else:
                    offset += len(batch)
            remaining = 0  # we used up the chunk in one stage per request

        state['stage'] = stage or 'done'
        state['offset'] = offset
        if state['processed'] >= state.get('total_local', 0) or stage is None:
            state['status'] = 'done'
            state['stage'] = 'done'
            # Drop big index to keep cache small
            state.pop('by_ident', None)
            logger.info(
                'contact_sync done empresa=%s alegra_total=%s mapped_new=%s mapped_updated=%s unmatched=%s',
                empresa_id,
                state.get('alegra_total'),
                state.get('mapped_new'),
                state.get('mapped_updated'),
                state.get('unmatched_count'),
            )
        try:
            cache.set(key, state, timeout=60 * 30)
        except Exception as exc:
            logger.error(
                'contact_sync cache.set (local) failed empresa=%s processed=%s: %s',
                empresa_id,
                state.get('processed'),
                exc,
                exc_info=True,
            )
            raise
        self._contact_sync_log_state(state, prefix='contact_sync local step')
        return self._contact_sync_state_public(state)

    def _contact_sync_state_public(self, state):
        total_local = int(state.get('total_local') or 0)
        processed = int(state.get('processed') or 0)
        # Backward-compatible fallback: older cached states may lack "phase"
        phase = state.get('phase') or ('alegra' if state.get('stage') == 'alegra' else 'local')
        if phase == 'alegra':
            # Only Alegra loading phase; show percent as unknown but increasing with loaded contacts.
            pct = 0
        else:
            pct = 0 if total_local <= 0 else int(round((processed / total_local) * 100))
        return {
            'status': state.get('status') or 'running',
            'stage': state.get('stage') or 'running',
            'phase': phase,
            'alegra_total': int(state.get('alegra_total') or 0),
            'alegra_loaded': int(state.get('alegra_loaded') or 0),
            'alegra_type': state.get('alegra_type') or None,
            'total_local': total_local,
            'processed': processed,
            'percent': pct,
            'mapped_new': int(state.get('mapped_new') or 0),
            'mapped_updated': int(state.get('mapped_updated') or 0),
            'unmatched_count': int(state.get('unmatched_count') or 0),
            'unmatched': state.get('unmatched') or [],
        }

    def batch_detail(self, batch_id):
        batch = AlegraSyncBatch.objects.select_related('created_by').get(pk=batch_id)
        return self._batch_response(batch, [self._document_summary(doc) for doc in batch.documents.order_by('id')])

    def delete_preview_batches(self, *, empresa_id=None, batch_id=None):
        """
        Elimina lotes en vista previa (o procesamiento abandonado) que no tengan
        documentos ya enviados o fallidos en Alegra. Los inválidos u omitidos sí
        se pueden borrar porque no hubo envío real.
        """
        non_deletable_doc_statuses = (
            AlegraDocument.STATUS_SENT,
            AlegraDocument.STATUS_FAILED,
        )
        qs = AlegraSyncBatch.objects.filter(
            status__in=(AlegraSyncBatch.STATUS_PREVIEW, AlegraSyncBatch.STATUS_PROCESSING),
        )
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        if batch_id:
            qs = qs.filter(pk=int(batch_id))

        deleted_ids = []
        skipped_ids = []
        for batch in qs.prefetch_related('documents'):
            docs = list(batch.documents.all())
            if not docs:
                deleted_ids.append(batch.pk)
                continue
            statuses = {doc.status for doc in docs}
            if statuses.intersection(non_deletable_doc_statuses):
                skipped_ids.append(batch.pk)
                continue
            deleted_ids.append(batch.pk)

        if deleted_ids:
            AlegraSyncBatch.objects.filter(pk__in=deleted_ids).delete()

        return {
            'deleted': len(deleted_ids),
            'ids': deleted_ids,
            'skipped': len(skipped_ids),
            'skipped_ids': skipped_ids,
        }

    def bulk_create_missing_contacts(self, *, batch_id):
        """
        For a given batch, find invalid documents failing due to missing contact mappings,
        validate existence in Alegra by identification, and create missing contacts in bulk.
        Then create AlegraMapping(CONTACT) records.
        """
        batch = AlegraSyncBatch.objects.get(pk=batch_id)
        empresa = batch.empresa
        client = AlegraMCPClient(empresa)

        missing = {}
        contact_error_docs = batch.documents.filter(
            status__in=(AlegraDocument.STATUS_INVALID, AlegraDocument.STATUS_FAILED),
        ).values('error', 'source_model', 'source_pk', 'local_key')
        for doc in contact_error_docs:
            for local_model, local_pk in _extract_missing_contact_refs(doc.get('error')):
                missing[(local_model, local_pk)] = True

        candidates = [{'local_model': k[0], 'local_pk': k[1]} for k in missing.keys()]

        created = 0
        mapped = 0
        found_existing = 0
        skipped_already_mapped = 0
        errors = []
        warnings = []

        def _match_by_ident(results, ident):
            target_keys = set(_ident_variants(ident))
            for c in (results or []):
                if not isinstance(c, dict):
                    continue
                raw = c.get('identification') or ''
                if isinstance(raw, dict):
                    raw = raw.get('number') or ''
                keys = set(_ident_variants(raw))
                if target_keys & keys:
                    return c
            return None

        for item in candidates:
            local_model = item['local_model']
            local_pk = item['local_pk']

            resolved_model, ident, name, contact_types = _local_third_party_info(local_model, local_pk)

            # Skip if already mapped
            existing = AlegraMapping.objects.filter(
                empresa=empresa,
                proyecto__isnull=True,
                mapping_type=AlegraMapping.CONTACT,
                local_model=resolved_model,
                local_pk=str(ident),
                local_code='',
                active=True,
            ).first()
            if existing:
                skipped_already_mapped += 1
                continue

            if not ident:
                errors.append({'local_model': local_model, 'local_pk': local_pk, 'error': 'No se pudo obtener identificación local'})
                continue

            try:
                # Validate if already exists in Alegra
                page = client.search_contacts(ident, start=0, limit=30)
                if isinstance(page, dict) and 'data' in page:
                    page = page['data']
                page = page if isinstance(page, list) else []
                match = _match_by_ident(page, ident)
                if match:
                    alegra_id = str(match.get('id'))
                    found_existing += 1
                    if not name:
                        # If local name is missing, we can still create the mapping using Alegra's name.
                        name = (match.get('name') or match.get('fullName') or match.get('businessName') or '').strip()
                else:
                    if not name:
                        # Do not block the whole batch: create a placeholder contact name.
                        name = f'TERCERO {ident}'.strip()
                        warnings.append({'local_model': resolved_model, 'local_pk': ident, 'warning': 'Nombre local vacío; se creó en Alegra con nombre placeholder.'})
                    payload = {
                        'name': name[:255],
                        'identification': str(ident),
                        'type': contact_types,
                    }
                    # Alegra sometimes returns transient error code 905. Retry a few times.
                    last_exc = None
                    created_obj = None
                    for attempt in range(3):
                        try:
                            created_obj = client.create_contact(payload)
                            last_exc = None
                            break
                        except Exception as exc:
                            last_exc = exc
                            msg = str(exc)
                            if 'code' in msg and '905' in msg and attempt < 2:
                                time.sleep(1.0 + attempt)
                                continue
                            break
                    # If it keeps failing with 905, try a minimal payload (some accounts reject identification formats).
                    if last_exc and ('905' in str(last_exc)):
                        try:
                            created_obj = client.create_contact({'name': name[:255], 'type': contact_types})
                            warnings.append({
                                'local_model': resolved_model,
                                'local_pk': ident,
                                'warning': 'Alegra devolvió 905 al crear con identificación; se creó con payload mínimo (sin identificación).',
                            })
                            last_exc = None
                        except Exception as exc2:
                            last_exc = exc2
                    if last_exc:
                        raise last_exc
                    alegra_id = str(created_obj.get('id') or created_obj.get('idContact') or '')
                    if not alegra_id:
                        raise AlegraIntegrationError(f'No se pudo obtener id del contacto creado: {created_obj}')
                    created += 1

                # Ensure alegra_id isn't linked to other local third party in this company
                conflict = AlegraMapping.objects.filter(
                    empresa=empresa,
                    proyecto__isnull=True,
                    mapping_type=AlegraMapping.CONTACT,
                    alegra_id=alegra_id,
                    active=True,
                ).exclude(local_model=resolved_model, local_pk=str(ident)).first()
                if conflict:
                    # If it's the same identification (same pk) but a different local_model, treat it as a non-error:
                    # normalize to the existing mapping model instead of blocking the batch.
                    if str(conflict.local_pk) == str(ident):
                        resolved_model = conflict.local_model
                    else:
                        errors.append({'local_model': local_model, 'local_pk': local_pk, 'error': f'Alegra ID {alegra_id} ya está enlazado a {conflict.local_model} pk={conflict.local_pk}'})
                        continue

                AlegraMapping.objects.update_or_create(
                    empresa=empresa,
                    proyecto=None,
                    mapping_type=AlegraMapping.CONTACT,
                    local_model=resolved_model,
                    local_pk=str(ident),
                    local_code='',
                    defaults={
                        'alegra_id': alegra_id,
                        'description': name[:255],
                        'active': True,
                    },
                )
                _upsert_contact_index_for_mapping(
                    empresa,
                    ident=_contact_index_ident(resolved_model, str(ident)),
                    alegra_id=alegra_id,
                    name=name,
                    contact_types=contact_types,
                )
                mapped += 1
            except Exception as exc:
                errors.append({'local_model': local_model, 'local_pk': local_pk, 'error': str(exc)})

        return {
            'batch_id': batch.pk,
            'empresa': empresa.pk,
            'candidates': len(candidates),
            'created': created,
            'found_existing': found_existing,
            'mapped': mapped,
            'skipped_already_mapped': skipped_already_mapped,
            'errors': errors,
            'warnings': warnings,
        }

    def contacts_missing_in_alegra(self, *, batch_id, max_refs_per_third=5):
        """
        For a given batch, list third-parties referenced by invalid documents due to missing CONTACT mapping
        that still do NOT exist in Alegra (by identification search), without duplicates.
        Returns enough context to tell the user what to create in Alegra first.
        """
        batch = AlegraSyncBatch.objects.get(pk=batch_id)
        empresa = batch.empresa
        client = AlegraMCPClient(empresa)

        # Collect candidates + doc refs
        missing = {}
        contact_error_docs = batch.documents.filter(
            status__in=(AlegraDocument.STATUS_INVALID, AlegraDocument.STATUS_FAILED),
        ).values('error', 'source_model', 'source_pk', 'local_key')
        for doc in contact_error_docs:
            for local_model, local_pk in _extract_missing_contact_refs(doc.get('error')):
                key = (local_model, local_pk)
                entry = missing.setdefault(key, {'local_model': local_model, 'local_pk': local_pk, 'refs': []})
                if len(entry['refs']) < int(max_refs_per_third or 0):
                    entry['refs'].append(
                        {
                            'source_model': doc.get('source_model'),
                            'source_pk': doc.get('source_pk'),
                            'local_key': doc.get('local_key'),
                        }
                    )

        def _match_by_ident(results, ident):
            target_keys = set(_ident_variants(ident))
            for c in (results or []):
                if not isinstance(c, dict):
                    continue
                raw = c.get('identification') or ''
                if isinstance(raw, dict):
                    raw = raw.get('number') or ''
                keys = set(_ident_variants(raw))
                if target_keys & keys:
                    return c
            return None

        out = {}
        for key, info in missing.items():
            local_model, local_pk = info['local_model'], info['local_pk']
            resolved_model, ident, name, _contact_types = _local_third_party_info(local_model, local_pk)
            if not ident:
                continue

            # If already mapped, it's not "missing in Alegra"
            if AlegraMapping.objects.filter(
                empresa=empresa,
                proyecto__isnull=True,
                mapping_type=AlegraMapping.CONTACT,
                local_model=resolved_model,
                local_pk=str(ident),
                local_code='',
                active=True,
            ).exists():
                continue

            try:
                page = client.search_contacts(ident, start=0, limit=30)
                if isinstance(page, dict) and 'data' in page:
                    page = page['data']
                page = page if isinstance(page, list) else []
                if _match_by_ident(page, ident):
                    # It exists in Alegra; user can bulk-create mappings (or link manually).
                    continue
            except Exception:
                # If Alegra search fails, keep it out of this list (avoid false negatives).
                continue

            # Deduplicate by ident
            entry = out.setdefault(
                str(ident),
                {
                    'identification': str(ident),
                    'local_model': resolved_model,
                    'local_pk': str(ident),
                    'name': name or '',
                    'refs': [],
                },
            )
            entry['refs'].extend(info.get('refs') or [])

        # Keep stable ordering
        missing_list = sorted(out.values(), key=lambda x: x.get('identification') or '')
        return {
            'batch_id': batch.pk,
            'empresa': empresa.pk,
            'count': len(missing_list),
            'missing': missing_list,
        }

    def _validate_input(self, empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id, caja_id=None):
        if document_type not in dict(AlegraSyncBatch.DOCUMENT_TYPES):
            raise AlegraConfigurationError(f'Tipo de documento no soportado: {document_type}')
        desde = parse_date(str(fecha_desde or ''))
        hasta = parse_date(str(fecha_hasta or ''))
        if not desde or not hasta:
            raise AlegraConfigurationError('Las fechas deben enviarse en formato YYYY-MM-DD.')
        if desde > hasta:
            raise AlegraConfigurationError('fecha_desde no puede ser mayor que fecha_hasta.')
        empresa = empresas.objects.get(pk=empresa_id)
        proyecto = None
        if document_type in (AlegraSyncBatch.DOC_RECEIPT, AlegraSyncBatch.DOC_COMMISSION, AlegraSyncBatch.DOC_GTT):
            if not proyecto_id:
                raise AlegraConfigurationError('Este tipo de documento requiere proyecto.')
            proyecto = proyectos.objects.get(pk=proyecto_id)
        elif proyecto_id:
            raise AlegraConfigurationError('Este tipo de documento no usa proyecto.')

        validated_caja_id = None
        if document_type == AlegraSyncBatch.DOC_CAJA:
            if not caja_id:
                raise AlegraConfigurationError('Debe seleccionar la caja efectivo.')
            from andinasoft.models import cuentas_pagos
            cuenta = cuentas_pagos.objects.filter(
                pk=caja_id,
                nit_empresa=empresa,
                activo=True,
                es_caja=True,
            ).first()
            if not cuenta:
                raise AlegraConfigurationError('Caja no encontrada o no activa para esta empresa.')
            validated_caja_id = cuenta.pk
        elif caja_id:
            raise AlegraConfigurationError('caja_id solo aplica al tipo caja efectivo.')

        return empresa, proyecto, desde, hasta, validated_caja_id

    def _build_documents(self, empresa, proyecto, document_type, desde, hasta, caja_id=None, batch=None):
        if document_type == AlegraSyncBatch.DOC_RECEIPT:
            builder = ReceiptPaymentBuilder(empresa, proyecto)
            queryset = Recaudos_general.objects.using(proyecto.pk).filter(fecha__range=(desde, hasta)).order_by('fecha', 'pk')
            results = []
            for receipt in queryset:
                results.extend(self._safe_build(builder, receipt, empresa=empresa, proyecto=proyecto))
            return results

        if document_type == AlegraSyncBatch.DOC_COMMISSION:
            builder = CommissionBuilder(empresa, proyecto)
            commissions = Pagocomision.objects.using(proyecto.pk).raw(
                f'CALL detalle_comisiones_fecha("{desde}","{hasta}")'
            )
            asesor_ids = {str(c.idgestor) for c in commissions if getattr(c, 'idgestor', None)}
            empresa_by_asesor = dict(
                asesores.objects.filter(cedula__in=asesor_ids).values_list(
                    'cedula', 'empresa_contable_id'
                )
            )
            batch_empresa_id = str(getattr(empresa, 'pk', empresa))
            results = []
            for commission in commissions:
                gestor_id = str(getattr(commission, 'idgestor', '') or '')
                asesor_empresa = empresa_by_asesor.get(gestor_id)
                if asesor_empresa is None:
                    asesor_empresa = asesores.EMPRESA_CONTABLE_DEFAULT
                if str(asesor_empresa) != batch_empresa_id:
                    continue
                results.extend(self._safe_build(builder, commission, empresa=empresa, proyecto=proyecto))
            return results

        if document_type == AlegraSyncBatch.DOC_GTT:
            builder = GttBuilder(empresa, proyecto)
            gtt_ids = Gtt.objects.filter(
                proyecto=proyecto.pk,
                estado__iexact='Aprobado',
                fecha_hasta__gte=desde,
                fecha_desde__lte=hasta,
            ).values_list('pk', flat=True)
            detalles = (
                Detalle_gtt.objects.filter(gtt_id__in=gtt_ids, valor__gt=0)
                .select_related('gtt', 'asesor')
                .order_by('gtt__fecha_hasta', 'gtt_id', 'pk')
            )
            results = []
            for detalle in detalles:
                results.extend(self._safe_build(builder, detalle, empresa=empresa, proyecto=proyecto))
            return results

        if document_type == AlegraSyncBatch.DOC_CAJA:
            bill_builder = CajaGastoBillBuilder(empresa)

            gastos_bill_qs = gastos_caja.objects.filter(
                estado__in=gastos_caja.ESTADOS_ELEGIBLES_ALEGRA_BILL,
                forma_pago_id=caja_id,
                forma_pago__nit_empresa=empresa,
                fecha_gasto__range=(desde, hasta),
            ).select_related(
                'reembolso',
                'reembolso__caja',
                'tercero',
                'concepto',
                'forma_pago',
                'cuenta_iva',
                'cuenta_rte',
            ).order_by('fecha_gasto', 'pk')

            results = []
            for gasto in gastos_bill_qs:
                results.extend(self._safe_build(bill_builder, gasto, empresa=empresa, proyecto=proyecto))

            gastos_journal = list(gastos_bill_qs)
            if gastos_journal:
                if not batch:
                    raise AlegraConfigurationError(
                        'El journal de caja por lote requiere un batch de preview.'
                    )
                results.append(
                    self._ensure_caja_batch_journal(
                        batch=batch,
                        empresa=empresa,
                        proyecto=proyecto,
                        caja_id=caja_id,
                        gastos=gastos_journal,
                        fecha_desde=desde,
                        fecha_hasta=hasta,
                    )
                )
            return results

        builder = ExpensePaymentBuilder(empresa)
        pagos = list(Pagos.objects.filter(empresa=empresa, fecha_pago__range=(desde, hasta)).select_related('nroradicado', 'cuenta', 'empresa'))
        anticipos = list(Anticipos.objects.filter(empresa=empresa, fecha_pago__range=(desde, hasta)).select_related('tipo_anticipo', 'cuenta', 'empresa'))
        transferencias = list(transferencias_companias.objects.filter(
            Q(empresa_sale=empresa) | Q(empresa_entra=empresa),
            fecha__range=(desde, hasta),
        ).select_related('cuenta_sale', 'cuenta_entra', 'empresa_sale', 'empresa_entra'))
        results = []
        for item in pagos + anticipos + transferencias:
            results.extend(self._safe_build(builder, item, empresa=empresa, proyecto=proyecto))
        return results

    def _sent_documents_for_source(self, empresa, proyecto, source_model, source_pk):
        """Documentos ya enviados a Alegra para esta fuente y empresa (no reconstruir en preview)."""
        qs = AlegraDocument.objects.filter(
            empresa_id=empresa.pk,
            source_model=source_model,
            source_pk=str(source_pk),
            status=AlegraDocument.STATUS_SENT,
        )
        if self._document_source_scoped_by_proyecto(source_model):
            if proyecto:
                qs = qs.filter(proyecto_id=proyecto.pk)
            else:
                qs = qs.filter(proyecto__isnull=True)
        return list(qs.order_by('pk'))

    @staticmethod
    def _document_source_scoped_by_proyecto(source_model):
        """Fuentes por proyecto (recibos/comisiones/GTT). Egresos son a nivel empresa."""
        return source_model in (
            'andinasoft.Recaudos_general',
            'andinasoft.Pagocomision',
            'andinasoft.Detalle_gtt',
        )

    def _safe_build(self, builder, source, *, empresa, proyecto):
        source_model = f'{source.__class__._meta.app_label}.{source.__class__.__name__}'
        source_pk = getattr(source, 'pk', None) or getattr(source, 'id_pago', '')
        sent_docs = self._sent_documents_for_source(empresa, proyecto, source_model, source_pk)
        sent_by_key = {d.local_key: d for d in sent_docs}

        # Pago enviado antes como documento único (expense:pago:{pk}): no reconstruir por tercero.
        if source_model == 'accounting.Pagos' and sent_docs:
            legacy_key = f'expense:pago:{source_pk}'
            legacy_sent = [d for d in sent_docs if d.local_key == legacy_key]
            if legacy_sent:
                return [{'existing_sent': doc} for doc in legacy_sent]

        try:
            built = builder.build(source)
            built_list = built if isinstance(built, list) else [built]
            out = []
            for b in built_list:
                existing = sent_by_key.get(b.local_key)
                if existing:
                    out.append({'existing_sent': existing})
                    continue
                # Attach local debugging payload when available (never sent to Alegra).
                try:
                    if hasattr(builder, 'local_payload'):
                        lp = builder.local_payload(source)
                        if isinstance(lp, dict) and lp:
                            b.payload = dict(b.payload)
                            b.payload['__local'] = lp
                except Exception:
                    pass
                out.append({'built': b})
            return out
        except (AlegraBuildError, AlegraConfigurationError, Exception) as exc:
            local_payload = {}
            try:
                if hasattr(builder, 'local_payload'):
                    lp = builder.local_payload(source)
                    if isinstance(lp, dict):
                        local_payload = lp
            except Exception:
                local_payload = {}
            return [{
                'error': str(exc),
                'document_type': 'invalid',
                'source_model': source_model,
                'source_pk': str(source_pk),
                'local_key': f'invalid:{source_model}:{source_pk}',
                'payload': {'__local': local_payload} if local_payload else {},
            }]

    @transaction.atomic
    def _upsert_document(self, batch, empresa, proyecto, *, document_type, source_model, source_pk, local_key, payload, operation, transport, status, error):
        # unique_alegra_document_local_key = (empresa, document_type, local_key) — sin proyecto
        existing = AlegraDocument.objects.filter(
            empresa=empresa,
            document_type=document_type,
            local_key=local_key,
        ).first()
        if existing and existing.status == AlegraDocument.STATUS_SENT:
            existing.batch = batch
            existing.save(update_fields=['batch', 'updated_at'])
            return existing  # preview no debería llegar aquí si _safe_build omitió el build

        doc, _ = AlegraDocument.objects.update_or_create(
            empresa=empresa,
            document_type=document_type,
            local_key=local_key,
            defaults={
                'proyecto': proyecto,
                'batch': batch,
                'source_model': source_model,
                'source_pk': source_pk,
                'payload': payload,
                'alegra_operation': operation,
                'transport': transport,
                'status': status,
                'error': error,
                'created_by': self.user if getattr(self.user, 'is_authenticated', False) else None,
            },
        )
        return doc

    def _send_document(self, client, doc):
        payload = doc.payload or {}
        if isinstance(payload, dict) and any(str(k).startswith('__') for k in payload.keys()):
            payload = {k: v for k, v in payload.items() if not str(k).startswith('__')}
        if doc.alegra_operation == 'incomePayments__createIncomePayment':
            return client.create_income_payment(payload)
        if doc.alegra_operation == 'accounting__createJournal':
            created = client.create_journal(payload)
            # POST /journals no siempre retorna numberTemplate/type. Hacemos GET para confirmar numeración aplicada.
            try:
                if isinstance(created, dict) and created.get('id'):
                    details = client.get_journal(created.get('id'), fields='numberTemplate,type')
                    if isinstance(details, dict):
                        # Keep original response intact; add fetched details under a reserved key.
                        created = dict(created)
                        created['__fetched'] = {'journal': details}
            except Exception as exc:
                if isinstance(created, dict):
                    created = dict(created)
                    created['__fetched'] = {'error': str(exc)}
            return created
        if doc.alegra_operation == 'POST /bills':
            return client.create_bill(payload)
        if doc.alegra_operation == 'POST /payments':
            return client.create_out_payment(payload)
        if isinstance(doc.alegra_operation, str) and doc.alegra_operation.startswith('POST /bank-accounts/') and doc.alegra_operation.endswith('/transfer'):
            # Operation format: POST /bank-accounts/{origin}/transfer
            origin = doc.alegra_operation.split('/bank-accounts/', 1)[1].split('/transfer', 1)[0].strip().strip('/')
            return client.bank_account_transfer(origin, payload)
        raise AlegraConfigurationError(f'Operacion Alegra no soportada: {doc.alegra_operation}')

    def subscribe_webhook(self, *, empresa_id, event, domain_base):
        """
        Crea suscripción en Alegra y persiste la respuesta en AlegraWebhookSubscriptionLog.
        """
        event = (event or '').strip()
        if event not in ALEGRA_WEBHOOK_EVENTS:
            raise AlegraIntegrationError('Evento no permitido o desconocido.')

        raw_domain = (domain_base or '').strip()
        parsed = urlparse(raw_domain if '://' in raw_domain else f'https://{raw_domain}')
        scheme = (parsed.scheme or 'https').lower()
        netloc = (parsed.netloc or '').strip().lower()
        if not netloc:
            raise AlegraIntegrationError(
                'Dominio inválido. Ejemplo: ibex-daring-molly.ngrok-free.app o https://ibex-daring-molly.ngrok-free.app'
            )
        if scheme not in ('http', 'https'):
            raise AlegraIntegrationError('Esquema no válido (solo http/https para interpretar el host).')

        # Alegra POST /webhooks/subscriptions exige URL *sin* "http://" ni "https://" (host + ruta).
        netloc = netloc.rstrip('/')
        # Preferir path-param para evitar pérdida de query params en delivery.
        suffix = ALEGRA_WEBHOOK_BILLS_INGEST_SUFFIX
        if not suffix.startswith('/'):
            suffix = '/' + suffix
        try:
            empresa = empresas.objects.get(pk=empresa_id)
        except empresas.DoesNotExist:
            raise AlegraIntegrationError('Empresa no encontrada.') from None

        if not getattr(empresa, 'alegra_enabled', False):
            raise AlegraIntegrationError('La empresa no tiene Alegra habilitado.')
        if not (getattr(empresa, 'alegra_token', None) or '').strip():
            raise AlegraIntegrationError('La empresa no tiene token de Alegra configurado.')

        # URL robusta: empresa en el path.
        # Mantiene compatibilidad: el endpoint acepta tanto ?empresa=<NIT> como /bills/<NIT>/.
        empresa_path = quote(str(empresa.pk), safe='')
        callback_url_alegra = f'{netloc}{suffix}{empresa_path}/'
        callback_url_https = f'https://{netloc}{suffix}{empresa_path}/'

        client = AlegraMCPClient(empresa)
        existing = self.list_webhook_subscriptions(empresa_id=empresa_id).get('subscriptions') or []
        same_event = [s for s in existing if (s.get('event') or '').strip() == event]
        if same_event:
            exact = [s for s in same_event if (s.get('url') or '').strip().rstrip('/') == callback_url_alegra.rstrip('/')]
            if exact:
                return {
                    'log_id': None,
                    'success': True,
                    'already_subscribed': True,
                    'status_code': 200,
                    'callback_url': callback_url_alegra,
                    'callback_url_https': callback_url_https,
                    'response': {
                        'message': 'Ya existe esta suscripción en Alegra.',
                        'subscription': exact[0],
                    },
                }
            urls = ', '.join(f"{s.get('id')}: {s.get('url')}" for s in same_event)
            raise AlegraIntegrationError(
                f'Ya hay {len(same_event)} webhook(s) activo(s) para "{event}" en esta empresa. '
                f'Elimínalos en la tabla «Suscripciones activas» antes de crear otro (evita radicados duplicados). '
                f'Actuales: {urls}'
            )

        status, payload = client.post_webhooks_subscription(event, callback_url_alegra)
        if not isinstance(payload, dict):
            payload = {'raw': str(payload)}

        success = 200 <= int(status or 0) < 300
        if isinstance(payload, dict) and payload.get('error'):
            success = False

        log = AlegraWebhookSubscriptionLog.objects.create(
            empresa=empresa,
            event=event,
            callback_url=callback_url_alegra,
            request_json={'event': event, 'url': callback_url_alegra},
            response_status=status,
            response_json=payload,
            success=success,
            created_by=self.user if getattr(self.user, 'is_authenticated', False) else None,
        )
        return {
            'log_id': log.pk,
            'success': success,
            'status_code': status,
            'callback_url': callback_url_alegra,
            'callback_url_https': callback_url_https,
            'response': payload,
        }

    def list_webhook_subscriptions(self, *, empresa_id):
        """
        Lista suscripciones activas en Alegra para la empresa (fuente de verdad).
        """
        empresa = empresas.objects.get(pk=str(empresa_id).strip())
        client = AlegraMCPClient(empresa)
        payload = client.list_webhooks_subscriptions()
        # Alegra puede devolver:
        # - lista: [...]
        # - wrapper: {"data":[...]} o {"subscriptions":[...]}
        if isinstance(payload, dict):
            if 'subscriptions' in payload:
                payload = payload.get('subscriptions')
            elif 'data' in payload:
                payload = payload.get('data')
        subs = payload if isinstance(payload, list) else []
        # Normaliza shape para UI
        out = []
        for s in subs:
            if not isinstance(s, dict):
                continue
            out.append(
                {
                    'id': str(s.get('id') or ''),
                    'event': str(s.get('event') or ''),
                    'url': str(s.get('url') or ''),
                }
            )
        return {'empresa': str(empresa.pk), 'subscriptions': out}

    def delete_webhook_subscription(self, *, empresa_id, subscription_id):
        """
        Elimina una suscripción de webhook en Alegra por id.
        """
        empresa = empresas.objects.get(pk=str(empresa_id).strip())
        client = AlegraMCPClient(empresa)
        resp = client.delete_webhooks_subscription(subscription_id)
        return {'empresa': str(empresa.pk), 'deleted_id': str(subscription_id), 'response': resp}

    def _fetch_bill_cxp_category_id(self, client, *, bill_data, alegra_id):
        """
        CxP del bill: respuesta almacenada, journal embebido, GET /bills/{id}?fields=journal
        o GET /contacts/{provider.id}?fields=accounting (debtToPay).
        """
        data = bill_data if isinstance(bill_data, dict) else {}
        cached = data.get('__cxp_category_id')
        if cached is not None and str(cached).strip():
            return str(cached).strip()

        cxp_id = cxp_category_id_from_bill(data)
        if cxp_id:
            return cxp_id

        merged = dict(data)
        if alegra_id and client is not None:
            try:
                fresh = client.get_bill(alegra_id, fields='journal')
                if isinstance(fresh, dict):
                    merged.update(fresh)
                    cxp_id = cxp_category_id_from_bill(fresh)
                    if cxp_id:
                        return cxp_id
            except AlegraIntegrationError:
                pass

        if client is not None:
            provider_id = (merged.get('provider') or {}).get('id')
            if provider_id is not None and str(provider_id).strip():
                try:
                    contact = client.get_contact(provider_id, fields='accounting')
                    cxp_id = cxp_category_id_from_contact(contact)
                    if cxp_id:
                        return cxp_id
                except AlegraIntegrationError:
                    pass

        return ''

    def _capture_caja_bill_cxp(self, client, doc):
        """Persiste __cxp_category_id en la respuesta del bill para el journal de caja."""
        bill_data = doc.response if isinstance(doc.response, dict) else {}
        cxp_id = self._fetch_bill_cxp_category_id(
            client, bill_data=bill_data, alegra_id=doc.alegra_id,
        )
        if not cxp_id:
            return
        response = dict(bill_data)
        response['__cxp_category_id'] = cxp_id
        doc.response = response
        doc.save(update_fields=['response', 'updated_at'])

    @staticmethod
    def _caja_journal_local_key(batch_id):
        return f'caja:journal:batch:{batch_id}'

    @staticmethod
    def _caja_pending_bills_from_gastos(gastos):
        pending = []
        for gasto in sorted(gastos, key=lambda g: (g.fecha_gasto, g.pk)):
            pending.append({
                'gasto_id': gasto.pk,
                'reembolso_id': gasto.reembolso_id,
                'local_key': f'caja:bill:{gasto.reembolso_id}:{gasto.pk}',
            })
        return pending

    def _count_sent_caja_bills(self, empresa, batch, pending_bills):
        ready = 0
        for ref in pending_bills or []:
            local_key = ref.get('local_key')
            if not local_key:
                continue
            bill_doc = AlegraDocument.objects.filter(
                batch=batch,
                document_type='caja_bill',
                local_key=local_key,
                status=AlegraDocument.STATUS_SENT,
            ).first()
            if not bill_doc:
                bill_doc = AlegraDocument.objects.filter(
                    empresa=empresa,
                    document_type='caja_bill',
                    local_key=local_key,
                    status=AlegraDocument.STATUS_SENT,
                ).first()
            if bill_doc and bill_doc.alegra_id:
                ready += 1
        return ready

    def _ensure_caja_batch_journal(
        self,
        *,
        batch,
        empresa,
        proyecto,
        caja_id,
        gastos,
        fecha_desde,
        fecha_hasta,
    ):
        local_key = self._caja_journal_local_key(batch.pk)
        sent = AlegraDocument.objects.filter(
            empresa=empresa,
            document_type='caja_journal',
            local_key=local_key,
            status=AlegraDocument.STATUS_SENT,
        ).first()
        if sent:
            return {'existing_sent': sent}

        pending_bills = self._caja_pending_bills_from_gastos(gastos)
        bills_ready = self._count_sent_caja_bills(empresa, batch, pending_bills)
        payload = {
            '__local': {
                'awaiting_bills': True,
                'batch_id': batch.pk,
                'caja_id': caja_id,
                'fecha_desde': fecha_desde.isoformat(),
                'fecha_hasta': fecha_hasta.isoformat(),
                'pending_bills': pending_bills,
                'bills_total': len(pending_bills),
                'bills_ready': bills_ready,
            },
        }
        doc = self._upsert_document(
            batch,
            empresa,
            proyecto,
            document_type='caja_journal',
            source_model=CajaLegalizationJournalBuilder.BATCH_SOURCE_MODEL,
            source_pk=str(batch.pk),
            local_key=local_key,
            payload=payload,
            operation='accounting__createJournal',
            transport=AlegraDocument.ALEGRA_REST,
            status=AlegraDocument.STATUS_PENDING,
            error='',
        )
        if bills_ready >= len(pending_bills) and pending_bills:
            try:
                self._activate_caja_journal_doc(batch, doc)
                return {'built': self._built_document_from_journal(doc)}
            except (AlegraBuildError, AlegraConfigurationError, AlegraIntegrationError) as exc:
                doc.status = AlegraDocument.STATUS_FAILED
                doc.error = str(exc)
                doc.save(update_fields=['status', 'error', 'updated_at'])
                return {
                    'error': str(exc),
                    'document_type': 'caja_journal',
                    'source_model': CajaLegalizationJournalBuilder.BATCH_SOURCE_MODEL,
                    'source_pk': str(batch.pk),
                    'local_key': local_key,
                    'payload': payload,
                }
        return {'pending_journal': doc}

    def _built_document_from_journal(self, doc):
        from alegra_integration.builders import BuiltDocument

        return BuiltDocument(
            document_type=doc.document_type,
            operation=doc.alegra_operation,
            transport=doc.transport,
            source_model=doc.source_model,
            source_pk=doc.source_pk,
            local_key=doc.local_key,
            payload=doc.payload,
            empresa_id=doc.empresa_id,
        )

    def _activate_caja_journal_doc(self, batch, doc):
        """Construye el journal con CxP reales una vez enviados todos los bills del lote."""
        payload = dict(doc.payload or {})
        local = payload.get('__local') if isinstance(payload.get('__local'), dict) else {}
        pending_bills = local.get('pending_bills') or []
        if not pending_bills:
            raise AlegraConfigurationError(
                f'El journal de caja {doc.local_key} no tiene gastos asociados.'
            )

        bills_ready = self._count_sent_caja_bills(doc.empresa, batch, pending_bills)
        if bills_ready < len(pending_bills):
            raise AlegraConfigurationError(
                f'Faltan bills enviados para el journal {doc.local_key}: '
                f'{bills_ready}/{len(pending_bills)} listos.'
            )

        caja_id = local.get('caja_id')
        if not caja_id:
            raise AlegraConfigurationError(
                f'El journal de caja {doc.local_key} no tiene caja_id en metadata local.'
            )

        from andinasoft.models import cuentas_pagos

        caja = cuentas_pagos.objects.get(pk=caja_id)
        gasto_ids = [ref.get('gasto_id') for ref in pending_bills if ref.get('gasto_id')]
        gastos = list(
            gastos_caja.objects.filter(pk__in=gasto_ids).select_related(
                'reembolso',
                'reembolso__caja',
                'tercero',
                'concepto',
                'forma_pago',
                'cuenta_iva',
                'cuenta_rte',
            )
        )
        gastos_by_id = {g.pk: g for g in gastos}
        ordered_gastos = [gastos_by_id[g_id] for g_id in gasto_ids if g_id in gastos_by_id]
        if len(ordered_gastos) != len(gasto_ids):
            raise AlegraBuildError('No se encontraron todos los gastos del lote para armar el journal.')

        fecha_desde = parse_date(str(local.get('fecha_desde') or '')) or batch.fecha_desde
        fecha_hasta = parse_date(str(local.get('fecha_hasta') or '')) or batch.fecha_hasta
        built = CajaLegalizationJournalBuilder(doc.empresa).build_batch(
            caja=caja,
            gastos=ordered_gastos,
            batch_id=batch.pk,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
        )
        doc.payload = built.payload
        doc.alegra_operation = built.operation
        doc.transport = built.transport
        doc.source_model = built.source_model
        doc.source_pk = built.source_pk
        doc.error = ''
        doc.save(update_fields=[
            'payload', 'alegra_operation', 'transport', 'source_model', 'source_pk', 'error', 'updated_at',
        ])
        self._finalize_caja_journal_doc(doc)
        doc.status = AlegraDocument.STATUS_VALID
        doc.save(update_fields=['status', 'updated_at'])

    def _refresh_caja_journal_progress(self, batch):
        """Tras enviar un bill, actualiza progreso y activa el journal cuando todos estén listos."""
        journal = batch.documents.filter(document_type='caja_journal').order_by('id').first()
        if not journal:
            return None
        if journal.status in (AlegraDocument.STATUS_SENT, AlegraDocument.STATUS_SKIPPED):
            return journal
        if journal.status == AlegraDocument.STATUS_VALID:
            return journal

        payload = dict(journal.payload or {})
        local = dict(payload.get('__local') or {})
        pending_bills = local.get('pending_bills') or []
        if not pending_bills:
            return journal

        bills_ready = self._count_sent_caja_bills(journal.empresa, batch, pending_bills)
        local['bills_ready'] = bills_ready
        local['bills_total'] = len(pending_bills)
        payload['__local'] = local
        journal.payload = payload
        journal.save(update_fields=['payload', 'updated_at'])

        if bills_ready < len(pending_bills):
            return journal

        try:
            self._activate_caja_journal_doc(batch, journal)
        except (AlegraBuildError, AlegraConfigurationError, AlegraIntegrationError) as exc:
            journal.status = AlegraDocument.STATUS_FAILED
            journal.error = str(exc)
            journal.save(update_fields=['status', 'error', 'updated_at'])
        return journal

    def _resolve_cxp_for_caja_bill(self, bill_doc, *, client=None):
        """CxP del bill (respuesta POST/GET/contacto); fallback mapeos caja_cxp / default_cxp."""
        bill_data = bill_doc.response if isinstance(bill_doc.response, dict) else {}
        cxp_id = self._fetch_bill_cxp_category_id(
            client, bill_data=bill_data, alegra_id=bill_doc.alegra_id,
        )
        if cxp_id:
            return cxp_id
        resolver = MappingResolver(bill_doc.empresa)
        cxp_id = resolver.get(AlegraMapping.CATEGORY, local_code='caja_cxp', required=False)
        if not cxp_id:
            cxp_id = resolver.get(AlegraMapping.CATEGORY, local_code='default_cxp', required=True)
        return str(cxp_id)

    def _finalize_caja_journal_doc(self, doc):
        """Inyecta idResource y cuenta CxP (desde bill) en cada línea del journal de caja."""
        payload = dict(doc.payload or {})
        local = payload.get('__local') if isinstance(payload.get('__local'), dict) else {}
        pending = local.get('pending_bills') or []
        if not pending:
            raise AlegraConfigurationError(
                f'El journal de caja {doc.local_key} no tiene referencias a bills pendientes.'
            )
        entries = list(payload.get('entries') or [])
        if len(entries) < len(pending):
            raise AlegraConfigurationError(
                f'El journal de caja {doc.local_key} tiene menos lineas ({len(entries)}) '
                f'que gastos ({len(pending)}).'
            )
        client = AlegraMCPClient(doc.empresa)
        missing = []
        for idx, ref in enumerate(pending):
            local_key = ref.get('local_key')
            bill_doc = AlegraDocument.objects.filter(
                empresa=doc.empresa,
                document_type='caja_bill',
                local_key=local_key,
                status=AlegraDocument.STATUS_SENT,
            ).first()
            if not bill_doc or not bill_doc.alegra_id:
                missing.append(local_key or f'gasto:{ref.get("gasto_id")}')
                continue
            try:
                bill_id = int(str(bill_doc.alegra_id).strip())
            except (TypeError, ValueError):
                missing.append(local_key)
                continue
            cxp_id = self._resolve_cxp_for_caja_bill(bill_doc, client=client)
            entries[idx]['id'] = cxp_id
            assoc = entries[idx].get('associatedDocument') or {}
            entries[idx]['associatedDocument'] = {
                'idResource': bill_id,
                'resourceType': assoc.get('resourceType') or 'bill',
            }
        if missing:
            raise AlegraConfigurationError(
                f'Faltan bills enviados para el journal {doc.local_key}: {", ".join(missing)}'
            )
        payload['entries'] = entries
        doc.payload = payload
        doc.save(update_fields=['payload', 'updated_at'])

    def _extract_alegra_id(self, response):
        if isinstance(response, dict):
            for key in ('id', 'idPayment', 'idJournal'):
                if response.get(key):
                    return str(response[key])
            result = response.get('result')
            if result:
                found = self._extract_alegra_id(result)
                if found:
                    return found
            content = response.get('content')
            if isinstance(content, list):
                for item in content:
                    found = self._extract_alegra_id(item)
                    if found:
                        return found
            data = response.get('data')
            if data:
                found = self._extract_alegra_id(data)
                if found:
                    return found
        if isinstance(response, list):
            for item in response:
                found = self._extract_alegra_id(item)
                if found:
                    return found
        return None

    def _document_summary(self, doc):
        summary = {
            'id': doc.pk,
            'document_type': doc.document_type,
            'operation': doc.alegra_operation,
            'transport': doc.transport,
            'source_model': doc.source_model,
            'source_pk': doc.source_pk,
            'local_key': doc.local_key,
            'status': doc.status,
            'alegra_id': doc.alegra_id,
            'error': doc.error,
            'payload': doc.payload,
            'response': doc.response,
        }
        hint = self._document_status_hint(doc)
        if hint:
            summary['status_hint'] = hint
        return summary

    @staticmethod
    def _document_status_hint(doc):
        if doc.document_type != 'caja_journal':
            return ''
        if doc.status == AlegraDocument.STATUS_PENDING:
            local = (doc.payload or {}).get('__local') if isinstance((doc.payload or {}).get('__local'), dict) else {}
            ready = int(local.get('bills_ready') or 0)
            total = int(local.get('bills_total') or 0)
            if total:
                return f'Esperando bills ({ready}/{total})'
            return 'Esperando bills del lote'
        if doc.status == AlegraDocument.STATUS_VALID:
            return 'Journal listo — se envía después de los bills'
        return ''

    def _batch_response(self, batch, documents):
        return {
            'batch': {
                'id': batch.pk,
                'empresa': batch.empresa_id,
                'proyecto': batch.proyecto_id,
                'document_type': batch.document_type,
                'fecha_desde': batch.fecha_desde.isoformat(),
                'fecha_hasta': batch.fecha_hasta.isoformat(),
                'status': batch.status,
                'summary': batch.summary,
                'total_documents': batch.total_documents,
                'success_count': batch.success_count,
                'error_count': batch.error_count,
                'created_by': (getattr(batch.created_by, 'username', None) or str(batch.created_by)) if batch.created_by_id else '',
            },
            'documents': documents,
        }
