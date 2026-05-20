"""Tests extracción CxP desde journals Alegra (payloads reales)."""
from django.test import SimpleTestCase

from accounting.journal_cxp import extraer_lineas_cxp, parsear_journal_para_radicado

# Journal 7 — arriendo, un proveedor, retención excluida
JOURNAL_7 = {
    'id': '7',
    'date': '2026-05-06',
    'observations': 'ARRIENDO MAYO CLUB TESORO',
    'reference': '',
    'total': 2500000,
    'entries': [
        {
            'type': 'category',
            'name': 'Gastos no deducibles',
            'debit': 2500000,
            'credit': 0,
            'client': {'identification': '31425903', 'name': 'LUZ ADRIANA RAMIREZ JARAMILLO',
                       'accounting': {'debtToPay': {'code': '22050501'}}},
        },
        {
            'type': 'category',
            'name': 'Retenciones arriendo 3.5% por pagar',
            'description': 'RETENCION ARRENDAMIENTO',
            'debit': 0,
            'credit': 87500,
            'client': {'identification': '31425903', 'name': 'LUZ ADRIANA RAMIREZ JARAMILLO',
                       'accounting': {'debtToPay': {'code': '23651501'}}},
        },
        {
            'type': 'category',
            'name': 'Arrendamientos',
            'debit': 0,
            'credit': 2412500,
            'client': {'identification': '31425903', 'name': 'LUZ ADRIANA RAMIREZ JARAMILLO',
                       'accounting': {'debtToPay': {'code': '22050501',
                        'categoryRule': {'key': 'DEBTS_TO_PAY_PROVIDERS'}}}},
            'associatedDocument': {
                'resourceType': 'v_bill',
                'resource': {'number': 'ARRIENDO MAYO', 'date': '2026-05-06', 'dueDate': '2026-05-06', 'total': 2412500},
            },
        },
    ],
}

# Journal 11 — comisiones, tres terceros (extracto)
def _cxp_credit(ident, name, credit):
    return {
        'type': 'category',
        'name': 'Comisiones',
        'id': '7558',
        'debit': 0,
        'credit': credit,
        'client': {
            'identification': ident,
            'name': name,
            'accounting': {'debtToPay': {'code': '22050501', 'categoryRule': {'key': 'DEBTS_TO_PAY_PROVIDERS'}}},
        },
    }


def _anticipo_debit(ident, name, debit):
    return {
        'type': 'category',
        'name': 'Anticipos comisiones a trabajadores',
        'id': '6537',
        'debit': debit,
        'credit': 0,
        'client': {
            'identification': ident,
            'name': name,
            'accounting': {'debtToPay': {'code': '22050501'}},
        },
    }


JOURNAL_11 = {
    'id': '11',
    'date': '2026-05-15',
    'observations': 'ANTICIPO DE COMISIONES',
    'total': 4517516,
    'client': None,
    'employee': {
        'identification': '901018375',
        'name': 'STATUS COMERCIALIZADORA S. A.',
    },
    'entries': [
        _anticipo_debit('1017232868', 'LAURA CRISTINA ALVAREZ BARRIEN', 801561),
        _cxp_credit('1017232868', 'LAURA CRISTINA ALVAREZ BARRIEN', 801561),
        _anticipo_debit('1037588511', 'JUAN SEBASTIAN BRICEÑO GOMEZ', 2404686),
        _cxp_credit('1037588511', 'JUAN SEBASTIAN BRICEÑO GOMEZ', 2404686),
        _anticipo_debit('8130000', 'HAROLD LEANDR TANGARIFE POSADA', 1311269),
        _cxp_credit('8130000', 'HAROLD LEANDR TANGARIFE POSADA', 1311269),
    ],
}


class JournalCxpTests(SimpleTestCase):
    def test_journal_7_una_cxp_sin_retencion(self):
        lineas = extraer_lineas_cxp(JOURNAL_7)
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0]['id_tercero'], '31425903')
        self.assertEqual(lineas[0]['valor'], 2412500)

    def test_journal_7_radicado(self):
        r = parsear_journal_para_radicado(JOURNAL_7)
        self.assertEqual(r['valor'], 2412500)
        self.assertEqual(r['nro_factura'], 'ARRIENDO MAYO')
        self.assertFalse(r['multi_tercero'])

    def test_journal_11_tres_cxp(self):
        lineas = extraer_lineas_cxp(JOURNAL_11)
        self.assertEqual(len(lineas), 3)
        total = sum(x['valor'] for x in lineas)
        self.assertEqual(total, 4517516)

    def test_journal_11_multi_radicado(self):
        r = parsear_journal_para_radicado(JOURNAL_11)
        self.assertTrue(r['multi_tercero'])
        self.assertEqual(r['cantidad_terceros'], 3)
        self.assertEqual(r['id_tercero'], '901018375')
        self.assertIn('COMISION', r['descripcion'].upper())
        self.assertEqual(len(r['pago_detallado']), 3)
