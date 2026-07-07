"""Tests polling in-app — gastos Alegra pendientes de aprobacion (seguimiento)."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounting.gasto_aprobacion_seguimiento_poll import poll_gastos_aprobacion_seguimiento
from accounting.models import Facturas, GastoContableNotificacion
from andinasoft.models import empresas

User = get_user_model()


class GastoAprobacionSeguimientoPollTests(TestCase):
    def setUp(self):
        self.empresa_a = empresas.objects.create(
            Nit='900000011',
            nombre='Empresa A',
            alegra_enabled=True,
        )
        self.empresa_b = empresas.objects.create(
            Nit='900000012',
            nombre='Empresa B',
            alegra_enabled=True,
        )
        self.contable = User.objects.create_user('contable_seg', password='x')
        self.aprobador = User.objects.create_user('aprobador_seg', password='x')
        self.otro = User.objects.create_user('otro_seg', password='x')
        GastoContableNotificacion.objects.create(
            user=self.contable, empresa=self.empresa_a, activo=True,
        )
        hace_2_dias = timezone.now() - timedelta(days=2)
        self.factura_atrasada = Facturas.objects.create(
            empresa=self.empresa_a,
            nrofactura='F-ATR',
            idtercero='123',
            nombretercero='Proveedor Atrasado',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            fecharadicado='2026-05-01',
            valor=100000,
            pago_neto=100000,
            origen='Alegra',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
            gasto_aprobado=False,
            gasto_aprobador_asignado=self.aprobador,
            gasto_asignado_en=hace_2_dias,
        )
        self.factura_reciente = Facturas.objects.create(
            empresa=self.empresa_a,
            nrofactura='F-REC',
            idtercero='456',
            nombretercero='Proveedor Reciente',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            fecharadicado='2026-05-01',
            valor=200000,
            pago_neto=200000,
            origen='Alegra',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
            gasto_aprobado=False,
            gasto_aprobador_asignado=self.aprobador,
            gasto_asignado_en=timezone.now(),
        )
        self.factura_otra_empresa = Facturas.objects.create(
            empresa=self.empresa_b,
            nrofactura='F-B',
            idtercero='789',
            nombretercero='Proveedor B',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            fecharadicado='2026-05-01',
            valor=300000,
            pago_neto=300000,
            origen='Alegra',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
            gasto_aprobado=False,
            gasto_aprobador_asignado=self.aprobador,
            gasto_asignado_en=hace_2_dias,
        )
        self.client = Client()

    def test_usuario_sin_configuracion_enabled_false(self):
        data = poll_gastos_aprobacion_seguimiento(self.otro, known_pks='')
        self.assertEqual(data, {'enabled': False})

    def test_devuelve_solo_atrasados_de_empresa_configurada(self):
        data = poll_gastos_aprobacion_seguimiento(self.contable, known_pks='')
        self.assertTrue(data['enabled'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['items'][0]['pk'], self.factura_atrasada.pk)
        self.assertEqual(data['total_atrasados'], 1)
        self.assertIn(self.factura_atrasada.pk, data['all_atrasados_pks'])
        self.assertNotIn(self.factura_reciente.pk, data['all_atrasados_pks'])
        self.assertNotIn(self.factura_otra_empresa.pk, data['all_atrasados_pks'])

    def test_known_pks_excluye_items_ya_vistos(self):
        data = poll_gastos_aprobacion_seguimiento(
            self.contable,
            known_pks=str(self.factura_atrasada.pk),
        )
        self.assertTrue(data['enabled'])
        self.assertEqual(data['items'], [])
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['total_atrasados'], 1)

    def test_endpoint_json(self):
        self.client.force_login(self.contable)
        resp = self.client.get(
            '/accounting/ajax/gastos-alegra/aprobacion-seguimiento-poll',
            {'known_pks': ''},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['enabled'])
        self.assertEqual(body['items'][0]['pk'], self.factura_atrasada.pk)
