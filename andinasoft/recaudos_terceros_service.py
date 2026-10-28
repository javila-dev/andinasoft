"""
Informe contable de recaudos por tercero (auxiliar por tercero).

Reparte cada recibo entre los titulares de la adjudicación con la misma regla que
la interfaz de recibos a SIIGO (`Recaudos_general.interfaz_contabilidad`): partes
iguales por titular y crédito por concepto (capital, interés corriente, interés de
mora y saldo a favor). Lo que el recibo no tiene aplicado en `recaudos` queda en
"sin aplicar" para que el total de cada recibo siga cuadrando con su valor.
"""
import io
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from andinasoft.models import clientes
from andinasoft.shared_models import Adjudicacion, Recaudos, Recaudos_general, consecutivos, formas_pago

CONCEPTOS = ('capital', 'interescte', 'interesmora', 'saldo_favor', 'sin_aplicar')
_CENT = Decimal('0.01')


def _dec(x):
    if x is None:
        return Decimal('0')
    return x if isinstance(x, Decimal) else Decimal(str(x))


def _ceros():
    return {c: Decimal('0') for c in CONCEPTOS + ('total',)}


def repartir(valor, partes):
    """Divide `valor` en `partes` iguales a 2 decimales; el residuo va a la primera parte."""
    valor = _dec(valor)
    if partes <= 1:
        return [valor]
    cuota = (valor / partes).quantize(_CENT, rounding=ROUND_HALF_UP)
    return [valor - cuota * (partes - 1)] + [cuota] * (partes - 1)


def agrupar_por_tercero(recibos, detalle, titulares_adj, nombres, cuentas_fp, cuentas_rc=None):
    """
    recibos: objetos con numrecibo, fecha, idadjudicacion, idtercero, valor, formapago.
    detalle: {numrecibo: {'capital', 'interescte', 'interesmora', 'saldo_favor'}}.
    titulares_adj: {idadjudicacion: [idtercero, ...]} en orden titular 1..4.
    nombres: {idtercero: nombrecompleto}.
    cuentas_fp: {formapago: cuenta_contable}.
    cuentas_rc: {'capital': cuenta, 'saldo_favor': cuenta} del consecutivo RC.
    """
    cuentas_rc = cuentas_rc or {}
    terceros = {}
    debitos = {}
    totales = _ceros()

    for r in recibos:
        valor = _dec(r.valor)
        det = detalle.get(r.numrecibo, {})
        montos = {c: _dec(det.get(c)) for c in CONCEPTOS[:-1]}
        montos['sin_aplicar'] = valor - sum(montos.values())

        ids = [t for t in titulares_adj.get(r.idadjudicacion, []) if t] or [r.idtercero or '']
        partes = {c: repartir(montos[c], len(ids)) for c in CONCEPTOS}
        participacion = (Decimal('100') / len(ids)).quantize(_CENT, rounding=ROUND_HALF_UP)

        for i, nit in enumerate(ids):
            grupo = terceros.get(nit)
            if grupo is None:
                grupo = terceros[nit] = {
                    'nit': nit,
                    'nombre': (nombres.get(nit) or ('TERCERO NO REGISTRADO' if nit else 'SIN TERCERO')).upper(),
                    'movimientos': [],
                    'totales': _ceros(),
                }
            mov = {c: partes[c][i] for c in CONCEPTOS}
            mov['total'] = sum(mov.values())
            mov.update({
                'fecha': r.fecha,
                'recibo': r.numrecibo,
                'contrato': r.idadjudicacion,
                'forma_pago': r.formapago or '',
                'participacion': participacion,
            })
            grupo['movimientos'].append(mov)
            for c in CONCEPTOS + ('total',):
                grupo['totales'][c] += mov[c]
                totales[c] += mov[c]

        forma = r.formapago or ''
        deb = debitos.setdefault(forma, {
            'concepto': forma or 'SIN FORMA DE PAGO',
            'cuenta': cuentas_fp.get(forma, ''),
            'recibos': 0,
            'debito': Decimal('0'),
            'credito': Decimal('0'),
        })
        deb['recibos'] += 1
        deb['debito'] += valor

    for grupo in terceros.values():
        grupo['movimientos'].sort(key=lambda m: (m['fecha'], m['recibo']))

    creditos = [
        {'concepto': 'Capital', 'cuenta': cuentas_rc.get('capital', ''), 'credito': totales['capital']},
        {'concepto': 'Interés corriente', 'cuenta': cuentas_rc.get('capital', ''), 'credito': totales['interescte']},
        {'concepto': 'Interés de mora', 'cuenta': cuentas_rc.get('capital', ''), 'credito': totales['interesmora']},
        {'concepto': 'Saldo a favor', 'cuenta': cuentas_rc.get('saldo_favor', ''), 'credito': totales['saldo_favor']},
        {'concepto': 'Sin aplicar', 'cuenta': '', 'credito': totales['sin_aplicar']},
    ]
    resumen = sorted(debitos.values(), key=lambda d: d['concepto']) + [
        {'concepto': c['concepto'], 'cuenta': c['cuenta'], 'recibos': None,
         'debito': Decimal('0'), 'credito': c['credito']}
        for c in creditos if c['credito']
    ]
    total_debito = sum(d['debito'] for d in debitos.values())

    return {
        'terceros': sorted(terceros.values(), key=lambda g: (g['nombre'], g['nit'])),
        'totales': totales,
        'resumen': resumen,
        'total_debito': total_debito,
        'total_credito': totales['total'],
        'num_recibos': sum(d['recibos'] for d in debitos.values()),
    }


