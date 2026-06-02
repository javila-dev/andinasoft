"""
Reconciliación de POST /payments cuando Alegra indica que la compra ya no tiene saldo (p. ej. 4031).

Tras un envío huérfano (pago creado en Alegra sin AlegraDocument sent local), un reintento devuelve
4031. Consultamos pagos existentes y enlazamos si coinciden monto, fecha, banco, contacto y bill.
"""
import ast
import re
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from alegra_integration.exceptions import AlegraIntegrationError
from alegra_integration.models import AlegraDocument
from alegra_integration.pago_link import sync_pago_from_alegra_document

# Alegra: monto mayor al saldo pendiente de la compra (compra ya pagada o parcialmente cubierta).
RECONCILABLE_PAYMENT_ERROR_CODES = frozenset({4031})


def _money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _money_equal(left, right):
    return _money(left) == _money(right)


def parse_alegra_http_error(message):
    """Extrae code y cuerpo de 'Alegra HTTP 400: {...}'."""
    msg = str(message or '')
    idx = msg.find(': {')
    if idx == -1:
        return None, {}
    try:
        body = ast.literal_eval(msg[idx + 2 :])
    except (SyntaxError, ValueError):
        return None, {}
    if not isinstance(body, dict):
        return None, {}
    code = body.get('code')
    try:
        code = int(code) if code is not None else None
    except (TypeError, ValueError):
        code = None
    return code, body


def should_attempt_payment_reconcile(exc):
    if not isinstance(exc, AlegraIntegrationError):
        return False
    code, _body = parse_alegra_http_error(str(exc))
    return code in RECONCILABLE_PAYMENT_ERROR_CODES


def _nested_id(value):
    if isinstance(value, dict):
        raw = value.get('id')
        return str(raw).strip() if raw not in (None, '') else ''
    if value not in (None, ''):
        return str(value).strip()
    return ''


def _normalize_date(value):
    return str(value or '')[:10]


def payment_criteria_from_payload(payload):
    """Campos esperados del POST /payments que iba a enviarse."""
    if not isinstance(payload, dict):
        return {}

    bills = payload.get('bills') or []
    categories = payload.get('categories') or []
    bill_lines = []
    if isinstance(bills, list):
        for row in bills:
            if not isinstance(row, dict):
                continue
            bill_id = _nested_id(row.get('id'))
            amount = row.get('amount')
            if bill_id and amount is not None:
                bill_lines.append({'id': bill_id, 'amount': _money(amount)})

    category_lines = []
    if isinstance(categories, list):
        for row in categories:
            if not isinstance(row, dict):
                continue
            cat_id = _nested_id(row.get('id'))
            qty = row.get('quantity', 1) or 1
            price = row.get('price')
            if cat_id and price is not None:
                category_lines.append({
                    'id': cat_id,
                    'amount': _money(Decimal(price) * Decimal(qty)),
                })

    if bill_lines:
        amount = sum(line['amount'] for line in bill_lines)
    elif category_lines:
        amount = sum(line['amount'] for line in category_lines)
    else:
        amount = None

    return {
        'date': _normalize_date(payload.get('date')),
        'bank_account_id': _nested_id(payload.get('bankAccount')),
        'client_id': _nested_id(payload.get('client')),
        'payment_type': (payload.get('type') or 'out').strip().lower() or 'out',
        'amount': amount,
        'bill_lines': bill_lines,
        'category_lines': category_lines,
    }


def _payment_bank_account_id(payment):
    if not isinstance(payment, dict):
        return ''
    for key in ('bankAccount', 'account'):
        bank_id = _nested_id(payment.get(key))
        if bank_id:
            return bank_id
    return ''


def _payment_client_id(payment):
    if not isinstance(payment, dict):
        return ''
    return _nested_id(payment.get('client'))


def _payment_type(payment):
    return (payment.get('type') or 'out').strip().lower() or 'out'


def _line_amount(row):
    if not isinstance(row, dict):
        return None
    for key in ('amount', 'totalPaid', 'price'):
        if row.get(key) is not None:
            if key == 'price':
                qty = row.get('quantity', 1) or 1
                return _money(Decimal(row['price']) * Decimal(qty))
            return _money(row[key])
    return None


def payment_total_amount(payment):
    if not isinstance(payment, dict):
        return None
    if payment.get('amount') not in (None, ''):
        return _money(payment['amount'])

    total = Decimal('0')
    found = False
    for key in ('bills', 'invoices'):
        rows = payment.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            amt = _line_amount(row)
            if amt is not None:
                total += amt
                found = True
    if found:
        return _money(total)

    categories = payment.get('categories') or []
    if isinstance(categories, list):
        for row in categories:
            amt = _line_amount(row)
            if amt is not None:
                total += amt
                found = True
    return _money(total) if found else None


