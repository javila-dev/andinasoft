from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from andinasoft.ajuste_capital_service import (
    aplicar_ajuste_valor_a_capital,
    recortar_plan_a_capital_pagado,
)


class RecortarPlanACapitalPagadoTests(SimpleTestCase):
    @patch('andinasoft.ajuste_capital_service.PlanPagos')
    @patch('andinasoft.ajuste_capital_service.saldos_adj')
    def test_elimina_cuotas_sin_abono_y_ajusta_parciales(self, mock_saldos, mock_plan):
        parcial = SimpleNamespace(
            idcta='CI5ADJ1',
            rcdocapital=Decimal('100'),
            rcdointcte=Decimal('10'),
        )
        sin_abono = SimpleNamespace(
            idcta='FN1ADJ1',
            rcdocapital=Decimal('0'),
            rcdointcte=Decimal('0'),
        )
        qs = MagicMock()
        qs.exclude.return_value.exclude.return_value = [parcial, sin_abono]
        mock_saldos.objects.using.return_value.filter.return_value = qs

        cta_parcial = MagicMock()
        mock_plan.objects.using.return_value.get.return_value = cta_parcial
        delete_qs = MagicMock()
        mock_plan.objects.using.return_value.filter.return_value = delete_qs

        recortar_plan_a_capital_pagado('Casas de Verano', 'ADJ1')

        self.assertEqual(cta_parcial.capital, Decimal('100'))
        self.assertEqual(cta_parcial.intcte, Decimal('10'))
        self.assertEqual(cta_parcial.cuota, Decimal('110'))
        cta_parcial.save.assert_called_once()
        mock_plan.objects.using.return_value.filter.assert_called_with(idcta='FN1ADJ1')
        delete_qs.delete.assert_called_once()


class AplicarAjusteValorACapitalTests(SimpleTestCase):
    @patch('andinasoft.ajuste_capital_service.recortar_plan_a_capital_pagado')
    @patch('andinasoft.ajuste_capital_service.backup_plan_y_recaudos')
    @patch('andinasoft.ajuste_capital_service.saldo_capital_adj', return_value=Decimal('2921800'))
    @patch('andinasoft.ajuste_capital_service.capital_pagado_adj', return_value=Decimal('63078200'))
    @patch('andinasoft.ajuste_capital_service.Adjudicacion')
    def test_actualiza_valor_y_estado(
        self, mock_adj_model, mock_cap, mock_saldo, mock_backup, mock_recortar
    ):
        obj = MagicMock()
        obj.estado = 'Aprobado'
        obj.valor = Decimal('66000000')
        mock_adj_model.objects.using.return_value.get.return_value = obj
        user = MagicMock()

        resultado = aplicar_ajuste_valor_a_capital('Casas de Verano', 'ADJ114', user)

        mock_backup.assert_called_once_with('Casas de Verano', 'ADJ114', user)
        mock_recortar.assert_called_once_with('Casas de Verano', 'ADJ114')
        self.assertEqual(obj.valor, Decimal('63078200'))
        self.assertEqual(obj.estado, 'Pagado')
        obj.save.assert_called_once()
        self.assertEqual(resultado['descuento'], Decimal('2921800'))
        self.assertEqual(resultado['valor_nuevo'], Decimal('63078200'))

    @patch('andinasoft.ajuste_capital_service.Adjudicacion')
    def test_rechaza_si_ya_pagado(self, mock_adj_model):
        obj = MagicMock()
        obj.estado = 'Pagado'
        mock_adj_model.objects.using.return_value.get.return_value = obj
        with self.assertRaises(ValueError):
            aplicar_ajuste_valor_a_capital('Casas de Verano', 'ADJ114', MagicMock())
