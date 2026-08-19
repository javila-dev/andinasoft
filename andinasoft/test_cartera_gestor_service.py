"""
Tests unitarios del servicio de dashboard gestores.

Solo mocks / helpers puros — no requieren BD de proyecto.
"""
import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from andinasoft.cartera_gestor_service import (
    BUCKET_LABELS,
    CARTA_EMAIL,
    CARTA_TELEFONO,
    DEFAULT_CHECKPOINTS,
    STUB_PLANTILLA,
    bucket_codigo_from_dias,
    contacto_carta_proyecto,
    dias_en_letras,
    evaluar_cumplimiento_compromiso,
    fecha_en_letras,
    filter_snapshot_for_gestor,
    firma_proyecto_carta,
    gestor_nombre_from_user,
    id_cuota_label,
    kpis_from_rows,
    logo_carta_static,
    registrar_carta_cobro_en_documentos_adj,
    nombres_titulares_carta,
    nro_contrato_from_adj,
    plantilla_html_por_codigo,
    visual_nodes_cartas,
    codigo_nodo_linea,
    montos_linea_cobro,
    agrupar_pagos_por_fecha,
    comportamiento_timeline_from_parts,
    color_umbral_mora,
    episodios_mora,
    fecha_pago_cuota,
    merge_intervalos,
    rango_comportamiento,
    _clasificar_recaudos_adj,
    _parse_fecha_compromiso,
)
from andinasoft.models import CarteraCheckpoint


