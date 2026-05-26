from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from unittest.mock import patch
import json

from accounting.gasto_aprobacion import (
    aplicar_aprobacion_automatica_alegra_saldo_cero,
    eliminar_gasto_alegra_pendiente_asignacion,
    aprobar_gasto_alegra,
    asignar_gasto_alegra,
    reasignar_gasto_alegra,
    sugerencias_asignacion_gasto_alegra,
    empresa_config_sin_aprobador,
    normalizar_alegra_bill_id,
    normalizar_id_tercero,
    parse_aprobador_user_id_opcional,
    parse_valor_entero,
    usuario_es_aprobador_gasto,
    validar_gasto_sin_aprobador,
)
from accounting.models import Facturas, GastoAprobador
from andinasoft.models import empresas

User = get_user_model()


class GastoAprobacionTests(TestCase):
    def setUp(self):
        self.empresa = empresas.objects.create(
            Nit='900000001',
            nombre='Empresa Test Alegra',
            alegra_enabled=True,
        )
        self.contable = User.objects.create_user('contable', password='x')
        self.aprobador = User.objects.create_user('aprobador', password='x')
        GastoAprobador.objects.create(user=self.aprobador, empresa=self.empresa, activo=True)
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

    def test_normalizar_id_tercero(self):
        self.assertEqual(normalizar_id_tercero('901234567'), '901234567')
        with self.assertRaises(ValueError):
            normalizar_id_tercero('90.123.456-7')
        with self.assertRaises(ValueError):
            normalizar_id_tercero('')

    def test_normalizar_alegra_bill_id(self):
        self.assertEqual(
            normalizar_alegra_bill_id('901018375', '12345', es_radicado_manual=True),
            '901018375:journal:12345',
        )
        self.assertEqual(
            normalizar_alegra_bill_id('901018375', '28', es_radicado_manual=False),
            '901018375:28',
        )
        with self.assertRaises(ValueError):
            normalizar_alegra_bill_id('901018375', '901018375:28')
        with self.assertRaises(ValueError):
            normalizar_alegra_bill_id('901018375', 'journal:28', es_radicado_manual=True)

    def test_parse_alegra_journal_id_for_api(self):
        from alegra_integration.bill_mapping import parse_alegra_journal_id_for_api

        self.assertEqual(
            parse_alegra_journal_id_for_api('901018375:journal:28'),
            ('901018375', '28'),
        )
        self.assertEqual(parse_alegra_journal_id_for_api('901018375:34'), (None, None))

    def test_parse_valor_entero(self):
        self.assertEqual(parse_valor_entero('1500000'), 1500000)
        self.assertEqual(parse_valor_entero('1,500,000'), 1500000)
        self.assertEqual(parse_valor_entero('1.500.000'), 1500000)
        with self.assertRaises(ValueError):
            parse_valor_entero('')
        with self.assertRaises(ValueError):
            parse_valor_entero('0')

    def test_usuario_es_aprobador(self):
        self.assertTrue(usuario_es_aprobador_gasto(self.aprobador, self.empresa.Nit))
        self.assertFalse(usuario_es_aprobador_gasto(self.contable, self.empresa.Nit))

    def test_parse_aprobador_opcional(self):
        self.assertIsNone(parse_aprobador_user_id_opcional(None))
        self.assertIsNone(parse_aprobador_user_id_opcional(''))
        self.assertIsNone(parse_aprobador_user_id_opcional(0))
        self.assertEqual(parse_aprobador_user_id_opcional(self.aprobador.pk), self.aprobador.pk)

    def test_empresa_sin_tope_no_permite_sin_aprobador(self):
        cfg = empresa_config_sin_aprobador(self.empresa)
        self.assertFalse(cfg['permite_sin_aprobador'])
        with self.assertRaises(ValueError):
            validar_gasto_sin_aprobador(self.empresa, 1000)

    def test_validar_gasto_sin_aprobador_supera_tope(self):
        self.empresa.alegra_gasto_max_sin_aprobador = 50_000
        self.empresa.save(update_fields=['alegra_gasto_max_sin_aprobador'])
        with self.assertRaises(ValueError) as ctx:
            validar_gasto_sin_aprobador(self.empresa, 100_000)
        self.assertIn('supera', str(ctx.exception).lower())

    def test_aprobacion_automatica_saldo_cero(self):
        self.factura.valor = 0
        self.factura.pago_neto = 0
        self.factura.save(update_fields=['valor', 'pago_neto'])
        ok = aplicar_aprobacion_automatica_alegra_saldo_cero(self.factura, self.contable)
        self.assertTrue(ok)
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.gasto_aprobado)
        self.assertEqual(self.factura.gasto_aprobacion_estado, Facturas.GASTO_APROB_APROBADO)
        self.assertIsNotNone(self.factura.gasto_aprobado_en)

    def test_aprobacion_automatica_saldo_cero_no_aplica_con_pago(self):
        ok = aplicar_aprobacion_automatica_alegra_saldo_cero(self.factura, self.contable)
        self.assertFalse(ok)
        self.factura.refresh_from_db()
        self.assertFalse(self.factura.gasto_aprobado)

    @patch('accounting.gasto_aprobacion.consultar_pago_neto_canje_alegra')
    def test_asignar_es_canje_pago_neto_cero_auto_aprobado(self, mock_canje):
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        self.factura.alegra_bill_id = f'{self.empresa.pk}:43'
        self.factura.alegra_document_type = 'bill'
        self.factura.save(update_fields=['alegra_bill_id', 'alegra_document_type'])
        mock_canje.return_value = {
            'bill_id': '43',
            'balance': 0,
            'totalPaid': 4039466,
            'total': 4450893,
            'status': 'closed',
            'pago_neto': 0,
            'pago_neto_anterior': 4039466,
        }

        asignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MEDELLIN',
            aprobador_user_id=self.aprobador.pk,
            es_canje=True,
        )
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.gasto_es_canje)
        self.assertEqual(self.factura.pago_neto, 0)
        self.assertTrue(self.factura.gasto_aprobado)
        self.assertEqual(self.factura.gasto_aprobacion_estado, Facturas.GASTO_APROB_APROBADO)
        self.assertIsNone(self.factura.gasto_aprobador_asignado_id)

    def test_sugerencias_incluye_es_canje(self):
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        prev = Facturas.objects.create(
            empresa=self.empresa,
            nrofactura='F-PREV',
            idtercero='123',
            nombretercero='Proveedor SA',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=50000,
            pago_neto=0,
            origen='Alegra',
            oficina='MEDELLIN',
            gasto_es_canje=True,
            gasto_aprobacion_estado=Facturas.GASTO_APROB_APROBADO,
            gasto_aprobado=True,
            gasto_asignado_en=timezone.now(),
        )
        data = sugerencias_asignacion_gasto_alegra(
            self.empresa.pk, '123', exclude_pk=self.factura.pk,
        )
        self.assertTrue(data['sugerencia']['es_canje'])
        self.assertTrue(data['historial'][0]['es_canje'])

    def test_eliminar_pendiente_asignacion(self):
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        self.factura.alegra_bill_id = f'{self.empresa.pk}:99'
        self.factura.save(update_fields=['alegra_bill_id'])
        pk = self.factura.pk
        resumen = eliminar_gasto_alegra_pendiente_asignacion(
            self._request(self.contable),
            factura=self.factura,
        )
        self.assertEqual(resumen['pk'], pk)
        self.assertFalse(Facturas.objects.filter(pk=pk).exists())

    def test_eliminar_rechaza_si_tiene_pagos(self):
        from django.contrib.auth.models import Group
        from accounting.models import Pagos
        from andinasoft.models import cuentas_pagos

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        cuenta = cuentas_pagos.objects.create(
            nro_cuentacontable='11100501',
            cuentabanco='transfer',
            nit_empresa=self.empresa,
        )
        Pagos.objects.create(
            nroradicado=self.factura,
            valor=1000,
            usuario=self.contable,
            fecha_pago='2026-05-01',
            empresa=self.empresa,
            cuenta=cuenta,
        )
        with self.assertRaises(ValueError):
            eliminar_gasto_alegra_pendiente_asignacion(
                self._request(self.contable),
                factura=self.factura,
            )

    def test_asignar_sin_aprobador_auto_aprobado(self):
        from django.contrib.auth.models import Group
        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        self.empresa.alegra_gasto_max_sin_aprobador = 500_000
        self.empresa.save(update_fields=['alegra_gasto_max_sin_aprobador'])

        asignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MEDELLIN',
            aprobador_user_id=None,
        )
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.oficina, 'MEDELLIN')
        self.assertTrue(self.factura.gasto_aprobado)
        self.assertEqual(self.factura.gasto_aprobacion_estado, Facturas.GASTO_APROB_APROBADO)
        self.assertIsNone(self.factura.gasto_aprobador_asignado_id)
        self.assertEqual(self.factura.gasto_aprobado_por, self.contable)

    def test_flujo_asignar_y_aprobar(self):
        from django.contrib.auth.models import Group
        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)

        asignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MONTERIA',
            aprobador_user_id=self.aprobador.pk,
            comentario_contable='Revisar soporte',
        )
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.oficina, 'MONTERIA')
        self.assertEqual(self.factura.gasto_aprobacion_estado, Facturas.GASTO_APROB_PENDIENTE_APROBACION)
        self.assertEqual(self.factura.gasto_aprobador_asignado, self.aprobador)

        aprobar_gasto_alegra(self._request(self.aprobador), factura=self.factura)
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.gasto_aprobado)
        self.assertEqual(self.factura.gasto_aprobacion_estado, Facturas.GASTO_APROB_APROBADO)

    @patch('accounting.gasto_n8n_notify.notify_gasto_pendiente_aprobacion')
    def test_reasignar_oficina_y_aprobador_dispara_n8n(self, mock_notify):
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        otro = User.objects.create_user('aprobador2', password='x')
        GastoAprobador.objects.create(user=otro, empresa=self.empresa, activo=True)

        asignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MONTERIA',
            aprobador_user_id=self.aprobador.pk,
        )
        mock_notify.reset_mock()

        reasignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MEDELLIN',
            aprobador_user_id=otro.pk,
            comentario_contable='Corrección de oficina',
        )
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.oficina, 'MEDELLIN')
        self.assertEqual(self.factura.gasto_aprobador_asignado, otro)
        self.assertEqual(
            self.factura.gasto_aprobacion_estado,
            Facturas.GASTO_APROB_PENDIENTE_APROBACION,
        )
        mock_notify.assert_called_once_with(
            self.factura.pk,
            assigned_by_user_id=self.contable.pk,
        )

    @patch('accounting.gasto_n8n_notify.notify_gasto_pendiente_aprobacion')
    def test_reasignar_solo_oficina_no_dispara_n8n(self, mock_notify):
        from django.contrib.auth.models import Group

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)

        asignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MONTERIA',
            aprobador_user_id=self.aprobador.pk,
        )
        mock_notify.reset_mock()

        reasignar_gasto_alegra(
            self._request(self.contable),
            factura=self.factura,
            oficina='MEDELLIN',
            aprobador_user_id=self.aprobador.pk,
        )
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.oficina, 'MEDELLIN')
        mock_notify.assert_not_called()

    def test_filtro_alegra_operable(self):
        from django.db.models import Q

        q = Facturas.filtro_alegra_operable()
        pendiente = Facturas.objects.filter(q).filter(pk=self.factura.pk).exists()
        self.assertFalse(pendiente)

        self.factura.gasto_aprobado = True
        self.factura.save(update_fields=['gasto_aprobado'])
        pendiente = Facturas.objects.filter(q).filter(pk=self.factura.pk).exists()
        self.assertTrue(pendiente)

    @patch('accounting.gasto_aprobacion_views.AlegraMCPClient')
    def test_journal_preview_advierte_journal_duplicado(self, client_cls):
        from django.contrib.auth.models import Group
        from accounting.gasto_aprobacion_views import ajax_gastos_alegra_journal_preview
        from accounting.test_journal_cxp import JOURNAL_7

        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)

        self.factura.alegra_bill_id = f'{self.empresa.pk}:journal:7'
        self.factura.alegra_document_type = Facturas.ALEGRA_DOC_JOURNAL
        self.factura.save(update_fields=['alegra_bill_id', 'alegra_document_type'])

        client_cls.return_value.get_journal.return_value = JOURNAL_7

        req = self.factory.get('/', {'empresa': self.empresa.pk, 'journal_id': '7'})
        req.user = self.contable
        resp = ajax_gastos_alegra_journal_preview(req)
        data = json.loads(resp.content)

        self.assertTrue(data['ok'])
        self.assertTrue(data['duplicate_journal'])
        self.assertEqual(data['alegra_bill_id'], f'{self.empresa.pk}:journal:7')
        self.assertEqual(data['radicado_existente']['pk'], self.factura.pk)
        self.assertIn('radicado', data)


