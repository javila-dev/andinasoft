"""Tests unitarios de novaciones y del plan de pagos compartido con la adjudicacion."""
import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch

from django.test import SimpleTestCase

from andinasoft import novaciones_service as svc
from andinasoft.adjudicacion_service import crear_plan_pagos, total_cuota_inicial


def _venta(**kwargs):
    base = {f'{campo}{i}': None for i in range(1, 8) for campo in ('cant_ci', 'fecha_ci', 'valor_ci')}
    base.update(
        pk=10, id_t1='111', id_t2='', id_t3=None, id_t4=None, inmueble='M1L1', estado='Pendiente',
        tipo_venta='Lote', saldo=0, forma_saldo='Regular', nro_cuotas_fn=None, inicio_fn=None,
        valor_ctas_fn=None, nro_cuotas_ce=None, inicio_ce=None, valor_ctas_ce=None, period_ce=None,
        tasa=Decimal('0.01'),
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


class PlanPagosTests(SimpleTestCase):
    def _crear(self, venta):
        with patch('andinasoft.adjudicacion_service.PlanPagos') as plan:
            crear_plan_pagos('Oasis', venta, 'ADJ7')
        return [c.kwargs for c in plan.objects.using.return_value.create.call_args_list]

    def test_cuota_inicial_numera_tramos_en_secuencia(self):
        hoy = datetime.date(2026, 1, 15)
        cuotas = self._crear(_venta(
            cant_ci1=2, fecha_ci1=hoy, valor_ci1=100,
            cant_ci2=1, fecha_ci2=datetime.date(2026, 6, 1), valor_ci2=50,
        ))
        self.assertEqual([c['idcta'] for c in cuotas], ['CI1ADJ7', 'CI2ADJ7', 'CI3ADJ7'])
        self.assertEqual(cuotas[1]['fecha'], datetime.date(2026, 2, 15))
        self.assertEqual(cuotas[2]['capital'], 50)

    def test_saldo_regular_amortiza_hasta_cero(self):
        cuotas = self._crear(_venta(
            saldo=1000, forma_saldo='Regular', nro_cuotas_fn=3,
            inicio_fn=datetime.date(2026, 1, 1), valor_ctas_fn=340, tasa=Decimal('0.01'),
        ))
        self.assertEqual([c['tipocta'] for c in cuotas], ['FN', 'FN', 'FN'])
        self.assertEqual(sum(c['capital'] for c in cuotas), 1000)

    def test_contado_y_extraordinarias(self):
        cuotas = self._crear(_venta(
            saldo=1000, forma_saldo='CONTADO', nro_cuotas_fn=1,
            inicio_fn=datetime.date(2026, 1, 1), valor_ctas_fn=600, tasa=Decimal('0'),
            nro_cuotas_ce=2, inicio_ce=datetime.date(2026, 6, 1), valor_ctas_ce=200, period_ce='Semestral',
        ))
        self.assertEqual(cuotas[0]['idcta'], 'CO1ADJ7')
        extras = [c for c in cuotas if c['tipocta'] == 'CE']
        self.assertEqual([c['fecha'] for c in extras], [datetime.date(2026, 6, 1), datetime.date(2026, 12, 1)])
        self.assertEqual(sum(c['capital'] for c in extras), 400)

    def test_total_cuota_inicial(self):
        self.assertEqual(total_cuota_inicial(_venta(cant_ci1=2, valor_ci1=100, cant_ci3=1, valor_ci3=50)), 250)


class ValidarNovacionTests(SimpleTestCase):
    PAGADO = {'capital': Decimal('1000'), 'interes_cte': Decimal('300'), 'interes_mora': Decimal('50')}

    def _validar(self, venta=None, adj=None, **kwargs):
        adj = adj or SimpleNamespace(estado='Aprobado', idinmueble='X1', idtercero1='111')
        venta = venta or _venta(cant_ci1=1, valor_ci1=2000)
        datos = dict(capital=1000, interes_cte=100, interes_mora=0, nro_nota='N-1')
        datos.update(kwargs)
        with patch.object(svc, 'Adjudicacion') as adj_model, \
                patch.object(svc, 'ventas_nuevas') as venta_model, \
                patch.object(svc, 'novacion_pendiente_origen', return_value=None), \
                patch.object(svc, 'novacion_pendiente_venta', return_value=None), \
                patch.object(svc, 'pagado_por_componente', return_value=dict(self.PAGADO)), \
                patch.object(svc, '_nota_usada', return_value=False), \
                patch.object(svc, 'Novacion') as novacion_model:
            adj_model.objects.using.return_value.get.return_value = adj
            venta_model.objects.using.return_value.get.return_value = venta
            novacion_model.ESTADO_RECHAZADA = 'Rechazada'
            novacion_model.objects.filter.return_value.exclude.return_value.exists.return_value = False
            return svc.validar(
                proyecto_origen='Oasis', adj_origen='ADJ1', proyecto_destino='Sotavento', venta_id=10, **datos
            )

    def assertRechaza(self, texto, **kwargs):
        with self.assertRaises(svc.NovacionError) as ctx:
            self._validar(**kwargs)
        self.assertIn(texto, str(ctx.exception))

    def test_traslado_parcial_valido(self):
        _, _, pagado = self._validar(capital=1000, interes_cte=150)
        self.assertEqual(pagado['capital'], Decimal('1000'))

    def test_no_traslada_mas_de_lo_pagado(self):
        self.assertRechaza('Interés de mora', interes_mora=51)

    def test_algo_hay_que_trasladar(self):
        self.assertRechaza('al menos un valor', capital=0, interes_cte=0)

    def test_no_supera_la_cuota_inicial_destino(self):
        self.assertRechaza('supera la cuota inicial', venta=_venta(cant_ci1=1, valor_ci1=500))

    def test_el_cliente_debe_ser_titular_de_la_venta(self):
        self.assertRechaza('no es titular', venta=_venta(id_t1='999', cant_ci1=1, valor_ci1=2000))

    def test_venta_destino_debe_estar_pendiente_o_aprobada(self):
        self.assertRechaza('debe estar Pendiente', venta=_venta(estado='Adjudicado', cant_ci1=1, valor_ci1=2000))

    def test_origen_desistido(self):
        adj = SimpleNamespace(estado='Desistido', idinmueble='X1', idtercero1='111')
        self.assertRechaza('ya está desistida', adj=adj)

    def test_nota_obligatoria_y_corta(self):
        self.assertRechaza('número de la nota', nro_nota='  ')
        self.assertRechaza('máximo 12', nro_nota='N' * 13)


class DocumentacionTests(SimpleTestCase):
    def _novacion(self, **kwargs):
        base = dict(
            pk=5, nro_nota='N-1', fecha_nota=datetime.date(2026, 10, 1), empresa_nota_id='900',
            soporte='novaciones/nota.pdf', usuario_solicita_id=1,
            fecha_entrega=datetime.date(2027, 6, 30), fecha_escritura=datetime.date(2027, 12, 15),
        )
        base.update(kwargs)
        return SimpleNamespace(**base)

    def _docs(self, *tipos):
        return [{'tipo': t} for t in tipos]

    def test_checklist_completo_con_nota_y_obligatorios(self):
        items, completo = svc.checklist(self._novacion(), self._docs('Novacion', 'Promesa'))
        self.assertTrue(completo)
        opcionales = [i['clave'] for i in items if not i['obligatorio']]
        self.assertEqual(opcionales, ['Pagare', 'Otrosi'])

    def test_checklist_sin_fechas_de_promesa(self):
        items, completo = svc.checklist(self._novacion(fecha_escritura=None), self._docs('Novacion', 'Promesa'))
        self.assertFalse(completo)
        self.assertFalse([i for i in items if i['clave'] == 'fechas_promesa'][0]['ok'])

    @patch.object(svc.transaction, 'atomic', MagicMock())
    @patch.object(svc, '_evento')
    @patch.object(svc, '_exigir_documentacion')
    def test_fechas_de_promesa_obligatorias(self, _exigir, _evento):
        novacion = Mock()
        with self.assertRaises(svc.NovacionError):
            svc.registrar_fechas_promesa(SimpleNamespace(pk=1), novacion,
                                         fecha_entrega=datetime.date(2027, 6, 30), fecha_escritura=None)
        svc.registrar_fechas_promesa(SimpleNamespace(pk=1), novacion,
                                     fecha_entrega=datetime.date(2027, 6, 30),
                                     fecha_escritura=datetime.date(2027, 12, 15))
        self.assertEqual(novacion.fecha_escritura, datetime.date(2027, 12, 15))
        novacion.save.assert_called_once()

    def test_checklist_falta_promesa(self):
        _, completo = svc.checklist(self._novacion(), self._docs('Novacion', 'Pagare'))
        self.assertFalse(completo)

    def test_checklist_nota_sin_pdf(self):
        _, completo = svc.checklist(self._novacion(soporte=None), self._docs('Novacion', 'Promesa'))
        self.assertFalse(completo)

    @patch.object(svc, 'guardar_documento_contrato')
    @patch.object(svc, 'documentos_cargados', return_value=[{'tipo': 'Promesa'}])
    @patch.object(svc, '_exigir_documentacion')
    def test_no_carga_un_tipo_que_ya_esta(self, _exigir, _docs, guardar):
        with self.assertRaises(svc.NovacionError) as ctx:
            svc.cargar_documento(SimpleNamespace(pk=1), self._novacion(), 'Promesa', object())
        self.assertIn('ya', str(ctx.exception).lower())
        guardar.assert_not_called()

    def test_puede_gestionar_creador_jefe_o_superusuario(self):
        novacion = self._novacion()

        def usuario(pk, superuser=False, jefe=False):
            return SimpleNamespace(pk=pk, is_superuser=superuser, has_perm=lambda perm: jefe)

        self.assertTrue(svc.puede_gestionar(usuario(1), novacion))
        self.assertTrue(svc.puede_gestionar(usuario(2, jefe=True), novacion))
        self.assertTrue(svc.puede_gestionar(usuario(3, superuser=True), novacion))
        self.assertFalse(svc.puede_gestionar(usuario(4), novacion))


class NotificacionTests(SimpleTestCase):
    def _novacion(self):
        solicitante = SimpleNamespace(
            pk=1, username='ana', email='ana@test.co', is_active=True, get_full_name=lambda: 'Ana Gil',
        )
        return SimpleNamespace(
            pk=7, estado='Por aprobar', get_estado_display=lambda: 'Por aprobar',
            capital_trasladado=Decimal('1000'), interes_cte_trasladado=Decimal('200'),
            interes_mora_trasladado=Decimal('0'), total_trasladado=Decimal('1200'), nro_nota='N-1',
            usuario_solicita=solicitante, usuario_solicita_id=1, usuario_envia=solicitante, usuario_envia_id=1,
            proyecto_origen_id='Oasis', adj_origen='ADJ1', inmueble_origen='A1',
            proyecto_destino_id='Sotavento', venta_destino=10, inmueble_destino='B2', adj_destino='',
            titular='111',
            aprobador=SimpleNamespace(
                pk=9, username='jefe', email='jefe@test.co', is_active=True, get_full_name=lambda: 'Jefe',
            ),
        )

    @patch('andinasoft.novaciones_notify._telefono', return_value='573001112233')
    @patch('andinasoft.novaciones_notify.clientes')
    def test_devuelta_va_al_solicitante_con_comentario(self, clientes, _tel):
        clientes.objects.filter.return_value.first.return_value = SimpleNamespace(nombrecompleto='Cliente Uno')
        from andinasoft.novaciones_notify import build_payload

        payload = build_payload(self._novacion(), 'devuelta', 'Falta la firma')
        self.assertEqual(payload['event'], 'novacion.devuelta')
        self.assertEqual(payload['comentario'], 'Falta la firma')
        self.assertEqual([r['email'] for r in payload['recipients']], ['ana@test.co'])
        self.assertEqual(payload['recipients'][0]['telefono'], '573001112233')
        self.assertIn('/operaciones/novaciones/7', payload['link'])

    @patch('andinasoft.novaciones_notify._telefono', return_value='')
    @patch('andinasoft.novaciones_notify.clientes')
    def test_por_aprobar_va_solo_al_aprobador_designado(self, clientes, _tel):
        clientes.objects.filter.return_value.first.return_value = None
        from andinasoft.novaciones_notify import build_payload

        payload = build_payload(self._novacion(), 'por_aprobar')
        self.assertEqual([(r['role'], r['email']) for r in payload['recipients']], [('aprobador', 'jefe@test.co')])
        self.assertEqual(payload['cliente']['nombre'], '111')


class AprobadorTests(SimpleTestCase):
    def _usuario(self, pk, superuser=False):
        return SimpleNamespace(pk=pk, is_superuser=superuser, username=f'u{pk}')

    def test_solo_el_aprobador_designado_o_superusuario_resuelve(self):
        novacion = SimpleNamespace(aprobador_id=9)
        self.assertTrue(svc.puede_resolver(self._usuario(9), novacion))
        self.assertTrue(svc.puede_resolver(self._usuario(1, superuser=True), novacion))
        self.assertFalse(svc.puede_resolver(self._usuario(2), novacion))
        self.assertFalse(svc.puede_resolver(self._usuario(2), SimpleNamespace(aprobador_id=None)))

    def test_aprobador_obligatorio_y_de_la_lista(self):
        with patch.object(svc, 'candidatos_aprobador', return_value=[self._usuario(9)]):
            with self.assertRaises(svc.NovacionError):
                svc._validar_aprobador(None, 'Oasis')
            with self.assertRaises(svc.NovacionError):
                svc._validar_aprobador(self._usuario(3), 'Oasis')
            svc._validar_aprobador(self._usuario(9), 'Oasis')


class ReciboOrigenTests(SimpleTestCase):
    def test_mismo_proyecto_usa_sufijo(self):
        self.assertEqual(svc.recibo_origen('CC-SV-1255', 'Carmelo', 'Carmelo'), 'CC-SV-1255-D')
        self.assertEqual(svc.recibo_origen('CC-SV-1255', 'Oasis', 'Carmelo'), 'CC-SV-1255')

    @patch.object(svc, 'Novacion')
    @patch.object(svc, '_nota_usada', return_value=False)
    def test_largo_maximo_menor_en_el_mismo_proyecto(self, usada, novacion_model):
        novacion_model.objects.filter.return_value.exclude.return_value.exists.return_value = False
        svc.validar_nota('N' * 12, 'Oasis', 'Carmelo')
        with self.assertRaises(svc.NovacionError):
            svc.validar_nota('N' * 11, 'Carmelo', 'Carmelo')
        svc.validar_nota('N' * 10, 'Carmelo', 'Carmelo')
        # En el mismo proyecto se revisan los dos recibos: el de entrada y el del origen.
        revisados = {c.args for c in usada.call_args_list[-2:]}
        self.assertEqual(revisados, {('Carmelo', 'N' * 10), ('Carmelo', 'N' * 10 + '-D')})


class DeshacerTests(SimpleTestCase):
    def test_revierte_en_orden_inverso_aunque_un_paso_falle(self):
        orden = []
        deshacer = svc._Deshacer()
        deshacer.registrar(lambda: orden.append('consecutivo'))
        deshacer.registrar(MagicMock(side_effect=RuntimeError('boom')))
        deshacer.registrar(lambda: orden.append('timeline'))
        with self.assertLogs('andinasoft.novaciones_service', level='ERROR'):
            deshacer.ejecutar()
        self.assertEqual(orden, ['timeline', 'consecutivo'])