class BucketHelpersTests(SimpleTestCase):
    def test_bucket_codigo(self):
        self.assertEqual(bucket_codigo_from_dias(0), 'por_vencer')
        self.assertEqual(bucket_codigo_from_dias(-1), 'por_vencer')
        self.assertEqual(bucket_codigo_from_dias(1), 'lt30')
        self.assertEqual(bucket_codigo_from_dias(30), 'lt30')
        self.assertEqual(bucket_codigo_from_dias(31), 'lt60')
        self.assertEqual(bucket_codigo_from_dias(121), 'gt120')

    def test_parse_fecha(self):
        self.assertEqual(_parse_fecha_compromiso('2026-08-10'), datetime.date(2026, 8, 10))
        self.assertEqual(_parse_fecha_compromiso('10/08/2026'), datetime.date(2026, 8, 10))
        self.assertEqual(_parse_fecha_compromiso(datetime.date(2026, 1, 2)), datetime.date(2026, 1, 2))
        self.assertIsNone(_parse_fecha_compromiso(''))
        self.assertIsNone(_parse_fecha_compromiso(None))

    def test_gestor_nombre(self):
        user = SimpleNamespace(first_name='Ana', last_name='Perez')
        self.assertEqual(gestor_nombre_from_user(user), 'ANA PEREZ')

    def test_filter_snapshot(self):
        user = SimpleNamespace(
            first_name='Ana',
            last_name='Perez',
            is_superuser=False,
            has_perm=lambda p: False,
            groups=MagicMock(filter=MagicMock(return_value=MagicMock(exists=MagicMock(return_value=False)))),
        )
        rows = [
            {'adj': 'A1', 'gestor': 'ANA PEREZ'},
            {'adj': 'A2', 'gestor': 'OTRO'},
            {'adj': 'A3', 'gestor': 'ANA PEREZ LOPEZ'},
        ]
        filtered = filter_snapshot_for_gestor(rows, user)
        self.assertEqual([r['adj'] for r in filtered], ['A1', 'A3'])

    def test_kpis(self):
        rows = [
            {
                'dias_mora': 45,
                'por_vencer': 0,
                'lt30': 0,
                'lt60': 1000,
                'lt90': 0,
                'lt120': 0,
                'gt120': 0,
                'total_pendiente': 1000,
            },
            {
                'dias_mora': 0,
                'por_vencer': 500,
                'lt30': 0,
                'lt60': 0,
                'lt90': 0,
                'lt120': 0,
                'gt120': 0,
                'total_pendiente': 500,
            },
        ]
        kpis = kpis_from_rows(rows, {'count_hoy': 2, 'vencidos': [1]})
        self.assertEqual(kpis['clientes'], 2)
        self.assertEqual(kpis['compromisos_hoy'], 2)
        self.assertEqual(kpis['compromisos_vencidos'], 1)
        self.assertEqual(kpis['total_mora'], Decimal(1000))
        self.assertEqual(kpis['distribucion_count']['lt60'], 1)
        self.assertEqual(kpis['distribucion_count']['por_vencer'], 1)
        self.assertIn('lt30', BUCKET_LABELS)

    def test_clasificar_recaudos_adj(self):
        # Paga vencido + cuota mes exacta
        ppto = {
            'A1': {'presupuesto': Decimal(1500), 'ppto_mes': Decimal(500), 'ppto_vencido': Decimal(1000)},
        }
        rec = {'A1': Decimal(1500)}
        out = _clasificar_recaudos_adj(rec, ppto)
        self.assertEqual(out['recaudo_total'], Decimal(1500))
        self.assertEqual(out['recaudo_vencido'], Decimal(1000))
        self.assertEqual(out['recaudo_cuota_mes'], Decimal(500))
        self.assertEqual(out['recaudo_nopptado'], Decimal(0))

        # Paga de más → no esperado
        rec2 = {'A1': Decimal(2000)}
        out2 = _clasificar_recaudos_adj(rec2, ppto)
        self.assertEqual(out2['recaudo_vencido'], Decimal(1000))
        self.assertEqual(out2['recaudo_cuota_mes'], Decimal(500))
        self.assertEqual(out2['recaudo_nopptado'], Decimal(500))

    def test_evaluar_cumplimiento_compromiso(self):
        today = datetime.date(2026, 8, 10)
        cache = {'ADJ1': [(datetime.date(2026, 8, 5), Decimal(500000))]}
        ok = evaluar_cumplimiento_compromiso(
            'X', 'ADJ1', datetime.date(2026, 8, 1), 400000,
            today=today, recaudos_cache=cache,
        )
        self.assertEqual(ok['estado'], 'cumplido')
        faltante = evaluar_cumplimiento_compromiso(
            'X', 'ADJ1', datetime.date(2026, 8, 1), 900000,
            today=today, recaudos_cache=cache,
        )
        self.assertEqual(faltante['estado'], 'vencido')
        self.assertEqual(faltante['faltante'], Decimal(400000))
        hoy = evaluar_cumplimiento_compromiso(
            'X', 'ADJ1', today, 100000,
            today=today, recaudos_cache={},
        )
        self.assertEqual(hoy['estado'], 'hoy')


