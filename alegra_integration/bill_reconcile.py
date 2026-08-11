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


def caja_gasto_pk_from_text(text):
    """PK del gasto si el texto incluye `[caja-gasto:{pk}]`; vacío si no."""
    match = CAJA_GASTO_MARKER_RE.search(str(text or ''))
    return match.group(1) if match else ''


def caja_gasto_pk_from_bill(bill):
    """
    Extrae el pk del gasto desde un bill Alegra (webhook o GET).
    Busca el marker en observations y, por si el payload lo trae aparte, en
    lines de purchases.
    """
    if not isinstance(bill, dict):
        return ''

    for key in ('observations', 'termsConditions', 'anotation', 'annotation'):
        gasto_pk = caja_gasto_pk_from_text(bill.get(key))
        if gasto_pk:
            return gasto_pk

    purchases = bill.get('purchases')
    categories = []
    if isinstance(purchases, dict):
        raw = purchases.get('categories') or purchases.get('items') or []
        if isinstance(raw, list):
            categories = raw
    elif isinstance(purchases, list):
        categories = purchases
    for row in categories:
        if not isinstance(row, dict):
            continue
        gasto_pk = caja_gasto_pk_from_text(row.get('observations') or row.get('name'))
        if gasto_pk:
            return gasto_pk
    return ''


def caja_bill_sent_document(empresa, alegra_numeric_id):
    """
    AlegraDocument caja_bill con este alegra_id, o None.

    Prefiere status=sent; si no hay, acepta cualquier doc con ese id
    (cubre carreras webhook vs save local).
    """
    alegra_id = str(alegra_numeric_id or '').strip()
    if not empresa or not alegra_id:
        return None
    qs = AlegraDocument.objects.filter(
        empresa=empresa,
        document_type='caja_bill',
        alegra_id=alegra_id,
    )
    sent = qs.filter(status=AlegraDocument.STATUS_SENT).order_by('-pk').first()
    if sent:
        return sent
    return qs.order_by('-pk').first()


def skip_factura_for_caja_bill(bill, *, empresa=None):
    """
    Si el bill es de caja efectivo, no debe crear radicado Facturas.

    Primario: marker `[caja-gasto:{pk}]` en el payload.
    Respaldo: AlegraDocument caja_bill sent con el mismo alegra_id.

    Retorna dict de skip (processed/skipped/skip_reason/gasto_id) o None.
    """
    gasto_pk = caja_gasto_pk_from_bill(bill)
    if gasto_pk:
        return {
            'processed': True,
            'skipped': True,
            'skip_reason': 'caja_gasto_bill',
            'gasto_id': gasto_pk,
        }

    alegra_id = _nested_id((bill or {}).get('id')) if isinstance(bill, dict) else ''
    doc = caja_bill_sent_document(empresa, alegra_id) if empresa else None
    if doc:
        return {
            'processed': True,
            'skipped': True,
            'skip_reason': 'caja_gasto_bill',
            'gasto_id': caja_gasto_pk_from_doc(doc) or '',
            'skip_via': 'alegra_document',
        }
    return None


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


def list_caja_bills_for_gasto(client, gasto_pk, *, max_pages=3):
    """
    Todos los bills en Alegra con marker exacto [caja-gasto:{pk}].
    Sin filtrar por fecha/proveedor (evita ocultar duplicados).
    """
    gasto_pk = str(gasto_pk or '').strip()
    if not gasto_pk.isdigit():
        return []
    marker = caja_bill_marker(gasto_pk)
    candidates = list_bills_filtered(
        client,
        observations=marker,
        max_pages=max_pages,
    )
    # Post-filtro: regex exacta del pk (Alegra observations es contains).
    return [
        bill for bill in candidates
        if caja_gasto_pk_from_text(_bill_observations(bill)) == gasto_pk
    ]


def list_caja_bills_soft_match(client, criteria, *, max_pages=3):
    """
    Candidatos posibles sin marker: misma fecha + mismo proveedor + mismo monto.
    El usuario decide en UI; no se usa para claim automático ambiguo.
    """
    criteria = criteria or {}
    provider_id = str(criteria.get('provider_id') or '').strip()
    date = _normalize_date(criteria.get('date'))
    amount = criteria.get('amount')
    if not provider_id or not date or amount is None:
        return []

    candidates = list_bills_filtered(
        client,
        date=date,
        client_id=provider_id,
        max_pages=max_pages,
    )
    matches = []
    for bill in candidates:
        if _bill_provider_id(bill) and _bill_provider_id(bill) != provider_id:
            continue
        if _bill_date(bill) and _bill_date(bill) != date:
            continue
        total = bill_total_amount(bill)
        if total is None or not _money_equal(total, amount):
            continue
        matches.append(bill)
    return matches


