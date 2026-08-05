"""Tests unitarios del flujo de saldo a favor (SF) al liquidar credito."""
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from andinasoft.saldo_favor import (
    is_sf_idcta,
    remanente_recibo,
    registrar_saldo_favor,
)
from andinasoft.views import _validar_recaudo_context


class SaldoFavorHelpersTests(SimpleTestCase):
    def test_is_sf_idcta(self):
        self.assertTrue(is_sf_idcta('SF1ADJ1'))
        self.assertFalse(is_sf_idcta('FN1ADJ1'))
        self.assertFalse(is_sf_idcta(None))

    @patch('andinasoft.saldo_favor.Recaudos')
    def test_remanente_recibo(self, recaudos):
        recaudos.objects.using.return_value.filter.return_value.aggregate.return_value = {
            'cap': Decimal('900'),
            'icte': Decimal('50'),
            'imora': Decimal('0'),
        }
        self.assertEqual(remanente_recibo('Oasis', '100', 1000), Decimal('50'))


class ValidarRecaudoExcesoTests(SimpleTestCase):
    def test_exceso_sin_abono_permite_guardar_con_warning(self):
        """Pago mayor al pendiente liquida el plan: verif_valor True + warning SF."""
        cuota = Mock()
        cuota.fecha = __import__('datetime').date(2020, 1, 1)
        cuota.idcta = 'FN1ADJ1'
        cuota.pendiente.return_value = {'capital': Decimal('100'), 'interes': Decimal('0'), 'total': Decimal('100')}
        cuota.mora.return_value = {'dias': 0, 'valor': 0}

        post = {
            'abonocapital': False,
            'fecha': '2026-08-05',
            'fecha_pago': '2026-08-05',
            'forma_pago': 'Efectivo',
            'condonacion_mora': 'No',
            'valor': '150',
            'concepto': 'Pago',
            'condonacion_porc': '',
            'numsolicitud': '',
        }
        request = Mock()
        with patch('andinasoft.views.form_nuevo_recibo') as form_cls:
            form_cls.return_value = Mock()
            context, alerts = _validar_recaudo_context(
                request=request,
                proyecto='Oasis',
                adj='ADJ1',
                titulares=Mock(),
                saldos_cuotas=[cuota],
                consecutivo=Mock(consecutivo=1),
                form_token='tok',
                post_data=post,
            )

        self.assertTrue(context['verif_valor'])
        codes = [a['code'] for a in alerts]
        self.assertIn('SALDO_FAVOR_PENDING', codes)
        self.assertNotIn('AMOUNT_EXCEEDS_PLAN', codes)


class RegistrarSaldoFavorTests(SimpleTestCase):
    @patch('andinasoft.saldo_favor.PlanPagos')
    @patch('andinasoft.saldo_favor.Recaudos')
    def test_crea_plan_y_recaudo_sf(self, recaudos, planpagos):
        planpagos.objects.using.return_value.filter.return_value.aggregate.return_value = {
            'nrocta__max': 0,
        }
        info = registrar_saldo_favor(
            proyecto='Oasis',
            adj='ADJ99',
            nro_recibo='555',
            fecha=__import__('datetime').date(2026, 8, 5),
            remanente=25000,
            usuario='operador',
            ledger_user=None,
        )
        self.assertIsNotNone(info)
        self.assertEqual(info['valor'], Decimal('25000'))
        self.assertTrue(str(info['idcta']).startswith('SF'))
        self.assertTrue(planpagos.objects.using.return_value.create.called)
        self.assertTrue(recaudos.objects.using.return_value.create.called)
        kwargs = planpagos.objects.using.return_value.create.call_args.kwargs
        self.assertEqual(kwargs['tipocta'], 'SF')
        self.assertEqual(kwargs['capital'], Decimal('25000'))


class DetallePagoExcluyeSfTests(SimpleTestCase):
    @patch('andinasoft.shared_models.Recaudos')
    def test_detalle_pago_excluye_sf(self, recaudos):
        from andinasoft.shared_models import Recaudos_general

        qs = Mock()
        recaudos.objects.using.return_value.filter.return_value = qs
        qs.exclude.return_value.aggregate.return_value = {
            'cap': Decimal('100'),
            'intcte': Decimal('10'),
            'intmora': Decimal('5'),
        }
        recibo = Recaudos_general()
        recibo.numrecibo = '1'
        recibo._state.db = 'Oasis'
        det = recibo.detalle_pago()
        qs.exclude.assert_called()
        self.assertEqual(det['capital'], Decimal('100'))
