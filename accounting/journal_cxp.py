"""
Extracción de líneas CxP desde GET /journals/{id} (Alegra).

Regla acordada:
- Movimiento con crédito > 0 y tercero identificado.
- Cuenta de pasivo orden 2 (código empieza por "2") cuando esté disponible.
- Excluir retenciones e impuestos por pagar (nombre/descripción).
- Priorizar líneas con associatedDocument v_bill.
"""
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_date

# Retenciones / impuestos por pagar (no CxP del proveedor/comisionado a radicar).
_EXCLUIR_PASIVO_TEXTO = re.compile(
    r'reten(?:cion|ci[oó]n)?|retefuente|rete\s*\.|ica\b|iva\b|impuesto',
    re.IGNORECASE,
)


def _money(value):
    if value is None:
        return 0
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return 0


def _client_identification(client):
    if not client or not isinstance(client, dict):
        return ''
    ident = (client.get('identification') or '').strip()
    if ident:
        return re.sub(r'\D', '', ident)
    obj = client.get('identificationObject') or {}
    return re.sub(r'\D', '', str(obj.get('number') or ''))


def _client_nombre(client):
    if not client:
        return ''
    return (client.get('name') or '').strip()[:255]


def _entry_account_code(entry):
    """Código contable del pasivo si Alegra lo envía en la línea o en el contacto."""
    for key in ('code', 'accountCode'):
        code = entry.get(key)
        if code:
            return str(code).strip()
    cat = entry.get('category')
    if isinstance(cat, dict) and cat.get('code'):
        return str(cat['code']).strip()
    client = entry.get('client') or {}
    debt = (client.get('accounting') or {}).get('debtToPay') or {}
    return str(debt.get('code') or '').strip()


def _es_retencion_o_impuesto(entry):
    texto = f"{entry.get('name') or ''} {entry.get('description') or ''}"
    return bool(_EXCLUIR_PASIVO_TEXTO.search(texto))


def _es_cxp_entry(entry):
    if (entry.get('type') or '').lower() != 'category':
        return False
    credit = _money(entry.get('credit'))
    if credit <= 0:
        return False
    if not _client_identification(entry.get('client')):
        return False
    if _es_retencion_o_impuesto(entry):
        return False

    assoc = entry.get('associatedDocument') or {}
    if (assoc.get('resourceType') or '') == 'v_bill':
        return True

    code = _entry_account_code(entry)
    if code:
        return code.startswith('2')
    # Sin código en payload: crédito con tercero y sin exclusión (p. ej. Comisiones).
    return True


def extraer_lineas_cxp(journal):
    """
    Devuelve líneas CxP agrupadas por identificación del tercero.
    Cada ítem: id_tercero, nombre_tercero, valor (suma créditos), detalle (líneas crudas).
    """
    entries = journal.get('entries') if isinstance(journal, dict) else []
    buckets = defaultdict(lambda: {'nombre_tercero': '', 'valor': 0, 'lineas': []})

    for entry in entries or []:
        if not _es_cxp_entry(entry):
            continue
        client = entry.get('client') or {}
        ident = _client_identification(client)
        credit = _money(entry.get('credit'))
        buckets[ident]['valor'] += credit
        buckets[ident]['nombre_tercero'] = _client_nombre(client) or buckets[ident]['nombre_tercero']
        buckets[ident]['lineas'].append({
            'name': entry.get('name'),
            'description': entry.get('description'),
            'credit': credit,
            'account_code': _entry_account_code(entry),
        })

    result = []
    for ident, data in sorted(buckets.items(), key=lambda x: x[0]):
        result.append({
            'id_tercero': ident,
            'nombre_tercero': data['nombre_tercero'],
            'valor': data['valor'],
            'vencimiento': 1,
            'lineas': data['lineas'],
        })
    return result


def _nro_factura_desde_journal(journal, journal_id):
    for entry in journal.get('entries') or []:
        assoc = entry.get('associatedDocument') or {}
        if (assoc.get('resourceType') or '') == 'v_bill':
            res = assoc.get('resource') or {}
            num = (res.get('number') or '').strip()
            if num:
                return num[:255]
    ref = (journal.get('reference') or '').strip()
    if ref:
        return ref[:255]
    obs = (journal.get('observations') or '').strip()
    if obs:
        return obs[:255]
    return f'JOURNAL-{journal_id}'[:255]


def _fechas_desde_journal(journal):
    fecha = parse_date(str(journal.get('date') or '')[:10])
    for entry in journal.get('entries') or []:
        assoc = entry.get('associatedDocument') or {}
        if (assoc.get('resourceType') or '') == 'v_bill':
            res = assoc.get('resource') or {}
            fd = parse_date(str(res.get('date') or '')[:10])
            fv = parse_date(str(res.get('dueDate') or '')[:10])
            if fd:
                fecha = fd
            if fv:
                return fecha, fv
    return fecha, fecha


def _cabecera_tercero(journal, lineas_cxp):
    if len(lineas_cxp) == 1:
        return lineas_cxp[0]['id_tercero'], lineas_cxp[0]['nombre_tercero']
    employee = journal.get('employee') or {}
    ident = _client_identification(employee)
    nombre = _client_nombre(employee)
    if ident and nombre:
        return ident, nombre
    if lineas_cxp:
        return lineas_cxp[0]['id_tercero'], f"VARIOS ({len(lineas_cxp)} terceros)"
    return '', ''


def _descripcion_desde_journal(journal, multi_tercero):
    obs = (journal.get('observations') or '').strip()[:255]
    if not obs:
        obs = 'Gasto Alegra journal'
    upper = obs.upper()
    if multi_tercero and 'COMISION' not in upper:
        obs = f'{obs} COMISION'[:255]
    return obs


def detalle_pago_desde_factura(factura):
    """Lista para pago_detallado_relacionado o None."""
    raw = getattr(factura, 'alegra_journal_detalle', None) or ''
    if not raw.strip():
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, list) or not data:
        return None
    return data


def parsear_journal_para_radicado(journal):
    """
    Mapeo journal → campos de Facturas + detalle para pago_detallado al pagar.
    Raises ValueError si no hay líneas CxP.
    """
    if not isinstance(journal, dict):
        raise ValueError('Journal inválido.')
    journal_id = str(journal.get('id') or '').strip()
    lineas_cxp = extraer_lineas_cxp(journal)
    if not lineas_cxp:
        raise ValueError('No se encontraron líneas CxP (crédito pasivo orden 2) en el comprobante.')

    valor_total = sum(row['valor'] for row in lineas_cxp)
    if valor_total <= 0:
        raise ValueError('El total CxP del journal es cero.')

    multi = len(lineas_cxp) > 1
    id_tercero, nombre_tercero = _cabecera_tercero(journal, lineas_cxp)
    if not id_tercero:
        raise ValueError('No se pudo determinar tercero de cabecera.')

    fecha_factura, fecha_venc = _fechas_desde_journal(journal)
    if not fecha_factura:
        raise ValueError('El journal no tiene fecha válida.')

    return {
        'journal_id': journal_id,
        'referencia_alegra': journal_id,
        'nro_factura': _nro_factura_desde_journal(journal, journal_id),
        'fecha_factura': fecha_factura.isoformat(),
        'fecha_vencimiento': (fecha_venc or fecha_factura).isoformat(),
        'id_tercero': id_tercero,
        'nombre_tercero': nombre_tercero,
        'valor': valor_total,
        'descripcion': _descripcion_desde_journal(journal, multi),
        'pago_detallado': lineas_cxp,
        'multi_tercero': multi,
        'cantidad_terceros': len(lineas_cxp),
    }
