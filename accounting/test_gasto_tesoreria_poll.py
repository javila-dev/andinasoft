"""Tests polling in-app — gastos Alegra aprobados para tesorería."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounting.gasto_tesoreria_poll import poll_gastos_tesoreria_aprobados
from accounting.models import (
    Facturas,
    GastoNotificacionOficina,
    GastoTesoreriaNotificacion,
)
from andinasoft.models import empresas

User = get_user_model()


class GastoTesoreriaPollTests(TestCase):
    def setUp(self):
        self.empresa_a = empresas.objects.create(
            Nit='900000011',
            nombre='Empresa Tesor A',
            alegra_enabled=True,
        )
        self.empresa_b = empresas.objects.create(
            Nit='900000012',
            nombre='Empresa Tesor B',
            alegra_enabled=True,
        )
        self.ofi_mde = GastoNotificacionOficina.objects.get(codigo='MEDELLIN')
        self.ofi_mtr = GastoNotificacionOficina.objects.get(codigo='MONTERIA')
        self.tesor = User.objects.create_user('tesor_poll', password='x')
        self.otro = User.objects.create_user('otro_tesor', password='x')
        cfg = GastoTesoreriaNotificacion.objects.create(user=self.tesor, activo=True)
        cfg.empresas.add(self.empresa_a)
        cfg.oficinas.add(self.ofi_mde)

        ahora = timezone.now()
        self.factura_ok = Facturas.objects.create(
            empresa=self.empresa_a,
            nrofactura='F-T1',
            idtercero='123',
            nombretercero='Proveedor T',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=300000,
            pago_neto=300000,
            origen='Alegra',
            oficina='MEDELLIN',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_APROBADO,
            gasto_aprobado=True,
            gasto_aprobado_en=ahora,
        )
        self.factura_otra_empresa = Facturas.objects.create(
            empresa=self.empresa_b,
            nrofactura='F-T2',
            idtercero='456',
            nombretercero='Proveedor B',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=400000,
            pago_neto=400000,
            origen='Alegra',
            oficina='MEDELLIN',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_APROBADO,
            gasto_aprobado=True,
            gasto_aprobado_en=ahora,
        )
        self.factura_otra_oficina = Facturas.objects.create(
            empresa=self.empresa_a,
            nrofactura='F-T3',
            idtercero='789',
            nombretercero='Proveedor C',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=500000,
            pago_neto=500000,
            origen='Alegra',
            oficina='MONTERIA',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_APROBADO,
            gasto_aprobado=True,
            gasto_aprobado_en=ahora,
        )
        self.client = Client()

    def test_sin_configuracion_enabled_false(self):
        data = poll_gastos_tesoreria_aprobados(self.otro)
        self.assertEqual(data, {'enabled': False})

    def test_filtra_empresa_y_oficina(self):
        data = poll_gastos_tesoreria_aprobados(self.tesor, since_ts='1970-01-01T00:00:00Z')
        self.assertTrue(data['enabled'])
        pks = [it['pk'] for it in data['items']]
        self.assertIn(self.factura_ok.pk, pks)
        self.assertNotIn(self.factura_otra_empresa.pk, pks)
        self.assertNotIn(self.factura_otra_oficina.pk, pks)

    def test_since_ts_excluye_aprobaciones_viejas(self):
        since = (self.factura_ok.gasto_aprobado_en + timedelta(seconds=1)).isoformat()
        data = poll_gastos_tesoreria_aprobados(self.tesor, since_ts=since)
        self.assertTrue(data['enabled'])
        self.assertEqual(data['items'], [])

    def test_sin_empresas_o_oficinas_enabled_false(self):
        cfg = GastoTesoreriaNotificacion.objects.get(user=self.tesor)
        cfg.oficinas.clear()
        data = poll_gastos_tesoreria_aprobados(self.tesor)
        self.assertEqual(data, {'enabled': False})

    def test_endpoint_json(self):
        self.client.force_login(self.tesor)
        resp = self.client.get(
            '/accounting/ajax/gastos-alegra/tesoreria-notificaciones-poll',
            {'since_ts': '1970-01-01T00:00:00+00:00'},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['enabled'])
        self.assertGreaterEqual(body['count'], 1)
