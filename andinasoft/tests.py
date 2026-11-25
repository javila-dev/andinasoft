"""
Tests del abono a capital (andinasoft/abono_capital_service.py).

Solo prueban los cálculos puros, sin BD (SimpleTestCase). El flujo completo contra la
BD se verifica con scripts en el entorno de desarrollo.
"""
import random
from decimal import Decimal

from django.test import SimpleTestCase

from andinasoft.abono_capital_service import (
    AbonoCapitalError,
    distribuir_en_vencidas,
    recalcular_cuotas,
)

D = Decimal


def _cuota(idcta, cuota, intcte=1, rcdocapital=0, rcdointcte=0):
    return {'idcta': idcta, 'cuota': D(cuota), 'intcte': D(intcte),
            'rcdocapital': D(rcdocapital), 'rcdointcte': D(rcdointcte)}


def _algoritmo_anterior(cuotas, saldo_por_distribuir, tasa):
    """Copia del recálculo que vivía en views._guardar_recaudo (antes del servicio)."""
    cambios = []
    for cta in cuotas:
        if saldo_por_distribuir <= 0:
            cambios.append(('delete', cta['idcta']))
            continue
        intcte_nuevo = round(saldo_por_distribuir * tasa) if cta['intcte'] > 0 else 0
        cap_calculado = cta['cuota'] - intcte_nuevo
        if cap_calculado >= saldo_por_distribuir:
            capital = saldo_por_distribuir
            cambios.append(('update', cta['idcta'], capital, intcte_nuevo, capital + intcte_nuevo))
            saldo_por_distribuir = 0
        else:
            cambios.append(('update', cta['idcta'], cap_calculado, intcte_nuevo, cta['cuota']))
            saldo_por_distribuir -= cap_calculado
    return cambios


class RecalcularCuotasTests(SimpleTestCase):

    def test_acorta_plazo_y_cierra_en_la_ultima_cuota(self):
        cuotas = [_cuota('FN1', 1000), _cuota('FN2', 1000), _cuota('FN3', 1000)]
        cambios, sobrante = recalcular_cuotas(cuotas, D('1500'), D('0.01'))
        self.assertEqual(sobrante, 0)
        self.assertEqual(cambios, [
            ('update', 'FN1', D('985'), D('15'), D('1000')),
            ('update', 'FN2', D('515'), D('5'), D('520')),
            ('delete', 'FN3'),
        ])

    def test_igual_al_algoritmo_anterior_sin_anticipos(self):
        rnd = random.Random(7)
        for _ in range(300):
            tasa = rnd.choice([D('0'), D('0.008'), D('0.0099'), D('0.015'), D('0.02')])
            cuota = D(rnd.randrange(300_000, 3_000_000))
            cuotas = [_cuota(f'FN{i}', cuota, intcte=0 if tasa == 0 else 1) for i in range(rnd.randrange(1, 60))]
            # El saldo debe poder pagarse con esas cuotas (como en un plan real).
            pendiente = D(rnd.randrange(1, int(cuota * len(cuotas) * D('0.6')) + 2))
            nuevo, sobrante = recalcular_cuotas(cuotas, pendiente, tasa)
            if sobrante > 0:
                continue
            viejo = _algoritmo_anterior(cuotas, pendiente, tasa)
            self.assertEqual(
                [tuple(D(str(x)) if not isinstance(x, str) else x for x in c) for c in viejo],
                nuevo,
            )

    def test_respeta_anticipos_y_conserva_el_capital(self):
        rnd = random.Random(11)
        for _ in range(300):
            tasa = rnd.choice([D('0'), D('0.0099'), D('0.015')])
            cuota = D(rnd.randrange(400_000, 2_000_000))
            cuotas = []
            for i in range(rnd.randrange(2, 40)):
                pc = D(rnd.randrange(0, int(cuota * D('0.5')))) if i == 0 and rnd.random() < 0.7 else D(0)
                pi = D(rnd.randrange(0, 5000)) if pc else D(0)
                cuotas.append(_cuota(f'FN{i}', cuota, rcdocapital=pc, rcdointcte=pi))
            pendiente = D(rnd.randrange(0, int(cuota * len(cuotas) * D('0.5')) + 1))
            try:
                cambios, sobrante = recalcular_cuotas(cuotas, pendiente, tasa)
            except AbonoCapitalError:
                continue
            if sobrante > 0:
                continue
            por_id = {c['idcta']: c for c in cuotas}
            capital_total = D(0)
            for cambio in cambios:
                cta = por_id[cambio[1]]
                if cambio[0] == 'delete':
                    self.assertEqual(cta['rcdocapital'] + cta['rcdointcte'], 0,
                                     'no se puede borrar una cuota con recaudos')
                    continue
                _, _, capital, intcte, valor_cuota = cambio
                self.assertGreaterEqual(capital, cta['rcdocapital'])
                self.assertGreaterEqual(intcte, cta['rcdointcte'])
                self.assertEqual(capital + intcte, valor_cuota)
                capital_total += capital
            pagado = sum(c['rcdocapital'] for c in cuotas)
            self.assertEqual(capital_total, pendiente + pagado)

    def test_sin_saldo_deja_lo_pagado_y_borra_lo_demas(self):
        cuotas = [_cuota('FN1', 1000, rcdocapital=200, rcdointcte=10), _cuota('FN2', 1000)]
        cambios, sobrante = recalcular_cuotas(cuotas, D('0'), D('0.01'))
        self.assertEqual(sobrante, 0)
        self.assertEqual(cambios, [
            ('update', 'FN1', D('200'), D('10'), D('210')),
            ('delete', 'FN2'),
        ])

    def test_cuota_parcial_calcula_interes_sobre_saldo_al_inicio(self):
        # FN1 ya tiene 400 de capital anticipado; quedan 1000 por distribuir.
        cuotas = [_cuota('FN1', 600, rcdocapital=400), _cuota('FN2', 600), _cuota('FN3', 600)]
        cambios, sobrante = recalcular_cuotas(cuotas, D('1000'), D('0.01'))
        self.assertEqual(sobrante, 0)
        # Interés FN1 sobre 1400 = 14; capital 586 (400 ya pagado + 186 nuevo).
        self.assertEqual(cambios[0], ('update', 'FN1', D('586'), D('14'), D('600')))
        # Quedan 814: FN2 interés 8, capital 592; quedan 222 -> FN3 cierra.
        self.assertEqual(cambios[1], ('update', 'FN2', D('592'), D('8'), D('600')))
        self.assertEqual(cambios[2], ('update', 'FN3', D('222'), D('2'), D('224')))

    def test_cuotas_sin_interes_se_quedan_sin_interes(self):
        cuotas = [_cuota('CI1', 500, intcte=0), _cuota('FN1', 1000)]
        cambios, _ = recalcular_cuotas(cuotas, D('800'), D('0.015'))
        self.assertEqual(cambios[0], ('update', 'CI1', D('500'), D('0'), D('500')))

    def test_cuota_que_no_cubre_el_interes_falla(self):
        cuotas = [_cuota('FN1', 10)]
        with self.assertRaises(AbonoCapitalError):
            recalcular_cuotas(cuotas, D('100000'), D('0.015'))

    def test_cuotas_insuficientes_dejan_sobrante(self):
        cuotas = [_cuota('FN1', 100, intcte=0)]
        _, sobrante = recalcular_cuotas(cuotas, D('250'), D('0'))
        self.assertEqual(sobrante, D('150'))


