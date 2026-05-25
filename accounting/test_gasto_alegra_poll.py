"""Tests polling in-app — nuevos gastos Alegra pendientes de asignación."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounting.gasto_poll import poll_gastos_alegra_notificaciones
from accounting.models import Facturas, GastoContableNotificacion
from andinasoft.models import empresas

User = get_user_model()


class GastoAlegraPollTests(TestCase):
    def setUp(self):
        self.empresa_a = empresas.objects.create(
            Nit='900000001',
            nombre='Empresa A',
            alegra_enabled=True,
        )
        self.empresa_b = empresas.objects.create(
            Nit='900000002',
            nombre='Empresa B',
            alegra_enabled=True,
        )
        self.contable = User.objects.create_user('contable_poll', password='x')
        self.otro = User.objects.create_user('otro_poll', password='x')
        GastoContableNotificacion.objects.create(
            user=self.contable, empresa=self.empresa_a, activo=True,
        )
        self.factura_a = Facturas.objects.create(
            empresa=self.empresa_a,
            nrofactura='F-A1',
            idtercero='123',
            nombretercero='Proveedor A',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=100000,
            pago_neto=100000,
            origen='Alegra',
            alegra_bill_id='900000001:28',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
            gasto_aprobado=False,
        )
        self.factura_b = Facturas.objects.create(
            empresa=self.empresa_b,
            nrofactura='F-B1',
            idtercero='456',
            nombretercero='Proveedor B',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=200000,
            pago_neto=200000,
            origen='Alegra',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
            gasto_aprobado=False,
        )
        self.client = Client()

    def test_usuario_sin_configuracion_enabled_false(self):
        data = poll_gastos_alegra_notificaciones(self.otro, since_pk=0)
        self.assertEqual(data, {'enabled': False})

        self.client.force_login(self.otro)
        resp = self.client.get('/accounting/ajax/gastos-alegra/notificaciones-poll')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {'enabled': False})

    def test_usuario_con_notificacion_devuelve_items(self):
        data = poll_gastos_alegra_notificaciones(self.contable, since_pk=0)
        self.assertTrue(data['enabled'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['pk'], self.factura_a.pk)
        self.assertEqual(data['items'][0]['nrofactura'], 'F-A1')
        self.assertEqual(data['max_pk'], self.factura_a.pk)

    def test_since_pk_excluye_radicados_viejos(self):
        data = poll_gastos_alegra_notificaciones(
            self.contable, since_pk=self.factura_a.pk,
        )
        self.assertTrue(data['enabled'])
        self.assertEqual(data['items'], [])
        self.assertEqual(data['count'], 0)
        self.assertEqual(data['max_pk'], self.factura_a.pk)

    def test_empresa_no_configurada_no_aparece(self):
        data = poll_gastos_alegra_notificaciones(self.contable, since_pk=0)
        pks = [it['pk'] for it in data['items']]
        self.assertIn(self.factura_a.pk, pks)
        self.assertNotIn(self.factura_b.pk, pks)

    def test_endpoint_incluye_since_pk_en_respuesta(self):
        self.client.force_login(self.contable)
        resp = self.client.get(
            '/accounting/ajax/gastos-alegra/notificaciones-poll',
            {'since_pk': 5},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['enabled'])
        self.assertEqual(body['since_pk'], 5)
