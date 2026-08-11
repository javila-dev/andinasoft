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
    bucket_codigo_from_dias,
    evaluar_cumplimiento_compromiso,
    filter_snapshot_for_gestor,
    gestor_nombre_from_user,
    kpis_from_rows,
    _clasificar_recaudos_adj,
    _parse_fecha_compromiso,
)


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