class CartaCobroHelpersTests(SimpleTestCase):
    def test_fecha_en_letras(self):
        self.assertEqual(fecha_en_letras(datetime.date(2026, 8, 18)), '18 de agosto del 2026')
        self.assertEqual(fecha_en_letras(None), '')

    def test_id_cuota_label(self):
        self.assertEqual(id_cuota_label('CI', 2), 'CI2')
        self.assertEqual(id_cuota_label('fn', '12'), 'FN12')
        self.assertEqual(id_cuota_label('CI', None), 'CI')

    def test_plantilla_lt30(self):
        self.assertEqual(plantilla_html_por_codigo('d30'), 'pdf/cartas_cobro/lt30.html')
        self.assertEqual(plantilla_html_por_codigo('d45'), 'pdf/cartas_cobro/lt60.html')
        self.assertEqual(plantilla_html_por_codigo('d60'), 'pdf/cartas_cobro/lt90.html')
        self.assertEqual(plantilla_html_por_codigo('d90'), 'pdf/cartas_cobro/d90.html')
        self.assertEqual(plantilla_html_por_codigo('lt30'), STUB_PLANTILLA)

    def test_dias_en_letras(self):
        self.assertEqual(dias_en_letras(45), 'cuarenta y cinco')
        self.assertEqual(dias_en_letras(60), 'sesenta')
        self.assertEqual(dias_en_letras(30), 'treinta')
        self.assertEqual(dias_en_letras(1), 'un')
        self.assertEqual(dias_en_letras(121), 'ciento veintiun')

    def test_nro_contrato_from_adj(self):
        self.assertEqual(nro_contrato_from_adj(SimpleNamespace(contrato='19'), 'adj10'), '19')
        self.assertEqual(nro_contrato_from_adj(SimpleNamespace(contrato='  19  '), 'adj10'), '19')
        self.assertEqual(nro_contrato_from_adj(SimpleNamespace(contrato=''), 'adj10'), 'adj10')
        self.assertEqual(nro_contrato_from_adj(SimpleNamespace(contrato=None), 'adj10'), 'adj10')

    def test_firma_proyecto(self):
        self.assertEqual(firma_proyecto_carta('Oasis'), 'OASIS DEL CARIBE')
        self.assertEqual(firma_proyecto_carta('Sotavento'), 'SOTAVENTO')

    def test_logo_casas_de_verano(self):
        self.assertEqual(logo_carta_static('Casas de Verano'), 'img/casas-de-verano450x.png')
        self.assertEqual(logo_carta_static('Oasis'), 'img/logo_oasis.png')

    def test_nombres_titulares_carta(self):
        names = nombres_titulares_carta({
            'titular': {'nombre': 'Ana Perez'},
            'otros_titulares': [
                {'nombre': 'Luis Perez'},
                {'nombre': ' ana  perez '},
                {'nombre': ''},
            ],
        })
        self.assertEqual(names, ['Ana Perez', 'Luis Perez'])
        self.assertEqual(
            nombres_titulares_carta({}, {'cliente': 'Cliente fila'}),
            ['Cliente fila'],
        )

    def test_contacto_carta_fallback(self):
        oasis = contacto_carta_proyecto('Oasis', lookup=False)
        self.assertEqual(oasis['firma_nombre'], 'OASIS DEL CARIBE')
        self.assertEqual(oasis['telefono'], CARTA_TELEFONO)
        self.assertEqual(oasis['email'], CARTA_EMAIL)
        sota = contacto_carta_proyecto('Sotavento', lookup=False)
        self.assertEqual(sota['firma_nombre'], 'SOTAVENTO')

    def test_contacto_carta_config(self):
        cfg = SimpleNamespace(
            firma_nombre='PROYECTO X',
            telefono='300 1112233',
            email='cartera@proyecto.co',
        )
        c = contacto_carta_proyecto('Sotavento', config=cfg, lookup=False)
        self.assertEqual(c['firma_nombre'], 'PROYECTO X')
        self.assertEqual(c['telefono'], '300 1112233')
        self.assertEqual(c['email'], 'cartera@proyecto.co')

    def test_contacto_carta_config_firma_vacia_usa_fallback(self):
        cfg = SimpleNamespace(firma_nombre='  ', telefono='300 000', email='')
        c = contacto_carta_proyecto('Oasis', config=cfg, lookup=False)
        self.assertEqual(c['firma_nombre'], 'OASIS DEL CARIBE')
        self.assertEqual(c['telefono'], '300 000')
        self.assertEqual(c['email'], '')

    def test_checkpoints_cartas(self):
        umbrales = [(c[0], c[2]) for c in DEFAULT_CHECKPOINTS]
        self.assertEqual(umbrales, [
            ('d30', 30),
            ('d45', 45),
            ('d60', 60),
            ('d90', 90),
        ])
        ck = CarteraCheckpoint(dias_desde=30)
        self.assertFalse(ck.alcanzado(29))
        self.assertTrue(ck.alcanzado(30))
        self.assertTrue(ck.alcanzado(45))

    def test_visual_nodes_cartas(self):
        labels = ['Por vencer', '<30 días', '30 días', '45 días', '60 días', '90 días+']
        nodes = visual_nodes_cartas(0)
        self.assertEqual([n['label'] for n in nodes], labels)
        self.assertTrue(nodes[0]['activo'])
        self.assertFalse(any(n['activo'] or n['superado'] for n in nodes[1:]))

        nodes = visual_nodes_cartas(10)
        by = {n['codigo']: n for n in nodes}
        self.assertTrue(by['por_vencer']['superado'])
        self.assertTrue(by['lt30']['activo'])
        self.assertFalse(by['d30']['activo'] or by['d30']['superado'])

        montos = {
            'por_vencer': Decimal('500000'),
            'lt30': Decimal('200000'),
            'd30': Decimal('100000'),
            'd45': Decimal('300000'),
            'd60': Decimal('800000'),
            'd90': Decimal('0'),
        }
        nodes = visual_nodes_cartas(50, montos)
        by = {n['codigo']: n for n in nodes}
        self.assertTrue(by['d30']['superado'])
        self.assertTrue(by['d45']['activo'])
        self.assertEqual(by['d45']['monto'], Decimal('300000'))
        self.assertEqual(by['d60']['monto'], Decimal('800000'))
        self.assertFalse(by['d60']['activo'] or by['d60']['superado'])

        nodes = visual_nodes_cartas(90, {'d90': Decimal('500')})
        by = {n['codigo']: n for n in nodes}
        self.assertTrue(by['d60']['superado'])
        self.assertTrue(by['d90']['activo'])
        self.assertEqual(by['d90']['monto'], Decimal('500'))

    def test_montos_linea_por_cuota(self):
        self.assertEqual(codigo_nodo_linea(10), 'lt30')
        self.assertEqual(codigo_nodo_linea(0), 'por_vencer')
        self.assertEqual(codigo_nodo_linea(30), 'd30')
        self.assertEqual(codigo_nodo_linea(60), 'd60')
        montos = montos_linea_cobro(
            [
                {'diasmora': 10, 'total': Decimal('100')},
                {'diasmora': 32, 'total': Decimal('200')},
                {'diasmora': 60, 'total': Decimal('300')},
            ],
            [{'saldocuota': Decimal('50')}],
        )
        self.assertEqual(montos['por_vencer'], Decimal('50'))
        self.assertEqual(montos['lt30'], Decimal('100'))
        self.assertEqual(montos['d30'], Decimal('200'))
        self.assertEqual(montos['d60'], Decimal('300'))
        self.assertEqual(montos['d45'], Decimal('0'))


