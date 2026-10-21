"""Cuadre de caja de la planilla diaria: saldo teórico por movimientos y cierres."""
import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from accounting import cierre_caja_signals, cierre_caja_views, saldo_caja
from accounting.models import CierreCaja, Pagos


def _cierre(fecha, teorico, fisico=None, estado=CierreCaja.AJUSTE_SIN_DIFERENCIA, pk=1):
    fisico = teorico if fisico is None else fisico
    return CierreCaja(pk=pk, fecha=fecha, saldo_teorico=Decimal(teorico),
                      saldo_fisico=Decimal(fisico), estado_ajuste=estado)


class SaldoTeoricoTests(SimpleTestCase):
    def test_neto_suma_entradas_y_resta_salidas(self):
        movs = {'ingresos': 1000, 'otros_ingresos': 200, 'transferencias_entra': 300,
                'transferencias_sale': 50, 'intercompania_entra': 10, 'intercompania_sale': 5,
                'hoteles': 1, 'anticipos': 100, 'pagos': 400, 'gastos_caja': 6}
        self.assertEqual(saldo_caja.neto(movs), Decimal(1000 + 200 + 300 - 50 + 10 - 5 + 1 - 100 - 400 - 6))

    def test_sin_cierre_previo_no_hay_saldo(self):
        with mock.patch.object(saldo_caja, 'ultimo_cierre', return_value=None):
            self.assertEqual(saldo_caja.saldo_al_cierre(9, '2026-07-10'), (None, None))

    def test_suma_los_dias_sin_arqueo_desde_el_ultimo_cierre(self):
        base = _cierre(datetime.date(2026, 7, 6), 500000)
        movimientos = mock.Mock(return_value={'ingresos': Decimal(80000), 'pagos': Decimal(30000)})
        with mock.patch.object(saldo_caja, 'ultimo_cierre', return_value=base), \
                mock.patch.object(saldo_caja, 'movimientos_caja', movimientos):
            saldo, cierre_base = saldo_caja.saldo_al_cierre(9, '2026-07-10')
        self.assertEqual(saldo, Decimal(550000))
        self.assertIs(cierre_base, base)
        # Los movimientos van desde el día siguiente al cierre hasta la fecha pedida.
        movimientos.assert_called_once_with(9, datetime.date(2026, 7, 7), datetime.date(2026, 7, 10))

    def test_dia_siguiente_a_un_ajuste_aprobado_parte_del_fisico(self):
        base = _cierre(datetime.date(2026, 7, 6), 500000, fisico=480000, estado=CierreCaja.AJUSTE_APROBADO)
        movimientos = mock.Mock(return_value={'ingresos': Decimal(10000)})
        with mock.patch.object(saldo_caja, 'ultimo_cierre', return_value=base), \
                mock.patch.object(saldo_caja, 'movimientos_caja', movimientos):
            cuadre = saldo_caja.cuadre_del_dia(9, '2026-07-07')
        self.assertEqual(cuadre['saldo_inicial'], Decimal(480000))
        self.assertEqual(cuadre['saldo_final'], Decimal(490000))

    def test_diferencia_pendiente_no_se_borra_al_dia_siguiente(self):
        # Faltaron 20.000 en el arqueo; mientras no se apruebe, el día siguiente parte del teórico.
        cierre = _cierre(datetime.date(2026, 7, 6), 500000, fisico=480000, estado=CierreCaja.AJUSTE_PENDIENTE)
        self.assertEqual(cierre.saldo_base_siguiente, Decimal(500000))

    def test_ajuste_aprobado_continua_desde_el_fisico(self):
        cierre = _cierre(datetime.date(2026, 7, 6), 500000, fisico=480000, estado=CierreCaja.AJUSTE_APROBADO)
        self.assertEqual(cierre.saldo_base_siguiente, Decimal(480000))


class LibroCajaTests(SimpleTestCase):
    def test_saldo_acumulado_desde_el_ultimo_cierre(self):
        base = _cierre(datetime.date(2026, 7, 31), 968050)
        filas = [
            saldo_caja._fila('2026-08-04', 'transferencias_sale', 'TR 1', 'a caja menor', 404520),
            saldo_caja._fila('2026-08-28', 'ingresos', 'RC 15148', 'cliente', 1814124),
        ]
        detalle = mock.Mock(return_value=filas)
        with mock.patch.object(saldo_caja, 'ultimo_cierre', return_value=base), \
                mock.patch.object(saldo_caja, 'detalle_movimientos_caja', detalle):
            libro = saldo_caja.libro_caja(9, '2026-08-28')
        detalle.assert_called_once_with(9, datetime.date(2026, 8, 1), datetime.date(2026, 8, 28))
        self.assertEqual([f['saldo'] for f in libro['filas']], [Decimal(563530), Decimal(2377654)])
        self.assertEqual(libro['total_entradas'], Decimal(1814124))
        self.assertEqual(libro['total_salidas'], Decimal(404520))
        self.assertEqual(libro['saldo_final'], Decimal(2377654))


