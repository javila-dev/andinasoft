import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

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
from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError


class ResolverStub:
    def bank_account_for_account(self, cuenta):
        return 'bank-1'

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
        if code == 'default_cxp':
            return 'cat-default-cxp'
        return 'mapped-id'

    def contact_by_identification(self, ident, **kwargs):
        return f'contact-{ident}'

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
        asesor = SimpleNamespace(pk='111', nombre='ASESOR INTERNO', tipo_asesor='Interno')
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
        self.assertEqual(built.payload['retentions'][0]['id'], 'ret-commission_retefuente')

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

    @patch('alegra_integration.builders.consecutivos')
    def test_gtt_builds_support_document(self, consecutivos):
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
        self.assertEqual(
            client._unwrap_rest_list({'1': {'name': 'IVA', 'percentage': 19}})[0]['id'],
            '1',
        )


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

    def test_pago_neto_canje_escenario_balance_igual_total_paid(self):
        from alegra_integration.bill_mapping import bill_pago_neto_canje

        bill = {'balance': 4039466, 'totalPaid': 4039466}
        self.assertEqual(bill_pago_neto_canje(bill), 0)

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


class CajaBuilderTests(SimpleTestCase):
    def setUp(self):
        self.empresa = SimpleNamespace(pk='901018375')
        self.resolver = ResolverStub()

    def _gasto(self, *, tipo='fe', valor=119000, subtotal_val=100000, valor_iva=None, valor_rte=None):
        concepto = SimpleNamespace(
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

    def test_caja_journal_includes_associated_document_placeholder(self):
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
        self.assertEqual(built.payload['entries'][-1]['credit'], 120000.0)
