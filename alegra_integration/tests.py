import datetime
import json
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase

from andinasoft.models import empresas

from alegra_integration.builders import (
    CajaGastoBillBuilder,
    CajaLegalizationJournalBuilder,
    CommissionBuilder,
    ExternalCommissionSupportDocumentBuilder,
    GttSupportDocumentBuilder,
    InternalCommissionAdvanceBuilder,
    ReceiptPaymentBuilder,
)
from alegra_integration.client import AlegraMCPClient
from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError, AlegraBuildError
from accounting.models import gastos_caja


class ResolverStub:
    def bank_account_for_account(self, cuenta):
        return 'bank-1'

    def bank_journal_category_for_account(self, cuenta, *, required=True):
        puc = getattr(cuenta, 'nro_cuentacontable', None)
        if puc in (None, ''):
            if required:
                raise AlegraConfigurationError('sin PUC')
            return None
        return f'cat-{puc}'

    def category_for_code(self, account_code):
        return f'cat-{account_code}'

    def contact_for_cliente(self, cliente_id):
        return f'client-{cliente_id}'

    def contact_for_asesor(self, asesor_id):
        return f'adviser-{asesor_id}'

    def contact_for_empresa(self, empresa_id):
        return f'company-{empresa_id}'

    def cost_center_for_project(self, required=True):
        return 'cc-1'

    def cost_center_for_commission(self, required=False):
        return 'cc-commission-1'

    def cost_center_for_caja(self, caja_id, *, required=False):
        return 'cc-caja-7'

    def numeration(self, document_code):
        return f'num-{document_code}'

    def retention(self, retention_code, required=True):
        return f'ret-{retention_code}'

    def tax_for_impuesto(self, impuesto_id, required=True):
        return f'tax-imp-{impuesto_id}'

    def retention_for_impuesto(self, impuesto_id, required=True):
        return f'ret-imp-{impuesto_id}'

    def category_for_puc_code(self, puc, required=False):
        return None

    def commission_amount_source(self, *, for_tipo, default='net', required=False):
        if for_tipo == 'external':
            return getattr(self, '_amount_source_external', default)
        return getattr(self, '_amount_source_internal', default)

    def receipt_forma_pago_config(self, forma_pago_descripcion, *, required=True):
        return {
            'category_id': getattr(self, '_receipt_debit_id', 'cat-receipt-debit'),
            'intercompany': getattr(self, '_receipt_interco', False),
            'counterparty_nit': getattr(self, '_receipt_interco_nit', ''),
        }

    def receipt_debit_for_forma_pago(self, forma_pago_descripcion, *, required=True):
        return self.receipt_forma_pago_config(forma_pago_descripcion, required=required)['category_id']

    def payment_method(self, local_method, required=True):
        return 'transfer'

    def get(self, *args, **kwargs):
        code = kwargs.get('local_code', '')
        if code == 'commission_expense':
            return 'cat-commission-expense'
        if code == 'commission_debit':
            return 'cat-commission-debit'
        if code == 'commission_credit':
            return 'cat-commission-credit'
        if code == 'caja_cxp':
            return 'cat-cxp'
        if code == 'caja_credit':
            return 'cat-caja-credit'
        if code == 'caja_expense' and kwargs.get('local_model') == 'accounting.conceptos_legalizacion':
            return 'cat-caja-expense-mapped'
        if code == 'default_cxp':
            return 'cat-default-cxp'
        return 'mapped-id'

    def contact_by_identification(self, ident, **kwargs):
        return f'contact-{ident}'

    def contact_for_partner(self, partner_pk, *, required=True):
        return f'contact-{partner_pk}'

    def category_for_puc_code(self, account_code, **kwargs):
        return f'cat-puc-{account_code}'


class BuilderTests(SimpleTestCase):
    def setUp(self):
        self.empresa = SimpleNamespace(pk='901018375')
        self.proyecto = SimpleNamespace(pk='Oasis')
        self.resolver = ResolverStub()

    @patch('alegra_integration.builders.Recaudos')
    @patch('alegra_integration.builders.consecutivos')
    @patch('alegra_integration.builders.formas_pago')
    @patch('alegra_integration.builders.cuentas_pagos')
    @patch('alegra_integration.builders.MappingResolver')
    @patch('alegra_integration.builders.clientes')
    def test_receipt_payment_payload_uses_mapped_ids(self, clientes_model, resolver_cls, cuentas_pagos_model, formas_pago, consecutivos, recaudos):
        resolver_cls.return_value = self.resolver
        clientes_model.objects.filter.return_value.first.return_value = SimpleNamespace(nombrecompleto='Titular Uno')
        cuentas_pagos_model.objects.filter.return_value.first.return_value = None
        formas_pago.objects.using.return_value.filter.return_value.first.return_value = SimpleNamespace(
            cuenta_asociada_id=12,
            cuenta_asociada=SimpleNamespace(pk=12),
        )
        consecutivos.objects.using.return_value.get.return_value = SimpleNamespace(
            cuenta_capital='130505',
            cuenta_intcte='421005',
            cuenta_inmora='421010',
        )
        recaudos.objects.using.return_value.filter.return_value.aggregate.return_value = {
            'capital': Decimal('100000'),
            'interescte': Decimal('2000'),
            'interesmora': Decimal('300'),
        }
        receipt = SimpleNamespace(
            pk=9,
            valor=Decimal('102300'),
            idtercero='123',
            idadjudicacion='ADJ-2024-001',
            numrecibo='RC-1',
            fecha=datetime.date(2026, 4, 1),
            fecha_pago=datetime.date(2026, 4, 2),
            formapago='TRANSFERENCIA',
            concepto='ABONO',
        )
        receipt.info_adj = lambda: SimpleNamespace(idtercero1='123', idtercero2='999', idtercero3='', idtercero4='')

        built = ReceiptPaymentBuilder(self.empresa, self.proyecto).build(receipt)

        self.assertEqual(built.operation, 'accounting__createJournal')
        self.assertEqual(built.payload['numberTemplate'], 'num-receipt_cash')
        self.assertEqual(built.payload['status'], 'open')
        self.assertEqual(built.payload['reference'], 'RC-Oasis-RC-1')
        self.assertIn('ADJ ADJ-2024-001', built.payload['observations'])
        self.assertIn('F.pago 2026-04-02', built.payload['observations'])
        self.assertEqual(built.payload['date'], '2026-04-01')
        self.assertEqual(len(built.payload['entries']), 3)
        self.assertEqual(built.payload['entries'][0]['debit'], 102300.0)
        self.assertEqual(built.payload['entries'][0]['credit'], 0)
        self.assertEqual(built.payload['entries'][0]['id'], 'cat-receipt-debit')
        self.assertEqual(built.payload['entries'][0]['client'], 'client-123')
        self.assertEqual(built.payload['entries'][1]['credit'], 51150.0)
        self.assertEqual(built.payload['entries'][1]['debit'], 0)
        self.assertEqual(built.payload['entries'][1]['client'], 'client-123')
        self.assertEqual(built.payload['entries'][2]['credit'], 51150.0)
        self.assertEqual(built.payload['entries'][2]['client'], 'client-999')

    @patch('alegra_integration.builders.MappingResolver')
    @patch('alegra_integration.builders.clientes')
    def test_receipt_debit_uses_forma_pago_mapping(self, clientes_model, resolver_cls):
        class FormaResolver(ResolverStub):
            def receipt_forma_pago_config(self, forma_pago_descripcion, *, required=True):
                return {
                    'category_id': 'cat-dataphone-bridge',
                    'intercompany': False,
                    'counterparty_nit': '',
                }

        resolver_cls.return_value = FormaResolver()
        clientes_model.objects.filter.return_value.first.return_value = SimpleNamespace(nombrecompleto='Titular')

        receipt = SimpleNamespace(
            pk=10989,
            valor=Decimal('500000'),
            idtercero='123',
            numrecibo='RC-99',
            fecha=datetime.date(2026, 5, 1),
            fecha_pago=datetime.date(2026, 5, 1),
            formapago='Datafono',
            concepto='',
        )
        receipt.info_adj = lambda: SimpleNamespace(idtercero1='123', idtercero2='', idtercero3='', idtercero4='')

        built = ReceiptPaymentBuilder(self.empresa, self.proyecto).build(receipt)

        self.assertEqual(built.payload['entries'][0]['id'], 'cat-dataphone-bridge')
        self.assertEqual(built.payload['__local']['forma_pago'], 'Datafono')
        self.assertEqual(built.payload['entries'][0]['client'], 'client-123')

    @patch('alegra_integration.builders.MappingResolver')
    @patch('alegra_integration.builders.clientes')
    def test_receipt_intercompany_debit_uses_empresa_contact(self, clientes_model, resolver_cls):
        class IntercoFormaResolver(ResolverStub):
            def receipt_forma_pago_config(self, forma_pago_descripcion, *, required=True):
                return {
                    'category_id': 'cat-interco-cxc',
                    'intercompany': True,
                    'counterparty_nit': '900999111',
                }

        resolver_cls.return_value = IntercoFormaResolver()
        clientes_model.objects.filter.return_value.first.return_value = SimpleNamespace(nombrecompleto='Titular')

        receipt = SimpleNamespace(
            pk=10990,
            valor=Decimal('500000'),
            idtercero='123',
            numrecibo='RC-100',
            fecha=datetime.date(2026, 5, 1),
            fecha_pago=datetime.date(2026, 5, 1),
            formapago='TRANSFERENCIA INTERCO',
            concepto='',
        )
        receipt.info_adj = lambda: SimpleNamespace(idtercero1='123', idtercero2='', idtercero3='', idtercero4='')

        built = ReceiptPaymentBuilder(self.empresa, self.proyecto).build(receipt)

        self.assertEqual(built.payload['entries'][0]['id'], 'cat-interco-cxc')
        self.assertEqual(built.payload['entries'][0]['client'], 'company-900999111')
        self.assertNotEqual(built.payload['entries'][0]['client'], 'client-123')
        self.assertIn('INTERCO 900999111', built.payload['observations'])
        self.assertEqual(built.payload['__local']['intercompany'], True)
        self.assertEqual(built.payload['entries'][1]['client'], 'client-123')

    @patch('alegra_integration.builders.asesores')
    @patch('alegra_integration.builders.consecutivos')
    @patch('alegra_integration.builders.MappingResolver')
    def test_internal_commission_builds_journal_advance(self, resolver_cls, consecutivos, asesores_model):
        resolver_cls.return_value = self.resolver
        asesor = SimpleNamespace(
            pk='111', nombre='ASESOR INTERNO', tipo_asesor='Interno', empresa_contable_id='901018375',
        )
        asesores_model.objects.get.return_value = asesor
        consecutivos.objects.using.return_value.get.return_value = SimpleNamespace(
            cuenta_aux1='133005',
            cuenta_inmora='220505',
        )
        commission = SimpleNamespace(
            idgestor='111',
            id_pago=77,
            pagoneto=Decimal('50000'),
            fecha=datetime.date(2026, 4, 3),
        )

        built = CommissionBuilder(self.empresa, self.proyecto).build(commission)

        self.assertEqual(built.operation, 'accounting__createJournal')
        self.assertEqual(built.document_type, 'commission_internal_advance')
        self.assertEqual(built.payload['numberTemplate'], 'num-commission_journal')
        self.assertEqual(built.payload['status'], 'open')
        self.assertNotIn('idNumeration', built.payload)
        self.assertEqual(built.payload['entries'][0]['debit'], 50000.0)
        self.assertEqual(built.payload['entries'][0]['id'], 'cat-commission-debit')
        self.assertEqual(built.payload['entries'][0]['client'], 'adviser-111')
        self.assertEqual(built.payload['entries'][1]['credit'], 50000.0)
        self.assertEqual(built.payload['entries'][1]['id'], 'cat-commission-credit')
        self.assertEqual(built.payload['entries'][0]['costCenter'], {'id': 'cc-commission-1'})
        self.assertEqual(built.payload['entries'][1]['costCenter'], {'id': 'cc-commission-1'})

    @patch('alegra_integration.builders.asesores')
    def test_commission_rejects_asesor_other_empresa(self, asesores_model):
        asesor = SimpleNamespace(
            pk='111', nombre='ASESOR', tipo_asesor='Interno', empresa_contable_id='900993044',
        )
        asesores_model.objects.get.return_value = asesor
        asesores_model.EMPRESA_CONTABLE_DEFAULT = '901018375'
        commission = SimpleNamespace(idgestor='111', id_pago=77)
        with self.assertRaises(AlegraBuildError) as ctx:
            CommissionBuilder(self.empresa, self.proyecto).build(commission)
        self.assertIn('900993044', str(ctx.exception))

    @patch('alegra_integration.builders.consecutivos')
    def test_external_commission_builds_support_document(self, consecutivos):
        self.resolver._amount_source_external = 'gross'
        consecutivos.objects.using.return_value.get.return_value = SimpleNamespace(cuenta_capital='529505')
        asesor = SimpleNamespace(pk='222', nombre='ASESOR EXTERNO', tipo_asesor='Externo')
        commission = SimpleNamespace(
            idgestor='222',
            id_pago=88,
            idadjudicacion='ADJ1',
            comision=Decimal('120000'),
            pagoneto=Decimal('106800'),
            retefuente=Decimal('13200'),
            fecha=datetime.date(2026, 4, 4),
        )

        built = ExternalCommissionSupportDocumentBuilder(self.empresa, self.proyecto, self.resolver).build(commission, asesor)

        self.assertEqual(built.operation, 'POST /bills')
        self.assertEqual(built.payload['provider']['id'], 'adviser-222')
        self.assertEqual(built.payload['numberTemplate'], {'id': 'num-commission_support_document'})
        self.assertEqual(built.payload['purchases']['categories'][0]['id'], 'cat-commission-expense')
        self.assertEqual(built.payload['purchases']['categories'][0]['price'], 120000.0)
        self.assertEqual(built.payload['__local']['amount_mode'], 'gross')
        self.assertEqual(built.payload['costCenter'], {'id': 'cc-commission-1'})
        self.assertEqual(built.payload['retentions'][0]['id'], 'ret-commission_retefuente')
        self.assertEqual(built.payload['retentions'][0]['amount'], 12000.0)

    @patch('alegra_integration.builders.consecutivos')
    def test_external_commission_retefuente_ten_percent_of_gross(self, consecutivos):
        """Retefuente = 10% del bruto enviado, sin depender de retefuente/provision del SP."""
        self.resolver._amount_source_external = 'gross'
        consecutivos.objects.using.return_value.get.return_value = SimpleNamespace(cuenta_capital='529505')
        asesor = SimpleNamespace(pk='222', nombre='ASESOR EXTERNO', tipo_asesor='Externo')
        commission = SimpleNamespace(
            idgestor='222',
            id_pago=10052,
            idadjudicacion='ADJ58',
            comision=Decimal('265125'),
            pagoneto=Decimal('238612'),
            retefuente=Decimal('13688'),
            provision=Decimal('26513'),
            fecha=datetime.date(2026, 5, 28),
        )

        built = ExternalCommissionSupportDocumentBuilder(self.empresa, self.proyecto, self.resolver).build(commission, asesor)

        self.assertEqual(built.payload['purchases']['categories'][0]['price'], 265125.0)
        self.assertEqual(built.payload['retentions'][0]['amount'], 26513.0)
        self.assertEqual(built.payload['__local']['retefuente'], 26513.0)

    @patch('alegra_integration.builders.consecutivos')
    def test_external_commission_net_omits_retentions(self, consecutivos):
        self.resolver._amount_source_external = 'net'
        consecutivos.objects.using.return_value.get.return_value = SimpleNamespace(cuenta_capital='529505')
        asesor = SimpleNamespace(pk='222', nombre='ASESOR EXTERNO', tipo_asesor='Externo')
        commission = SimpleNamespace(
            idgestor='222',
            id_pago=89,
            idadjudicacion='',
            comision=Decimal('120000'),
            pagoneto=Decimal('106800'),
            retefuente=Decimal('13200'),
            fecha=datetime.date(2026, 4, 5),
        )

        built = ExternalCommissionSupportDocumentBuilder(self.empresa, self.proyecto, self.resolver).build(commission, asesor)

        self.assertEqual(built.payload['purchases']['categories'][0]['price'], 106800.0)
        self.assertNotIn('retentions', built.payload)
        self.assertEqual(built.payload['__local']['amount_mode'], 'net')

    @patch('alegra_integration.builders.timezone')
    @patch('alegra_integration.builders.consecutivos')
    def test_gtt_builds_support_document(self, consecutivos, timezone_mock):
        timezone_mock.localdate.return_value = datetime.date(2026, 6, 2)
        def _get(*a, **kw):
            code = kw.get('local_code', '')
            return {
                'gtt_expense': 'cat-gtt-expense',
                'gtt_cxp': 'cat-gtt-cxp',
            }.get(code, 'mapped-id')
        self.resolver.get = _get
        asesor = SimpleNamespace(pk='333', nombre='ASESOR GTT', tipo_asesor='Externo')
        gtt = SimpleNamespace(
            pk=10,
            proyecto='Oasis',
            fecha_desde=datetime.date(2026, 4, 1),
            fecha_hasta=datetime.date(2026, 4, 7),
            estado='Aprobado',
        )
        detalle = SimpleNamespace(pk=55, valor=112500, gtt=gtt, asesor=asesor)

        built = GttSupportDocumentBuilder(self.empresa, self.proyecto, self.resolver).build(detalle, gtt, asesor)

        self.assertEqual(built.operation, 'POST /bills')
        self.assertEqual(built.document_type, 'gtt_support')
        self.assertEqual(built.payload['provider']['id'], 'adviser-333')
        self.assertEqual(built.payload['numberTemplate'], {'id': 'num-gtt_support_document'})
        self.assertEqual(built.payload['date'], '2026-06-02')
        self.assertEqual(built.payload['dueDate'], '2026-06-02')
        self.assertEqual(built.payload['purchases']['categories'][0]['price'], 112500.0)
        self.assertEqual(built.local_key, 'gtt:Oasis:10:55')


