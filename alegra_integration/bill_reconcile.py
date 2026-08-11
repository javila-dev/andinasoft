"""
Reconciliación de POST /bills de caja efectivo.

Evita duplicar bills cuando Alegra ya creó el documento (timeout, failed local, reintento)
pero AlegraDocument no quedó en status=sent.

Identidad estable: observations incluye `[caja-gasto:{pk}]` (CajaGastoBillBuilder).
Fallback: provider + fecha + monto (+ observations exactas) con match único.
"""
from decimal import Decimal, ROUND_HALF_UP
import re

from django.utils import timezone

from alegra_integration.models import AlegraDocument
from alegra_integration.pago_link import sync_pago_from_alegra_document

CAJA_GASTO_MARKER_RE = re.compile(r'\[caja-gasto:(\d+)\]')


def _money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _money_equal(left, right):
    return _money(left) == _money(right)


def _clean_payload(payload):
    if not isinstance(payload, dict):
        return {}
    if any(str(k).startswith('__') for k in payload.keys()):
        return {k: v for k, v in payload.items() if not str(k).startswith('__')}
    return payload


def _nested_id(value):
    if isinstance(value, dict):
        raw = value.get('id')
        return str(raw).strip() if raw not in (None, '') else ''
    if value not in (None, ''):
        return str(value).strip()
    return ''


def _normalize_date(value):
    return str(value or '')[:10]


def should_attempt_caja_bill_reconcile(doc):
    """Solo bills de caja (local_key caja:bill:…)."""
    if getattr(doc, 'alegra_operation', None) != 'POST /bills':
        return False
    if getattr(doc, 'document_type', None) != 'caja_bill':
        return False
    local_key = str(getattr(doc, 'local_key', '') or '')
    return local_key.startswith('caja:bill:')


def caja_gasto_pk_from_doc(doc):
    """PK del gasto local desde source_pk, local_key o marker en observations."""
    source_pk = str(getattr(doc, 'source_pk', '') or '').strip()
    if source_pk.isdigit():
        return source_pk

    local_key = str(getattr(doc, 'local_key', '') or '')
    if local_key.startswith('caja:bill:'):
        # caja:bill:{reembolso_id}:{gasto_pk}
        parts = local_key.split(':')
        if len(parts) >= 4 and parts[-1].isdigit():
            return parts[-1]

    payload = getattr(doc, 'payload', None)
    if isinstance(payload, dict):
        obs = str(payload.get('observations') or '')
        match = CAJA_GASTO_MARKER_RE.search(obs)
        if match:
            return match.group(1)
    return ''


def caja_bill_marker(gasto_pk):
    return f'[caja-gasto:{gasto_pk}]'


def expected_amount_from_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    local = payload.get('__local') if isinstance(payload.get('__local'), dict) else {}
    if local.get('valor_esperado') is not None:
        return _money(local['valor_esperado'])

    clean = _clean_payload(payload)
    purchases = clean.get('purchases') if isinstance(clean.get('purchases'), dict) else {}
    categories = purchases.get('categories') or []
    total = Decimal('0')
    found = False
    if isinstance(categories, list):
        for row in categories:
            if not isinstance(row, dict) or row.get('price') is None:
                continue
            qty = row.get('quantity', 1) or 1
            total += Decimal(row['price']) * Decimal(qty)
            found = True
    return _money(total) if found else None


def bill_criteria_from_payload(payload):
    clean = _clean_payload(payload)
    local = payload.get('__local') if isinstance(payload, dict) and isinstance(payload.get('__local'), dict) else {}
    obs = str(clean.get('observations') or '').strip()
    marker_match = CAJA_GASTO_MARKER_RE.search(obs)
    gasto_pk = (
        str(local.get('gasto_id') or '').strip()
        or (marker_match.group(1) if marker_match else '')
    )
    return {
        'date': _normalize_date(clean.get('date')),
        'provider_id': _nested_id(clean.get('provider')),
        'observations': obs,
        'amount': expected_amount_from_payload(payload if isinstance(payload, dict) else {}),
        'gasto_pk': gasto_pk,
    }


def _unwrap_bills_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get('data')
        if isinstance(data, list):
            return data
    return []


def _bill_observations(bill):
    if not isinstance(bill, dict):
        return ''
    return str(bill.get('observations') or '').strip()


def _bill_provider_id(bill):
    if not isinstance(bill, dict):
        return ''
    for key in ('provider', 'client', 'contact'):
        pid = _nested_id(bill.get(key))
        if pid:
            return pid
    return ''


def _bill_date(bill):
    if not isinstance(bill, dict):
        return ''
    for key in ('date', 'dueDate'):
        if bill.get(key):
            return _normalize_date(bill.get(key))
    return ''


