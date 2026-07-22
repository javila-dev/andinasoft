"""
Reconciliación de POST /journals por `reference` exacta.

Aplica a cualquier AlegraDocument con operation accounting__createJournal y reference
estable (recibos RC-…, comisiones COM-…, caja LC-…, intercompany INTERCO-…).

Evita duplicar asientos cuando Alegra ya creó el journal (timeout, failed local, reintento)
pero el documento local no quedó en status=sent.
"""
from django.utils import timezone

from alegra_integration.models import AlegraDocument
from alegra_integration.pago_link import sync_pago_from_alegra_document


def _clean_payload(payload):
    if not isinstance(payload, dict):
        return {}
    if any(str(k).startswith('__') for k in payload.keys()):
        return {k: v for k, v in payload.items() if not str(k).startswith('__')}
    return payload


def reference_from_payload(payload):
    payload = _clean_payload(payload)
    ref = payload.get('reference')
    if ref is None:
        return ''
    return str(ref).strip()


def should_attempt_journal_reconcile(doc):
    """Cualquier journal con reference no vacía (recibos, comisiones, caja, interco, …)."""
    if getattr(doc, 'alegra_operation', None) != 'accounting__createJournal':
        return False
    return bool(reference_from_payload(getattr(doc, 'payload', None)))


# Alias histórico (tests / imports viejos)
should_attempt_receipt_reconcile = should_attempt_journal_reconcile


def _nested_id(value):
    if isinstance(value, dict):
        raw = value.get('id')
        return str(raw).strip() if raw not in (None, '') else ''
    if value not in (None, ''):
        return str(value).strip()
    return ''


def _unwrap_journals_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get('data')
        if isinstance(data, list):
            return data
    return []


def _journal_reference(journal):
    if not isinstance(journal, dict):
        return ''
    ref = journal.get('reference')
    if ref is None:
        return ''
    return str(ref).strip()


def list_journals_by_reference(client, reference, *, limit=30, max_pages=3):
    """Página GET /journals?reference=… (contains) y acumula resultados."""
    reference = str(reference or '').strip()
    if not reference:
        return []

    items = []
    start = 0
    for _ in range(max_pages):
        page = client.list_journals(
            start=start,
            limit=limit,
            reference=reference,
            order_field='date',
            order_direction='DESC',
        )
        chunk = _unwrap_journals_list(page)
        if not chunk:
            break
        items.extend(chunk)
        if len(chunk) < limit:
            break
        start += limit
    return items


def find_journal_by_exact_reference(client, reference):
    """
    Busca un journal cuya reference coincida exactamente.
    Retorna el journal solo si hay exactamente un match exacto
    (el filtro Alegra es 'contains', así que RC-X-1 no debe confundirse con RC-X-10).
    """
    reference = str(reference or '').strip()
    if not reference:
        return None

    matches = [
        journal
        for journal in list_journals_by_reference(client, reference)
        if _journal_reference(journal) == reference
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _alegra_id_already_linked(doc, alegra_id):
    alegra_id = str(alegra_id or '').strip()
    if not alegra_id:
        return False
    return AlegraDocument.objects.filter(
        empresa=doc.empresa,
        document_type=doc.document_type,
        alegra_id=alegra_id,
        status=AlegraDocument.STATUS_SENT,
    ).exclude(pk=doc.pk).exists()


def mark_document_from_journal(doc, journal, *, reason, error_context=None):
    """Enlaza doc al journal existente y marca sent. Retorna True si enlazó."""
    alegra_id = _nested_id((journal or {}).get('id'))
    if not alegra_id or _alegra_id_already_linked(doc, alegra_id):
        return False

    response = {
        'reconciled': True,
        'reconciled_reason': reason,
        'journal': journal,
    }
    if error_context is not None:
        response['reconcile_error'] = str(error_context)[:500]

    doc.status = AlegraDocument.STATUS_SENT
    doc.alegra_id = alegra_id
    doc.error = ''
    doc.response = response
    doc.sent_at = timezone.now()
    doc.save(update_fields=['status', 'response', 'alegra_id', 'error', 'sent_at', 'updated_at'])
    sync_pago_from_alegra_document(doc)
    return True


mark_receipt_document_from_journal = mark_document_from_journal


def claim_existing_journal(doc, client):
    """
    Pre-check: si ya existe un journal con la misma reference exacta, marca sent sin POST.
    """
    if not should_attempt_journal_reconcile(doc):
        return False
    reference = reference_from_payload(doc.payload)
    journal = find_journal_by_exact_reference(client, reference)
    if not journal:
        return False
    return mark_document_from_journal(
        doc,
        journal,
        reason='journal_already_exists_by_reference',
    )


claim_existing_receipt_journal = claim_existing_journal


def reconcile_journal_document(doc, client, exc=None):
    """
    Tras un fallo de envío: busca journal por reference y enlaza si hay match único.
    """
    if not should_attempt_journal_reconcile(doc):
        return False
    reference = reference_from_payload(doc.payload)
    journal = find_journal_by_exact_reference(client, reference)
    if not journal:
        return False
    return mark_document_from_journal(
        doc,
        journal,
        reason='journal_reconciled_by_reference',
        error_context=exc,
    )


reconcile_receipt_document = reconcile_journal_document
