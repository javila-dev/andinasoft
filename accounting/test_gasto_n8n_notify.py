"""Tests webhooks salientes n8n — gastos Alegra."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import RequestFactory, TestCase, override_settings
from django.test import captureOnCommitCallbacks

from accounting.gasto_aprobacion import asignar_gasto_alegra
from accounting.models import Facturas, GastoAprobador, GastoContableNotificacion
from alegra_integration.webhook_bills import _handle_new_bill, composite_alegra_bill_id
from andinasoft.models import empresas

User = get_user_model()

N8N_SETTINGS = {
    'N8N_ALEGRA_NOTIFICATIONS_ENABLED': True,
    'N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_ASIGNACION': 'http://n8n.test/pendiente-asignacion',
    'N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION': 'http://n8n.test/pendiente-aprobacion',
    'ANDINA_PUBLIC_BASE_URL': 'https://app.test',
    'N8N_WEBHOOK_AUTH_TOKEN': 'test-n8n-token',
    'N8N_WEBHOOK_AUTH_PREFIX': 'Bearer',
}


@override_settings(**N8N_SETTINGS)
class GastoN8nNotifyTests(TestCase):
    def setUp(self):
        self.empresa = empresas.objects.create(
            Nit='900000001',
            nombre='Empresa Test Alegra',
            alegra_enabled=True,
        )
        self.contable = User.objects.create_user(
            'contable', password='x', email='contable@test.co',
        )
        self.aprobador = User.objects.create_user(
            'aprobador', password='x', email='aprobador@test.co',
        )
        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        GastoAprobador.objects.create(
            user=self.aprobador, empresa=self.empresa, activo=True, telefono='573001112233',
        )
        GastoContableNotificacion.objects.create(
            user=self.contable, empresa=self.empresa, activo=True,
        )
        self.factura = Facturas.objects.create(
            empresa=self.empresa,
            nrofactura='F-1',
            idtercero='123',
            nombretercero='Proveedor SA',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=100000,
            pago_neto=100000,
            origen='Alegra',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
            gasto_aprobado=False,
        )
        self.factory = RequestFactory()

    def _request(self, user):
        req = self.factory.get('/')
        req.user = user
        return req

    @patch('accounting.gasto_n8n_notify.requests.post')
    def test_asignar_con_aprobador_dispara_n8n(self, mock_post):
        with captureOnCommitCallbacks(execute=True):
            asignar_gasto_alegra(
                self._request(self.contable),
                factura=self.factura,
                oficina='MEDELLIN',
                aprobador_user_id=self.aprobador.pk,
                comentario_contable='Revisar',
            )
        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertEqual(url, N8N_SETTINGS['N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION'])
        self.assertEqual(
            (kwargs.get('headers') or {}).get('Authorization'),
            'Bearer test-n8n-token',
        )
        payload = kwargs['json']
        self.assertEqual(payload['event'], 'gasto_alegra.pendiente_aprobacion')
        self.assertEqual(len(payload['recipients']), 1)
        self.assertEqual(payload['recipients'][0]['email'], 'aprobador@test.co')
        self.assertEqual(payload['recipients'][0]['telefono'], '573001112233')
        self.assertEqual(payload['assigned_by']['user_id'], self.contable.pk)
        self.assertIn('https://app.test/accounting/gastos-alegra/aprobar/', payload['links']['aprobar'])

    @patch('accounting.gasto_n8n_notify.requests.post')
    def test_asignar_sin_aprobador_no_dispara_aprobacion(self, mock_post):
        self.empresa.alegra_gasto_max_sin_aprobador = 500_000
        self.empresa.save(update_fields=['alegra_gasto_max_sin_aprobador'])
        with captureOnCommitCallbacks(execute=True):
            asignar_gasto_alegra(
                self._request(self.contable),
                factura=self.factura,
                oficina='MEDELLIN',
                aprobador_user_id=None,
            )
        mock_post.assert_not_called()

    @patch('accounting.gasto_n8n_notify.requests.post')
    def test_sin_destinatarios_contables_no_post(self, mock_post):
        GastoContableNotificacion.objects.all().delete()
        bill = {
            'id': '99',
            'client': {'name': 'Prov', 'identification': '800'},
            'total': 50000,
            'state': 'open',
            'numberTemplate': {'number': 'F-99'},
        }
        composite = composite_alegra_bill_id(self.empresa.pk, '99')
        with captureOnCommitCallbacks(execute=True):
            _handle_new_bill(self.empresa, composite, bill)
        mock_post.assert_not_called()

    @patch('accounting.gasto_n8n_notify.requests.post')
    def test_new_bill_created_dispara_asignacion(self, mock_post):
        bill = {
            'id': '42',
            'client': {'name': 'Proveedor', 'identification': '900111'},
            'total': 250000,
            'state': 'open',
            'numberTemplate': {'number': 'FCII42'},
            'date': '2026-05-04',
            'dueDate': '2026-05-04',
        }
        composite = composite_alegra_bill_id(self.empresa.pk, '42')
        with captureOnCommitCallbacks(execute=True):
            result = _handle_new_bill(self.empresa, composite, bill)
        self.assertTrue(result.get('created'))
        mock_post.assert_called_once()
        url = mock_post.call_args[0][0]
        payload = mock_post.call_args[1]['json']
        self.assertEqual(url, N8N_SETTINGS['N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_ASIGNACION'])
        self.assertEqual(payload['event'], 'gasto_alegra.pendiente_asignacion')
        self.assertEqual(payload['trigger'], 'webhook_new_bill')
        self.assertEqual(payload['recipients'][0]['email'], 'contable@test.co')
        self.assertEqual(payload['alegra_bill']['id'], '42')

    @patch('accounting.gasto_n8n_notify.requests.post')
    @patch('alegra_integration.webhook_bills._schedule_bill_pdf_download')
    def test_new_bill_idempotent_no_dispara(self, _pdf, mock_post):
        self.factura.alegra_bill_id = composite_alegra_bill_id(self.empresa.pk, '1')
        self.factura.gasto_aprobacion_estado = Facturas.GASTO_APROB_PENDIENTE_ASIGNACION
        self.factura.save(update_fields=['alegra_bill_id', 'gasto_aprobacion_estado'])
        bill = {'id': '1', 'client': {'name': 'X', 'identification': '1'}, 'total': 1}
        with captureOnCommitCallbacks(execute=True):
            result = _handle_new_bill(
                self.empresa,
                self.factura.alegra_bill_id,
                bill,
            )
        self.assertTrue(result.get('idempotent'))
        mock_post.assert_not_called()

    @patch('accounting.gasto_n8n_notify.requests.post')
    @patch('alegra_integration.webhook_bills._schedule_bill_pdf_download')
    def test_idempotent_entrada_flujo_asignacion_si_dispara(self, _pdf, mock_post):
        self.factura.alegra_bill_id = composite_alegra_bill_id(self.empresa.pk, '2')
        self.factura.gasto_aprobacion_estado = Facturas.GASTO_APROB_NO_APLICA
        self.factura.save(update_fields=['alegra_bill_id', 'gasto_aprobacion_estado'])
        bill = {'id': '2', 'client': {'name': 'Y', 'identification': '2'}, 'total': 2}
        with captureOnCommitCallbacks(execute=True):
            _handle_new_bill(self.empresa, self.factura.alegra_bill_id, bill)
        mock_post.assert_called_once()
        self.assertEqual(
            mock_post.call_args[1]['json']['event'],
            'gasto_alegra.pendiente_asignacion',
        )


@override_settings(N8N_ALEGRA_NOTIFICATIONS_ENABLED=False)
class GastoN8nNotifyDisabledTests(TestCase):
    @patch('accounting.gasto_n8n_notify.requests.post')
    def test_disabled_no_post(self, mock_post):
        from accounting.gasto_n8n_notify import notify_gasto_pendiente_asignacion

        notify_gasto_pendiente_asignacion(1, trigger='test')
        with captureOnCommitCallbacks(execute=True):
            pass
        mock_post.assert_not_called()
