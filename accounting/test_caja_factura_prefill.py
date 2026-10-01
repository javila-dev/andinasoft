from decimal import Decimal

from django.test import SimpleTestCase

from accounting.caja_factura_lectura import (
    _asegurar_lineas_calculadas,
    _corregir_iva_lineas,
    _corregir_punto_decimal,
    _fecha_desde_texto,
    _fecha_modelo_es_resolucion,
    _lineas_tirilla_pos,
    _nit_candidatos,
    _num,
    _total_desde_texto,
    normalize_factura_payload,
)
from accounting.caja_gasto_detalle import (
    DetalleGastoError,
    _valor_con_tolerancia_redondeo,
    cuadre_total,
    validar_cuadre,
)


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
        self.assertEqual(_nit_candidatos(data['nit']), ['9001234561', '900123456'])
        self.assertEqual(_nit_candidatos(''), [])
        self.assertEqual(data['total'], 119000.0)
        self.assertEqual(len(data['lineas']), 1)
        self.assertEqual(data['lineas'][0]['impuesto_id'], 12)
        self.assertEqual(data['lineas'][0]['base'], 100000.0)
        self.assertEqual(len(data['retenciones']), 1)
        self.assertEqual(data['retenciones'][0]['impuesto_id'], 5)

    def test_impuesto_suelto_pasa_al_subtotal_y_no_se_digita(self):
        catalogo = [
            {'id': 3, 'descripcion': 'IVA 19%'},
            {'id': 15, 'descripcion': 'ICUI 20%'},
        ]
        payload = {'lineas': [{
            'descripcion': 'Impuesto al Consumo Licores (Vino Rose)',
            'base': 0,
            'impuesto_id': None,
            'valor_impuesto': 5667,
        }, {
            'descripcion': 'Vino',
            'base': 10000,
            'impuesto_id': 15,
            'valor_impuesto': 5667,
        }]}
        _asegurar_lineas_calculadas(payload, catalogo)
        licor, vino = payload['lineas']
        self.assertEqual(licor['base'], 5667.0)
        self.assertIsNone(licor['impuesto_id'])
        self.assertEqual(licor['valor_impuesto'], 0.0)
        self.assertEqual(vino['valor_impuesto'], 2000.0)
        self.assertEqual(vino['impuesto_id'], 15)

    def test_monto_sin_id_recupera_la_tarifa(self):
        catalogo = [
            {'id': 3, 'descripcion': 'IVA 19%'},
            {'id': 12, 'descripcion': 'ICO 8%'},
            {'id': 15, 'descripcion': 'ICUI 20%'},
        ]
        payload = {'lineas': [
            {'descripcion': 'Cena', 'base': 10000, 'impuesto_id': None, 'valor_impuesto': 1900},
            {'descripcion': 'Gaseosa', 'base': 5000, 'impuesto_id': None, 'valor_impuesto': 1000},
            {'descripcion': 'Servicio', 'base': 8000, 'impuesto_id': None, 'valor_impuesto': 640},
        ]}
        _asegurar_lineas_calculadas(payload, catalogo)
        cena, gaseosa, servicio = payload['lineas']
        self.assertEqual(cena['impuesto_id'], 3)
        self.assertEqual(cena['valor_impuesto'], 1900.0)
        self.assertEqual(gaseosa['impuesto_id'], 15)
        self.assertEqual(gaseosa['valor_impuesto'], 1000.0)
        self.assertEqual(servicio['impuesto_id'], 12)
        self.assertEqual(servicio['valor_impuesto'], 640.0)

    def test_redondeo_de_un_peso_se_conserva(self):
        from decimal import Decimal
        self.assertEqual(
            _valor_con_tolerancia_redondeo(Decimal('678'), '679'),
            Decimal('679'),
        )
        self.assertEqual(
            _valor_con_tolerancia_redondeo(Decimal('1900'), '99999'),
            Decimal('1900'),
        )

    def test_total_no_usa_el_efectivo_entregado(self):
        texto = """
        SUBTOTAL 100.000
        IVA 19.000
        TOTAL 119.000
        EFECTIVO 150.000
        CAMBIO 31.000
        """
        self.assertEqual(_total_desde_texto(texto), 119000.0)
        self.assertEqual(_total_desde_texto(
            'Total a pagar: $119.000\nValor recibido en efectivo: 200.000'
        ), 119000.0)
        self.assertEqual(_total_desde_texto(
            'TOTAL\n119.000\nEFECTIVO\n200.000'
        ), 119000.0)
        self.assertIsNone(_total_desde_texto('EFECTIVO 150.000\nCAMBIO 1.000'))
        self.assertEqual(_total_desde_texto(
            'PRODUCTO 10000.00\nTOTAL COP 68000.00 EFECTIVO COP 100000.00\nCAMBIO 32000.00'
        ), 68000.0)

    def test_punto_dos_ceros_no_se_pega_como_miles(self):
        self.assertEqual(_num('2000.00'), 2000)
        self.assertEqual(_num('2.000.00'), 2000)
        self.assertEqual(_num('12000.00'), 12000)
        self.assertEqual(_num('12.000.00'), 12000)
        self.assertEqual(_num('68000.00'), 68000)
        self.assertEqual(_num('200.000'), 200000)
        self.assertEqual(_num('119.000'), 119000)
        self.assertEqual(_num('10857.15'), 10857.15)

    def test_punto_dos_ceros_es_decimal_no_doscientos_mil(self):
        texto = """
        ARROZ 2000.00
        ACEITE 12000.00
        TOTAL COP 68000.00
        """
        payload = normalize_factura_payload({
            'total': 6800000,
            'lineas': [
                {'descripcion': 'ARROZ', 'base': 200000, 'valor_impuesto': 38000},
                {'descripcion': 'ACEITE', 'base': 1200000, 'valor_impuesto': 0},
            ],
        })
        _corregir_punto_decimal(payload, texto)
        self.assertEqual(payload['total'], 68000.0)
        self.assertEqual(payload['lineas'][0]['base'], 2000.0)
        self.assertEqual(payload['lineas'][0]['valor_impuesto'], 380.0)
        self.assertEqual(payload['lineas'][1]['base'], 12000.0)
        ya_bien = normalize_factura_payload({
            'lineas': [{'descripcion': 'ARROZ', 'base': 2000, 'valor_impuesto': 380}],
        })
        _corregir_punto_decimal(ya_bien, texto)
        self.assertEqual(ya_bien['lineas'][0]['base'], 2000.0)
        self.assertEqual(ya_bien['lineas'][0]['valor_impuesto'], 380.0)
        miles = normalize_factura_payload({
            'total': 200000,
            'lineas': [{'descripcion': 'X', 'base': 200000, 'valor_impuesto': 0}],
        })
        _corregir_punto_decimal(miles, 'TOTAL 200.000\nPRODUCTO 200.000')
        self.assertEqual(miles['total'], 200000.0)
        self.assertEqual(miles['lineas'][0]['base'], 200000.0)

    def test_fecha_de_compra_no_usa_la_resolucion(self):
        texto = """
        Resolución DIAN 18764012345678 del 19/01/2022
        Fecha: 30/09/2026 14:22
        TOTAL COP 68000.00
        """
        self.assertEqual(_fecha_desde_texto(texto), '2026-09-30')
        self.assertTrue(_fecha_modelo_es_resolucion(
            'Resolución DIAN del 19/01/2022\nTOTAL 68000',
            '2022-01-19',
        ))
        self.assertFalse(_fecha_modelo_es_resolucion(texto, '2026-09-30'))

    def test_tirilla_pos_separa_iva_segun_la_letra(self):
        texto = """
        1 BOLSA ECOLOGICA DE GRANDE
        5052 2000.00 B
        1 @ 2000.00
        2 VALENTINE - CORONA DE CORAZONES
        667568863550 12000.00 B
        TOTAL COP 68000.00
        EFECTIVO COP 100000.00
        CAMBIO COP 32000.00
        SUBTOTAL COP 57142.85
        PRECIOS VISUALIZADOS:
        (B) A2 VENTAS AL 19% COP 10857.15
        (R) A1 VENTAS AL 5% COP 0.00
        (E) A3 VENTAS EXENTAS COP 0.00
        """
        catalogo = [
            {'id': 3, 'descripcion': 'IVA 19%'},
            {'id': 4, 'descripcion': 'IVA 5%'},
        ]
        lineas = _lineas_tirilla_pos(texto, catalogo)
        self.assertEqual(_total_desde_texto(texto), 68000.0)
        self.assertEqual([row['descripcion'] for row in lineas], [
            'BOLSA ECOLOGICA DE GRANDE',
            'VALENTINE - CORONA DE CORAZONES',
        ])
        self.assertEqual(lineas[0]['impuesto_id'], 3)
        self.assertEqual(lineas[0]['base'], 1681.0)
        self.assertEqual(lineas[0]['valor_impuesto'], 319.0)
        self.assertEqual(lineas[1]['base'], 10084.0)
        self.assertEqual(lineas[1]['valor_impuesto'], 1916.0)
        payload = {'lineas': lineas, 'aviso': ''}
        _corregir_iva_lineas(payload, texto, catalogo)
        self.assertEqual(payload['lineas'][0]['base'], 1681.0)
        self.assertEqual(payload['lineas'][0]['valor_impuesto'], 319.0)
        self.assertEqual(payload['lineas'][0]['impuesto_id'], 3)
        self.assertEqual(_lineas_tirilla_pos(
            'IVA 19% 19000\nTOTAL 119000\nProducto sin letra 100000',
            catalogo,
        ), [])

    def test_precio_visualizado_no_suma_el_iva_encima(self):
        catalogo = [
            {'id': 3, 'descripcion': 'IVA 19%'},
            {'id': 4, 'descripcion': 'IVA 5%'},
        ]
        payload = normalize_factura_payload({
            'total': 5000,
            'lineas': [
                {'descripcion': 'ARROZ', 'base': 5000, 'impuesto_id': 3, 'valor_impuesto': 950},
            ],
        })
        _corregir_iva_lineas(payload, """
            ARROZ 5000.00
            TOTAL COP 5000.00
            PRECIOS VISUALIZADOS
            IVA 19% COP 798.32
        """, catalogo)
        self.assertEqual(payload['lineas'][0]['impuesto_id'], 3)
        self.assertEqual(payload['lineas'][0]['base'], 4202.0)
        self.assertEqual(payload['lineas'][0]['valor_impuesto'], 798.0)

    def test_no_inventa_iva_si_hay_varias_tarifas(self):
        catalogo = [
            {'id': 3, 'descripcion': 'IVA 19%'},
            {'id': 4, 'descripcion': 'IVA 5%'},
        ]
        payload = normalize_factura_payload({
            'lineas': [
                {'descripcion': 'A', 'base': 2000, 'impuesto_id': 3, 'valor_impuesto': 380},
                {'descripcion': 'B', 'base': 3000, 'impuesto_id': 3, 'valor_impuesto': 570},
            ],
        })
        _corregir_iva_lineas(payload, """
            A 2000.00
            B 3000.00
            PRECIOS VISUALIZADOS
            IVA 19% COP 500.00
            IVA 5% COP 100.00
        """, catalogo)
        self.assertIsNone(payload['lineas'][0]['impuesto_id'])
        self.assertEqual(payload['lineas'][0]['valor_impuesto'], 0)
        self.assertIsNone(payload['lineas'][1]['impuesto_id'])
        self.assertIn('Revisa el IVA', payload['aviso'])

    def test_factura_normal_conserva_el_iva_que_cuadra(self):
        catalogo = [{'id': 3, 'descripcion': 'IVA 19%'}]
        payload = normalize_factura_payload({
            'lineas': [
                {'descripcion': 'Papel', 'base': 100000, 'impuesto_id': 3, 'valor_impuesto': 19000},
            ],
        })
        _corregir_iva_lineas(payload, """
            SUBTOTAL 100000
            IVA 19% 19000
            TOTAL 119000
        """, catalogo)
        self.assertEqual(payload['lineas'][0]['impuesto_id'], 3)
        self.assertEqual(payload['lineas'][0]['base'], 100000.0)
        self.assertEqual(payload['lineas'][0]['valor_impuesto'], 19000.0)

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