def informe_recaudos_terceros(proyecto, desde, hasta):
    """Arma el informe para un proyecto entre dos fechas (inclusive). Excluye recibos anulados (valor 0)."""
    recibos_qs = Recaudos_general.objects.using(proyecto).filter(
        fecha__range=(desde, hasta), valor__gt=0,
    ).order_by('fecha', 'numrecibo')
    recibos = list(recibos_qs)

    detalle = defaultdict(lambda: dict.fromkeys(CONCEPTOS[:-1], Decimal('0')))
    lineas = Recaudos.objects.using(proyecto).filter(
        recibo__in=recibos_qs.values('numrecibo'),
    ).values_list('recibo', 'idcta', 'capital', 'interescte', 'interesmora')
    for recibo, idcta, capital, intcte, intmora in lineas:
        d = detalle[recibo]
        if (idcta or '').startswith('SF'):
            d['saldo_favor'] += _dec(capital)
        else:
            d['capital'] += _dec(capital)
            d['interescte'] += _dec(intcte)
            d['interesmora'] += _dec(intmora)

    adjs = {r.idadjudicacion for r in recibos if r.idadjudicacion}
    titulares_adj = {
        pk: [t for t in (t1, t2, t3, t4) if t]
        for pk, t1, t2, t3, t4 in Adjudicacion.objects.using(proyecto).filter(pk__in=adjs).values_list(
            'pk', 'idtercero1', 'idtercero2', 'idtercero3', 'idtercero4',
        )
    }

    ids = {r.idtercero for r in recibos if r.idtercero}
    for lista in titulares_adj.values():
        ids.update(lista)
    nombres = dict(clientes.objects.filter(pk__in=ids).values_list('pk', 'nombrecompleto'))

    cuentas_fp = dict(formas_pago.objects.using(proyecto).values_list('descripcion', 'cuenta_contable'))
    rc = consecutivos.objects.using(proyecto).filter(documento='RC').first()
    cuentas_rc = {}
    if rc:
        cuentas_rc = {
            'capital': rc.cuenta_capital or '',
            'saldo_favor': (rc.cuenta_aux1 or '').strip() or rc.cuenta_capital or '',
        }

    return agrupar_por_tercero(recibos, detalle, titulares_adj, nombres, cuentas_fp, cuentas_rc)


_COLUMNAS = (
    ('Fecha', 12), ('Recibo', 12), ('Contrato', 12), ('Forma de pago', 24), ('% Part.', 9),
    ('Capital', 16), ('Int. corriente', 16), ('Int. mora', 16), ('Saldo a favor', 16),
    ('Sin aplicar', 16), ('Total', 18),
)
_NUM = '#,##0.00;[Red]-#,##0.00'