class BloqueoCierreTests(SimpleTestCase):
    def setUp(self):
        self.cuenta = SimpleNamespace(pk=9)
        existe = mock.patch.object(cierre_caja_views.CierreCaja.objects, 'filter',
                                   return_value=mock.Mock(exists=mock.Mock(return_value=False)))
        existe.start()
        self.addCleanup(existe.stop)

    def _bloqueo(self, fecha, previo):
        with mock.patch.object(cierre_caja_views, 'ultimo_cierre', return_value=previo):
            return cierre_caja_views._bloqueo_cierre(self.cuenta, fecha)

    def test_no_cierra_fechas_futuras(self):
        manana = datetime.date.today() + datetime.timedelta(days=1)
        self.assertIn('futura', self._bloqueo(manana, None))

    def test_no_cierra_antes_del_ultimo_cierre(self):
        previo = _cierre(datetime.date(2026, 7, 10), 0)
        self.assertIn('solo se pueden cerrar fechas posteriores',
                      self._bloqueo(datetime.date(2026, 7, 8), previo))

    def test_ajuste_pendiente_impide_cerrar_el_siguiente_dia(self):
        previo = _cierre(datetime.date(2026, 7, 10), 100, fisico=90, estado=CierreCaja.AJUSTE_PENDIENTE)
        self.assertIn('pendiente de aprobar', self._bloqueo(datetime.date(2026, 7, 11), previo))

    def test_permite_cerrar_despues_de_un_cierre_cuadrado(self):
        previo = _cierre(datetime.date(2026, 7, 10), 100)
        self.assertIsNone(self._bloqueo(datetime.date(2026, 7, 13), previo))


class SenalCajaCerradaTests(SimpleTestCase):
    def _pago(self, **kwargs):
        datos = dict(pk=None, fecha_pago='2026-07-10', cuenta_id=9, valor=1000)
        datos.update(kwargs)
        pago = Pagos(valor=datos['valor'], fecha_pago=datos['fecha_pago'])
        pago.pk = datos['pk']
        pago.cuenta_id = datos['cuenta_id']
        return pago

    def _guardar(self, pago, anterior=None):
        qs = mock.Mock()
        qs.filter.return_value.values.return_value.first.return_value = anterior
        validar = mock.Mock()
        with mock.patch.object(Pagos, 'objects') as objects, \
                mock.patch.object(cierre_caja_signals, 'validar_caja_abierta', validar):
            objects.using.return_value = qs
            cierre_caja_signals.validar_guardado(Pagos, pago, using='default')
        return validar

    def test_pago_nuevo_valida_su_fecha_y_cuenta(self):
        validar = self._guardar(self._pago())
        validar.assert_called_once_with((9,), datetime.date(2026, 7, 10))

    def test_cambio_sin_mover_efectivo_no_valida(self):
        anterior = {'fecha_pago': datetime.date(2026, 7, 10), 'cuenta_id': 9, 'valor': 1000}
        validar = self._guardar(self._pago(pk=5), anterior)
        validar.assert_not_called()

    def test_mover_un_pago_valida_dia_original_y_nuevo(self):
        anterior = {'fecha_pago': datetime.date(2026, 7, 3), 'cuenta_id': 9, 'valor': 1000}
        validar = self._guardar(self._pago(pk=5), anterior)
        self.assertEqual(validar.call_args_list, [
            mock.call((9,), datetime.date(2026, 7, 3)),
            mock.call((9,), datetime.date(2026, 7, 10)),
        ])

    def test_caja_cerrada_bloquea_el_pago(self):
        with mock.patch.object(Pagos, 'objects'), \
                mock.patch.object(cierre_caja_signals, 'validar_caja_abierta',
                                  side_effect=saldo_caja.CajaCerrada('cerrada')):
            with self.assertRaises(saldo_caja.CajaCerrada):
                cierre_caja_signals.validar_guardado(Pagos, self._pago(), using='default')
