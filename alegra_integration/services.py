import re
import time
from urllib.parse import quote, urlparse

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.cache import cache

from accounting.models import Anticipos, Pagos, transferencias_companias
from alegra_integration.builders import CommissionBuilder, ExpensePaymentBuilder, ReceiptPaymentBuilder
from alegra_integration.client import AlegraMCPClient
from alegra_integration.exceptions import AlegraBuildError, AlegraConfigurationError, AlegraIntegrationError
from alegra_integration.models import (
    AlegraContactIndex,
    AlegraDocument,
    AlegraMapping,
    AlegraSyncBatch,
    AlegraWebhookSubscriptionLog,
)
from andinasoft.models import asesores, clientes, empresas, proyectos
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


class AlegraIntegrationService:
    def __init__(self, user=None):
        self.user = user

    def preview(self, *, empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id=None):
        empresa, proyecto, desde, hasta = self._validate_input(empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id)
        batch = AlegraSyncBatch.objects.create(
            empresa=empresa,
            proyecto=proyecto,
            document_type=document_type,
            fecha_desde=desde,
            fecha_hasta=hasta,
            status=AlegraSyncBatch.STATUS_PREVIEW,
            created_by=self.user if getattr(self.user, 'is_authenticated', False) else None,
        )

        built_results = self._build_documents(empresa, proyecto, document_type, desde, hasta)
        valid = 0
        invalid = 0
        documents = []

        for result in built_results:
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
                valid += 1
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
            documents.append(self._document_summary(doc))

        batch.total_documents = len(documents)
        batch.success_count = valid
        batch.error_count = invalid
        batch.summary = {'valid': valid, 'invalid': invalid}
        batch.save(update_fields=['total_documents', 'success_count', 'error_count', 'summary', 'updated_at'])
        return self._batch_response(batch, documents)

    def send(self, *, empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id=None, retry_failed=True):
        preview = self.preview(
            empresa_id=empresa_id,
            document_type=document_type,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            proyecto_id=proyecto_id,
        )
        batch = AlegraSyncBatch.objects.get(pk=preview['batch']['id'])
        batch.status = AlegraSyncBatch.STATUS_PROCESSING
        batch.save(update_fields=['status', 'updated_at'])

        client_by_empresa = {}
        sent = 0
        skipped = 0
        failed = 0
        documents = []

        for doc in batch.documents.order_by('id'):
            if doc.status == AlegraDocument.STATUS_SENT:
                skipped += 1
                documents.append(self._document_summary(doc))
                continue

            if doc.status == AlegraDocument.STATUS_INVALID:
                failed += 1
                documents.append(self._document_summary(doc))
                continue

            existing_sent = AlegraDocument.objects.filter(
                empresa=doc.empresa,
                proyecto=doc.proyecto,
                document_type=doc.document_type,
                local_key=doc.local_key,
                status=AlegraDocument.STATUS_SENT,
            ).exclude(pk=doc.pk).first()
            if existing_sent:
                doc.status = AlegraDocument.STATUS_SKIPPED
                doc.response = {'skipped_reason': 'already_sent', 'existing_document_id': existing_sent.pk}
                doc.alegra_id = existing_sent.alegra_id
                doc.save(update_fields=['status', 'response', 'alegra_id', 'updated_at'])
                skipped += 1
                documents.append(self._document_summary(doc))
                continue

            if doc.status == AlegraDocument.STATUS_FAILED and not retry_failed:
                skipped += 1
                documents.append(self._document_summary(doc))
                continue

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
                sent += 1
            except AlegraIntegrationError as exc:
                doc.status = AlegraDocument.STATUS_FAILED
                doc.error = str(exc)
                doc.save(update_fields=['status', 'error', 'updated_at'])
                failed += 1
            documents.append(self._document_summary(doc))

        batch.success_count = sent
        batch.error_count = failed
        batch.summary = {'sent': sent, 'failed': failed, 'skipped': skipped}
        final_status = AlegraSyncBatch.STATUS_DONE if failed == 0 else AlegraSyncBatch.STATUS_PARTIAL if sent else AlegraSyncBatch.STATUS_FAILED
        batch.status = final_status
        batch.completed_at = timezone.now()
        batch.save(update_fields=['success_count', 'error_count', 'summary', 'status', 'completed_at', 'updated_at'])
        return self._batch_response(batch, documents)

    def reference_sync(self, *, empresa_id):
        empresa = empresas.objects.get(pk=empresa_id)
        client = AlegraMCPClient(empresa)
        return client.get_reference_data()

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

        def _ident(contact):
            raw = contact.get('identification') or ''
            if isinstance(raw, dict):
                raw = raw.get('number') or ''
            return _norm_ident(raw)

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
            return self._contact_sync_state_public(state)

        if action == 'status':
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
            page = client.get_contacts_page(start=start, limit=limit, contact_type=contact_type)
            # Alegra returns list; if wrapped in metadata=true it'd be page['data']
            if isinstance(page, dict) and 'data' in page:
                page = page['data']
            page = page if isinstance(page, list) else []
            for c in page:
                k = _ident(c)
                for kk in _ident_variants(k):
                    if kk:
                        by_ident[kk] = {'id': str(c.get('id')), 'name': c.get('name') or c.get('businessName') or ''}
                # Also upsert the contact index as we stream pages
                if k:
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
            state['by_ident'] = by_ident
            state['alegra_loaded'] = int(state.get('alegra_loaded') or 0) + len(page)
            state['alegra_start'] = start + limit
            state['stage'] = 'alegra'

            if len(page) < limit:
                # finished this type; switch to providers if we just finished clients
                if contact_type == 'client':
                    state['alegra_type'] = 'provider'
                    state['alegra_start'] = 0
                else:
                    # finished loading all Alegra contacts (client + provider)
                    state['phase'] = 'local'
                    state['alegra_total'] = int(state.get('alegra_loaded') or 0)
                    state['total_local'] = clientes.objects.count() + asesores.objects.count() + empresas.objects.count()
                    state['stage'] = 'clientes'
                    state['offset'] = 0
            cache.set(key, state, timeout=60 * 30)
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
        cache.set(key, state, timeout=60 * 30)
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
        invalid_docs = batch.documents.filter(status=AlegraDocument.STATUS_INVALID).only('error')
        for d in invalid_docs:
            err = (d.error or '')
            if 'tipo "contact"' not in err and 'tipo "contact"' not in err.lower() and 'mapping_type' not in err:
                # keep it strict; we only handle missing contact mappings
                pass
            if 'tipo "contact"' not in err:
                continue
            m = _MISSING_CONTACT_RE.search(err)
            if not m:
                continue
            local_model = (m.group('model') or '').strip()
            local_pk = (m.group('pk') or '').strip()
            if local_model and local_pk:
                missing[(local_model, local_pk)] = True

        candidates = [{'local_model': k[0], 'local_pk': k[1]} for k in missing.keys()]

        created = 0
        mapped = 0
        found_existing = 0
        skipped_already_mapped = 0
        errors = []
        warnings = []

        def _local_info(local_model, local_pk):
            """
            Returns (resolved_local_model, ident, name, contact_types) for a local third-party.
            We treat `ident` as the local_pk (NIT/CC) and try multiple model/field fallbacks because:
            - some invalid docs were built with the wrong local_model (e.g. proveedores stored as clientes)
            - name fields vary across tables
            """

            def _pick_name(obj, fields):
                if not obj:
                    return ''
                for f in fields:
                    v = getattr(obj, f, None)
                    v = (v or '').strip() if isinstance(v, str) else (str(v).strip() if v is not None else '')
                    if v:
                        return v
                return ''

            ident = str(local_pk or '').strip()
            if not ident:
                return (local_model, '', '', ['client'])

            # 1) Try the declared model first
            if local_model == 'andinasoft.clientes':
                obj = clientes.objects.filter(pk=ident).first()
                name = _pick_name(obj, ['nombrecompleto', 'nombres', 'apellidos', 'nombre', 'razon_social', 'razonSocial'])
                if obj and not name:
                    # Some records store names split; build a display name.
                    n = _pick_name(obj, ['nombres'])
                    a = _pick_name(obj, ['apellidos'])
                    name = f'{n} {a}'.strip()
                if name:
                    return ('andinasoft.clientes', ident, name, ['client'])
                # fall through to cross-table fallback (many proveedores are "empresas")
            elif local_model == 'andinasoft.empresas':
                obj = empresas.objects.filter(pk=ident).first()
                name = _pick_name(obj, ['nombre', 'razon_social', 'razonSocial', 'nombrecompleto'])
                if name:
                    return ('andinasoft.empresas', ident, name, ['provider'])
            elif local_model == 'andinasoft.asesores':
                obj = asesores.objects.filter(pk=ident).first()
                name = _pick_name(obj, ['nombre', 'nombrecompleto'])
                if name:
                    return ('andinasoft.asesores', ident, name, ['provider'])

            # 2) Cross-table fallback (handles stale invalid docs built with wrong model)
            obj = empresas.objects.filter(pk=ident).first()
            name = _pick_name(obj, ['nombre', 'razon_social', 'razonSocial', 'nombrecompleto'])
            if name:
                return ('andinasoft.empresas', ident, name, ['provider'])

            obj = clientes.objects.filter(pk=ident).first()
            name = _pick_name(obj, ['nombrecompleto', 'nombres', 'apellidos', 'nombre', 'razon_social', 'razonSocial'])
            if obj and not name:
                n = _pick_name(obj, ['nombres'])
                a = _pick_name(obj, ['apellidos'])
                name = f'{n} {a}'.strip()
            if name:
                return ('andinasoft.clientes', ident, name, ['client'])

            obj = asesores.objects.filter(pk=ident).first()
            name = _pick_name(obj, ['nombre', 'nombrecompleto'])
            if name:
                return ('andinasoft.asesores', ident, name, ['provider'])

            return (local_model, ident, '', ['client'])

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

            resolved_model, ident, name, contact_types = _local_info(local_model, local_pk)

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
        invalid_docs = batch.documents.filter(status=AlegraDocument.STATUS_INVALID).values('error', 'source_model', 'source_pk', 'local_key')
        for d in invalid_docs:
            err = (d.get('error') or '')
            if 'tipo "contact"' not in err:
                continue
            m = _MISSING_CONTACT_RE.search(err)
            if not m:
                continue
            local_model = (m.group('model') or '').strip()
            local_pk = (m.group('pk') or '').strip()
            if not local_model or not local_pk:
                continue
            key = (local_model, local_pk)
            entry = missing.setdefault(key, {'local_model': local_model, 'local_pk': local_pk, 'refs': []})
            if len(entry['refs']) < int(max_refs_per_third or 0):
                entry['refs'].append(
                    {
                        'source_model': d.get('source_model'),
                        'source_pk': d.get('source_pk'),
                        'local_key': d.get('local_key'),
                    }
                )

        # Local info helper (reuse logic from bulk create)
        def _local_info(local_model, local_pk):
            def _pick_name(obj, fields):
                if not obj:
                    return ''
                for f in fields:
                    v = getattr(obj, f, None)
                    v = (v or '').strip() if isinstance(v, str) else (str(v).strip() if v is not None else '')
                    if v:
                        return v
                return ''

            ident = str(local_pk or '').strip()
            if not ident:
                return (local_model, '', '')
            if local_model == 'andinasoft.empresas':
                obj = empresas.objects.filter(pk=ident).first()
                name = _pick_name(obj, ['nombre'])
                if name:
                    return ('andinasoft.empresas', ident, name)
            if local_model == 'andinasoft.asesores':
                obj = asesores.objects.filter(pk=ident).first()
                name = _pick_name(obj, ['nombre'])
                if name:
                    return ('andinasoft.asesores', ident, name)
            # clientes (idTercero is PK)
            obj = clientes.objects.filter(pk=ident).first()
            name = _pick_name(obj, ['nombrecompleto', 'nombres', 'apellidos'])
            if obj and not name:
                n = _pick_name(obj, ['nombres'])
                a = _pick_name(obj, ['apellidos'])
                name = f'{n} {a}'.strip()
            if name:
                return ('andinasoft.clientes', ident, name)
            # fallback: try empresas
            obj = empresas.objects.filter(pk=ident).first()
            name = _pick_name(obj, ['nombre'])
            if name:
                return ('andinasoft.empresas', ident, name)
            return (local_model, ident, '')

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
            resolved_model, ident, name = _local_info(local_model, local_pk)
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

    def _validate_input(self, empresa_id, document_type, fecha_desde, fecha_hasta, proyecto_id):
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
        if document_type in (AlegraSyncBatch.DOC_RECEIPT, AlegraSyncBatch.DOC_COMMISSION):
            if not proyecto_id:
                raise AlegraConfigurationError('Este tipo de documento requiere proyecto.')
            proyecto = proyectos.objects.get(pk=proyecto_id)
        elif proyecto_id:
            proyecto = proyectos.objects.get(pk=proyecto_id)
        return empresa, proyecto, desde, hasta

    def _build_documents(self, empresa, proyecto, document_type, desde, hasta):
        if document_type == AlegraSyncBatch.DOC_RECEIPT:
            builder = ReceiptPaymentBuilder(empresa, proyecto)
            queryset = Recaudos_general.objects.using(proyecto.pk).filter(fecha__range=(desde, hasta)).order_by('fecha', 'pk')
            return [self._safe_build(builder, receipt) for receipt in queryset]

        if document_type == AlegraSyncBatch.DOC_COMMISSION:
            builder = CommissionBuilder(empresa, proyecto)
            commissions = Pagocomision.objects.using(proyecto.pk).raw(f'CALL detalle_comisiones_fecha("{desde}","{hasta}")')
            return [self._safe_build(builder, commission) for commission in commissions]

        builder = ExpensePaymentBuilder(empresa)
        pagos = list(Pagos.objects.filter(empresa=empresa, fecha_pago__range=(desde, hasta)).select_related('nroradicado', 'cuenta', 'empresa'))
        anticipos = list(Anticipos.objects.filter(empresa=empresa, fecha_pago__range=(desde, hasta)).select_related('tipo_anticipo', 'cuenta', 'empresa'))
        transferencias = list(transferencias_companias.objects.filter(
            Q(empresa_sale=empresa) | Q(empresa_entra=empresa),
            fecha__range=(desde, hasta),
        ).select_related('cuenta_sale', 'cuenta_entra', 'empresa_sale', 'empresa_entra'))
        results = []
        for item in pagos + anticipos + transferencias:
            results.extend(self._safe_build(builder, item))
        return results

    def _safe_build(self, builder, source):
        source_model = f'{source.__class__._meta.app_label}.{source.__class__.__name__}'
        source_pk = getattr(source, 'pk', None) or getattr(source, 'id_pago', '')
        try:
            built = builder.build(source)
            built_list = built if isinstance(built, list) else [built]
            out = []
            for b in built_list:
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
        existing = AlegraDocument.objects.filter(
            empresa=empresa,
            proyecto=proyecto,
            document_type=document_type,
            local_key=local_key,
        ).first()
        if existing and existing.status == AlegraDocument.STATUS_SENT:
            existing.batch = batch
            existing.save(update_fields=['batch', 'updated_at'])
            return existing

        doc, _ = AlegraDocument.objects.update_or_create(
            empresa=empresa,
            proyecto=proyecto,
            document_type=document_type,
            local_key=local_key,
            defaults={
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
            return client.create_journal(payload)
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
        return {
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