class ComportamientoTimelineTests(SimpleTestCase):
    def test_fecha_pago_cuota(self):
        self.assertIsNone(fecha_pago_cuota(100, []))
        self.assertEqual(
            fecha_pago_cuota(100, [
                (datetime.date(2026, 1, 10), 40),
                (datetime.date(2026, 2, 5), 60),
            ]),
            datetime.date(2026, 2, 5),
        )
        self.assertIsNone(fecha_pago_cuota(100, [(datetime.date(2026, 1, 10), 40)]))
        self.assertIsNone(fecha_pago_cuota(
            100,
            [(datetime.date(2026, 1, 10), 100, 0)],
            interes_due=20,
        ))
        self.assertEqual(
            fecha_pago_cuota(
                100,
                [(datetime.date(2026, 1, 10), 100, 20)],
                interes_due=20,
            ),
            datetime.date(2026, 1, 10),
        )

    def test_merge_intervalos(self):
        merged = merge_intervalos([
            (datetime.date(2026, 1, 1), datetime.date(2026, 1, 20)),
            (datetime.date(2026, 1, 21), datetime.date(2026, 2, 10)),
            (datetime.date(2026, 3, 1), datetime.date(2026, 3, 5)),
        ])
        self.assertEqual(merged, [
            (datetime.date(2026, 1, 1), datetime.date(2026, 2, 10)),
            (datetime.date(2026, 3, 1), datetime.date(2026, 3, 5)),
        ])

    def test_episodios_mora_omite_pago_a_tiempo(self):
        today = datetime.date(2026, 8, 18)
        eps = episodios_mora([
            {
                'fecha': datetime.date(2026, 6, 1),
                'capital': 100,
                'pagos': [(datetime.date(2026, 5, 28), 100)],
            },
            {
                'fecha': datetime.date(2026, 7, 1),
                'capital': 80,
                'pagos': [],
            },
        ], today=today)
        self.assertEqual(eps, [{
            'inicio': datetime.date(2026, 7, 1),
            'fin': today,
            'origen': datetime.date(2026, 7, 1),
            'abierto': True,
        }])

    def test_episodios_mora_cierra_cuando_paga(self):
        today = datetime.date(2026, 8, 18)
        eps = episodios_mora([
            {
                'fecha': datetime.date(2026, 6, 1),
                'capital': 100,
                'pagos': [(datetime.date(2026, 6, 20), 100)],
            },
        ], today=today)
        self.assertEqual(eps, [{
            'inicio': datetime.date(2026, 6, 1),
            'fin': datetime.date(2026, 6, 20),
            'origen': datetime.date(2026, 6, 1),
            'abierto': False,
        }])

    def test_episodios_mora_no_infla_edad_con_cuota_ya_pagada(self):
        """Pagar la cuota vieja recorta la edad actual a la impaga mas antigua."""
        today = datetime.date(2026, 8, 18)
        eps = episodios_mora([
            {
                'fecha': datetime.date(2026, 2, 19),
                'capital': 100,
                'pagos': [(datetime.date(2026, 6, 25), 100)],
            },
            {
                'fecha': datetime.date(2026, 6, 18),
                'capital': 80,
                'pagos': [],
            },
        ], today=today)
        self.assertEqual(eps, [
            {
                'inicio': datetime.date(2026, 2, 19),
                'fin': datetime.date(2026, 6, 24),
                'origen': datetime.date(2026, 2, 19),
                'abierto': True,
            },
            {
                'inicio': datetime.date(2026, 6, 25),
                'fin': today,
                'origen': datetime.date(2026, 6, 18),
                'abierto': True,
            },
        ])
        self.assertLess((eps[1]['fin'] - eps[1]['origen']).days, 90)

    def test_episodios_mora_varias_impagas_un_episodio(self):
        today = datetime.date(2026, 8, 18)
        eps = episodios_mora([
            {'fecha': datetime.date(2026, 2, 19), 'capital': 100, 'pagos': []},
            {'fecha': datetime.date(2026, 6, 18), 'capital': 80, 'pagos': []},
        ], today=today)
        self.assertEqual(eps, [{
            'inicio': datetime.date(2026, 2, 19),
            'fin': today,
            'origen': datetime.date(2026, 2, 19),
            'abierto': True,
        }])

    def test_comportamiento_banda_actual_sigue_cuota_impaga(self):
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[
                {
                    'fecha': datetime.date(2026, 2, 19),
                    'capital': 100,
                    'pagos': [(datetime.date(2026, 6, 25), 100)],
                },
                {
                    'fecha': datetime.date(2026, 6, 18),
                    'capital': 80,
                    'pagos': [],
                },
            ],
            today=today,
        )
        actuales = [b for b in data['bandas'] if b['fin'] == today.isoformat()]
        self.assertTrue(actuales)
        self.assertTrue(any(b['dias'] >= 45 for b in data['bandas']))
        self.assertFalse(any(e['tipo'] == 'mora_salida' for e in data['eventos']))
        entras = [e for e in data['eventos'] if e['tipo'] == 'mora']
        self.assertEqual(len(entras), 1)
        self.assertEqual(entras[0]['fecha'], '2026-03-06')
        ordered = sorted(data['bandas'], key=lambda b: b['inicio'])
        for prev, cur in zip(ordered, ordered[1:]):
            self.assertLess(
                prev['fin'], cur['inicio'],
                f"solape {prev['label']} {prev['inicio']}-{prev['fin']} vs {cur['inicio']}-{cur['fin']}",
            )

    def test_mora_sigue_si_solo_pago_capital(self):
        today = datetime.date(2026, 8, 18)
        eps = episodios_mora([
            {
                'fecha': datetime.date(2026, 6, 1),
                'capital': 100,
                'intcte': 20,
                'pagos': [(datetime.date(2026, 6, 10), 100, 0)],
            },
        ], today=today)
        self.assertEqual(len(eps), 1)
        self.assertTrue(eps[0]['abierto'])
        self.assertEqual(eps[0]['inicio'], datetime.date(2026, 6, 1))

    def test_timeline_adj_en_carril_inferior(self):
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[],
            today=today,
            tl_rows=[
                (datetime.date(2026, 3, 1), 'Registro otrosi de reestructuracion', 'ANA'),
            ],
        )
        adj_ev = next(e for e in data['eventos'] if e['tipo'] == 'adj')
        self.assertEqual(adj_ev['fecha'], '2026-03-01')
        self.assertIn('reestructuracion', adj_ev['label'].lower())
        self.assertEqual(adj_ev['detalle'], 'ANA')

    def test_rango_default_acorta_si_hay_poca_historia(self):
        today = datetime.date(2026, 8, 18)
        desde, hasta = rango_comportamiento(
            [datetime.date(2026, 7, 1), datetime.date(2026, 8, 10)],
            today=today,
        )
        self.assertEqual(desde, datetime.date(2026, 7, 1))
        self.assertEqual(hasta, today)

    def test_rango_ventana_12_meses(self):
        today = datetime.date(2026, 8, 18)
        desde, hasta = rango_comportamiento(
            [datetime.date(2024, 1, 1), datetime.date(2026, 8, 1)],
            today=today,
        )
        self.assertEqual(desde, datetime.date(2025, 8, 18))
        self.assertEqual(hasta, today)

    def test_agrupar_pagos_por_fecha(self):
        grouped = agrupar_pagos_por_fecha([
            (datetime.date(2026, 8, 1), 100, 'R1'),
            (datetime.date(2026, 8, 1), 50, 'R2'),
            (datetime.date(2026, 8, 3), 20, 'R3'),
        ])
        self.assertEqual(len(grouped), 2)
        self.assertEqual(grouped[0]['valor'], Decimal('150'))
        self.assertEqual(grouped[0]['count'], 2)

    def test_timeline_from_parts(self):
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[(datetime.date(2026, 8, 10), 500000, 'R99')],
            envios=[{
                'fecha_envio': datetime.date(2026, 8, 5),
                'checkpoint_label': '30 dias',
                'canal_label': 'WhatsApp',
            }],
            cuotas=[{
                'fecha': datetime.date(2026, 6, 1),
                'capital': 100,
                'pagos': [],
            }],
            today=today,
        )
        tipos = {e['tipo'] for e in data['eventos']}
        self.assertIn('pago', tipos)
        self.assertIn('carta', tipos)
        self.assertIn('mora', tipos)
        self.assertIn('umbral', tipos)
        self.assertEqual(data['bandas'][0]['inicio'], '2026-06-16')
        self.assertEqual(data['bandas'][0]['dias'], 15)
        self.assertEqual(data['bandas'][0]['color'], color_umbral_mora(15))
        umbrales = [e['dias'] for e in data['eventos'] if e['tipo'] == 'umbral']
        self.assertEqual(umbrales, [30, 45, 60])
        u30 = next(e for e in data['eventos'] if e.get('dias') == 30)
        self.assertEqual(u30['color'], color_umbral_mora(30))
        carta = next(e for e in data['eventos'] if e['tipo'] == 'carta')
        self.assertIn('WhatsApp', carta['detalle'])
        pago = next(e for e in data['eventos'] if e['tipo'] == 'pago')
        self.assertEqual(pago['valor'], 500000)

    def test_pago_en_gracia_no_pinta_salida_de_mora(self):
        """0-15 días es gracia: ni barra ni 'Salió de mora' (el rango empieza en 15)."""
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[{
                'fecha': datetime.date(2026, 1, 12),
                'capital': 100,
                'pagos': [(datetime.date(2026, 1, 27), 100)],
            }],
            today=today,
        )
        tipos = {e['tipo'] for e in data['eventos']}
        self.assertNotIn('mora', tipos)
        self.assertNotIn('mora_salida', tipos)
        self.assertNotIn('edad', tipos)
        self.assertFalse(data['bandas'])

        data12 = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[{
                'fecha': datetime.date(2026, 1, 15),
                'capital': 100,
                'pagos': [(datetime.date(2026, 1, 27), 100)],
            }],
            today=today,
        )
        tipos12 = {e['tipo'] for e in data12['eventos']}
        self.assertNotIn('mora_salida', tipos12)
        self.assertFalse(data12['bandas'])

    def test_tramo_corto_sigue_siendo_banda(self):
        """El % mínimo de barra lo decide el gráfico según el rango visible, no los días."""
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[{
                'fecha': datetime.date(2026, 6, 1),
                'capital': 100,
                'pagos': [(datetime.date(2026, 6, 20), 100)],
            }],
            today=today,
        )
        self.assertEqual(len(data['bandas']), 1)
        self.assertEqual(data['bandas'][0]['dias'], 15)
        self.assertEqual(data['bandas'][0]['inicio'], '2026-06-16')
        self.assertEqual(data['bandas'][0]['fin'], '2026-06-20')
        self.assertFalse(any(e['tipo'] == 'edad' for e in data['eventos']))

    def test_bandas_empalman_sin_hueco(self):
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[{
                'fecha': datetime.date(2026, 6, 1),
                'capital': 100,
                'pagos': [],
            }],
            today=today,
        )
        bandas = data['bandas']
        self.assertGreaterEqual(len(bandas), 2)
        for prev, cur in zip(bandas, bandas[1:]):
            self.assertLess(prev['fin'], cur['inicio'])
            self.assertTrue(prev['join_der'])
            self.assertTrue(cur['join_izq'])

    def test_colores_fijos_por_umbral(self):
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[
                {
                    'fecha': datetime.date(2026, 1, 1),
                    'capital': 50,
                    'pagos': [(datetime.date(2026, 2, 15), 50)],
                },
                {
                    'fecha': datetime.date(2026, 6, 1),
                    'capital': 80,
                    'pagos': [],
                },
            ],
            today=today,
        )
        u30 = [e for e in data['eventos'] if e.get('dias') == 30]
        self.assertGreaterEqual(len(u30), 2)
        self.assertTrue(all(e['color'] == color_umbral_mora(30) for e in u30))
        u45 = [e for e in data['eventos'] if e.get('dias') == 45]
        self.assertTrue(all(e['color'] == color_umbral_mora(45) for e in u45))
        self.assertNotEqual(color_umbral_mora(30), color_umbral_mora(45))
        tipos = {e['tipo'] for e in data['eventos']}
        self.assertIn('mora_salida', tipos)
        salida = next(e for e in data['eventos'] if e['tipo'] == 'mora_salida')
        self.assertEqual(salida['fecha'], '2026-02-15')
        bandas_30 = [b for b in data['bandas'] if b['dias'] == 30]
        self.assertTrue(bandas_30)
        self.assertTrue(all(b['color'] == color_umbral_mora(30) for b in bandas_30))

    def test_seguimientos_y_acuerdos(self):
        today = datetime.date(2026, 8, 18)
        data = comportamiento_timeline_from_parts(
            pagos_rows=[],
            envios=[],
            cuotas=[],
            today=today,
            segs=[
                {
                    'fecha': datetime.date(2026, 8, 2),
                    'tipo_seguimiento': 'Cobro',
                    'forma_contacto': 'Whatsapp',
                    'respuesta_cliente': 'Promete pagar',
                    'valor_compromiso': 800000,
                    'fecha_compromiso': '2026-08-10',
                    'usuario': 'ANA',
                },
                {
                    'fecha': datetime.date(2026, 8, 4),
                    'tipo_seguimiento': 'Llamada',
                    'forma_contacto': 'Telefono',
                    'respuesta_cliente': 'No contesta',
                    'valor_compromiso': 0,
                    'fecha_compromiso': '',
                    'usuario': 'ANA',
                },
            ],
        )
        tipos = [e['tipo'] for e in data['eventos']]
        self.assertIn('seguimiento', tipos)
        self.assertIn('acuerdo', tipos)
        acuerdo = next(e for e in data['eventos'] if e['tipo'] == 'acuerdo')
        self.assertEqual(acuerdo['fecha'], '2026-08-10')
        self.assertEqual(acuerdo['valor'], 800000)


