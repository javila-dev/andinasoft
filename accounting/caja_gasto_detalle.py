"""Líneas de compra y retenciones de un gasto de caja."""
from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from django.db import transaction

from accounting.models import gastos_caja_linea, gastos_caja_retencion, impuestos_legalizacion

CUADRE_TOLERANCIA = Decimal('1')


class DetalleGastoError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _decimal(raw, default=Decimal('0')):
    if raw is None or raw == '':
        return default
    if isinstance(raw, Decimal):
        return raw
    text = str(raw).replace('$', '').replace(',', '').strip()
    if not text:
        return default
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise DetalleGastoError('Hay un valor numérico inválido en las líneas.') from exc


def cuadre_total(valor_pagado, lineas, retenciones):
    """Bases + impuestos − retenciones no asumidas."""
    base = sum((_decimal(row['base']) for row in lineas), Decimal('0'))
    impuestos = sum((_decimal(row['valor_impuesto']) for row in lineas), Decimal('0'))
    rete = sum(
        (_decimal(row['valor']) for row in retenciones if not row.get('asumida')),
        Decimal('0'),
    )
    return base + impuestos - rete


def parse_detalle(lineas_raw, retenciones_raw):
    """
    Valida el JSON del formulario.
    Devuelve (lineas, retenciones) listas para guardar.
    """
    lineas = _load_json_list(lineas_raw, 'líneas')
    retenciones = _load_json_list(retenciones_raw, 'retenciones')
    if not lineas:
        raise DetalleGastoError('Agrega al menos una línea de la factura.')

    impuestos = {
        row.pk: row
        for row in impuestos_legalizacion.objects.filter(activo=True)
    }
    parsed_lineas = []
    for index, row in enumerate(lineas, start=1):
        if not isinstance(row, dict):
            raise DetalleGastoError(f'La línea {index} no tiene un formato válido.')
        base = _decimal(row.get('base'))
        valor_impuesto = _decimal(row.get('valor_impuesto'))
        if base <= 0:
            raise DetalleGastoError(f'La línea {index} debe tener una base mayor que cero.')
        if valor_impuesto < 0:
            raise DetalleGastoError(f'El impuesto de la línea {index} no puede ser negativo.')
        impuesto = _impuesto(impuestos, row.get('impuesto_id'), f'línea {index}')
        if valor_impuesto > 0 and impuesto is None:
            raise DetalleGastoError(f'La línea {index} tiene valor de impuesto pero no tiene tipo.')
        if impuesto is not None and valor_impuesto <= 0:
            raise DetalleGastoError(f'La línea {index} tiene tipo de impuesto pero el valor es cero.')
        parsed_lineas.append({
            'orden': index,
            'descripcion': str(row.get('descripcion') or '')[:255],
            'base': base,
            'impuesto': impuesto,
            'valor_impuesto': valor_impuesto,
        })

    parsed_rets = []
    vistos = set()
    for index, row in enumerate(retenciones, start=1):
        if not isinstance(row, dict):
            raise DetalleGastoError(f'La retención {index} no tiene un formato válido.')
        valor = _decimal(row.get('valor'))
        if valor <= 0:
            continue
        impuesto = _impuesto(impuestos, row.get('impuesto_id'), f'retención {index}')
        if impuesto is None:
            raise DetalleGastoError(f'La retención {index} no tiene tipo.')
        if impuesto.pk in vistos:
            raise DetalleGastoError('No repitas la misma retención en el gasto.')
        vistos.add(impuesto.pk)
        parsed_rets.append({
            'impuesto': impuesto,
            'valor': valor,
            'asumida': bool(row.get('asumida')),
        })
    return parsed_lineas, parsed_rets


