"""
Generacion dinamica del Excel de bonos / override de cartera.

Reemplaza la dependencia de resources/excel_formats/Bonos_cartera.xlsx
(plantilla con gestores y proyectos hardcodeados).

Logica equivalente a la hoja Override del template historico:
- Por (gestor, proyecto): suma presupuesto, rcdo pptado, rcdo no pptado sin cashout
- Cumplimiento = rcdo_pptado / presupuesto
- Total bonificable = rcdo_pptado + rcdo_no_pptado_sin_cashout
- Bono override = total_bonificable * tasa_ov (default 0.2%)

La hoja Escalas se incluye como referencia parametrizable; el Override
historico usaba tasa fija (no consultaba Escalas).
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace

import openpyxl
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter

from andinasoft.cartera_gestor_service import GESTOR_JURIDICO

ENCABEZADOS_DETALLE = [
    'Adjudicacion',
    'Cliente',
    'Estado',
    'Origen',
    'Venta Mes',
    'Tipo Cartera',
    'Edad',
    'Cuota Mes',
    'Recaudo Mes',
    'Cuotas Vencidas',
    'Recaudo Vencido',
    'Presupuesto Total',
    'Recaudo Presupuestado',
    'Recaudo No Pptado',
    'Recaudo Total',
    'Asesor',
    'Cashout',
]

# Escala historica (hoja Escalas del template). Cumplimiento minimo -> % bono.
ESCALAS_DEFAULT = (
    (Decimal('0.40'), Decimal('0.0010')),
    (Decimal('0.60'), Decimal('0.0012')),
    (Decimal('0.90'), Decimal('0.0014')),
    (Decimal('1.00'), Decimal('0.0016')),
)

TASA_OV_DEFAULT = Decimal('0.002')  # 0.2% como en Override!H
ZERO = Decimal('0')


def _dec(value) -> Decimal:
    if value is None or value == '':
        return ZERO
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return ZERO


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _pct(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)


def normalizar_gestor(asesor) -> str:
    nombre = (asesor or '').strip()
    return nombre.upper() if nombre else 'SIN GESTOR'


def es_cashout(valor) -> bool:
    """True si la fila se considera cashout (no entra al rcdo no pptado bonificable)."""
    if valor is None:
        return False
    text = str(valor).strip().lower()
    if not text or text in ('no', 'n', '0', 'false'):
        return False
    return text in ('si', 'sí', 'yes', 'y', '1', 'true', 'cashout')


def bono_por_escala(cumplimiento: Decimal, escalas=ESCALAS_DEFAULT) -> Decimal:
    """Devuelve el % de bono segun la escala (mayor umbral alcanzado)."""
    tasa = ZERO
    for minimo, bono in escalas:
        if cumplimiento >= minimo:
            tasa = bono
    return tasa


def agregar_fila_override(acc, proyecto: str, fila, *, excluir_juridico=True):
    """Acumula montos de una fila de informe en el dict (gestor, proyecto)."""
    gestor = normalizar_gestor(getattr(fila, 'asesor', None))
    if excluir_juridico and gestor == GESTOR_JURIDICO:
        return
    key = (gestor, proyecto)
    bucket = acc[key]
    bucket['presupuesto'] += _dec(getattr(fila, 'presupuesto', 0))
    bucket['rcdo_pptado'] += _dec(getattr(fila, 'recaudo_pptado', 0))
    no_ppt = _dec(getattr(fila, 'recaudo_nopptado', 0))
    cashout = getattr(fila, 'cashout', None)
    if not es_cashout(cashout):
        bucket['rcdo_nopptado_sin_cashout'] += no_ppt
    bucket['filas'] += 1


def calcular_override_row(gestor, proyecto, montos, *, tasa_ov=TASA_OV_DEFAULT, escalas=ESCALAS_DEFAULT):
    ppto = montos.get('presupuesto', ZERO)
    pptado = montos.get('rcdo_pptado', ZERO)
    noppt = montos.get('rcdo_nopptado_sin_cashout', ZERO)
    cumplimiento = (pptado / ppto) if ppto > 0 else ZERO
    total_bonificable = pptado + noppt
    bono_ov = total_bonificable * tasa_ov
    bono_escala = total_bonificable * bono_por_escala(cumplimiento, escalas)
    return SimpleNamespace(
        gestor=gestor,
        proyecto=proyecto,
        presupuesto=_money(ppto),
        rcdo_pptado=_money(pptado),
        cumplimiento=_pct(cumplimiento),
        rcdo_nopptado_sin_cashout=_money(noppt),
        total_bonificable=_money(total_bonificable),
        tasa_ov=tasa_ov,
        bono_override=_money(bono_ov),
        tasa_escala=bono_por_escala(cumplimiento, escalas),
        bono_escala=_money(bono_escala),
        filas=montos.get('filas', 0),
    )


def construir_override(por_gestor_proyecto, *, tasa_ov=TASA_OV_DEFAULT, escalas=ESCALAS_DEFAULT):
    """
    por_gestor_proyecto: dict[(gestor, proyecto)] -> montos
    Returns: lista de filas detalle + lista de totales por gestor.
    """
    filas = []
    for (gestor, proyecto) in sorted(por_gestor_proyecto.keys(), key=lambda k: (k[0], k[1])):
        filas.append(
            calcular_override_row(
                gestor,
                proyecto,
                por_gestor_proyecto[(gestor, proyecto)],
                tasa_ov=tasa_ov,
                escalas=escalas,
            )
        )
    totales = []
    by_gestor = defaultdict(lambda: {'bono_override': ZERO, 'bono_escala': ZERO, 'total_bonificable': ZERO})
    for row in filas:
        g = by_gestor[row.gestor]
        g['bono_override'] += row.bono_override
        g['bono_escala'] += row.bono_escala
        g['total_bonificable'] += row.total_bonificable
    for gestor in sorted(by_gestor.keys()):
        g = by_gestor[gestor]
        totales.append(
            SimpleNamespace(
                gestor=gestor,
                bono_override=_money(g['bono_override']),
                bono_escala=_money(g['bono_escala']),
                total_bonificable=_money(g['total_bonificable']),
            )
        )
    return filas, totales


def _style_header(ws, ncol):
    bold = Font(bold=True)
    for c in range(1, ncol + 1):
        cell = ws.cell(1, c)
        cell.font = bold
        cell.alignment = Alignment(wrap_text=True, horizontal='center')


def _autofit(ws, max_width=28):
    for col in ws.columns:
        letter = get_column_letter(col[0].column)
        length = 0
        for cell in col[:80]:
            if cell.value is None:
                continue
            length = max(length, min(len(str(cell.value)), max_width))
        ws.column_dimensions[letter].width = max(10, length + 2)


def _write_detalle_sheet(wb, proyecto: str, filas):
    title = proyecto[:31]  # limite Excel
    if title in wb.sheetnames:
        ws = wb[title]
        wb.remove(ws)
    ws = wb.create_sheet(title)
    for j, h in enumerate(ENCABEZADOS_DETALLE, start=1):
        ws.cell(1, j, h)
    _style_header(ws, len(ENCABEZADOS_DETALLE))

    for i, fila in enumerate(filas, start=2):
        ws.cell(i, 1, getattr(fila, 'pk', ''))
        ws.cell(i, 2, getattr(fila, 'cliente', '') or '')
        ws.cell(i, 3, getattr(fila, 'estado', '') or '')
        ws.cell(i, 4, getattr(fila, 'origen', '') or '')
        ws.cell(i, 5, getattr(fila, 'venta_mes', '') or '')
        ws.cell(i, 6, getattr(fila, 'tipocartera', '') or '')
        ws.cell(i, 7, getattr(fila, 'edad', '') or '')
        ws.cell(i, 8, float(_dec(getattr(fila, 'ppto_mes', 0))))
        ws.cell(i, 9, float(_dec(getattr(fila, 'recaudo_mes', 0))))
        ws.cell(i, 10, float(_dec(getattr(fila, 'ppto_vencido', 0))))
        ws.cell(i, 11, float(_dec(getattr(fila, 'recaudo_vencido', 0))))
        ws.cell(i, 12, float(_dec(getattr(fila, 'presupuesto', 0))))
        ws.cell(i, 13, float(_dec(getattr(fila, 'recaudo_pptado', 0))))
        ws.cell(i, 14, float(_dec(getattr(fila, 'recaudo_nopptado', 0))))
        ws.cell(i, 15, float(_dec(getattr(fila, 'recaudo_total', 0))))
        ws.cell(i, 16, normalizar_gestor(getattr(fila, 'asesor', None)))
        cashout = getattr(fila, 'cashout', None)
        ws.cell(i, 17, '' if cashout is None else str(cashout))
    _autofit(ws)
    return ws


def _write_escalas_sheet(wb, escalas=ESCALAS_DEFAULT):
    if 'Escalas' in wb.sheetnames:
        del wb['Escalas']
    ws = wb.create_sheet('Escalas', 0)
    ws.cell(1, 1, 'Cumplimiento (Minimo)')
    ws.cell(1, 2, 'Bono')
    _style_header(ws, 2)
    for i, (minimo, bono) in enumerate(escalas, start=2):
        ws.cell(i, 1, float(minimo))
        ws.cell(i, 2, float(bono))
        ws.cell(i, 1).number_format = '0%'
        ws.cell(i, 2).number_format = '0.00%'
    _autofit(ws)
    return ws


def _write_override_sheet(wb, filas_ov, totales, *, tasa_ov=TASA_OV_DEFAULT):
    if 'Override' in wb.sheetnames:
        del wb['Override']
    ws = wb.create_sheet('Override', 0)
    headers = [
        'Gestor',
        'Proyecto',
        'Presupuesto',
        'Rcdo Presupuestado',
        'Cumplimiento Ppto',
        'Rcdo No pptado (sin Cashout)',
        'Total Rcdo Bonificable',
        'Ov',
        'Bono Override',
        'Bono por Escala (ref)',
    ]
    for j, h in enumerate(headers, start=1):
        ws.cell(1, j, h)
    _style_header(ws, len(headers))

    row_i = 2
    for row in filas_ov:
        ws.cell(row_i, 1, row.gestor)
        ws.cell(row_i, 2, row.proyecto)
        ws.cell(row_i, 3, float(row.presupuesto))
        ws.cell(row_i, 4, float(row.rcdo_pptado))
        ws.cell(row_i, 5, float(row.cumplimiento))
        ws.cell(row_i, 6, float(row.rcdo_nopptado_sin_cashout))
        ws.cell(row_i, 7, float(row.total_bonificable))
        ws.cell(row_i, 8, float(tasa_ov))
        ws.cell(row_i, 9, float(row.bono_override))
        ws.cell(row_i, 10, float(row.bono_escala))
        for c in (3, 4, 6, 7, 9, 10):
            ws.cell(row_i, c).number_format = '#,##0.00'
        ws.cell(row_i, 5).number_format = '0.00%'
        ws.cell(row_i, 8).number_format = '0.00%'
        row_i += 1

    row_i += 1
    ws.cell(row_i, 1, 'TOTALES POR GESTOR').font = Font(bold=True)
    row_i += 1
    ws.cell(row_i, 1, 'Gestor').font = Font(bold=True)
    ws.cell(row_i, 2, 'Total Rcdo Bonificable').font = Font(bold=True)
    ws.cell(row_i, 3, 'Bono Override').font = Font(bold=True)
    ws.cell(row_i, 4, 'Bono por Escala (ref)').font = Font(bold=True)
    row_i += 1
    for tot in totales:
        ws.cell(row_i, 1, f'TOTAL {tot.gestor}')
        ws.cell(row_i, 2, float(tot.total_bonificable))
        ws.cell(row_i, 3, float(tot.bono_override))
        ws.cell(row_i, 4, float(tot.bono_escala))
        for c in (2, 3, 4):
            ws.cell(row_i, c).number_format = '#,##0.00'
            ws.cell(row_i, c).font = Font(bold=True)
        row_i += 1

    # nota
    row_i += 1
    ws.cell(row_i, 1, 'Nota: generado dinamicamente. Gestores/proyectos salen de los datos del periodo.')
    ws.cell(row_i + 1, 1, 'JURIDICO se excluye del Override. Cashout vacio se trata como No.')
    _autofit(ws)
    return ws


def generar_libro_bonos(
    datos_por_proyecto: dict,
    *,
    tasa_ov=TASA_OV_DEFAULT,
    escalas=ESCALAS_DEFAULT,
    excluir_juridico=True,
    errores=None,
):
    """
    datos_por_proyecto: {nombre_proyecto: lista de filas informe_cartera_rows}
    errores: lista opcional [(proyecto, mensaje)]
    """
    wb = openpyxl.Workbook()
    # quitar hoja default
    default = wb.active
    wb.remove(default)

    _write_escalas_sheet(wb, escalas)

    acc = defaultdict(lambda: {
        'presupuesto': ZERO,
        'rcdo_pptado': ZERO,
        'rcdo_nopptado_sin_cashout': ZERO,
        'filas': 0,
    })

    for proyecto in sorted(datos_por_proyecto.keys()):
        filas = datos_por_proyecto[proyecto] or []
        _write_detalle_sheet(wb, proyecto, filas)
        for fila in filas:
            agregar_fila_override(acc, proyecto, fila, excluir_juridico=excluir_juridico)

    filas_ov, totales = construir_override(acc, tasa_ov=tasa_ov, escalas=escalas)
    _write_override_sheet(wb, filas_ov, totales, tasa_ov=tasa_ov)

    if errores:
        if 'Errores' in wb.sheetnames:
            del wb['Errores']
        err_ws = wb.create_sheet('Errores')
        err_ws.append(['Proyecto', 'Error'])
        _style_header(err_ws, 2)
        for proyecto, msg in errores:
            err_ws.append([proyecto, (msg or '')[:500]])
        _autofit(err_ws)

    return wb