class RegistrarCartaDocumentosAdjTests(SimpleTestCase):
    def test_registra_pdf_en_documentos_contratos(self):
        checkpoint = SimpleNamespace(label='30 dias', codigo='d30')
        envio = SimpleNamespace(
            id=42,
            fecha_envio=datetime.date(2026, 8, 19),
            soporte=MagicMock(name='soporte.pdf'),
        )
        envio.soporte.name = 'cartera/cartas_soporte/2026/08/soporte.pdf'
        envio.soporte.open.return_value.__enter__.return_value = b'%PDF'

        docs_qs = MagicMock()
        with patch('andinasoft.cartera_gestor_service.upload_docs_contratos') as upload_pdf, \
             patch('andinasoft.cartera_gestor_service.upload_docs') as upload_other, \
             patch('andinasoft.cartera_gestor_service.documentos_contratos') as docs_model:
            docs_model.objects.using.return_value = docs_qs
            descrip = registrar_carta_cobro_en_documentos_adj(
                'PROY1', 'ADJ-1', 'gestor1', envio, checkpoint,
            )

        upload_pdf.assert_called_once()
        upload_other.assert_not_called()
        docs_qs.create.assert_called_once()
        self.assertEqual(descrip, 'Carta de Cobro_30_dias_2026-08-19_42')
        self.assertEqual(docs_qs.create.call_args.kwargs['descripcion_doc'], descrip)

    def test_registra_imagen_con_extension_en_descripcion(self):
        checkpoint = SimpleNamespace(label='45 dias', codigo='d45')
        envio = SimpleNamespace(
            id=7,
            fecha_envio=datetime.date(2026, 8, 19),
            soporte=MagicMock(name='captura.jpg'),
        )
        envio.soporte.name = 'cartera/cartas_soporte/2026/08/captura.jpg'
        envio.soporte.open.return_value.__enter__.return_value = b'JPEG'

        docs_qs = MagicMock()
        with patch('andinasoft.cartera_gestor_service.upload_docs_contratos') as upload_pdf, \
             patch('andinasoft.cartera_gestor_service.upload_docs') as upload_other, \
             patch('andinasoft.cartera_gestor_service.documentos_contratos') as docs_model:
            docs_model.objects.using.return_value = docs_qs
            descrip = registrar_carta_cobro_en_documentos_adj(
                'PROY1', 'ADJ-1', 'gestor1', envio, checkpoint,
            )

        upload_other.assert_called_once()
        upload_pdf.assert_not_called()
        self.assertEqual(descrip, 'Carta de Cobro_45_dias_2026-08-19_7.jpg')