@override_settings(N8N_WEBHOOK_GASTO_APROBACION_SECRET='test-secret-n8n')
class WebhookN8nGastoAprobacionTests(TestCase):
    def setUp(self):
        self.empresa = empresas.objects.create(
            Nit='900000002',
            nombre='Empresa Webhook',
            alegra_enabled=True,
        )
        self.contable = User.objects.create_user('contable2', password='x')
        self.aprobador = User.objects.create_user('aprobador2', password='x')
        GastoAprobador.objects.create(user=self.aprobador, empresa=self.empresa, activo=True)
        self.factura = Facturas.objects.create(
            empresa=self.empresa,
            nrofactura='F-WA',
            idtercero='456',
            nombretercero='Proveedor WA',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=50000,
            pago_neto=50000,
            origen='Alegra',
            oficina='MEDELLIN',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
            gasto_aprobador_asignado=self.aprobador,
            gasto_aprobado=False,
        )
        self.factory = RequestFactory()

    def _post_webhook(self, payload, secret='test-secret-n8n'):
        from accounting.gasto_aprobacion_views import webhook_n8n_gasto_aprobacion

        req = self.factory.post(
            '/accounting/webhooks/n8n/gasto-aprobacion',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_ANDINA_WEBHOOK_SECRET=secret,
        )
        return webhook_n8n_gasto_aprobacion(req)

    def test_webhook_aprobar_ok(self):
        resp = self._post_webhook({
            'accion': 'aprobar',
            'radicado': self.factura.pk,
            'aprobador_user_id': self.aprobador.pk,
            'canal': 'WhatsApp',
        })
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertTrue(data['ok'])
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.gasto_aprobado)
        self.assertEqual(self.factura.gasto_aprobacion_estado, Facturas.GASTO_APROB_APROBADO)

    def test_webhook_secret_invalido(self):
        resp = self._post_webhook(
            {'radicado': self.factura.pk, 'aprobador_user_id': self.aprobador.pk},
            secret='wrong',
        )
        self.assertEqual(resp.status_code, 401)

    @override_settings(
        N8N_WEBHOOK_GASTO_APROBACION_SECRET='test-secret-n8n',
        N8N_WEBHOOK_AUTH_TOKEN='n8n-bearer-dl',
        N8N_WEBHOOK_AUTH_PREFIX='Bearer',
    )
    def test_webhook_soporte_pdf_con_bearer(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from accounting.gasto_aprobacion_views import webhook_n8n_gasto_soporte_pdf
        from accounting.gasto_n8n_notify import build_gasto_notification_payload

        self.factura.soporte_radicado.save(
            'test-soporte.pdf',
            SimpleUploadedFile('test-soporte.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        payload = build_gasto_notification_payload(
            self.factura,
            event='gasto_alegra.pendiente_aprobacion',
            trigger='test',
            recipients=[],
        )
        self.assertIn(
            f'/accounting/webhooks/n8n/gastos-alegra/soporte-pdf/{self.factura.pk}',
            payload['factura']['soporte_pdf_url'],
        )

        req = self.factory.get(
            f'/accounting/webhooks/n8n/gastos-alegra/soporte-pdf/{self.factura.pk}',
            HTTP_AUTHORIZATION='Bearer n8n-bearer-dl',
        )
        resp = webhook_n8n_gasto_soporte_pdf(req, self.factura.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        b''.join(resp.streaming_content)

    def test_webhook_soporte_pdf_sin_archivo(self):
        from accounting.gasto_aprobacion_views import webhook_n8n_gasto_soporte_pdf

        req = self.factory.get(
            f'/accounting/webhooks/n8n/gastos-alegra/soporte-pdf/{self.factura.pk}',
            HTTP_X_ANDINA_WEBHOOK_SECRET='test-secret-n8n',
        )
        resp = webhook_n8n_gasto_soporte_pdf(req, self.factura.pk)
        self.assertEqual(resp.status_code, 404)

    @override_settings(
        N8N_WEBHOOK_GASTO_APROBACION_SECRET='test-secret-n8n',
    )
    def test_ajax_soporte_pdf_aprobador(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from accounting.gasto_aprobacion_views import ajax_gastos_alegra_soporte_pdf

        self.factura.gasto_aprobador_asignado = self.aprobador
        self.factura.save(update_fields=['gasto_aprobador_asignado'])
        self.factura.soporte_radicado.save(
            'test-soporte.pdf',
            SimpleUploadedFile('test-soporte.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        req = self.factory.get(
            f'/accounting/ajax/gastos-alegra/soporte-pdf/{self.factura.pk}',
        )
        req.user = self.aprobador
        resp = ajax_gastos_alegra_soporte_pdf(req, self.factura.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        b''.join(resp.streaming_content)

    def test_ajax_soporte_pdf_sin_permiso(self):
        from accounting.gasto_aprobacion_views import ajax_gastos_alegra_soporte_pdf

        otro = User.objects.create_user('otro_pdf', password='x')
        req = self.factory.get(
            f'/accounting/ajax/gastos-alegra/soporte-pdf/{self.factura.pk}',
            HTTP_ACCEPT='application/json',
        )
        req.user = otro
        resp = ajax_gastos_alegra_soporte_pdf(req, self.factura.pk)
        self.assertEqual(resp.status_code, 403)

    @override_settings(
        N8N_WEBHOOK_GASTO_APROBACION_SECRET='test-secret-n8n',
        N8N_WEBHOOK_AUTH_TOKEN='n8n-bearer-dl',
        N8N_WEBHOOK_AUTH_PREFIX='Bearer',
    )
    @patch('accounting.gasto_n8n_notify._attach_soporte_from_alegra', return_value=True)
    @patch('accounting.gasto_n8n_notify._soporte_radicado_legible')
    def test_webhook_soporte_pdf_reintenta_alegra_si_storage_falla(
        self, mock_legible, mock_attach,
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from accounting.gasto_aprobacion_views import webhook_n8n_gasto_soporte_pdf

        self.factura.soporte_radicado.save(
            'test-soporte.pdf',
            SimpleUploadedFile('test-soporte.pdf', b'%PDF-1.4', content_type='application/pdf'),
        )
        mock_legible.side_effect = [False, True]

        req = self.factory.get(
            f'/accounting/webhooks/n8n/gastos-alegra/soporte-pdf/{self.factura.pk}',
            HTTP_AUTHORIZATION='Bearer n8n-bearer-dl',
        )
        resp = webhook_n8n_gasto_soporte_pdf(req, self.factura.pk)
        self.assertEqual(resp.status_code, 200)
        mock_attach.assert_called_once()
        mock_attach.assert_called_with(self.factura, force=True)

    def test_webhook_aprobador_no_asignado(self):
        otro = User.objects.create_user('otro', password='x')
        GastoAprobador.objects.create(user=otro, empresa=self.empresa, activo=True)
        resp = self._post_webhook({
            'radicado': self.factura.pk,
            'aprobador_user_id': otro.pk,
        })
        self.assertEqual(resp.status_code, 403)


class GastoAlegraSugerenciasAsignacionTests(TestCase):
    def setUp(self):
        self.empresa = empresas.objects.create(
            Nit='900000010',
            nombre='Empresa Sugerencias',
            alegra_enabled=True,
        )
        self.contable = User.objects.create_user('contable_sug', password='x')
        self.aprobador = User.objects.create_user('aprobador_sug', password='x')
        GastoAprobador.objects.create(user=self.aprobador, empresa=self.empresa, activo=True)
        from django.contrib.auth.models import Group
        g, _ = Group.objects.get_or_create(name='Contabilidad')
        self.contable.groups.add(g)
        self.factura_pendiente = Facturas.objects.create(
            empresa=self.empresa,
            nrofactura='F-PEND',
            idtercero='901111111',
            nombretercero='Proveedor Hist',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=50000,
            pago_neto=50000,
            origen='Alegra',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
            gasto_aprobado=False,
        )
        self.factura_hist = Facturas.objects.create(
            empresa=self.empresa,
            nrofactura='F-HIST',
            idtercero='901111111',
            nombretercero='Proveedor Hist',
            fechafactura='2026-04-01',
            fechavenc='2026-04-15',
            valor=120000,
            pago_neto=120000,
            origen='Alegra',
            descripcion='Servicios de consultoría mensual',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
            gasto_aprobado=False,
            oficina='MEDELLIN',
        )
        self.factura_hist.gasto_aprobador_asignado = self.aprobador
        self.factura_hist.gasto_asignado_en = timezone.now()
        self.factura_hist.save(update_fields=[
            'gasto_aprobador_asignado', 'gasto_asignado_en', 'oficina',
        ])

    def test_sugerencias_desde_historial_mismo_tercero(self):
        data = sugerencias_asignacion_gasto_alegra(
            self.empresa.Nit,
            '901111111',
            exclude_pk=self.factura_pendiente.pk,
        )
        self.assertEqual(len(data['historial']), 1)
        self.assertEqual(data['historial'][0]['pk'], self.factura_hist.pk)
        self.assertEqual(data['historial'][0]['oficina'], 'MEDELLIN')
        self.assertEqual(data['sugerencia']['oficina'], 'MEDELLIN')
        self.assertEqual(data['sugerencia']['aprobador_id'], self.aprobador.pk)

    def test_sin_historial_sugerencia_vacia(self):
        data = sugerencias_asignacion_gasto_alegra(
            self.empresa.Nit,
            '999999999',
            exclude_pk=self.factura_pendiente.pk,
        )
        self.assertEqual(data['historial'], [])
        self.assertEqual(data['sugerencia']['oficina'], '')
        self.assertIsNone(data['sugerencia']['aprobador_id'])


@override_settings(
    GASTO_APROBACION_LINK_SECRET='test-link-secret',
    GASTO_APROBACION_LINK_MAX_AGE=3600,
)
class GastoAprobacionLinkTests(TestCase):
    def setUp(self):
        self.empresa = empresas.objects.create(
            Nit='900000003',
            nombre='Empresa Link',
            alegra_enabled=True,
        )
        self.aprobador = User.objects.create_user('aprobador3', password='x')
        GastoAprobador.objects.create(user=self.aprobador, empresa=self.empresa, activo=True)
        self.factura = Facturas.objects.create(
            empresa=self.empresa,
            nrofactura='F-LINK',
            idtercero='789',
            nombretercero='Proveedor Link',
            fechafactura='2026-05-01',
            fechavenc='2026-05-15',
            valor=75000,
            pago_neto=75000,
            origen='Alegra',
            oficina='MEDELLIN',
            gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
            gasto_aprobador_asignado=self.aprobador,
            gasto_aprobado=False,
        )
        self.factory = RequestFactory()

    def _link_parts(self):
        from accounting.gasto_aprobacion_link import build_gasto_aprobacion_link_token

        token = build_gasto_aprobacion_link_token(self.factura.pk, self.aprobador.pk)
        path = f'/accounting/gastos-alegra/aprobar-link/{self.factura.pk}/{token}/'
        return path, token

    def test_link_aprobar_ok(self):
        from accounting.gasto_aprobacion_views import gasto_aprobacion_link_aprobar

        path, token = self._link_parts()
        req = self.factory.get(path)
        resp = gasto_aprobacion_link_aprobar(req, self.factura.pk, token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'aprobado correctamente', resp.content)
        self.factura.refresh_from_db()
        self.assertTrue(self.factura.gasto_aprobado)

    def test_link_token_invalido(self):
        from accounting.gasto_aprobacion_views import gasto_aprobacion_link_aprobar

        path, token = self._link_parts()
        req = self.factory.get(path)
        resp = gasto_aprobacion_link_aprobar(req, self.factura.pk, 'token-invalido')
        self.assertEqual(resp.status_code, 403)

    def test_link_idempotente_si_ya_aprobado(self):
        from accounting.gasto_aprobacion_views import gasto_aprobacion_link_aprobar

        self.factura.gasto_aprobado = True
        self.factura.gasto_aprobacion_estado = Facturas.GASTO_APROB_APROBADO
        self.factura.save(update_fields=['gasto_aprobado', 'gasto_aprobacion_estado'])
        path, token = self._link_parts()
        req = self.factory.get(path)
        resp = gasto_aprobacion_link_aprobar(req, self.factura.pk, token)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'ya estaba aprobado', resp.content)