def bill_total_amount(bill):
    if not isinstance(bill, dict):
        return None
    for key in ('total', 'totalAmount', 'amount'):
        if bill.get(key) not in (None, ''):
            return _money(bill[key])

    purchases = bill.get('purchases') if isinstance(bill.get('purchases'), dict) else {}
    categories = purchases.get('categories') or bill.get('categories') or []
    total = Decimal('0')
    found = False
    if isinstance(categories, list):
        for row in categories:
            if not isinstance(row, dict) or row.get('price') is None:
                continue
            qty = row.get('quantity', 1) or 1
            total += Decimal(row['price']) * Decimal(qty)
            found = True
    return _money(total) if found else None


def list_bills_filtered(client, *, date=None, client_id=None, observations=None, limit=30, max_pages=3):
    items = []
    start = 0
    for _ in range(max_pages):
        page = client.list_bills(
            start=start,
            limit=limit,
            date=date,
            client_id=client_id,
            observations=observations,
            order_field='date',
            order_direction='DESC',
        )
        chunk = _unwrap_bills_list(page)
        if not chunk:
            break
        items.extend(chunk)
        if len(chunk) < limit:
            break
        start += limit
    return items


def find_caja_bill_in_alegra(client, doc):
    """
    Busca un bill existente único para este documento de caja.
    1) Por marker [caja-gasto:{pk}] en observations.
    2) Fallback: provider + fecha + monto (+ observations exactas si hay).
    """
    if not should_attempt_caja_bill_reconcile(doc):
        return None

    gasto_pk = caja_gasto_pk_from_doc(doc)
    criteria = bill_criteria_from_payload(getattr(doc, 'payload', None))
    if gasto_pk:
        criteria['gasto_pk'] = gasto_pk

    marker = caja_bill_marker(criteria['gasto_pk']) if criteria.get('gasto_pk') else ''

    # 1) Búsqueda por marker (contains); luego exigir marker exacto en observations.
    if marker:
        candidates = list_bills_filtered(
            client,
            date=criteria.get('date') or None,
            client_id=criteria.get('provider_id') or None,
            observations=marker,
        )
        marked = [
            bill for bill in candidates
            if marker in _bill_observations(bill)
        ]
        if len(marked) == 1:
            return marked[0]
        if len(marked) > 1 and criteria.get('amount') is not None:
            amount_matches = [
                bill for bill in marked
                if bill_total_amount(bill) is not None
                and _money_equal(bill_total_amount(bill), criteria['amount'])
            ]
            if len(amount_matches) == 1:
                return amount_matches[0]
            return None
        if marked:
            return None

    # 2) Fallback sin marker (bills huérfanos previos al cambio de observations).
    if not criteria.get('provider_id') or not criteria.get('date') or criteria.get('amount') is None:
        return None

    candidates = list_bills_filtered(
        client,
        date=criteria['date'],
        client_id=criteria['provider_id'],
    )
    matches = []
    for bill in candidates:
        if _bill_provider_id(bill) and _bill_provider_id(bill) != criteria['provider_id']:
            continue
        if _bill_date(bill) and _bill_date(bill) != criteria['date']:
            continue
        total = bill_total_amount(bill)
        if total is None or not _money_equal(total, criteria['amount']):
            continue
        obs = _bill_observations(bill)
        expected_obs = criteria.get('observations') or ''
        # Si el payload ya trae marker, exigir que el bill lo tenga o que observations coincidan.
        if marker and marker not in obs and expected_obs and obs != expected_obs:
            # Permitir match si observations del bill == descripción sin marker
            stripped = expected_obs.replace(marker, '').strip()
            if stripped and obs != stripped and obs != expected_obs:
                continue
        elif expected_obs and not marker and obs and obs != expected_obs:
            continue
        matches.append(bill)

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


def mark_document_from_bill(doc, bill, *, reason, error_context=None):
    """Enlaza doc al bill existente y marca sent. Retorna True si enlazó."""
    alegra_id = _nested_id((bill or {}).get('id'))
    if not alegra_id or _alegra_id_already_linked(doc, alegra_id):
        return False

    response = {
        'reconciled': True,
        'reconciled_reason': reason,
        'bill': bill,
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


def claim_existing_caja_bill(doc, client):
    """Pre-check: si ya existe el bill en Alegra, marca sent sin POST."""
    if not should_attempt_caja_bill_reconcile(doc):
        return False
    bill = find_caja_bill_in_alegra(client, doc)
    if not bill:
        return False
    return mark_document_from_bill(
        doc,
        bill,
        reason='caja_bill_already_exists',
    )


def reconcile_caja_bill_document(doc, client, exc=None):
    """Tras fallo de envío: busca bill existente y enlaza si hay match único."""
    if not should_attempt_caja_bill_reconcile(doc):
        return False
    bill = find_caja_bill_in_alegra(client, doc)
    if not bill:
        return False
    return mark_document_from_bill(
        doc,
        bill,
        reason='caja_bill_reconciled_after_error',
        error_context=exc,
    )