def validar_cuadre(valor_pagado, lineas, retenciones):
    total = cuadre_total(valor_pagado, lineas, retenciones)
    esperado = _decimal(valor_pagado)
    if abs(total - esperado) > CUADRE_TOLERANCIA:
        raise DetalleGastoError(
            'El total de las líneas (base + impuestos − retenciones no asumidas) '
            'no coincide con el valor pagado.'
        )


@transaction.atomic
def replace_detalle(gasto, lineas, retenciones):
    gasto.lineas.all().delete()
    gasto.retenciones.all().delete()
    gastos_caja_linea.objects.bulk_create([
        gastos_caja_linea(
            gasto=gasto,
            orden=row['orden'],
            descripcion=row['descripcion'],
            base=row['base'],
            impuesto=row['impuesto'],
            valor_impuesto=row['valor_impuesto'],
        )
        for row in lineas
    ])
    if retenciones:
        gastos_caja_retencion.objects.bulk_create([
            gastos_caja_retencion(
                gasto=gasto,
                impuesto=row['impuesto'],
                valor=row['valor'],
                asumida=row['asumida'],
            )
            for row in retenciones
        ])
    sync_legacy_fields(gasto)


def sync_legacy_fields(gasto):
    """Mantiene cuenta_iva/valor_iva y la rete para listados que aún leen esas columnas."""
    lineas = list(gasto.lineas.select_related('impuesto').all())
    rets = list(gasto.retenciones.select_related('impuesto').all())
    tax_lines = [row for row in lineas if row.impuesto_id and (row.valor_impuesto or 0) > 0]
    gasto.valor_iva = float(sum((row.valor_impuesto or 0) for row in tax_lines)) if tax_lines else None
    gasto.cuenta_iva = tax_lines[0].impuesto if tax_lines else None
    gasto.valor_rte = float(sum((row.valor or 0) for row in rets)) if rets else None
    gasto.cuenta_rte = rets[0].impuesto if rets else None
    gasto.rte_asumida = bool(rets) and all(row.asumida for row in rets)
    gasto.save(update_fields=[
        'valor_iva', 'cuenta_iva', 'valor_rte', 'cuenta_rte', 'rte_asumida',
    ])


def detalle_para_api(gasto):
    lineas = []
    for row in gasto.lineas.all():
        lineas.append({
            'descripcion': row.descripcion or '',
            'base': float(row.base or 0),
            'impuesto_id': row.impuesto_id,
            'valor_impuesto': float(row.valor_impuesto or 0),
        })
    retenciones = []
    for row in gasto.retenciones.all():
        retenciones.append({
            'impuesto_id': row.impuesto_id,
            'valor': float(row.valor or 0),
            'asumida': bool(row.asumida),
        })
    return lineas, retenciones


def catalogo_impuestos_formulario():
    taxes = []
    retentions = []
    for row in impuestos_legalizacion.objects.filter(activo=True).order_by('descripcion'):
        desc = (row.descripcion or '').strip()
        low = desc.lower()
        item = {'id': row.pk, 'descripcion': desc}
        if 'rte' in low or 'rete' in low:
            retentions.append(item)
        elif 'iva' in low or 'impuesto' in low:
            taxes.append(item)
    return {'taxes': taxes, 'retentions': retentions}


def _load_json_list(raw, etiqueta):
    if raw is None or str(raw).strip() == '':
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise DetalleGastoError(f'No se pudo leer el detalle de {etiqueta}.') from exc
    if not isinstance(data, list):
        raise DetalleGastoError(f'El detalle de {etiqueta} debe ser una lista.')
    return data


def _impuesto(catalogo, raw_id, etiqueta):
    if raw_id is None or str(raw_id).strip() == '':
        return None
    try:
        pk = int(raw_id)
    except (TypeError, ValueError) as exc:
        raise DetalleGastoError(f'El impuesto de la {etiqueta} no es válido.') from exc
    impuesto = catalogo.get(pk)
    if impuesto is None:
        raise DetalleGastoError(f'El impuesto de la {etiqueta} no está activo.')
    return impuesto