class GuardarRecaudoAbonoTests(SimpleTestCase):
    """El recibo nuevo marcado como abono delega en el servicio y no se crea si falla."""

    def _guardar(self, **cleaned):
        from unittest.mock import Mock
        from andinasoft.views import _guardar_recaudo
        datos = {
            'abonocapital': True, 'fecha': '2026-11-25', 'fecha_pago': '2026-11-24',
            'forma_pago': 'Efectivo', 'condonacion_mora': 'No', 'valor': '5,000,000',
            'concepto': 'Abono', 'condonacion_porc': None, 'numsolicitud': None,
        }
        datos.update(cleaned)
        form = Mock(cleaned_data=datos)
        form.is_valid.return_value = True
        return _guardar_recaudo(
            request=Mock(session={}), proyecto='Casas de Verano', adj='ADJ1',
            titulares=Mock(), saldo_cuotas=[], saldos_cuotas=[],
            consecutivo=Mock(consecutivo=999), obj_adj=Mock(), form_recibo=form, form_token='t',
        )

    def test_abono_rechazado_no_crea_el_recibo(self):
        from unittest.mock import patch
        error = AbonoCapitalError('La validación del plan falló.', [{'message': 'Capital del plan cambió', 'code': 'X'}])
        with patch('andinasoft.views.novacion_pendiente_origen', return_value=None), \
             patch('andinasoft.views.validar_recaudo_caja_abierta'), \
             patch('andinasoft.views.aplicar_abono_capital', side_effect=error) as abono, \
             patch('andinasoft.views.Recaudos_general') as rg:
            updates, alerts, should_return = self._guardar()
        self.assertTrue(should_return)
        self.assertEqual(alerts[0]['code'], 'ABONO_CAPITAL_VALIDATION_FAILED')
        self.assertIn('Capital del plan cambió', alerts[0]['message'])
        self.assertEqual(updates['titulo'], 'Abono a capital rechazado')
        rg.objects.using.return_value.create.assert_not_called()
        kwargs = abono.call_args.kwargs
        self.assertEqual((kwargs['nro_recibo'], kwargs['valor'], kwargs['fecha_corte'], kwargs['cobro_mora']),
                         ('999', 5000000, '2026-11-24', 1))


class DistribuirEnVencidasTests(SimpleTestCase):

    def test_orden_mora_interes_capital_y_sobrante(self):
        cuotas = [
            {'idcta': 'FN1', 'saldocapital': D('900'), 'saldointcte': D('100'), 'mora': D('50')},
            {'idcta': 'FN2', 'saldocapital': D('900'), 'saldointcte': D('100'), 'mora': D('0')},
        ]
        lineas, sobrante = distribuir_en_vencidas(cuotas, D('2500'))
        self.assertEqual(lineas, [
            {'idcta': 'FN1', 'mora': D('50'), 'interes': D('100'), 'capital': D('900')},
            {'idcta': 'FN2', 'mora': D('0'), 'interes': D('100'), 'capital': D('900')},
        ])
        self.assertEqual(sobrante, D('450'))

    def test_pago_parcial_no_deja_sobrante(self):
        cuotas = [{'idcta': 'FN1', 'saldocapital': D('900'), 'saldointcte': D('100'), 'mora': D('50')}]
        lineas, sobrante = distribuir_en_vencidas(cuotas, D('120'))
        self.assertEqual(lineas, [{'idcta': 'FN1', 'mora': D('50'), 'interes': D('70'), 'capital': D('0')}])
        self.assertEqual(sobrante, 0)

    def test_saldos_negativos_no_restan(self):
        cuotas = [{'idcta': 'FN1', 'saldocapital': D('-5'), 'saldointcte': D('0'), 'mora': D('0')}]
        lineas, sobrante = distribuir_en_vencidas(cuotas, D('100'))
        self.assertEqual(lineas, [])
        self.assertEqual(sobrante, D('100'))