def criteria_from_alegra_bill(bill):
    """Criterios de soft-match a partir de un bill Alegra (p. ej. el keep local)."""
    if not isinstance(bill, dict):
        return {}
    return {
        'date': _bill_date(bill),
        'provider_id': _bill_provider_id(bill),
        'amount': bill_total_amount(bill),
        'observations': _bill_observations(bill),
        'gasto_pk': caja_gasto_pk_from_text(_bill_observations(bill)),
    }


def collect_caja_bills_for_review(client, *, gasto_pk, criteria, keep_alegra_id=''):
    """
    Une candidatos por marker y por soft-match (fecha/tercero/valor).
    Incluye el bill keep vía GET si no apareció en listados.
    Retorna dict id -> {'bill', 'match_kind'} (marker | soft | keep).
    """
    by_id = {}
    for bill in list_caja_bills_for_gasto(client, gasto_pk):
        bid = _nested_id((bill or {}).get('id'))
        if bid:
            by_id[bid] = {'bill': bill, 'match_kind': 'marker'}

    for bill in list_caja_bills_soft_match(client, criteria):
        bid = _nested_id((bill or {}).get('id'))
        if not bid or bid in by_id:
            continue
        by_id[bid] = {'bill': bill, 'match_kind': 'soft'}

    keep = str(keep_alegra_id or '').strip()
    if keep and keep not in by_id:
        try:
            bill = client.get_bill(keep)
        except Exception:
            bill = None
        if isinstance(bill, dict) and _nested_id(bill.get('id')):
            by_id[keep] = {'bill': bill, 'match_kind': 'keep'}
    return by_id


def summarize_caja_bill_for_review(
    bill, *, criteria=None, keep_alegra_id='', locked_ids=None, match_kind='marker',
    owner=None, current_gasto_pk='',
):
    """Resumen liviano para UI Revisar gasto."""
    criteria = criteria or {}
    locked_ids = {str(x).strip() for x in (locked_ids or set()) if str(x).strip()}
    bill_id = _nested_id((bill or {}).get('id'))
    total = bill_total_amount(bill)
    date = _bill_date(bill)
    provider_id = _bill_provider_id(bill)
    nt = (bill or {}).get('numberTemplate') if isinstance(bill, dict) else None
    number = ''
    if isinstance(nt, dict) and nt.get('number') is not None:
        number = str(nt.get('number')).strip()

    amount_mismatch = False
    date_mismatch = False
    provider_mismatch = False
    if criteria.get('amount') is not None and total is not None:
        amount_mismatch = not _money_equal(total, criteria['amount'])
    if criteria.get('date') and date:
        date_mismatch = date != criteria['date']
    if criteria.get('provider_id') and provider_id:
        provider_mismatch = provider_id != criteria['provider_id']

    is_keep = bool(keep_alegra_id) and bill_id == str(keep_alegra_id).strip()
    journal_locked = bill_id in locked_ids
    kind = str(match_kind or 'marker').strip() or 'marker'

    owner = owner if isinstance(owner, dict) else None
    linked_document_id = (owner or {}).get('document_id')
    linked_gasto_id = str((owner or {}).get('gasto_id') or '').strip()
    linked_local_key = str((owner or {}).get('local_key') or '').strip()
    linked_batch_id = (owner or {}).get('batch_id')
    if linked_batch_id not in (None, ''):
        try:
            linked_batch_id = int(linked_batch_id)
        except (TypeError, ValueError):
            linked_batch_id = None
    else:
        linked_batch_id = None
    current_gasto = str(current_gasto_pk or '').strip()
    linked_other = bool(owner) and linked_gasto_id != current_gasto
    # Ya ligado a algún gasto de caja (aunque sea el mismo) → no re-asociar.
    already_linked = bool(owner)

    return {
        'id': bill_id,
        'date': date,
        'total': float(total) if total is not None else None,
        'observations': _bill_observations(bill)[:200],
        'number': number,
        'provider_id': provider_id,
        'match_kind': kind,
        'is_keep': is_keep,
        'journal_locked': journal_locked,
        'linked_document_id': linked_document_id,
        'linked_gasto_id': linked_gasto_id or None,
        'linked_local_key': linked_local_key or None,
        'linked_batch_id': linked_batch_id,
        'linked_other': linked_other,
        'already_linked': already_linked,
        'amount_mismatch': amount_mismatch,
        'date_mismatch': date_mismatch,
        'provider_mismatch': provider_mismatch,
        'can_delete': (
            bool(bill_id) and not is_keep and not journal_locked and not linked_other
        ),
        'can_associate': (
            bool(bill_id)
            and not is_keep
            and not journal_locked
            and not already_linked
        ),
    }