class BillPdfExtractionTests(SimpleTestCase):
    """Extractor de URL de PDF en JSON de GET /bills (alegra_integration.bill_pdf)."""

    def _extract(self, bill_data):
        from alegra_integration.bill_pdf import _extract_pdf_url

        return _extract_pdf_url(bill_data)

    def test_top_level_url(self):
        self.assertEqual(
            self._extract({'url': 'https://api.alegra.com/api/v1/files/bill.pdf'}),
            'https://api.alegra.com/api/v1/files/bill.pdf',
        )

    def test_nested_stamp_public_url(self):
        payload = {
            'stamp': {
                'issuer': {
                    'certificate': {
                        'publicURL': 'https://files.alegra.com/stamp/cert.pdf',
                    }
                }
            }
        }
        self.assertEqual(self._extract(payload), 'https://files.alegra.com/stamp/cert.pdf')

    def test_stamp_files_deep_nesting(self):
        payload = {
            'stampFiles': [
                {
                    'type': 'PDF',
                    'resource': {'link': 'https://cdn.example.com/docs/electronic.pdf'},
                }
            ]
        }
        self.assertEqual(self._extract(payload), 'https://cdn.example.com/docs/electronic.pdf')

    def test_attachments_array_prefers_pdf(self):
        payload = {
            'attachments': [
                {'id': '1', 'name': 'scan.pdf', 'url': 'https://alegra.files.com/a/scan.pdf'},
                {'id': '2', 'name': 'thumb.jpg', 'url': 'https://alegra.files.com/a/thumb.jpg'},
            ]
        }
        self.assertEqual(self._extract(payload), 'https://alegra.files.com/a/scan.pdf')

    def test_pick_prefers_pdf_looking_url_when_multiple(self):
        payload = {
            'stampFiles': [
                {
                    'preview': 'https://app.alegra.com/preview',
                    'download': 'https://storage.com/x/document.pdf?token=abc',
                }
            ]
        }
        self.assertEqual(self._extract(payload), 'https://storage.com/x/document.pdf?token=abc')

    def test_s3_style_url_without_alegra_domain(self):
        """Si no hay filtro .pdf/api/files, el pool completo de candidatos sigue funcionando."""
        payload = {
            'attachments': [
                {'url': 'https://my-bucket.s3.amazonaws.com/invoices/99.pdf'},
            ]
        }
        self.assertEqual(
            self._extract(payload),
            'https://my-bucket.s3.amazonaws.com/invoices/99.pdf',
        )

    def test_returns_none_when_no_http_strings(self):
        self.assertIsNone(
            self._extract(
                {
                    'id': 1,
                    'attachments': [{'id': '42', 'name': 'x.pdf'}],
                    'stamp': {'status': 'ok'},
                }
            )
        )

    def test_colombia_prefers_named_pdf_in_attachments_over_stampfiles_xml(self):
        """stampFiles es un dict de URLs a XML (S3); el PDF representación va en attachments."""
        payload = {
            'stampFiles': {
                'governmentResponseXml': 'https://alegra.s3.amazonaws.com/bucket/gov.xml?token=1',
                'xml': 'https://alegra.s3.amazonaws.com/bucket/x.xml?token=2',
            },
            'attachments': [
                {
                    'id': 8,
                    'name': 'ad08001443550072600327559.xml',
                    'url': 'https://cdn3.alegra.com/a.xml?Expires=1',
                },
                {
                    'id': 9,
                    'name': 'ad08001443550072600327559.pdf',
                    'url': 'https://cdn3.alegra.com/b.pdf?Expires=2&Signature=x',
                },
            ],
        }
        self.assertEqual(self._extract(payload), 'https://cdn3.alegra.com/b.pdf?Expires=2&Signature=x')

    def test_only_xml_urls_score_negative_returns_none(self):
        self.assertIsNone(
            self._extract(
                {
                    'stampFiles': {
                        'xml': 'https://alegra.s3.amazonaws.com/application/stamp-files/colombia/1.xml?q=1',
                    },
                }
            )
        )


class ClientTests(SimpleTestCase):
    def test_client_requires_enabled_company(self):
        empresa = SimpleNamespace(pk='1', alegra_enabled=False, alegra_token='token')
        with self.assertRaises(AlegraConfigurationError):
            AlegraMCPClient(empresa)

    def test_client_raises_on_http_error(self):
        empresa = SimpleNamespace(pk='1', alegra_enabled=True, alegra_token='token')
        client = AlegraMCPClient(empresa)
        response = Mock(status_code=400)
        response.json.return_value = {'message': 'bad request'}

        with self.assertRaises(AlegraClientError):
            client._handle_decoded_response(response, {'message': 'bad request'})

    def test_unwrap_rest_list_accepts_common_wrappers(self):
        empresa = SimpleNamespace(pk='1', alegra_enabled=True, alegra_token='user@test.com:tok')
        client = AlegraMCPClient(empresa)
        plain = [{'id': '1', 'name': 'IVA'}]
        self.assertEqual(client._unwrap_rest_list(plain), plain)
        self.assertEqual(client._unwrap_rest_list({'data': plain}), plain)
        self.assertEqual(client._unwrap_rest_list({'taxes': plain}), plain)
        self.assertEqual(client._unwrap_rest_list({'cost_centers': plain}), plain)
        self.assertEqual(
            client._unwrap_rest_list({'1': {'name': 'IVA', 'percentage': 19}})[0]['id'],
            '1',
        )


class WebhookInboundConsoleFilterTests(TestCase):
    def setUp(self):
        from alegra_integration.models import AlegraWebhookInboundLog

        self.Log = AlegraWebhookInboundLog
        self.Log.objects.create(
            http_method='POST',
            empresa_nit='900111',
            process_status='ok',
            process_detail='created',
            factura_id=10,
            payload={'subject': 'new-bill', 'message': {'bill': {'id': '1'}}},
        )
        self.Log.objects.create(
            http_method='POST',
            empresa_nit='900111',
            process_status='skip',
            process_detail='radicado_not_created',
            payload={'subject': 'new-bill', 'message': {'bill': {'id': '2'}}},
        )
        self.Log.objects.create(
            http_method='GET',
            empresa_nit='900111',
            payload={},
        )

    def test_filter_empresa_and_missing(self):
        from alegra_integration.webhook_inbound_status import queryset_inbound_logs_for_console

        all_posts = queryset_inbound_logs_for_console()
        self.assertEqual(all_posts.count(), 2)

        by_empresa = queryset_inbound_logs_for_console(empresa='900111')
        self.assertEqual(by_empresa.count(), 2)

        missing = queryset_inbound_logs_for_console(estado='missing')
        self.assertEqual(missing.count(), 1)
        self.assertEqual(missing.first().process_detail, 'radicado_not_created')


class WebhookInboundImportViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(username='whk_tester', password='x')
        self.client.force_login(self.user)
        self.empresa = empresas.objects.create(
            Nit='900222',
            nombre='Empresa prueba',
            alegra_enabled=True,
        )

    def test_import_bill_requires_bill_id(self):
        res = self.client.post(
            '/accounting/alegra/webhooks/inbound/import-bill',
            data=json.dumps({'empresa': '900222'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn('factura', res.json()['detail'].lower())

    @mock.patch('alegra_integration.views.import_factura_from_alegra_bill')
    def test_import_bill_success(self, import_mock):
        import_mock.return_value = {
            'created': True,
            'factura_pk': 55,
            'alegra_bill_id': '900222:9',
            'pdf_saved': True,
            'enriched_fields': [],
        }
        res = self.client.post(
            '/accounting/alegra/webhooks/inbound/import-bill',
            data=json.dumps({'empresa': '900222', 'bill_id': '9'}),
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['created'])
        self.assertEqual(data['factura_pk'], 55)
        import_mock.assert_called_once()


class WebhookInboundLogHelpersTests(SimpleTestCase):
    def test_radicado_status_from_stored_skip(self):
        from types import SimpleNamespace
        from alegra_integration.webhook_inbound_status import radicado_status_display

        log = SimpleNamespace(
            process_status='skip',
            process_detail='missing_empresa',
            factura_id=None,
            empresa_nit='',
        )
        st = radicado_status_display(log, '', '28', 'new-bill')
        self.assertEqual(st['kind'], 'skip')
        self.assertIn('empresa', st['label'].lower())

    def test_resolve_empresa_from_log_field(self):
        from types import SimpleNamespace
        from alegra_integration.webhook_inbound_status import resolve_empresa_nit_for_log

        log = SimpleNamespace(empresa_nit='901018375', query_string='')
        self.assertEqual(resolve_empresa_nit_for_log(log), '901018375')

    def test_radicado_status_created(self):
        from types import SimpleNamespace
        from alegra_integration.webhook_inbound_status import radicado_status_display

        log = SimpleNamespace(
            process_status='ok',
            process_detail='created',
            factura_id=99,
        )
        st = radicado_status_display(log, '900123', '28', 'new-bill')
        self.assertEqual(st['kind'], 'ok')
        self.assertIn('99', st['label'])

    def test_extract_bill_display_fields_from_sample(self):
        from alegra_integration.webhook_inbound_status import extract_bill_display_fields

        bill = {
            'id': '1',
            'total': 142456,
            'balance': 142456,
            'client': {
                'name': 'TELESENTINEL DE ANTIOQUIA LTDA',
                'identification': '800144355',
            },
            'numberTemplate': {'number': 'FCII327559'},
        }
        display = extract_bill_display_fields(bill)
        self.assertEqual(display['tercero_nombre'], 'TELESENTINEL DE ANTIOQUIA LTDA')
        self.assertEqual(display['tercero_nit'], '800144355')
        self.assertEqual(display['nro_factura'], 'FCII327559')
        self.assertEqual(display['valor'], 142456)
        self.assertEqual(display['valor_display'], '$142,456')


class BillMappingEnrichTests(SimpleTestCase):
    def test_descripcion_from_items(self):
        from alegra_integration.bill_mapping import descripcion_from_bill, map_bill_to_factura_fields

        bill = {
            'id': '28',
            'observations': None,
            'items': [{'name': 'Servicio mensual'}, {'name': 'IVA'}],
            'numberTemplate': {'number': 2766},
        }
        self.assertEqual(descripcion_from_bill(bill), 'Servicio mensual, IVA')
        fields = map_bill_to_factura_fields(bill)
        self.assertEqual(fields['descripcion'], 'Servicio mensual, IVA')

    def test_cxp_category_id_from_bill_journal_credit(self):
        from alegra_integration.bill_mapping import cxp_category_id_from_bill

        bill = {
            'journal': {
                'categories': [
                    {'id': '5011', 'operation': 'debit', 'name': 'IVA'},
                    {'id': '5195', 'operation': 'debit', 'name': 'Gasto'},
                    {'id': '5033', 'operation': 'credit', 'name': 'Cuentas por pagar a proveedores'},
                ],
            },
        }
        self.assertEqual(cxp_category_id_from_bill(bill), '5033')

    def test_cxp_category_id_from_bill_provider_debt_to_pay(self):
        from alegra_integration.bill_mapping import cxp_category_id_from_bill

        bill = {
            'provider': {
                'accounting': {
                    'debtToPay': {'id': '8821', 'code': '22050501'},
                },
            },
        }
        self.assertEqual(cxp_category_id_from_bill(bill), '8821')

    def test_cxp_category_id_from_contact_debt_to_pay(self):
        from alegra_integration.bill_mapping import cxp_category_id_from_contact

        self.assertEqual(
            cxp_category_id_from_contact({'accounting': {'debtToPay': {'id': '5033'}}}),
            '5033',
        )

    def test_cxp_category_id_from_bill_minimal_post_response(self):
        """Respuesta típica POST /bills sin journal ni provider.accounting."""
        from alegra_integration.bill_mapping import cxp_category_id_from_bill

        bill = {
            'id': '1',
            'provider': {'id': '1', 'name': 'Coorporación Alegrate', 'identification': '159.549.847'},
            'purchases': {'categories': [{'id': '1', 'name': 'Ajustes de inventario', 'total': 2100}]},
            'total': 2100,
        }
        self.assertEqual(cxp_category_id_from_bill(bill), '')

    def test_fetch_bill_cxp_via_get_journal_fields(self):
        from alegra_integration.services import AlegraIntegrationService

        svc = AlegraIntegrationService()
        bill_data = {
            'id': '1',
            'provider': {'id': '1', 'name': 'Proveedor'},
        }

        class FakeClient:
            def get_bill(self, bill_id, *, fields=None):
                self.bill_fields = fields
                return {
                    'journal': {
                        'categories': [
                            {'id': '5033', 'operation': 'credit', 'name': 'Cuentas por pagar a proveedores'},
                        ],
                    },
                }

            def get_contact(self, contact_id, *, fields=None):
                raise AssertionError('no debe consultar contacto si GET journal trae CxP')

        client = FakeClient()
        cxp_id = svc._fetch_bill_cxp_category_id(client, bill_data=bill_data, alegra_id='1')
        self.assertEqual(cxp_id, '5033')
        self.assertEqual(client.bill_fields, 'journal')

    def test_fetch_bill_cxp_via_contact_after_minimal_post(self):
        from alegra_integration.services import AlegraIntegrationService

        svc = AlegraIntegrationService()
        bill_data = {
            'id': '1',
            'provider': {'id': '1', 'name': 'Proveedor'},
        }

        class FakeClient:
            def get_bill(self, bill_id, *, fields=None):
                self.bill_fields = fields
                return bill_data

            def get_contact(self, contact_id, *, fields=None):
                self.contact_fields = fields
                return {'accounting': {'debtToPay': {'id': '8821', 'code': '22050501'}}}

        client = FakeClient()
        cxp_id = svc._fetch_bill_cxp_category_id(client, bill_data=bill_data, alegra_id='1')
        self.assertEqual(cxp_id, '8821')
        self.assertEqual(client.bill_fields, 'journal')
        self.assertEqual(client.contact_fields, 'accounting')

    def test_descripcion_from_purchases_categories_not_terms(self):
        from alegra_integration.bill_mapping import descripcion_from_bill, bill_descripcion_candidatos

        bill = {
            'id': '28',
            'observations': '',
            'termsConditions': 'Autorización de numeración de documento soporte N° 18764096316941',
            'purchases': {
                'categories': [
                    {'name': 'Comisiones por ventas', 'observations': 'COMISIÓN CASAS DE VERANO'},
                ],
            },
        }
        self.assertEqual(descripcion_from_bill(bill), 'COMISIÓN CASAS DE VERANO')
        cand = bill_descripcion_candidatos(bill)
        self.assertEqual(cand['mapeo_actual'], 'COMISIÓN CASAS DE VERANO')
        self.assertTrue(cand['termsConditions_es_autorizacion_numeracion'])

    def test_stale_descripcion_autorizacion_numeracion(self):
        from alegra_integration.bill_mapping import is_stale_alegra_descripcion

        txt = 'Autorización de numeración de documento soporte N° 18764096316941'
        self.assertTrue(is_stale_alegra_descripcion(txt))
        self.assertFalse(is_stale_alegra_descripcion('COMISIÓN CASAS DE VERANO'))

    def test_enrich_no_overwrite_custom_descripcion(self):
        from types import SimpleNamespace
        from alegra_integration.bill_mapping import enrich_factura_from_bill_data

        fac = SimpleNamespace(
            descripcion='Descripción editada por contador',
            nombretercero='Proveedor X',
            idtercero='123',
            valor=100,
            pago_neto=100,
            fechafactura=None,
            fechavenc=None,
            fechacausa=None,
            nrocausa='X',
            save=lambda update_fields=None: None,
        )
        bill = {
            'id': '1',
            'observations': 'Texto desde Alegra GET',
            'balance': 100,
            'date': '2026-05-15',
            'dueDate': '2026-05-15',
            'client': {'identification': '123', 'name': 'Proveedor X'},
            'numberTemplate': {'number': 'DS1'},
        }
        updated = enrich_factura_from_bill_data(fac, bill)
        self.assertNotIn('descripcion', updated)
        self.assertEqual(fac.descripcion, 'Descripción editada por contador')


class WebhookBillMappingTests(SimpleTestCase):
    def test_valor_usa_balance_cxp_no_total_bruto(self):
        from alegra_integration.bill_mapping import map_bill_to_factura_fields

        bill = {
            'id': '28',
            'date': '2026-05-15',
            'dueDate': '2026-05-15',
            'subtotal': 65000,
            'total': 65000,
            'balance': 58500,
            'client': {'identification': '42786943', 'name': 'LUZ ARLECY RESTREPO RUA'},
            'numberTemplate': {'number': 2766},
        }
        fields = map_bill_to_factura_fields(bill)
        self.assertEqual(fields['valor'], 58500)
        self.assertEqual(fields['pago_neto'], 58500)

    def test_valor_sin_balance_usa_total(self):
        from alegra_integration.bill_mapping import map_bill_to_factura_fields

        bill = {
            'id': '1',
            'date': '2026-05-04',
            'total': 142456,
            'subtotal': 139800,
            'client': {'identification': '800144355', 'name': 'TELESENTINEL'},
        }
        fields = map_bill_to_factura_fields(bill)
        self.assertEqual(fields['valor'], 142456)

    def test_valor_balance_cero(self):
        from alegra_integration.bill_mapping import map_bill_to_factura_fields

        bill = {
            'id': '9',
            'date': '2026-05-01',
            'total': 100000,
            'balance': 0,
            'client': {'identification': '1', 'name': 'X'},
        }
        fields = map_bill_to_factura_fields(bill)
        self.assertEqual(fields['valor'], 0)
        self.assertEqual(fields['pago_neto'], 0)

    def test_pago_neto_sin_balance_usa_total_menos_total_paid(self):
        from alegra_integration.bill_mapping import bill_saldo_por_pagar, map_bill_to_factura_fields

        bill = {
            'id': '43',
            'date': '2026-05-20',
            'total': 4450893,
            'totalPaid': 4450893,
            'client': {'identification': '900727672', 'name': 'Proveedor'},
        }
        self.assertEqual(bill_saldo_por_pagar(bill), 0)
        fields = map_bill_to_factura_fields(bill)
        self.assertEqual(fields['pago_neto'], 0)
        self.assertEqual(fields['valor'], 0)

    def test_pago_neto_usa_balance_no_total(self):
        from alegra_integration.bill_mapping import map_bill_to_factura_fields

        bill = {
            'id': '43',
            'date': '2026-05-20',
            'subtotal': 3740246,
            'total': 4450893,
            'totalPaid': 0,
            'balance': 4039466,
            'client': {'identification': '900727672', 'name': 'SUMAS IGUALES'},
            'numberTemplate': {'number': '43'},
        }
        fields = map_bill_to_factura_fields(bill)
        self.assertEqual(fields['pago_neto'], 4039466)
        self.assertEqual(fields['valor'], 4039466)
        self.assertNotEqual(fields['pago_neto'], 4450893)

    def test_pago_neto_canje_balance_cero_total_paid(self):
        from alegra_integration.bill_mapping import bill_pago_neto_canje

        bill = {
            'id': '43',
            'total': 4450893,
            'totalPaid': 4039466,
            'balance': 0,
            'status': 'closed',
        }
        self.assertEqual(bill_pago_neto_canje(bill), 0)

    def test_pago_neto_canje_usa_balance_sin_restar_total_paid(self):
        from alegra_integration.bill_mapping import bill_pago_neto_canje

        bill = {
            'total': 362950,
            'totalPaid': 146400,
            'balance': 204350,
        }
        self.assertEqual(bill_pago_neto_canje(bill), 204350)

    def test_pago_neto_canje_escenario_balance_igual_total_paid(self):
        from alegra_integration.bill_mapping import bill_pago_neto_canje

        bill = {'balance': 4039466, 'totalPaid': 4039466}
        self.assertEqual(bill_pago_neto_canje(bill), 4039466)

    def test_infer_document_type(self):
        from alegra_integration.bill_mapping import (
            ALEGRA_DOC_BILL,
            ALEGRA_DOC_JOURNAL,
            infer_alegra_document_type,
        )

        self.assertEqual(infer_alegra_document_type('901018375:34'), ALEGRA_DOC_BILL)
        self.assertEqual(infer_alegra_document_type('901018375:journal:11'), ALEGRA_DOC_JOURNAL)
        self.assertEqual(infer_alegra_document_type(''), '')

    def test_expense_payment_uses_bills_when_alegra_bill(self):
        from alegra_integration.builders import ExpensePaymentBuilder

        class BillResolver(ResolverStub):
            def bill_for_factura(self, factura_id, required=False, *, factura=None):
                return '3'

            def numeration(self, document_code, required=True):
                return 'num-4'

            def get(self, mapping_type, *args, **kwargs):
                if kwargs.get('local_code') == 'default_cxp':
                    return None
                return super().get(mapping_type, *args, **kwargs)

        factura = SimpleNamespace(
            pk=17228,
            idtercero='900123456',
            nrofactura='2',
            descripcion='SERVICIO',
            empresa=SimpleNamespace(pk='901018375'),
            cuenta_por_pagar=None,
            alegra_bill_id='901018375:3',
            alegra_document_type='bill',
        )
        pago = SimpleNamespace(
            pk=14817,
            valor=400000,
            fecha_pago=datetime.date(2026, 5, 6),
            cuenta=SimpleNamespace(pk=1, nro_cuentacontable='11100501', cuentabanco='transfer', nit_empresa_id='901018375'),
            nroradicado=factura,
        )
        builder = ExpensePaymentBuilder(SimpleNamespace(pk='901018375'))
        builder.resolver = BillResolver()
        with patch('alegra_integration.builders.clientes') as mock_cli:
            mock_cli.objects.filter.return_value.exists.return_value = False
            with patch('alegra_integration.builders.empresas') as mock_emp:
                mock_emp.objects.filter.return_value.exists.return_value = False
                with patch('alegra_integration.builders.asesores') as mock_ase:
                    mock_ase.objects.filter.return_value.exists.return_value = False
                    builder.resolver.contact_by_identification = lambda *a, **k: '175'
                    built = builder._from_pago(pago)
        self.assertIn('bills', built.payload)
        self.assertEqual(built.payload['bills'][0]['id'], '3')
        self.assertNotIn('categories', built.payload)

    def test_expense_payment_journal_usa_account_code_detalle(self):
        from accounting.journal_cxp import serializar_detalle_journal_pago
        from alegra_integration.builders import ExpensePaymentBuilder
        from accounting.journal_cxp import extraer_lineas_cxp
        from accounting.test_journal_cxp import JOURNAL_7

        class JournalResolver(ResolverStub):
            def bill_for_factura(self, *a, **k):
                return None

            def numeration(self, document_code, required=True):
                return 'num-4'

            def category_for_puc_code(self, account_code, required=False):
                return f'cat-{account_code}'

        lineas = serializar_detalle_journal_pago(extraer_lineas_cxp(JOURNAL_7))
        import json
        factura = SimpleNamespace(
            pk=99,
            idtercero='31425903',
            nrofactura='ARRIENDO',
            descripcion='ARRIENDO',
            empresa=SimpleNamespace(pk='901018375'),
            cuenta_por_pagar=None,
            alegra_bill_id='901018375:journal:7',
            alegra_document_type='journal',
            alegra_journal_detalle=json.dumps(lineas),
        )
        pago = SimpleNamespace(
            pk=1,
            valor=2412500,
            fecha_pago=datetime.date(2026, 5, 6),
            cuenta=SimpleNamespace(pk=1, nro_cuentacontable='11100501', cuentabanco='transfer', nit_empresa_id='901018375'),
            nroradicado=factura,
        )
        builder = ExpensePaymentBuilder(SimpleNamespace(pk='901018375'))
        builder.resolver = JournalResolver()
        with patch('alegra_integration.builders.clientes') as mock_cli:
            mock_cli.objects.filter.return_value.exists.return_value = True
            builder.resolver.contact_for_cliente = lambda _x: '175'
            with patch('accounting.models.pago_detallado_relacionado') as mock_pd:
                mock_pd.objects.filter.return_value.order_by.return_value = []
                built = builder._from_pago(pago)
        self.assertEqual(built.payload['categories'][0]['id'], 'cat-22050501')

    def test_expense_payment_journal_pago_unico_usa_id_del_get(self):
        """Pago normal (sin detalle tesorería): categories[].id viene del journal, no del mapeo PUC."""
        import json
        from types import SimpleNamespace

        from alegra_integration.builders import ExpensePaymentBuilder

        class JournalResolver(ResolverStub):
            def bill_for_factura(self, *a, **k):
                return None

            def numeration(self, document_code, required=True):
                return 'num-4'

            def category_for_puc_code(self, account_code, required=False):
                return 'default-cxp-should-not-use'

        detalle = [{
            'id_tercero': '31425903',
            'nombre_tercero': 'PROVEEDOR',
            'valor': 2412500,
            'account_code': '22050501',
            'alegra_category_id': '8821',
        }]
        factura = SimpleNamespace(
            pk=99,
            idtercero='31425903',
            nrofactura='ARRIENDO',
            descripcion='ARRIENDO',
            empresa=SimpleNamespace(pk='901018375'),
            cuenta_por_pagar=None,
            alegra_bill_id='901018375:journal:7',
            alegra_document_type='journal',
            alegra_journal_detalle=json.dumps(detalle),
        )
        pago = SimpleNamespace(
            pk=1,
            valor=2412500,
            fecha_pago=datetime.date(2026, 5, 6),
            cuenta=SimpleNamespace(pk=1, nro_cuentacontable='11100501', cuentabanco='transfer', nit_empresa_id='901018375'),
            nroradicado=factura,
        )
        builder = ExpensePaymentBuilder(SimpleNamespace(pk='901018375'))
        builder.resolver = JournalResolver()
        with patch('alegra_integration.builders.clientes') as mock_cli:
            mock_cli.objects.filter.return_value.exists.return_value = True
            builder.resolver.contact_for_cliente = lambda _x: '175'
            with patch('accounting.models.pago_detallado_relacionado') as mock_pd:
                mock_pd.objects.filter.return_value.order_by.return_value = []
                built = builder._from_pago(pago)
        self.assertEqual(built.payload['categories'][0]['id'], '8821')
        self.assertEqual(built.payload['categories'][0]['price'], 2412500.0)

    def test_expense_payment_journal_multi_tercero_un_pago_por_detalle(self):
        import json
        from types import SimpleNamespace

        from accounting.journal_cxp import extraer_lineas_cxp, serializar_detalle_journal_pago
        from accounting.test_journal_cxp import JOURNAL_11
        from alegra_integration.builders import ExpensePaymentBuilder

        class JournalResolver(ResolverStub):
            def bill_for_factura(self, *a, **k):
                return None

            def numeration(self, document_code, required=True):
                return 'num-4'

            def category_for_puc_code(self, account_code, required=False):
                return f'cat-{account_code}'

        lineas = serializar_detalle_journal_pago(extraer_lineas_cxp(JOURNAL_11))
        factura = SimpleNamespace(
            pk=17335,
            idtercero='901018375',
            nrofactura='J-11',
            descripcion='COMISIONES',
            empresa=SimpleNamespace(pk='901018375'),
            cuenta_por_pagar=None,
            alegra_bill_id='901018375:journal:11',
            alegra_document_type='journal',
            alegra_journal_detalle=json.dumps(lineas),
        )
        detalle_rows = [
            SimpleNamespace(pk=1, id_tercero='1017232868', nombre_tercero='LAURA', valor=801561),
            SimpleNamespace(pk=2, id_tercero='1037588511', nombre_tercero='JUAN', valor=2404686),
            SimpleNamespace(pk=3, id_tercero='8130000', nombre_tercero='HAROLD', valor=1311269),
        ]
        pago = SimpleNamespace(
            pk=14906,
            valor=4517516,
            fecha_pago=datetime.date(2026, 5, 15),
            cuenta=SimpleNamespace(pk=1, nro_cuentacontable='11100501', cuentabanco='transfer', nit_empresa_id='901018375'),
            nroradicado=factura,
        )
        builder = ExpensePaymentBuilder(SimpleNamespace(pk='901018375'))
        builder.resolver = JournalResolver()
        with patch('alegra_integration.builders.clientes') as mock_cli:
            mock_cli.objects.filter.return_value.exists.return_value = False
            with patch('alegra_integration.builders.empresas') as mock_emp:
                mock_emp.objects.filter.return_value.exists.return_value = False
                with patch('alegra_integration.builders.asesores') as mock_ase:
                    mock_ase.objects.filter.return_value.exists.return_value = True
                    builder.resolver.contact_for_asesor = lambda _x: '175'
                    with patch.object(builder, '_pagos_detalle', return_value=detalle_rows):
                        built_list = builder._from_pago(pago)
        self.assertEqual(len(built_list), 3)
        keys = {b.local_key for b in built_list}
        self.assertEqual(keys, {
            'expense:pago:14906:t:1017232868',
            'expense:pago:14906:t:1037588511',
            'expense:pago:14906:t:8130000',
        })
        prices = sorted(c['price'] for b in built_list for c in b.payload['categories'])
        self.assertEqual(prices, [801561.0, 1311269.0, 2404686.0])
        for b in built_list:
            self.assertEqual(b.payload['categories'][0]['id'], '7558')
            self.assertNotIn('bills', b.payload)

    def test_expense_payment_sin_bill_con_cxp_pone_categories(self):
        """Sin bill en Alegra pero con cuenta_por_pagar: el valor va en categories[].price."""
        from alegra_integration.builders import ExpensePaymentBuilder

        class CxpResolver(ResolverStub):
            def bill_for_factura(self, *a, **k):
                return None

            def numeration(self, document_code, required=True):
                return 'num-4'

            def category_for_puc_code(self, account_code, required=False):
                return f'cat-{account_code}'

        cuenta_por_pagar = SimpleNamespace(cuenta_credito_1='22050501')
        factura = SimpleNamespace(
            pk=17332,
            idtercero='31425903',
            nrofactura='INT-901018375-L-011-6374',
            descripcion='SS MARZO 2026',
            empresa=SimpleNamespace(pk='901018375'),
            cuenta_por_pagar=cuenta_por_pagar,
            cuenta_por_pagar_id=11,
            alegra_bill_id='',
            alegra_document_type='',
            alegra_journal_detalle=None,
        )
        pago = SimpleNamespace(
            pk=14823,
            valor=1500000,
            fecha_pago=datetime.date(2026, 5, 5),
            cuenta=SimpleNamespace(pk=1, nro_cuentacontable='11100501', cuentabanco='transfer', nit_empresa_id='901018375'),
            nroradicado=factura,
        )
        builder = ExpensePaymentBuilder(SimpleNamespace(pk='901018375'))
        builder.resolver = CxpResolver()
        with patch('alegra_integration.builders.clientes') as mock_cli:
            mock_cli.objects.filter.return_value.exists.return_value = True
            builder.resolver.contact_for_cliente = lambda _x: '290'
            built = builder._from_pago(pago)
        self.assertNotIn('bills', built.payload)
        cats = built.payload['categories']
        self.assertEqual(len(cats), 1)
        self.assertEqual(cats[0]['price'], 1500000.0)
        self.assertEqual(cats[0]['quantity'], 1)
        self.assertTrue(cats[0]['id'])

    @patch('alegra_integration.builders.MappingResolver')
    @patch('alegra_integration.builders.empresas')
    @patch('alegra_integration.builders.cuentas_intercompanias')
    def test_intercompany_pago_journal_usa_number_template_como_recibos(
        self, interco_model, empresas_model, resolver_cls,
    ):
        from alegra_integration.builders import ExpensePaymentBuilder

        class IntercoResolver(ResolverStub):
            def numeration(self, document_code, required=True):
                if document_code == 'interco_journal':
                    return 'num-interco'
                return super().numeration(document_code, required=required)

            def get(self, mapping_type, *args, **kwargs):
                if mapping_type == 'contact' and kwargs.get('local_model') == 'andinasoft.empresas':
                    return f"contact-emp-{kwargs.get('local_pk')}"
                lc = kwargs.get('local_code') or ''
                if lc.startswith('interco_cxc:') or lc.startswith('interco_cxp:'):
                    return 'cat-interco'
                if kwargs.get('local_code') == 'cxp_credito_1':
                    return 'cat-cxp'
                return super().get(mapping_type, *args, **kwargs)

            def bank_journal_category_for_account(self, cuenta, *, required=True):
                return 'cat-bank-journal'

        empresas_model.objects.get.side_effect = lambda pk: SimpleNamespace(
            pk=pk, nombre=f'Empresa {pk}',
        )
        rel_b_to_a = SimpleNamespace(pk=1, cuenta_por_cobrar='1380')
        rel_a_to_b = SimpleNamespace(pk=2, cuenta_por_pagar='2380')
        interco_model.objects.filter.side_effect = lambda **kw: SimpleNamespace(
            first=lambda: rel_b_to_a if kw.get('empresa_desde_id') == '900B' else rel_a_to_b,
        )

        factura = SimpleNamespace(
            pk=1,
            nombretercero='Proveedor X',
            descripcion='',
            idtercero='123',
            cuenta_por_pagar=SimpleNamespace(cuenta_credito_1='22050501'),
            cuenta_por_pagar_id=5,
        )
        pago = SimpleNamespace(
            pk=99,
            valor=500000,
            fecha_pago=datetime.date(2026, 5, 5),
            cuenta=SimpleNamespace(nro_cuentacontable='11100501'),
            nroradicado=factura,
        )
        resolver_cls.return_value = IntercoResolver()
        with patch('alegra_integration.builders.empresas') as mock_emp:
            mock_emp.objects.filter.return_value.exists.return_value = True
            builder = ExpensePaymentBuilder(SimpleNamespace(pk='900B'))
            built = builder._from_pago_intercompany(
                pago, factura, empresa_origen_id='900A', empresa_pago_id='900B',
            )
        self.assertEqual(built.operation, 'accounting__createJournal')
        self.assertEqual(built.payload['numberTemplate'], 'num-interco')
        self.assertEqual(built.payload['status'], 'open')
        self.assertNotIn('idNumeration', built.payload)
        self.assertEqual(built.payload['entries'][0]['debit'], 500000.0)
        self.assertEqual(built.payload['entries'][0]['credit'], 0)
        self.assertEqual(built.payload['entries'][0]['client'], 'contact-emp-900A')
        self.assertNotIn('client', built.payload['entries'][1])
        self.assertEqual(built.payload['entries'][1]['id'], 'cat-bank-journal')
        self.assertEqual(built.payload['entries'][1]['credit'], 500000.0)


class BankJournalCategoryResolverTests(TestCase):
    def setUp(self):
        from alegra_integration.mapping import MappingResolver
        from alegra_integration.models import AlegraMapping
        from andinasoft.models import cuentas_pagos

        self.AlegraMapping = AlegraMapping
        self.empresa = empresas.objects.create(
            Nit='900993044',
            nombre='Andina prueba',
            alegra_enabled=True,
        )
        self.cuenta = cuentas_pagos.objects.create(
            idcuenta=793339,
            nit_empresa=self.empresa,
            cuentabanco='234-793339-39',
            nro_cuentacontable=11100501,
            activo=True,
        )
        self.resolver = MappingResolver(self.empresa)

    def test_bank_journal_category_by_local_idcuenta(self):
        self.AlegraMapping.objects.create(
            empresa=self.empresa,
            mapping_type=self.AlegraMapping.CATEGORY,
            local_model='andinasoft.cuentas_pagos',
            local_pk=str(self.cuenta.idcuenta),
            local_code='bank_journal',
            alegra_id='6308',
            alegra_payload={
                'source': 'bank_account',
                'bank_account_id': 'bank-1',
                'local_idcuenta': str(self.cuenta.idcuenta),
                'nro_cuentacontable': '11100501',
            },
            active=True,
        )
        self.assertEqual(
            self.resolver.bank_journal_category_for_account(self.cuenta),
            '6308',
        )

    def test_bank_journal_category_per_account_same_puc(self):
        from alegra_integration.mapping import BANK_JOURNAL_LOCAL_CODE, BANK_JOURNAL_LOCAL_MODEL
        from andinasoft.models import cuentas_pagos

        cuenta_b = cuentas_pagos.objects.create(
            idcuenta=793340,
            nit_empresa=self.empresa,
            cuentabanco='Caja Medellin',
            nro_cuentacontable=11100501,
            es_caja=True,
            activo=True,
        )
        self.AlegraMapping.objects.create(
            empresa=self.empresa,
            mapping_type=self.AlegraMapping.CATEGORY,
            local_model=BANK_JOURNAL_LOCAL_MODEL,
            local_pk=str(self.cuenta.idcuenta),
            local_code=BANK_JOURNAL_LOCAL_CODE,
            alegra_id='6308',
            alegra_payload={'source': 'bank_account', 'local_idcuenta': str(self.cuenta.idcuenta)},
            active=True,
        )
        self.AlegraMapping.objects.create(
            empresa=self.empresa,
            mapping_type=self.AlegraMapping.CATEGORY,
            local_model=BANK_JOURNAL_LOCAL_MODEL,
            local_pk=str(cuenta_b.idcuenta),
            local_code=BANK_JOURNAL_LOCAL_CODE,
            alegra_id='7777',
            alegra_payload={'source': 'bank_account', 'local_idcuenta': str(cuenta_b.idcuenta)},
            active=True,
        )
        self.assertEqual(self.resolver.bank_journal_category_for_account(self.cuenta), '6308')
        self.assertEqual(self.resolver.bank_journal_category_for_account(cuenta_b), '7777')

    def test_bank_journal_category_legacy_payload(self):
        self.AlegraMapping.objects.create(
            empresa=self.empresa,
            mapping_type=self.AlegraMapping.CATEGORY,
            local_code='11100501',
            alegra_id='6308',
            alegra_payload={
                'source': 'bank_account',
                'local_idcuenta': str(self.cuenta.idcuenta),
            },
            active=True,
        )
        self.assertEqual(
            self.resolver.bank_journal_category_for_account(self.cuenta),
            '6308',
        )


class BatchSendStopOnErrorTests(TestCase):
    def setUp(self):
        from alegra_integration.models import AlegraDocument, AlegraSyncBatch

        self.AlegraDocument = AlegraDocument
        self.AlegraSyncBatch = AlegraSyncBatch
        self.empresa = empresas.objects.create(
            Nit='900111',
            nombre='Empresa lote',
            alegra_enabled=True,
        )
        self.batch = AlegraSyncBatch.objects.create(
            empresa=self.empresa,
            document_type=AlegraSyncBatch.DOC_EXPENSE,
            fecha_desde=datetime.date(2026, 1, 1),
            fecha_hasta=datetime.date(2026, 1, 31),
            status=AlegraSyncBatch.STATUS_PREVIEW,
            total_documents=2,
        )
        common = dict(
            batch=self.batch,
            empresa=self.empresa,
            document_type='expense_payment',
            alegra_operation='POST /payments',
            transport=AlegraDocument.ALEGRA_REST,
            source_model='accounting.Pagos',
            payload={'amount': 1},
        )
        self.doc_ok = AlegraDocument.objects.create(
            source_pk='1',
            local_key='expense:pago:1',
            status=AlegraDocument.STATUS_VALID,
            **common,
        )
        self.doc_fail = AlegraDocument.objects.create(
            source_pk='2',
            local_key='expense:pago:2',
            status=AlegraDocument.STATUS_VALID,
            **common,
        )
        self.doc_pending = AlegraDocument.objects.create(
            source_pk='3',
            local_key='expense:pago:3',
            status=AlegraDocument.STATUS_VALID,
            **common,
        )

    @patch('alegra_integration.services.AlegraIntegrationService._try_send_batch_document')
    def test_send_batch_stops_on_first_failure(self, mock_try):
        from alegra_integration.services import AlegraIntegrationService

        def _side_effect(batch, doc, client_by_empresa, *, retry_failed=True):
            if doc.pk == self.doc_fail.pk:
                doc.status = AlegraDocument.STATUS_FAILED
                doc.error = 'fallo alegra'
                doc.save(update_fields=['status', 'error', 'updated_at'])
                return 'failed'
            doc.status = AlegraDocument.STATUS_SENT
            doc.save(update_fields=['status', 'updated_at'])
            return 'sent'

        mock_try.side_effect = _side_effect

        result = AlegraIntegrationService()._send_batch_documents(self.batch)

        self.assertTrue(result.get('stopped_on_error'))
        self.assertEqual(mock_try.call_count, 2)
        self.doc_pending.refresh_from_db()
        self.assertEqual(self.doc_pending.status, AlegraDocument.STATUS_VALID)

    @patch('alegra_integration.services.AlegraIntegrationService._try_send_batch_document')
    def test_send_one_stops_on_failure(self, mock_try):
        from alegra_integration.services import AlegraIntegrationService

        def _side_effect(batch, doc, client_by_empresa, *, retry_failed=True):
            doc.status = AlegraDocument.STATUS_FAILED
            doc.error = 'fallo alegra'
            doc.save(update_fields=['status', 'error', 'updated_at'])
            return 'failed'

        mock_try.side_effect = _side_effect

        result = AlegraIntegrationService().send_one_batch_document(
            batch_id=self.batch.pk,
            document_id=self.doc_ok.pk,
        )

        self.assertTrue(result.get('complete'))
        self.assertTrue(result.get('stopped_on_error'))
        self.doc_pending.refresh_from_db()
        self.assertEqual(self.doc_pending.status, AlegraDocument.STATUS_VALID)


class CajaBuilderTests(SimpleTestCase):
    def setUp(self):
        self.empresa = SimpleNamespace(pk='901018375')
        self.resolver = ResolverStub()

    def _gasto(self, *, tipo='fe', valor=119000, subtotal_val=100000, valor_iva=None, valor_rte=None):
        concepto = SimpleNamespace(
            pk=12,
            cuenta_andina='5195950100',
            cuenta_status='',
            cuenta_quadrata='',
        )
        tercero = SimpleNamespace(idTercero='900123456')
        caja = SimpleNamespace(pk=7, cuentabanco='Caja Menor', usuario_responsable=SimpleNamespace(pk=1))
        forma_pago = SimpleNamespace(empresa='Promotora Sandville', pk=7)
        reembolso = SimpleNamespace(pk=99, caja=caja, valor=valor, fecha_aprueba=datetime.date(2026, 5, 10))
        gasto = SimpleNamespace(
            pk=501,
            estado='Legalizado',
            reembolso_id=99,
            reembolso=reembolso,
            fecha_gasto=datetime.date(2026, 5, 5),
            descripcion='COMPRA PAPELERIA',
            valor=valor,
            valor_iva=valor_iva,
            valor_rte=valor_rte,
            rte_asumida=False,
            cuenta_iva_id=None,
            cuenta_rte_id=None,
            concepto=concepto,
            tercero=tercero,
            forma_pago=forma_pago,
            tipo_documento_soporte=tipo,
            subtotal=lambda: subtotal_val,
        )
        return gasto, reembolso

    def test_caja_bill_fe_omits_number_template(self):
        gasto, _ = self._gasto(tipo='fe')
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        self.assertEqual(built.document_type, 'caja_bill')
        self.assertEqual(built.operation, 'POST /bills')
        self.assertNotIn('numberTemplate', built.payload)
        self.assertEqual(built.local_key, 'caja:bill:99:501')
        self.assertEqual(built.payload['purchases']['categories'][0]['id'], 'cat-caja-expense-mapped')

    def test_caja_bill_falls_back_to_puc_when_no_concept_mapping(self):
        resolver = ResolverStub()

        def get_no_concept(*args, **kwargs):
            if kwargs.get('local_code') == 'caja_expense':
                return None
            return ResolverStub.get(resolver, *args, **kwargs)

        resolver.get = get_no_concept
        gasto, _ = self._gasto(tipo='fe')
        built = CajaGastoBillBuilder(self.empresa, resolver).build(gasto)
        self.assertEqual(built.payload['purchases']['categories'][0]['id'], 'cat-puc-5195950100')

    def test_caja_bill_revisado_sin_reembolso(self):
        gasto, _ = self._gasto(tipo='fe')
        gasto.estado = gastos_caja.ESTADO_REVISADO
        gasto.reembolso_id = None
        gasto.reembolso = None
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        self.assertEqual(built.document_type, 'caja_bill')
        self.assertEqual(built.local_key, 'caja:bill:None:501')

    def test_caja_bill_reembolso(self):
        gasto, _ = self._gasto(tipo='fe')
        gasto.estado = gastos_caja.ESTADO_REEMBOLSO
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        self.assertEqual(built.document_type, 'caja_bill')
        self.assertEqual(built.local_key, 'caja:bill:99:501')

    def test_caja_bill_cuenta_cobro_uses_cc_numeration(self):
        gasto, _ = self._gasto(tipo='cuenta_cobro')
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        self.assertEqual(built.payload['numberTemplate'], {'id': 'num-caja_cuenta_cobro'})

    def test_caja_bill_with_iva_uses_tax_on_base_line(self):
        gasto, _ = self._gasto(valor=119000, subtotal_val=100000, valor_iva=19000.0)
        gasto.cuenta_iva_id = 12
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        line = built.payload['purchases']['categories'][0]
        self.assertEqual(line['price'], 100000.0)
        self.assertEqual(line['tax'], [{'id': 'tax-imp-12'}])
        self.assertNotIn('retentions', built.payload)
        self.assertEqual(built.payload['__local']['valor_esperado'], 119000.0)

    def test_caja_bill_with_retefuente_uses_impuesto_mapping(self):
        gasto, _ = self._gasto(valor=97000, subtotal_val=100000)
        gasto.valor_iva = None
        gasto.valor_rte = 3000.0
        gasto.cuenta_rte_id = 5
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        self.assertEqual(built.payload['retentions'], [{'id': 'ret-imp-5', 'amount': 3000.0}])
        self.assertNotIn('tax', built.payload['purchases']['categories'][0])

    def test_caja_bill_with_cost_center(self):
        gasto, _ = self._gasto(tipo='fe')
        built = CajaGastoBillBuilder(self.empresa, self.resolver).build(gasto)
        self.assertEqual(built.payload['costCenter'], {'id': 'cc-caja-7'})
        self.assertEqual(built.payload['__local']['cost_center_id'], 'cc-caja-7')

    def test_caja_journal_applies_cost_center_to_all_entries(self):
        gasto, reembolso = self._gasto(valor=120000, subtotal_val=100000, valor_iva=19000.0)
        gasto.cuenta_iva_id = 12
        with patch('alegra_integration.builders.Profiles') as profiles_model:
            profiles_model.objects.filter.return_value.first.return_value = SimpleNamespace(identificacion='123456789')
            built = CajaLegalizationJournalBuilder(self.empresa, self.resolver).build(
                {'reembolso': reembolso, 'gastos': [gasto]}
            )
        self.assertEqual(built.document_type, 'caja_journal')
        self.assertEqual(built.operation, 'accounting__createJournal')
        self.assertEqual(built.payload['numberTemplate'], 'num-caja_legalization_journal')
        assoc = built.payload['entries'][0]['associatedDocument']
        self.assertEqual(assoc['resourceType'], 'bill')
        self.assertEqual(assoc['idResource'], 0)
        self.assertIn('pending_bills', built.payload['__local'])
        self.assertEqual(built.local_key, 'caja:journal:99')
        self.assertEqual(built.payload['entries'][-1]['credit'], 120000.0)
        for entry in built.payload['entries']:
            self.assertEqual(entry['costCenter'], {'id': 'cc-caja-7'})
        self.assertEqual(built.payload['__local']['cost_center_id'], 'cc-caja-7')

    def test_caja_journal_credit_matches_exact_gastos_sum(self):
        gasto, reembolso = self._gasto(valor=45500, subtotal_val=38235)
        reembolso.valor = 45500
        with patch('alegra_integration.builders.Profiles') as profiles_model:
            profiles_model.objects.filter.return_value.first.return_value = SimpleNamespace(
                identificacion='123456789'
            )
            built = CajaLegalizationJournalBuilder(self.empresa, self.resolver).build(
                {'reembolso': reembolso, 'gastos': [gasto]}
            )
        credits = [e for e in built.payload['entries'] if e.get('credit')]
        self.assertEqual(credits[-1]['credit'], 45500.0)
        debits = [e for e in built.payload['entries'] if e.get('debit') and not e.get('associatedDocument')]
        self.assertEqual(debits, [])

    def test_caja_journal_batch_single_comprobante_por_lote(self):
        gasto1, reembolso1 = self._gasto(valor=50000, subtotal_val=42000)
        gasto2, reembolso2 = self._gasto(valor=70000, subtotal_val=58824)
        reembolso2.pk = 100
        gasto2.reembolso = reembolso2
        gasto2.reembolso_id = reembolso2.pk
        caja = reembolso1.caja
        reembolso2.caja = caja
        reembolso1.valor = 50000
        reembolso2.valor = 70000
        with patch('alegra_integration.builders.Profiles') as profiles_model:
            profiles_model.objects.filter.return_value.first.return_value = SimpleNamespace(
                identificacion='123456789'
            )
            built = CajaLegalizationJournalBuilder(self.empresa, self.resolver).build_batch(
                caja=caja,
                gastos=[gasto1, gasto2],
                batch_id=42,
                fecha_desde=datetime.date(2026, 5, 1),
                fecha_hasta=datetime.date(2026, 5, 31),
            )
        self.assertEqual(built.local_key, 'caja:journal:batch:42')
        self.assertEqual(built.payload['reference'], 'LC-Caja Menor-LOTE-42')
        self.assertEqual(len(built.payload['__local']['pending_bills']), 2)
        self.assertEqual(built.payload['__local']['reembolso_ids'], [99, 100])
        debits = [e for e in built.payload['entries'] if e.get('debit')]
        credits = [e for e in built.payload['entries'] if e.get('credit')]
        self.assertEqual(len(debits), 2)
        self.assertEqual(len(credits), 2)
        self.assertEqual(debits[0]['associatedDocument']['resourceType'], 'bill')

    def test_caja_journal_batch_includes_revisado_sin_reembolso(self):
        gasto1, reembolso1 = self._gasto(valor=50000, subtotal_val=42000)
        gasto2, _ = self._gasto(valor=70000, subtotal_val=58824)
        gasto2.pk = 502
        caja = reembolso1.caja
        gasto1.reembolso = None
        gasto1.reembolso_id = None
        gasto2.reembolso = None
        gasto2.reembolso_id = None
        with patch('alegra_integration.builders.Profiles') as profiles_model:
            profiles_model.objects.filter.return_value.first.return_value = SimpleNamespace(
                identificacion='123456789'
            )
            built = CajaLegalizationJournalBuilder(self.empresa, self.resolver).build_batch(
                caja=caja,
                gastos=[gasto1, gasto2],
                batch_id=43,
                fecha_desde=datetime.date(2026, 6, 1),
                fecha_hasta=datetime.date(2026, 6, 30),
            )
        self.assertEqual(built.local_key, 'caja:journal:batch:43')
        self.assertEqual(len(built.payload['__local']['pending_bills']), 2)
        self.assertEqual(built.payload['__local']['reembolso_ids'], [])
        debits = [e for e in built.payload['entries'] if e.get('debit')]
        credits = [e for e in built.payload['entries'] if e.get('credit')]
        self.assertEqual(len(debits), 2)
        self.assertEqual(len(credits), 1)
        self.assertEqual(credits[0]['credit'], 120000.0)

    def test_caja_journal_batch_uses_zero_placeholder_without_cxp_mapping(self):
        """Sin caja_cxp/default_cxp el journal igual se arma; CxP se inyecta al finalizar."""
        gasto, reembolso = self._gasto(valor=50000, subtotal_val=42000)
        caja = reembolso.caja

        class ResolverNoCxp(ResolverStub):
            def get(self, *args, **kwargs):
                code = kwargs.get('local_code', '')
                if code in ('caja_cxp', 'default_cxp'):
                    return None
                return super().get(*args, **kwargs)

        with patch('alegra_integration.builders.Profiles') as profiles_model:
            profiles_model.objects.filter.return_value.first.return_value = SimpleNamespace(
                identificacion='123456789'
            )
            built = CajaLegalizationJournalBuilder(self.empresa, ResolverNoCxp()).build_batch(
                caja=caja,
                gastos=[gasto],
                batch_id=44,
                fecha_desde=datetime.date(2026, 6, 1),
                fecha_hasta=datetime.date(2026, 6, 30),
            )
        debits = [e for e in built.payload['entries'] if e.get('debit')]
        self.assertEqual(debits[0]['id'], '0')
        self.assertEqual(debits[0]['associatedDocument']['idResource'], 0)

    @patch('andinasoft.models.cuentas_pagos.objects.filter')
    @patch('alegra_integration.services.empresas.objects.get')
    def test_validate_caja_requires_caja_id(self, mock_emp_get, mock_caja_filter):
        from alegra_integration.services import AlegraIntegrationService
        from alegra_integration.models import AlegraSyncBatch
        from alegra_integration.exceptions import AlegraConfigurationError

        mock_emp_get.return_value = SimpleNamespace(pk='900')
        svc = AlegraIntegrationService()
        with self.assertRaises(AlegraConfigurationError) as ctx:
            svc._validate_input(
                '900', AlegraSyncBatch.DOC_CAJA, '2026-01-01', '2026-01-31', None, caja_id=None,
            )
        self.assertIn('caja', str(ctx.exception).lower())
        mock_caja_filter.assert_not_called()

    @patch('andinasoft.models.cuentas_pagos.objects.filter')
    @patch('alegra_integration.services.empresas.objects.get')
    def test_validate_caja_accepts_active_caja(self, mock_emp_get, mock_caja_filter):
        from alegra_integration.services import AlegraIntegrationService
        from alegra_integration.models import AlegraSyncBatch

        empresa = SimpleNamespace(pk='900')
        mock_emp_get.return_value = empresa
        cuenta = SimpleNamespace(pk=7)
        mock_caja_filter.return_value.first.return_value = cuenta
        svc = AlegraIntegrationService()
        out = svc._validate_input(
            '900', AlegraSyncBatch.DOC_CAJA, '2026-01-01', '2026-01-31', None, caja_id='7',
        )
        self.assertEqual(out[4], 7)
        mock_caja_filter.assert_called_once_with(
            pk='7', nit_empresa=empresa, activo=True, es_caja=True,
        )


class CajaJournalFinalizeTests(SimpleTestCase):
    def test_next_sendable_prefers_bills_before_journals(self):
        from alegra_integration.models import AlegraSyncBatch, AlegraDocument
        from alegra_integration.services import AlegraIntegrationService

        batch = SimpleNamespace(document_type=AlegraSyncBatch.DOC_CAJA)
        journal = SimpleNamespace(document_type='caja_journal', pk=20, status=AlegraDocument.STATUS_VALID)
        bill = SimpleNamespace(document_type='caja_bill', pk=10, status=AlegraDocument.STATUS_VALID)
        svc = AlegraIntegrationService()

        class _Qs(list):
            def filter(self, **kwargs):
                statuses = kwargs.get('status__in') or []
                return _Qs([d for d in self if d.status in statuses])

        batch.documents = _Qs([journal, bill])
        picked = svc._next_sendable_batch_document(batch, retry_failed=False)
        self.assertEqual(picked.document_type, 'caja_bill')

    @patch('alegra_integration.services.AlegraMCPClient')
    def test_finalize_injects_bill_id_and_cxp(self, mock_client_cls):
        from alegra_integration.models import AlegraDocument, AlegraSyncBatch
        from alegra_integration.services import AlegraIntegrationService

        empresa = SimpleNamespace(pk='900')
        bill_doc = SimpleNamespace(
            empresa=empresa,
            document_type='caja_bill',
            local_key='caja:bill:99:501',
            alegra_id='555',
            status=AlegraDocument.STATUS_SENT,
            response={'__cxp_category_id': 'cat-cxp-88'},
        )
        journal_doc = SimpleNamespace(
            empresa=empresa,
            document_type='caja_journal',
            local_key='caja:journal:batch:99',
            payload={
                'entries': [{
                    'id': 'placeholder-cxp',
                    'debit': 1000,
                    'credit': 0,
                    'associatedDocument': {'idResource': 0, 'resourceType': 'bill'},
                }],
                '__local': {
                    'pending_bills': [{
                        'local_key': 'caja:bill:99:501',
                        'gasto_id': 501,
                        'amount': 1000,
                        'provider_id': '175',
                    }],
                },
            },
            save=Mock(),
        )
        batch = SimpleNamespace(document_type=AlegraSyncBatch.DOC_CAJA)

        with patch.object(AlegraDocument.objects, 'filter') as doc_filter:
            doc_filter.return_value.first.return_value = bill_doc
            AlegraIntegrationService()._prepare_caja_document_for_send(batch, journal_doc)

        entry = journal_doc.payload['entries'][0]
        self.assertEqual(entry['id'], 'cat-cxp-88')
        self.assertEqual(entry['associatedDocument']['idResource'], 555)
        journal_doc.save.assert_called_once()

    @patch('alegra_integration.services.AlegraMCPClient')
    def test_finalize_aligns_debit_to_bill_balance(self, mock_client_cls):
        """Redondeo IVA: gasto.valor 11300 vs balance Alegra 11299 → cerrar con 11299."""
        from alegra_integration.models import AlegraDocument
        from alegra_integration.services import AlegraIntegrationService

        empresa = SimpleNamespace(pk='900')
        bill_doc = SimpleNamespace(
            empresa=empresa,
            document_type='caja_bill',
            local_key='caja:bill:190:501',
            alegra_id='211',
            status=AlegraDocument.STATUS_SENT,
            response={
                '__cxp_category_id': '6787',
                'total': 11299,
                'balance': 11299,
                'totalPaid': 0,
            },
        )
        journal_doc = SimpleNamespace(
            empresa=empresa,
            document_type='caja_journal',
            local_key='caja:journal:batch:448',
            payload={
                'entries': [
                    {
                        'id': 'placeholder-cxp',
                        'description': 'COMPRA DE CINTA PARA COLOCAR EN KIOSCO',
                        'debit': 11300,
                        'credit': 0,
                        'associatedDocument': {'idResource': 0, 'resourceType': 'bill'},
                    },
                    {
                        'id': '6444',
                        'description': 'REEMB CAJA 190 CAJA ALTTUM CARMELO',
                        'debit': 0,
                        'credit': 11300,
                        'client': '148',
                    },
                ],
                '__local': {
                    'pending_bills': [{
                        'local_key': 'caja:bill:190:501',
                        'gasto_id': 501,
                        'reembolso_id': 190,
                        'amount': 11300,
                    }],
                    'valor_credito_total': 11300,
                },
            },
            save=Mock(),
        )

        with patch.object(AlegraDocument.objects, 'filter') as doc_filter:
            doc_filter.return_value.first.return_value = bill_doc
            AlegraIntegrationService()._finalize_caja_journal_doc(journal_doc)

        debit = journal_doc.payload['entries'][0]
        credit = journal_doc.payload['entries'][1]
        self.assertEqual(debit['debit'], 11299.0)
        self.assertEqual(debit['id'], '6787')
        self.assertEqual(debit['associatedDocument']['idResource'], 211)
        self.assertEqual(credit['credit'], 11299.0)
        self.assertEqual(journal_doc.payload['__local']['valor_credito_total'], 11299.0)
        self.assertEqual(journal_doc.payload['__local']['pending_bills'][0]['amount'], 11299.0)

    @patch('alegra_integration.services.MappingResolver')
    @patch('alegra_integration.services.AlegraMCPClient')
    def test_finalize_reports_gasto_and_bill_when_cxp_missing(self, mock_client_cls, mock_resolver_cls):
        from alegra_integration.models import AlegraDocument
        from alegra_integration.services import AlegraIntegrationService
        from alegra_integration.exceptions import AlegraConfigurationError

        empresa = SimpleNamespace(pk='901018375')
        bill_doc = SimpleNamespace(
            empresa=empresa,
            document_type='caja_bill',
            local_key='caja:bill:99:501',
            alegra_id='777',
            status=AlegraDocument.STATUS_SENT,
            response={'id': '777'},  # sin __cxp_category_id ni journal
        )
        journal_doc = SimpleNamespace(
            empresa=empresa,
            document_type='caja_journal',
            local_key='caja:journal:batch:99',
            payload={
                'entries': [{
                    'id': '0',
                    'debit': 1000,
                    'credit': 0,
                    'associatedDocument': {'idResource': 0, 'resourceType': 'bill'},
                }],
                '__local': {
                    'pending_bills': [{
                        'local_key': 'caja:bill:99:501',
                        'gasto_id': 501,
                        'amount': 1000,
                    }],
                },
            },
            save=Mock(),
        )
        mock_client = Mock()
        mock_client.get_bill.return_value = {'id': '777'}
        mock_client_cls.return_value = mock_client
        mock_resolver_cls.return_value.get.return_value = None

        with patch.object(AlegraDocument.objects, 'filter') as doc_filter:
            doc_filter.return_value.first.return_value = bill_doc
            with self.assertRaises(AlegraConfigurationError) as ctx:
                AlegraIntegrationService()._finalize_caja_journal_doc(journal_doc)

        msg = str(ctx.exception)
        self.assertIn('Linea 1', msg)
        self.assertIn('gasto 501', msg)
        self.assertIn('Alegra id 777', msg)
        self.assertIn('caja:bill:99:501', msg)
        self.assertIn('901018375', msg)
        self.assertIn('caja_cxp/default_cxp', msg)


class CajaJournalProgressTests(SimpleTestCase):
    def test_ensure_caja_batch_journal_creates_pending_placeholder(self):
        from alegra_integration.models import AlegraDocument, AlegraSyncBatch
        from alegra_integration.services import AlegraIntegrationService

        empresa = SimpleNamespace(pk='901')
        proyecto = SimpleNamespace(pk='PRJ')
        batch = SimpleNamespace(pk=55, fecha_desde=datetime.date(2026, 6, 1), fecha_hasta=datetime.date(2026, 6, 30))
        gasto = SimpleNamespace(pk=501, reembolso_id=None, fecha_gasto=datetime.date(2026, 6, 5))
        svc = AlegraIntegrationService()
        pending_doc = SimpleNamespace(
            pk=900,
            status=AlegraDocument.STATUS_PENDING,
            document_type='caja_journal',
            local_key='caja:journal:batch:55',
            payload={'__local': {'bills_ready': 0, 'bills_total': 1}},
        )

        with patch.object(AlegraDocument.objects, 'filter') as doc_filter, \
             patch.object(svc, '_upsert_document', return_value=pending_doc) as upsert, \
             patch.object(svc, '_count_sent_caja_bills', return_value=0):
            doc_filter.return_value.first.return_value = None
            result = svc._ensure_caja_batch_journal(
                batch=batch,
                empresa=empresa,
                proyecto=proyecto,
                caja_id=7,
                gastos=[gasto],
                fecha_desde=batch.fecha_desde,
                fecha_hasta=batch.fecha_hasta,
            )

        self.assertIn('pending_journal', result)
        upsert.assert_called_once()
        kwargs = upsert.call_args.kwargs
        self.assertEqual(kwargs['status'], AlegraDocument.STATUS_PENDING)
        self.assertEqual(kwargs['document_type'], 'caja_journal')
        local = kwargs['payload']['__local']
        self.assertTrue(local['awaiting_bills'])
        self.assertEqual(local['bills_total'], 1)
        self.assertEqual(local['pending_bills'][0]['local_key'], 'caja:bill:None:501')

    def test_refresh_does_not_auto_activate_journal(self):
        from alegra_integration.services import AlegraIntegrationService

        batch = SimpleNamespace(pk=56)
        svc = AlegraIntegrationService()
        with patch.object(svc, '_activate_caja_journal_doc') as activate:
            out = svc._refresh_caja_journal_progress(batch)
        self.assertIsNone(out)
        activate.assert_not_called()


class CajaJournalSelectionTests(SimpleTestCase):
    def test_journaled_bills_index_from_pending_bills(self):
        from alegra_integration.models import AlegraDocument
        from alegra_integration.services import AlegraIntegrationService

        empresa = SimpleNamespace(pk='901')
        journal = SimpleNamespace(
            pk=1,
            local_key='caja:journal:batch:10:part:1',
            payload={
                'reference': 'LC-CAJA-LOTE-10-P1',
                '__local': {
                    'caja_id': 7,
                    'pending_bills': [
                        {'local_key': 'caja:bill:190:501', 'alegra_bill_id': 211},
                        {'local_key': 'caja:bill:190:502', 'alegra_bill_id': 212},
                    ],
                },
            },
        )

        class _Qs(list):
            def filter(self, **kwargs):
                return self
            def order_by(self, *args):
                return self

        with patch.object(AlegraDocument.objects, 'filter', return_value=_Qs([journal])):
            by_key, by_id = AlegraIntegrationService()._caja_journaled_bills_index(empresa, caja_id=7)

        self.assertEqual(by_key['caja:bill:190:501'], 'LC-CAJA-LOTE-10-P1')
        self.assertEqual(by_id['211'], 'LC-CAJA-LOTE-10-P1')
        self.assertEqual(by_id['212'], 'LC-CAJA-LOTE-10-P1')

    def test_list_marks_used_bills(self):
        from alegra_integration.models import AlegraDocument, AlegraSyncBatch
        from alegra_integration.services import AlegraIntegrationService

        empresa = SimpleNamespace(pk='901')
        batch = SimpleNamespace(
            pk=10,
            empresa=empresa,
            empresa_id='901',
            document_type=AlegraSyncBatch.DOC_CAJA,
            summary={'caja_id': 7},
        )
        bill_used = SimpleNamespace(
            pk=1, local_key='caja:bill:None:501', source_pk='501', alegra_id='211',
            status=AlegraDocument.STATUS_SENT, payload={'__local': {}},
        )
        bill_free = SimpleNamespace(
            pk=2, local_key='caja:bill:None:502', source_pk='502', alegra_id='212',
            status=AlegraDocument.STATUS_SENT, payload={'__local': {}},
        )
        gasto501 = SimpleNamespace(
            pk=501, fecha_gasto=datetime.date(2026, 6, 2), valor=11300,
            tercero=SimpleNamespace(nombres='PAULA', apellidos='HENAO', nombre_completo=lambda: 'PAULA HENAO'),
        )
        gasto502 = SimpleNamespace(
            pk=502, fecha_gasto=datetime.date(2026, 6, 3), valor=50000,
            tercero=SimpleNamespace(nombres='JUAN', apellidos='PEREZ', nombre_completo=lambda: 'JUAN PEREZ'),
        )

        class _BillQs(list):
            def filter(self, **kwargs):
                return self
            def exclude(self, **kwargs):
                return self
            def order_by(self, *args):
                return self

        batch.documents = SimpleNamespace(
            filter=lambda **kw: _BillQs([bill_used, bill_free])
        )

        with patch.object(AlegraSyncBatch.objects, 'select_related') as sel, \
             patch.object(AlegraIntegrationService, '_caja_journaled_bills_index', return_value=(
                 {'caja:bill:None:501': 'LC-REF'}, {'211': 'LC-REF'},
             )), \
             patch('alegra_integration.services.gastos_caja.objects') as gastos_objects:
            sel.return_value.get.return_value = batch
            gastos_objects.filter.return_value.select_related.return_value = [gasto501, gasto502]
            data = AlegraIntegrationService().list_caja_journal_bills(10)

        self.assertEqual(data['total'], 2)
        self.assertEqual(data['used'], 1)
        self.assertEqual(data['available'], 1)
        used_row = next(r for r in data['bills'] if r['bill_id'] == '211')
        free_row = next(r for r in data['bills'] if r['bill_id'] == '212')
        self.assertTrue(used_row['used'])
        self.assertEqual(used_row['journal_ref'], 'LC-REF')
        self.assertFalse(free_row['used'])
        self.assertEqual(free_row['tercero'], 'JUAN PEREZ')

    def test_build_rejects_already_used_bill(self):
        from alegra_integration.models import AlegraDocument, AlegraSyncBatch
        from alegra_integration.services import AlegraIntegrationService
        from alegra_integration.exceptions import AlegraConfigurationError

        empresa = SimpleNamespace(pk='901')
        batch = SimpleNamespace(
            pk=10,
            empresa=empresa,
            document_type=AlegraSyncBatch.DOC_CAJA,
            summary={'caja_id': 7},
            fecha_desde=datetime.date(2026, 6, 1),
            fecha_hasta=datetime.date(2026, 6, 30),
        )
        bill = SimpleNamespace(
            pk=1, local_key='caja:bill:None:501', source_pk='501', alegra_id='211',
            status=AlegraDocument.STATUS_SENT, payload={},
        )

        class _BillQs(list):
            def filter(self, **kwargs):
                return self
            def order_by(self, *args):
                return self

        batch.documents = SimpleNamespace(filter=lambda **kw: _BillQs([bill]))

        with patch.object(AlegraSyncBatch.objects, 'select_related') as sel, \
             patch.object(AlegraIntegrationService, '_caja_journaled_bills_index', return_value=(
                 {'caja:bill:None:501': 'LC-REF'}, {'211': 'LC-REF'},
             )):
            sel.return_value.get.return_value = batch
            with self.assertRaises(AlegraConfigurationError) as ctx:
                AlegraIntegrationService().build_caja_journal_from_selection(10, [1])
        self.assertIn('ya fue usado', str(ctx.exception))

    def test_build_creates_part_local_key_and_activates(self):
        from alegra_integration.models import AlegraDocument, AlegraSyncBatch
        from alegra_integration.services import AlegraIntegrationService

        empresa = SimpleNamespace(pk='901')
        batch = SimpleNamespace(
            pk=10,
            empresa=empresa,
            empresa_id='901',
            proyecto_id=None,
            document_type=AlegraSyncBatch.DOC_CAJA,
            summary={'caja_id': 7},
            fecha_desde=datetime.date(2026, 6, 1),
            fecha_hasta=datetime.date(2026, 6, 30),
            status='preview',
            total_documents=1,
            success_count=0,
            error_count=0,
            created_by_id=None,
            save=Mock(),
        )
        bill = SimpleNamespace(
            pk=1, local_key='caja:bill:None:501', source_pk='501', alegra_id='211',
            status=AlegraDocument.STATUS_SENT, payload={'__local': {'reembolso_id': None}},
        )
        gasto = SimpleNamespace(
            pk=501, reembolso_id=None, fecha_gasto=datetime.date(2026, 6, 2),
            forma_pago_id=7, valor=11299,
        )
        journal_doc = SimpleNamespace(
            pk=99,
            status=AlegraDocument.STATUS_PENDING,
            local_key='caja:journal:batch:10:part:1',
            payload={'__local': {}, 'reference': 'old'},
            save=Mock(),
        )

        class _BillQs(list):
            def filter(self, **kwargs):
                return self
            def order_by(self, *args):
                return self
            def count(self):
                return len(self)
            def values_list(self, *args, **kwargs):
                return []

        def documents_filter(**kwargs):
            if kwargs.get('document_type') == 'caja_bill':
                return _BillQs([bill])
            if kwargs.get('document_type') == 'caja_journal':
                return _BillQs([])
            return _BillQs([])

        batch.documents = SimpleNamespace(
            filter=documents_filter,
            count=lambda: 2,
            order_by=lambda *a: [bill, journal_doc],
        )

        with patch.object(AlegraSyncBatch.objects, 'select_related') as sel, \
             patch.object(AlegraIntegrationService, '_caja_journaled_bills_index', return_value=({}, {})), \
             patch.object(AlegraIntegrationService, '_discard_caja_journal_drafts'), \
             patch.object(AlegraIntegrationService, '_upsert_document', return_value=journal_doc) as upsert, \
             patch.object(AlegraIntegrationService, '_activate_caja_journal_doc') as activate, \
             patch.object(AlegraIntegrationService, '_document_summary', side_effect=lambda d: {'id': getattr(d, 'pk', None)}), \
             patch('alegra_integration.services.gastos_caja.objects') as gastos_objects, \
             patch('andinasoft.models.cuentas_pagos.objects') as caja_objects:
            sel.return_value.get.return_value = batch
            gastos_objects.filter.return_value.select_related.return_value = [gasto]
            caja_objects.filter.return_value.first.return_value = SimpleNamespace(pk=7, cuentabanco='CAJA')
            journal_doc.status = AlegraDocument.STATUS_VALID
            journal_doc.payload = {
                'reference': 'LC-CAJA-LOTE-10',
                '__local': {'pending_bills': [{'local_key': 'caja:bill:None:501'}]},
            }
            data = AlegraIntegrationService().build_caja_journal_from_selection(10, [1])

        upsert.assert_called_once()
        self.assertEqual(upsert.call_args.kwargs['local_key'], 'caja:journal:batch:10:part:1')
        activate.assert_called_once()
        self.assertIn('documents', data)
        self.assertEqual(journal_doc.payload['reference'], 'LC-CAJA-LOTE-10-P1')


class PaymentReconcileTests(SimpleTestCase):
    def test_should_attempt_on_code_4031(self):
        from alegra_integration.exceptions import AlegraClientError
        from alegra_integration.pago_reconcile import should_attempt_payment_reconcile

        exc = AlegraClientError(
            "Alegra HTTP 400: {'message': 'El monto es mayor que lo que falta por pagar', 'code': 4031}"
        )
        self.assertTrue(should_attempt_payment_reconcile(exc))

    def test_payment_criteria_from_bills_payload(self):
        from alegra_integration.pago_reconcile import payment_criteria_from_payload

        criteria = payment_criteria_from_payload({
            'type': 'out',
            'date': '2026-05-15',
            'bankAccount': {'id': '12'},
            'client': {'id': '175'},
            'bills': [{'id': '50', 'amount': 801561.0}],
        })
        self.assertEqual(criteria['date'], '2026-05-15')
        self.assertEqual(criteria['bank_account_id'], '12')
        self.assertEqual(criteria['client_id'], '175')
        self.assertEqual(float(criteria['amount']), 801561.0)
        self.assertEqual(criteria['bill_lines'][0]['id'], '50')

    def test_payment_matches_criteria_bills(self):
        from alegra_integration.pago_reconcile import payment_criteria_from_payload, payment_matches_criteria

        payload = {
            'type': 'out',
            'date': '2026-05-15',
            'bankAccount': {'id': '12'},
            'client': {'id': '175'},
            'bills': [{'id': '50', 'amount': 801561.0}],
        }
        criteria = payment_criteria_from_payload(payload)
        payment = {
            'id': '9001',
            'type': 'out',
            'date': '2026-05-15',
            'bankAccount': {'id': '12'},
            'client': {'id': '175'},
            'bills': [{'id': '50', 'amount': 801561.0}],
        }
        self.assertTrue(payment_matches_criteria(payment, criteria))

    def test_find_matching_payment_requires_single_match(self):
        from alegra_integration.pago_reconcile import find_matching_payment

        payload = {
            'type': 'out',
            'date': '2026-05-15',
            'bankAccount': {'id': '12'},
            'client': {'id': '175'},
            'bills': [{'id': '50', 'amount': 100.0}],
        }
        client = Mock()
        client.list_payments.return_value = [
            {
                'id': '1',
                'type': 'out',
                'date': '2026-05-15',
                'bankAccount': {'id': '12'},
                'client': {'id': '175'},
                'bills': [{'id': '50', 'amount': 100.0}],
            },
            {
                'id': '2',
                'type': 'out',
                'date': '2026-05-15',
                'bankAccount': {'id': '12'},
                'client': {'id': '175'},
                'bills': [{'id': '50', 'amount': 100.0}],
            },
        ]
        self.assertIsNone(find_matching_payment(client, payload))

    @patch('alegra_integration.pago_reconcile.sync_pago_from_alegra_document')
    @patch('alegra_integration.pago_reconcile.find_matching_payment')
    def test_reconcile_marks_document_sent(self, mock_find, mock_sync):
        from alegra_integration.exceptions import AlegraClientError
        from alegra_integration.models import AlegraDocument
        from alegra_integration.pago_reconcile import reconcile_expense_payment_document

        doc = SimpleNamespace(
            pk=1,
            empresa=SimpleNamespace(pk='901018375'),
            document_type='expense_payment',
            payload={
                'type': 'out',
                'date': '2026-05-15',
                'bankAccount': {'id': '12'},
                'client': {'id': '175'},
                'bills': [{'id': '50', 'amount': 801561.0}],
            },
            status='failed',
            alegra_id='',
            error='',
            response={},
            sent_at=None,
            source_model='accounting.Pagos',
            source_pk='14906',
            save=Mock(),
        )
        mock_find.return_value = {'id': '777', 'date': '2026-05-15'}
        exc = AlegraClientError("Alegra HTTP 400: {'message': 'x', 'code': 4031}")

        with patch.object(AlegraDocument.objects, 'filter') as mock_filter:
            mock_filter.return_value.exclude.return_value.exists.return_value = False
            self.assertTrue(reconcile_expense_payment_document(doc, Mock(), exc))

        self.assertEqual(doc.status, AlegraDocument.STATUS_SENT)
        self.assertEqual(doc.alegra_id, '777')
        self.assertTrue(doc.response.get('reconciled'))
        mock_sync.assert_called_once_with(doc)

    @patch('alegra_integration.services.reconcile_expense_payment_document')
    @patch('alegra_integration.services.AlegraMCPClient')
    def test_try_send_reconciles_on_4031(self, mock_client_cls, mock_reconcile):
        from alegra_integration.exceptions import AlegraClientError
        from alegra_integration.models import AlegraDocument
        from alegra_integration.services import AlegraIntegrationService

        doc = SimpleNamespace(
            pk=10,
            empresa_id='901018375',
            empresa=SimpleNamespace(pk='901018375'),
            document_type='expense_payment',
            alegra_operation='POST /payments',
            status=AlegraDocument.STATUS_VALID,
            local_key='expense:pago:1:t:123',
            payload={'client': {'id': '175'}, 'bills': [{'id': '50', 'amount': 100}]},
            alegra_id='',
            error='',
            response={},
            sent_at=None,
            source_model='accounting.Pagos',
            source_pk='1',
            save=Mock(),
        )
        client = Mock()
        client.create_out_payment.side_effect = AlegraClientError(
            "Alegra HTTP 400: {'message': 'El monto es mayor', 'code': 4031}"
        )
        mock_client_cls.return_value = client
        mock_reconcile.return_value = True

        with patch.object(AlegraDocument.objects, 'filter') as mock_filter:
            mock_filter.return_value.exclude.return_value.first.return_value = None
            outcome = AlegraIntegrationService()._try_send_batch_document(
                SimpleNamespace(), doc, {}, retry_failed=True,
            )

        self.assertEqual(outcome, 'sent')
        mock_reconcile.assert_called_once()


class AnticipoPaymentBuilderTests(SimpleTestCase):
    @patch('alegra_integration.builders.asesores')
    @patch('alegra_integration.builders.empresas')
    @patch('alegra_integration.builders.clientes')
    def test_anticipo_payload_includes_client(self, mock_clientes, mock_empresas, mock_asesores):
        from alegra_integration.builders import ExpensePaymentBuilder

        mock_clientes.objects.filter.return_value.exists.return_value = True

        class AnticipoResolver(ResolverStub):
            def contact_for_cliente(self, cliente_id):
                return 'contact-anticipo-99'

            def numeration(self, document_code, required=True):
                return 'num-anticipo'

            def get(self, mapping_type, *args, **kwargs):
                if kwargs.get('local_code') == 'default_anticipo':
                    return 'cat-anticipo-default'
                return super().get(mapping_type, *args, **kwargs)

        anticipo = SimpleNamespace(
            pk=501,
            id_tercero='900111222',
            nombre_tercero='PROVEEDOR ANTICIPO',
            descripcion='Anticipo marzo',
            valor=250000,
            fecha_pago=datetime.date(2026, 5, 10),
            cuenta=SimpleNamespace(pk=3, cuentabanco='transfer', nit_empresa_id='901018375'),
            tipo_anticipo=SimpleNamespace(cuenta_debito_1='13300501'),
            tipo_anticipo_id=8,
        )
        builder = ExpensePaymentBuilder(SimpleNamespace(pk='901018375'))
        builder.resolver = AnticipoResolver()
        built = builder._from_anticipo(anticipo)

        self.assertEqual(built.payload['client'], {'id': 'contact-anticipo-99'})
        self.assertEqual(built.payload['type'], 'out')
        self.assertEqual(built.local_key, 'expense:anticipo:501')


class PartnerContactToolsTests(SimpleTestCase):
    def test_extract_missing_contact_refs_for_caja_partner(self):
        from alegra_integration.services import _extract_missing_contact_refs

        err = (
            'Falta mapeo Alegra tipo "contact" para empresa 900, '
            'proyecto empresa (model=accounting.partners, pk=900123456).'
        )
        refs = _extract_missing_contact_refs(err)
        self.assertEqual(refs, [('accounting.partners', '900123456')])

    def test_extract_missing_contact_refs_for_legacy_index_error(self):
        from alegra_integration.services import _extract_missing_contact_refs

        err = (
            'Falta contacto en índice Alegra para empresa 900 '
            '(identification=900123456). Sincroniza contactos o enlázalo manualmente.'
        )
        with patch('alegra_integration.services._resolve_identification_to_local') as resolve:
            resolve.return_value = ('andinasoft.profiles', '7', 'MARIA LOPEZ')
            refs = _extract_missing_contact_refs(err)
        self.assertEqual(refs, [('andinasoft.profiles', '7')])

    def test_resolve_identification_prefers_profile_when_not_partner(self):
        from alegra_integration.services import _resolve_identification_to_local

        profile = SimpleNamespace(pk=12, identificacion='1152463184')
        profile.__str__ = lambda: 'ANA RESP'
        with patch('alegra_integration.services.Partners') as partners_model, \
             patch('andinasoft.models.Profiles') as profiles_model:
            partners_model.objects.filter.return_value.first.return_value = None
            profiles_model.objects.filter.return_value.first.return_value = profile
            out = _resolve_identification_to_local('1152463184')
        self.assertEqual(out[0], 'andinasoft.profiles')
        self.assertEqual(out[1], '12')

    def test_local_third_party_info_resolves_profile(self):
        from alegra_integration.services import _local_third_party_info

        profile = SimpleNamespace(pk=12, identificacion='1152463184')
        with patch('andinasoft.models.Profiles') as profiles_model:
            profiles_model.objects.filter.return_value.first.return_value = profile
            model, ident, name, types = _local_third_party_info('andinasoft.profiles', '12')
        self.assertEqual(model, 'andinasoft.profiles')
        self.assertEqual(ident, '12')
        self.assertIn('provider', types)

    @patch('alegra_integration.services.Partners')
    def test_local_third_party_info_resolves_partner(self, mock_partners):
        from alegra_integration.services import _local_third_party_info

        partner = SimpleNamespace(nombres='JUAN', apellidos='PEREZ')
        partner.nombre_completo = lambda: 'JUAN PEREZ'
        mock_partners.objects.filter.return_value.first.return_value = partner

        model, ident, name, types = _local_third_party_info('accounting.partners', '123456')
        self.assertEqual(model, 'accounting.partners')
        self.assertEqual(ident, '123456')
        self.assertEqual(name, 'JUAN PEREZ')
        self.assertEqual(types, ['provider'])

    def test_contact_for_cliente_falls_back_to_identification(self):
        from alegra_integration.mapping import MappingResolver

        resolver = MappingResolver(SimpleNamespace(pk='900'))
        resolver.get = Mock(return_value=None)
        resolver.contact_by_identification = Mock(return_value='alegra-from-index')
        self.assertEqual(resolver.contact_for_cliente('901560549'), 'alegra-from-index')
        resolver.contact_by_identification.assert_called_once()

    def test_resolve_identification_returns_terceros_raw_when_unknown(self):
        from alegra_integration.services import _resolve_identification_to_local

        with patch('alegra_integration.services.Partners') as partners_model, \
             patch('andinasoft.models.Profiles') as profiles_model, \
             patch('alegra_integration.services.asesores') as asesores_model, \
             patch('alegra_integration.services.clientes') as clientes_model, \
             patch('alegra_integration.services.empresas') as empresas_model:
            partners_model.objects.filter.return_value.first.return_value = None
            profiles_model.objects.filter.return_value.first.return_value = None
            asesores_model.objects.filter.return_value.first.return_value = None
            clientes_model.objects.filter.return_value.first.return_value = None
            empresas_model.objects.filter.return_value.first.return_value = None
            out = _resolve_identification_to_local('800999888')
        self.assertEqual(out[0], 'andinasoft.terceros_raw')
        self.assertEqual(out[1], '800999888')

    def test_contact_for_partner_uses_mapping_before_index(self):
        from alegra_integration.mapping import MappingResolver

        resolver = MappingResolver(SimpleNamespace(pk='900'))
        resolver.get = Mock(return_value='mapped-99')
        resolver.contact_by_identification = Mock()
        self.assertEqual(resolver.contact_for_partner('123456'), 'mapped-99')
        resolver.get.assert_called_once()
        resolver.contact_by_identification.assert_not_called()

    def test_contact_for_partner_raises_standard_contact_error(self):
        from alegra_integration.mapping import MappingResolver

        resolver = MappingResolver(SimpleNamespace(pk='900'))
        resolver.get = Mock(return_value=None)
        resolver.contact_by_identification = Mock(return_value=None)
        with self.assertRaises(AlegraConfigurationError) as ctx:
            resolver.contact_for_partner('123456')
        self.assertIn('tipo "contact"', str(ctx.exception))
        self.assertIn('accounting.partners', str(ctx.exception))
        self.assertIn('pk=123456', str(ctx.exception))

    def test_contact_by_identification_falls_back_to_contact_mapping(self):
        from alegra_integration.mapping import MappingResolver
        from alegra_integration.models import AlegraContactIndex, AlegraMapping

        resolver = MappingResolver(SimpleNamespace(pk='900'))
        with patch.object(AlegraContactIndex.objects, 'filter') as index_filter, \
             patch.object(AlegraMapping.objects, 'filter') as mapping_filter:
            index_qs = index_filter.return_value
            index_qs.order_by.return_value.first.return_value = None
            mapped = SimpleNamespace(alegra_id='alegra-88')
            mapping_qs = mapping_filter.return_value
            mapping_qs.order_by.return_value.first.return_value = mapped
            self.assertEqual(
                resolver.contact_by_identification('1152463184'),
                'alegra-88',
            )
            mapping_filter.assert_called()

    def test_caja_bill_uses_contact_for_partner(self):
        gasto, _ = CajaBuilderTests()._gasto()
        resolver = ResolverStub()
        resolver.contact_for_partner = Mock(return_value='provider-900123456')
        built = CajaGastoBillBuilder(SimpleNamespace(pk='901018375'), resolver).build(gasto)
        self.assertEqual(built.payload['provider'], {'id': 'provider-900123456'})
        resolver.contact_for_partner.assert_called_once_with('900123456', required=True)


class BankMappingViewTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from andinasoft.models import cuentas_pagos

        User = get_user_model()
        self.user = User.objects.create_user(username='bank_map_tester', password='x')
        self.client.force_login(self.user)
        self.empresa = empresas.objects.create(
            Nit='900993044',
            nombre='Andina prueba',
            alegra_enabled=True,
        )
        self.cuenta = cuentas_pagos.objects.create(
            idcuenta=793339,
            nit_empresa=self.empresa,
            cuentabanco='234-793339-39',
            nro_cuentacontable=11100501,
            activo=True,
        )

    @patch('alegra_integration.views.AlegraMCPClient')
    def test_save_bank_requires_category_when_puc_present(self, client_cls):
        client_cls.return_value.rest.return_value = {'category': {}}
        resp = self.client.post(
            '/accounting/alegra/references/save-bank-mapping',
            data=json.dumps({
                'empresa': self.empresa.pk,
                'local_idcuenta': self.cuenta.idcuenta,
                'alegra_id': 'bank-99',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 400)

    @patch('alegra_integration.views.AlegraMCPClient')
    def test_save_bank_persists_bank_and_category(self, client_cls):
        from alegra_integration.models import AlegraMapping

        client_cls.return_value.rest.return_value = {
            'category': {'id': '6308', 'code': '1110', 'name': 'Bancos'},
        }
        resp = self.client.post(
            '/accounting/alegra/references/save-bank-mapping',
            data=json.dumps({
                'empresa': self.empresa.pk,
                'local_idcuenta': self.cuenta.idcuenta,
                'alegra_id': 'bank-99',
                'category_alegra_id': '6308',
                'category_description': '1110 · Bancos',
            }),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body['ok'])
        self.assertEqual(body['category_mapping']['alegra_category_id'], '6308')
        self.assertTrue(
            AlegraMapping.objects.filter(
                empresa_id=self.empresa.pk,
                mapping_type=AlegraMapping.BANK_ACCOUNT,
                local_pk=str(self.cuenta.idcuenta),
                alegra_id='bank-99',
            ).exists()
        )
        cat = AlegraMapping.objects.get(
            empresa_id=self.empresa.pk,
            mapping_type=AlegraMapping.CATEGORY,
            local_model='andinasoft.cuentas_pagos',
            local_pk=str(self.cuenta.idcuenta),
            local_code='bank_journal',
        )
        self.assertEqual(cat.alegra_id, '6308')

    @patch('alegra_integration.views.AlegraMCPClient')
    def test_suggest_bank_category(self, client_cls):
        client_cls.return_value.rest.return_value = {
            'category': {'id': '5144', 'code': '1110', 'name': 'Banco Davivienda'},
        }
        resp = self.client.get(
            '/accounting/alegra/references/suggest-bank-category',
            {'empresa': self.empresa.pk, 'bank_id': 'bank-99'},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['category_id'], '5144')
        self.assertIn('Banco Davivienda', body['category_label'])

