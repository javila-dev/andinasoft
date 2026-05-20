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


# Journal 28 (nómina): misma cuenta 22050501 en muchos conceptos; solo «Salarios por pagar».
def _nomina_credit(name, ident, name_client, credit):
    return {
        'type': 'category',
        'name': name,
        'debit': 0,
        'credit': credit,
        'client': {
            'identification': ident,
            'name': name_client,
            'accounting': {'debtToPay': {'code': '22050501', 'categoryRule': {'key': 'DEBTS_TO_PAY_PROVIDERS'}}},
        },
    }


# Journal 9 — pago retención DIAN; solo pasivo 23x (sin CxP 22x en créditos).
JOURNAL_9_IMPUESTOS = {
    'id': '9',
    'date': '2026-05-14',
    'observations': 'RETENCION 2-2026',
    'total': 3518000,
    'client': {
        'identification': '800197268',
        'name': 'DIRECCIÓN DE IMPUESTOS Y ADUAN',
    },
    'entries': [
        {
            'type': 'category',
            'name': 'Retencion en la fuente por pagar',
            'debit': 3377000,
            'credit': 0,
            'client': {
                'identification': '800197268',
                'name': 'DIRECCIÓN DE IMPUESTOS Y ADUAN',
                'accounting': {'debtToPay': {'code': '23450501'}},
            },
        },
        {
            'type': 'category',
            'name': 'Intereses',
            'debit': 141000,
            'credit': 0,
            'client': {
                'identification': '800197268',
                'name': 'DIRECCIÓN DE IMPUESTOS Y ADUAN',
                'accounting': {'debtToPay': {'code': '23450501'}},
            },
        },
        {
            'type': 'category',
            'name': 'Retencion en la fuente por pagar',
            'debit': 0,
            'credit': 3518000,
            'client': {
                'identification': '800197268',
                'name': 'DIRECCIÓN DE IMPUESTOS Y ADUAN',
                'accounting': {'debtToPay': {'code': '23450501'}},
            },
        },
    ],
}


JOURNAL_28_NOMINA = {
    'id': '28',
    'date': '2026-05-15',
    'observations': 'Nómina del 1 al 15 de mayo del 2026',
    'total': 22797594,
    'entries': [
        _nomina_credit('Anticipos comisiones a trabajadores', '8130000', 'HAROLD LEANDR TANGARIFE POSADA', 2452754),
        _nomina_credit('Fondos de cesantías y/o pensiones', '800037800', 'PROTECCIÓN S.A', 162513),
        _nomina_credit('Salarios por pagar', '8130000', 'HAROLD LEANDR TANGARIFE POSADA', 1285039),
        _nomina_credit('Anticipos comisiones a trabajadores', '1037588511', 'JUAN SEBASTIAN BRICEÑO GOMEZ', 4728406),
        _nomina_credit('Salarios por pagar', '1037588511', 'JUAN SEBASTIAN BRICEÑO GOMEZ', 2985313),
        _nomina_credit('Salarios por pagar', '1017232868', 'LAURA CRISTINA ALVAREZ BARRIEN', 910679),
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

    def test_journal_28_nomina_solo_salarios_por_pagar(self):
        lineas = extraer_lineas_cxp(JOURNAL_28_NOMINA)
        self.assertEqual(len(lineas), 3)
        total = sum(x['valor'] for x in lineas)
        self.assertEqual(total, 1285039 + 2985313 + 910679)
        for row in lineas:
            for ln in row['lineas']:
                self.assertIn('salario', (ln.get('name') or '').lower())

    def test_journal_28_nomina_radicado(self):
        r = parsear_journal_para_radicado(JOURNAL_28_NOMINA)
        self.assertEqual(r['valor'], 5181031)
        self.assertEqual(r['cantidad_terceros'], 3)
        self.assertNotEqual(r['valor'], JOURNAL_28_NOMINA['total'])

    def test_journal_9_impuestos_cxp_dian(self):
        lineas = extraer_lineas_cxp(JOURNAL_9_IMPUESTOS)
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0]['id_tercero'], '800197268')
        self.assertEqual(lineas[0]['valor'], 3518000)

    def test_journal_9_impuestos_radicado(self):
        r = parsear_journal_para_radicado(JOURNAL_9_IMPUESTOS)
        self.assertEqual(r['valor'], 3518000)
        self.assertEqual(r['id_tercero'], '800197268')
        self.assertIn('RETENCION', r['nro_factura'].upper())
