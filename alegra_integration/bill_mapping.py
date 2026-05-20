"""
Mapeo GET/webhook Alegra bill -> campos de accounting.Facturas.
"""
from django.utils import timezone
from django.utils.dateparse import parse_date


def parse_alegra_bill_id_for_api(alegra_bill_id):
    """
    Extrae (NIT empresa, id numérico bill) para GET /bills/{id}.
    Retorna (None, None) si es journal manual u otro formato no bill.
    """
    raw = (alegra_bill_id or '').strip()
    if not raw or ':journal:' in raw:
        return None, None
    if ':' not in raw:
        return None, None
    nit, rest = raw.split(':', 1)
    nit = nit.strip()
    rest = rest.strip()
    if not nit or not rest or rest.startswith('journal'):
        return None, None
    return nit, rest


def _parse_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _lineas_descripcion_purchases(bill):
    """Concepto del gasto en CO suele venir en purchases.categories (no en termsConditions)."""
    if not isinstance(bill, dict):
        return []
    purchases = bill.get('purchases')
    categories = []
    if isinstance(purchases, dict):
        raw = purchases.get('categories') or purchases.get('items') or []
        if isinstance(raw, list):
            categories = raw
    elif isinstance(purchases, list):
        categories = purchases
    parts = []
    for row in categories:
        if not isinstance(row, dict):
            continue
        obs = (row.get('observations') or '').strip()
        name = (row.get('name') or '').strip()
        if obs:
            parts.append(obs)
        elif name:
            parts.append(name)
    return parts


def bill_descripcion_candidatos(bill):
    """Resumen para depurar qué trae GET /bills/{id} vs lo que mapeamos."""
    if not isinstance(bill, dict):
        return {}
    purchase_lines = _lineas_descripcion_purchases(bill)
    items = bill.get('items') or []
    item_names = []
    for item in items:
        if isinstance(item, dict):
            n = (item.get('name') or item.get('description') or '').strip()
            if n:
                item_names.append(n)
    return {
        'observations': (bill.get('observations') or '').strip() or None,
        'termsConditions': (bill.get('termsConditions') or '').strip() or None,
        'termsConditions_es_autorizacion_numeracion': bool(
            'autorización de numeración' in ((bill.get('termsConditions') or '').lower())
        ),
        'purchases_categories': purchase_lines or None,
        'items': item_names or None,
        'mapeo_actual': descripcion_from_bill(bill),
    }


def descripcion_from_bill(bill, *, number_str='', bid=''):
    """Texto para Facturas.descripcion: observations, purchases.categories, ítems."""
    if not isinstance(bill, dict):
        return (f'Factura compra Alegra {number_str or bid}')[:255]

    observations = bill.get('observations')
    if observations is not None and str(observations).strip():
        return str(observations).strip()[:255]

    purchase_parts = _lineas_descripcion_purchases(bill)
    if purchase_parts:
        text = ', '.join(purchase_parts)
        return text[:252] + '…' if len(text) > 255 else text

    items = bill.get('items') or []
    parts = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (item.get('name') or item.get('description') or item.get('product') or '').strip()
        if isinstance(name, dict):
            name = (name.get('name') or '').strip()
        if name:
            parts.append(name)
    if parts:
        text = ', '.join(parts)
        return text[:252] + '…' if len(text) > 255 else text

    return (f'Factura compra Alegra {number_str or bid}')[:255]


def is_stale_alegra_descripcion(descripcion):
    """Descripción genérica o texto legal DIAN que no debe mostrarse como concepto."""
    d = (descripcion or '').strip()
    if not d:
        return True
    if d.startswith('Factura compra Alegra') or d.startswith('ALEGRA-'):
        return True
    low = d.lower()
    if 'autorización de numeración' in low or 'autorizacion de numeracion' in low:
        return True
    if 'documento soporte n°' in low or 'documento soporte nº' in low:
        return True
    return False


def is_placeholder_descripcion(descripcion):
    return is_stale_alegra_descripcion(descripcion)


def map_bill_to_factura_fields(bill):
    """
    Campos locales derivados de un bill (webhook o GET /bills/{id}).
    """
    nt = bill.get('numberTemplate') or {}
    if isinstance(nt, dict):
        raw_num = nt.get('number')
        number_str = str(raw_num).strip() if raw_num is not None else ''
    else:
        number_str = ''

    client = bill.get('client') or {}
    identification = (client.get('identification') or '').strip()
    if not identification and client.get('id') is not None:
        identification = str(client.get('id')).strip()

    nombre = (client.get('name') or '')[:255]
    bid = str(bill.get('id') or '').strip()

    if bill.get('balance') is not None:
        valor = _parse_int(bill.get('balance'))
    else:
        total = _parse_int(bill.get('total'))
        subtotal = _parse_int(bill.get('subtotal'))
        valor = total if total else subtotal
    pago_neto = valor

    fecha_fact = parse_date(str(bill.get('date') or '')[:10]) if bill.get('date') else None
    if not fecha_fact:
        fecha_fact = timezone.now().date()
    fecha_venc = (
        parse_date(str(bill.get('dueDate') or '')[:10]) if bill.get('dueDate') else fecha_fact
    ) or fecha_fact
    fecha_causa = fecha_fact

    nrocausa = (number_str or f'ALEGRA-{bid}')[:255]
    nrofactura = (number_str or f'ALEGRA-{bid}')[:255]
    idtercero = (identification or str(client.get('id') or ''))[:255]

    return {
        'nrofactura': nrofactura,
        'fechafactura': fecha_fact,
        'fechavenc': fecha_venc,
        'idtercero': idtercero,
        'nombretercero': (nombre or 'SIN NOMBRE')[:255],
        'descripcion': descripcion_from_bill(bill, number_str=number_str, bid=bid),
        'valor': valor,
        'pago_neto': pago_neto,
        'nrocausa': nrocausa,
        'fechacausa': fecha_causa,
        'origen': 'Alegra',
    }


def enrich_factura_from_bill_data(factura, bill_data):
    """
    Completa campos del radicado con GET /bills/{id} sin tocar flujo de aprobación ni nrofactura
    (evita choques con unique idtercero+nrofactura).
    Retorna lista de nombres de campo actualizados.
    """
    if not isinstance(bill_data, dict):
        return []

    mapped = map_bill_to_factura_fields(bill_data)
    update_fields = []

    new_desc = mapped['descripcion']
    if is_stale_alegra_descripcion(factura.descripcion) and not is_placeholder_descripcion(new_desc):
        factura.descripcion = new_desc
        update_fields.append('descripcion')

    if (factura.nombretercero or '').strip() in ('', 'SIN NOMBRE'):
        nombre = (mapped.get('nombretercero') or '').strip()
        if nombre and nombre != 'SIN NOMBRE':
            factura.nombretercero = nombre[:255]
            update_fields.append('nombretercero')

    if not (factura.idtercero or '').strip() and (mapped.get('idtercero') or '').strip():
        factura.idtercero = mapped['idtercero']
        update_fields.append('idtercero')

    for key in ('valor', 'pago_neto', 'fechafactura', 'fechavenc', 'fechacausa', 'nrocausa'):
        new_val = mapped.get(key)
        if new_val is None:
            continue
        if getattr(factura, key, None) != new_val:
            setattr(factura, key, new_val)
            update_fields.append(key)

    if update_fields:
        factura.save(update_fields=update_fields)
    return update_fields