def _payment_bill_lines(payment):
    lines = []
    for key in ('bills', 'invoices'):
        rows = payment.get(key) or []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            bill_id = _nested_id(row.get('id'))
            amt = _line_amount(row)
            if bill_id and amt is not None:
                lines.append({'id': bill_id, 'amount': amt})
    return lines


def _payment_category_lines(payment):
    rows = payment.get('categories') or []
    if not isinstance(rows, list):
        return []
    lines = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cat_id = _nested_id(row.get('id'))
        amt = _line_amount(row)
        if cat_id and amt is not None:
            lines.append({'id': cat_id, 'amount': amt})
    return lines


def payment_matches_criteria(payment, criteria):
    if not criteria:
        return False

    expected_type = (criteria.get('payment_type') or 'out').lower()
    if _payment_type(payment) != expected_type:
        return False

    expected_date = criteria.get('date') or ''
    if expected_date and _normalize_date(payment.get('date')) != expected_date:
        return False

    expected_bank = criteria.get('bank_account_id') or ''
    if expected_bank and _payment_bank_account_id(payment) != expected_bank:
        return False

    expected_client = criteria.get('client_id') or ''
    if expected_client and _payment_client_id(payment) != expected_client:
        return False

    expected_amount = criteria.get('amount')
    if expected_amount is not None:
        actual_amount = payment_total_amount(payment)
        if actual_amount is None or not _money_equal(actual_amount, expected_amount):
            return False

    expected_bills = criteria.get('bill_lines') or []
    if expected_bills:
        actual_bills = _payment_bill_lines(payment)
        if len(actual_bills) != len(expected_bills):
            return False
        for exp in expected_bills:
            match = [
                row for row in actual_bills
                if row['id'] == exp['id'] and _money_equal(row['amount'], exp['amount'])
            ]
            if len(match) != 1:
                return False

    expected_categories = criteria.get('category_lines') or []
    if expected_categories and not expected_bills:
        actual_categories = _payment_category_lines(payment)
        if len(actual_categories) != len(expected_categories):
            return False
        for exp in expected_categories:
            match = [
                row for row in actual_categories
                if row['id'] == exp['id'] and _money_equal(row['amount'], exp['amount'])
            ]
            if len(match) != 1:
                return False

    return True


def _unwrap_payments_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        data = payload.get('data')
        if isinstance(data, list):
            return data
    return []


def list_out_payments_for_client(client, client_id, *, limit=30, max_pages=6):
    """Pagina GET /payments filtrado por client_id y type=out."""
    client_id = str(client_id or '').strip()
    if not client_id:
        return []

    items = []
    start = 0
    for _ in range(max_pages):
        page = client.list_payments(
            start=start,
            limit=limit,
            type='out',
            client_id=client_id,
            order_field='date',
            order_direction='DESC',
        )
        chunk = _unwrap_payments_list(page)
        if not chunk:
            break
        items.extend(chunk)
        if len(chunk) < limit:
            break
        start += limit
    return items


def find_matching_payment(client, payload):
    criteria = payment_criteria_from_payload(payload)
    client_id = criteria.get('client_id')
    if not client_id or criteria.get('amount') is None:
        return None

    matches = [
        payment for payment in list_out_payments_for_client(client, client_id)
        if payment_matches_criteria(payment, criteria)
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


def reconcile_expense_payment_document(doc, client, exc):
    """
    Busca en Alegra un pago out que coincida con doc.payload; si hay uno solo, marca doc sent.
    Retorna True si reconcilió.
    """
    payload = doc.payload or {}
    if isinstance(payload, dict) and any(str(k).startswith('__') for k in payload.keys()):
        payload = {k: v for k, v in payload.items() if not str(k).startswith('__')}

    payment = find_matching_payment(client, payload)
    if not payment:
        return False

    alegra_id = _nested_id(payment.get('id'))
    if not alegra_id or _alegra_id_already_linked(doc, alegra_id):
        return False

    code, error_body = parse_alegra_http_error(str(exc))
    doc.status = AlegraDocument.STATUS_SENT
    doc.alegra_id = alegra_id
    doc.error = ''
    doc.response = {
        'reconciled': True,
        'reconciled_reason': 'payment_already_applied',
        'reconcile_error_code': code,
        'reconcile_error': error_body,
        'payment': payment,
    }
    doc.sent_at = timezone.now()
    doc.save(update_fields=['status', 'response', 'alegra_id', 'error', 'sent_at', 'updated_at'])
    sync_pago_from_alegra_document(doc)
    return True