def caja_bill_owners_by_alegra_ids(empresa, alegra_ids, *, exclude_doc_pk=None):
    """
    Mapa alegra_id → {document_id, gasto_id, local_key, batch_id} para caja_bill sent
    de esa empresa. Sirve para no asociar/borrar ids ya ligados a otro gasto
    y para mostrar dónde buscarlo en la UI.
    """
    ids = sorted({str(x).strip() for x in (alegra_ids or []) if str(x or '').strip()})
    if not ids:
        return {}
    qs = AlegraDocument.objects.filter(
        empresa=empresa,
        document_type='caja_bill',
        status=AlegraDocument.STATUS_SENT,
        alegra_id__in=ids,
    ).only('pk', 'alegra_id', 'local_key', 'source_pk', 'payload', 'batch_id')
    if exclude_doc_pk not in (None, ''):
        qs = qs.exclude(pk=exclude_doc_pk)
    out = {}
    for doc in qs:
        aid = str(doc.alegra_id or '').strip()
        if not aid or aid in out:
            continue
        batch_id = getattr(doc, 'batch_id', None)
        out[aid] = {
            'document_id': doc.pk,
            'gasto_id': caja_gasto_pk_from_doc(doc),
            'local_key': doc.local_key,
            'batch_id': batch_id,
        }
    return out


def journal_locked_caja_bill_ids(empresa):
    """Bill ids referenciados por caja_journal sent (no borrar)."""
    locked = set()
    qs = AlegraDocument.objects.filter(
        empresa=empresa,
        document_type='caja_journal',
        status=AlegraDocument.STATUS_SENT,
    ).only('payload')
    for doc in qs:
        payload = doc.payload if isinstance(doc.payload, dict) else {}
        local = payload.get('__local') if isinstance(payload.get('__local'), dict) else {}
        for row in local.get('pending_bills') or []:
            if not isinstance(row, dict):
                continue
            bid = row.get('alegra_bill_id')
            if bid not in (None, ''):
                locked.add(str(bid).strip())
        for entry in payload.get('entries') or []:
            if not isinstance(entry, dict):
                continue
            assoc = entry.get('associatedDocument')
            if not isinstance(assoc, dict):
                continue
            if str(assoc.get('resourceType') or '').lower() != 'bill':
                continue
            rid = assoc.get('idResource')
            if rid in (None, '', 0, '0'):
                continue
            locked.add(str(rid).strip())
    return locked


def find_caja_bill_in_alegra(client, doc):
    """
    Busca un bill existente único para este documento de caja.
    1) Por marker [caja-gasto:{pk}] — solo si hay exactamente 1.
    2) Fallback histórico: provider + fecha + monto (solo claim; no borrado).
    """
    if not should_attempt_caja_bill_reconcile(doc):
        return None

    gasto_pk = caja_gasto_pk_from_doc(doc)
    criteria = bill_criteria_from_payload(getattr(doc, 'payload', None))
    if gasto_pk:
        criteria['gasto_pk'] = gasto_pk

    marker = caja_bill_marker(criteria['gasto_pk']) if criteria.get('gasto_pk') else ''

    # 1) Listado unificado por marker (sin date/provider).
    if criteria.get('gasto_pk'):
        marked = list_caja_bills_for_gasto(client, criteria['gasto_pk'])
        if len(marked) == 1:
            return marked[0]
        if len(marked) > 1:
            # Ambiguo: el usuario limpia con Revisar gasto (no auto-elegir por monto).
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
        if marker and marker not in obs and expected_obs and obs != expected_obs:
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
