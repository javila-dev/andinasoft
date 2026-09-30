from decimal import Decimal

from django.test import SimpleTestCase

from accounting.caja_factura_lectura import normalize_factura_payload
from accounting.caja_gasto_detalle import DetalleGastoError, cuadre_total, validar_cuadre


class FacturaPrefillTests(SimpleTestCase):
    def test_respuesta_incompleta_no_arma_lineas(self):
        data = normalize_factura_payload({'fecha': '2026-05-02'})
        self.assertEqual(data['lineas'], [])
        self.assertEqual(data['retenciones'], [])
        self.assertEqual(data['fecha'], '2026-05-02')
        self.assertTrue(data['aviso'])
        self.assertNotIn('guardar', data['aviso'].lower())

    def test_normaliza_lineas_y_retenciones(self):
        data = normalize_factura_payload({
            'fecha': '02/05/2026',
            'nit': '900.123.456-1',
            'total': '119.000',
            'lineas': [
                {'descripcion': 'Papel', 'base': '100000', 'impuesto_id': '12', 'valor_impuesto': 19000},
                'basura',
            ],
            'retenciones': [
                {'impuesto_id': 5, 'valor': 2500, 'asumida': False},
                {'impuesto_id': None, 'valor': 0},
            ],
        })
        self.assertEqual(data['fecha'], '2026-05-02')
        self.assertEqual(data['nit'], '9001234561')
        self.assertEqual(data['total'], 119000.0)
        self.assertEqual(len(data['lineas']), 1)
        self.assertEqual(data['lineas'][0]['impuesto_id'], 12)
        self.assertEqual(data['lineas'][0]['base'], 100000.0)
        self.assertEqual(len(data['retenciones']), 1)
        self.assertEqual(data['retenciones'][0]['impuesto_id'], 5)

    def test_cuadre_resta_solo_retencion_no_asumida(self):
        lineas = [{'base': Decimal('100000'), 'valor_impuesto': Decimal('19000')}]
        rets = [
            {'valor': Decimal('2500'), 'asumida': False},
            {'valor': Decimal('800'), 'asumida': True},
        ]
        self.assertEqual(cuadre_total(116500, lineas, rets), Decimal('116500'))
        validar_cuadre(116500, lineas, rets)
        with self.assertRaises(DetalleGastoError):
            validar_cuadre(119000, lineas, rets)