def excel_recaudos_terceros(informe, proyecto, desde, hasta):
    """Devuelve los bytes de un .xlsx con el auxiliar por tercero y el resumen contable."""
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = 'Recaudos por tercero'

    negrita = Font(bold=True)
    encabezado = PatternFill('solid', fgColor='1F3864')
    grupo_fill = PatternFill('solid', fgColor='D9E1F2')
    subtotal_fill = PatternFill('solid', fgColor='F2F2F2')
    linea = Side(style='thin', color='999999')

    sheet['A1'] = f'RECAUDOS POR TERCERO - {str(proyecto).upper()}'
    sheet['A1'].font = Font(bold=True, size=14)
    sheet['A2'] = f'Desde {desde:%d/%m/%Y} hasta {hasta:%d/%m/%Y}'
    sheet['A3'] = (f"{informe['num_recibos']} recibos · {len(informe['terceros'])} terceros · "
                   'Valores repartidos entre titulares como en la interfaz contable')

    row = 5
    for col, (titulo, ancho) in enumerate(_COLUMNAS, start=1):
        celda = sheet.cell(row, col, titulo)
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = encabezado
        celda.alignment = Alignment(horizontal='center')
        sheet.column_dimensions[get_column_letter(col)].width = ancho
    sheet.freeze_panes = 'A6'
    row += 1

    def _montos(fila, datos):
        for col, c in enumerate(CONCEPTOS + ('total',), start=6):
            celda = sheet.cell(fila, col, float(datos[c]))
            celda.number_format = _NUM

    for g in informe['terceros']:
        sheet.cell(row, 1, f"{g['nit']}  {g['nombre']}").font = negrita
        for col in range(1, len(_COLUMNAS) + 1):
            sheet.cell(row, col).fill = grupo_fill
        row += 1
        for m in g['movimientos']:
            sheet.cell(row, 1, m['fecha']).number_format = 'DD/MM/YYYY'
            sheet.cell(row, 2, m['recibo'])
            sheet.cell(row, 3, m['contrato'])
            sheet.cell(row, 4, m['forma_pago'])
            sheet.cell(row, 5, float(m['participacion']) / 100).number_format = '0%'
            _montos(row, m)
            row += 1
        sheet.cell(row, 1, f"Total {g['nombre']}").font = negrita
        _montos(row, g['totales'])
        for col in range(1, len(_COLUMNAS) + 1):
            sheet.cell(row, col).fill = subtotal_fill
            sheet.cell(row, col).font = negrita
            sheet.cell(row, col).border = Border(top=linea)
        row += 2

    sheet.cell(row, 1, 'TOTAL GENERAL').font = Font(bold=True, size=12)
    _montos(row, informe['totales'])
    for col in range(1, len(_COLUMNAS) + 1):
        sheet.cell(row, col).font = negrita
        sheet.cell(row, col).border = Border(top=linea, bottom=Side(style='double'))

    resumen = book.create_sheet('Resumen contable')
    for col, (titulo, ancho) in enumerate((('Concepto', 32), ('Cuenta', 16), ('Recibos', 10),
                                           ('Débito', 18), ('Crédito', 18)), start=1):
        celda = resumen.cell(1, col, titulo)
        celda.font = Font(bold=True, color='FFFFFF')
        celda.fill = encabezado
        resumen.column_dimensions[get_column_letter(col)].width = ancho
    fila = 2
    for r in informe['resumen']:
        resumen.cell(fila, 1, r['concepto'])
        resumen.cell(fila, 2, r['cuenta'])
        resumen.cell(fila, 3, r['recibos'])
        resumen.cell(fila, 4, float(r['debito'])).number_format = _NUM
        resumen.cell(fila, 5, float(r['credito'])).number_format = _NUM
        fila += 1
    resumen.cell(fila, 1, 'Sumas iguales').font = negrita
    resumen.cell(fila, 4, float(informe['total_debito'])).number_format = _NUM
    resumen.cell(fila, 5, float(informe['total_credito'])).number_format = _NUM
    for col in range(1, 6):
        resumen.cell(fila, col).font = negrita
        resumen.cell(fila, col).border = Border(top=linea)

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
