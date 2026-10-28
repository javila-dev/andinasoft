from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from andinasoft.recaudos_terceros_service import agrupar_por_tercero, excel_recaudos_terceros, repartir

D = Decimal


def _recibo(num, adj, valor, fecha=date(2026, 10, 1), tercero='1', forma='BANCO'):
    return SimpleNamespace(numrecibo=num, idadjudicacion=adj, idtercero=tercero, valor=D(valor),
                           fecha=fecha, formapago=forma)


class RepartirTests(SimpleTestCase):
    def test_un_titular(self):
        self.assertEqual(repartir(D('100'), 1), [D('100')])

    def test_residuo_al_primero(self):
        partes = repartir(D('100'), 3)
        self.assertEqual(partes, [D('33.34'), D('33.33'), D('33.33')])
        self.assertEqual(sum(partes), D('100'))


class AgruparPorTerceroTests(SimpleTestCase):
    def test_reparte_entre_titulares_y_cuadra(self):
        recibos = [_recibo('M1', 'ADJ1', '1000')]
        detalle = {'M1': {'capital': D('700'), 'interescte': D('200'), 'interesmora': D('50'), 'saldo_favor': D('0')}}
        informe = agrupar_por_tercero(
            recibos, detalle, {'ADJ1': ['1', '2']}, {'1': 'ana', '2': 'luis'},
            {'BANCO': '11100501'}, {'capital': '13050501', 'saldo_favor': '28050501'},
        )
        self.assertEqual([g['nombre'] for g in informe['terceros']], ['ANA', 'LUIS'])
        ana = informe['terceros'][0]['movimientos'][0]
        self.assertEqual(ana['capital'], D('350'))
        self.assertEqual(ana['sin_aplicar'], D('25'))
        self.assertEqual(ana['participacion'], D('50.00'))
        self.assertEqual(informe['totales']['total'], D('1000'))
        self.assertEqual(informe['total_debito'], informe['total_credito'])
        self.assertEqual(informe['resumen'][0]['cuenta'], '11100501')

    def test_agrupa_varios_recibos_del_mismo_tercero(self):
        recibos = [
            _recibo('M2', 'ADJ1', '50', fecha=date(2026, 10, 5)),
            _recibo('M1', 'ADJ1', '30', fecha=date(2026, 10, 2)),
        ]
        detalle = {r.numrecibo: {'capital': r.valor} for r in recibos}
        informe = agrupar_por_tercero(recibos, detalle, {'ADJ1': ['1']}, {'1': 'Ana'}, {})
        grupo = informe['terceros'][0]
        self.assertEqual([m['recibo'] for m in grupo['movimientos']], ['M1', 'M2'])
        self.assertEqual(grupo['totales']['capital'], D('80'))
        self.assertEqual(informe['num_recibos'], 2)

    def test_sin_adjudicacion_usa_tercero_del_recibo(self):
        informe = agrupar_por_tercero([_recibo('M1', 'ADJ9', '10', tercero='77')], {}, {}, {}, {})
        grupo = informe['terceros'][0]
        self.assertEqual(grupo['nit'], '77')
        self.assertEqual(grupo['totales']['sin_aplicar'], D('10'))

    def test_excel_se_genera(self):
        informe = agrupar_por_tercero([_recibo('M1', 'ADJ1', '10')], {}, {'ADJ1': ['1']}, {'1': 'Ana'}, {})
        contenido = excel_recaudos_terceros(informe, 'Oasis', date(2026, 10, 1), date(2026, 10, 31))
        self.assertTrue(contenido.startswith(b'PK'))
