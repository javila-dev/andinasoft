"""
Tests unitarios del servicio de dashboard gestores.

Solo mocks / helpers puros — no requieren BD de proyecto.
"""
import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

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
    nro_contrato_from_adj,
    plantilla_html_por_codigo,
    visual_nodes_cartas,
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
        checkpoints = [
            SimpleNamespace(codigo=c, label=l, dias_desde=d)
            for c, l, d, _, _ in DEFAULT_CHECKPOINTS
        ]
        nodes = visual_nodes_cartas(checkpoints, 29, 1000)
        self.assertEqual([n['label'] for n in nodes], ['30 días', '45 días', '60 días', '90 días+'])
        self.assertFalse(any(n['activo'] or n['superado'] for n in nodes))

        nodes = visual_nodes_cartas(checkpoints, 50, 7777730)
        by = {n['codigo']: n for n in nodes}
        self.assertTrue(by['d30']['superado'])
        self.assertTrue(by['d45']['activo'])
        self.assertEqual(by['d45']['monto'], Decimal('7777730'))
        self.assertFalse(by['d60']['activo'] or by['d60']['superado'])
        self.assertEqual(by['d60']['monto'], Decimal(0))

        nodes = visual_nodes_cartas(checkpoints, 90, 500)
        by = {n['codigo']: n for n in nodes}
        self.assertTrue(by['d60']['superado'])
        self.assertTrue(by['d90']['activo'])
        self.assertEqual(by['d90']['monto'], Decimal(500))
