import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from alegra_integration.builders import (
    CommissionBuilder,
    ExternalCommissionSupportDocumentBuilder,
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

    def payment_method(self, local_method, required=True):
        return 'transfer'

    def get(self, *args, **kwargs):
        return 'mapped-id'


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
            numrecibo='RC-1',
            fecha=datetime.date(2026, 4, 1),
            fecha_pago=datetime.date(2026, 4, 2),
            formapago='TRANSFERENCIA',
            concepto='ABONO',
        )
        receipt.info_adj = lambda: SimpleNamespace(idtercero1='123', idtercero2='999', idtercero3='', idtercero4='')

        built = ReceiptPaymentBuilder(self.empresa, self.proyecto).build(receipt)

        self.assertEqual(built.operation, 'accounting__createJournal')
        self.assertEqual(built.payload['idNumeration'], 'num-receipt_cash')
        self.assertEqual(built.payload['reference'], 'RC-Oasis-RC-1')
        self.assertEqual(len(built.payload['entries']), 3)
        self.assertEqual(built.payload['entries'][0]['debit'], 102300.0)
        self.assertEqual(built.payload['entries'][0]['id'], 'mapped-id')
        self.assertEqual(built.payload['entries'][1]['credit'], 51150.0)
        self.assertEqual(built.payload['entries'][1]['client']['id'], 'client-123')
        self.assertEqual(built.payload['entries'][2]['credit'], 51150.0)
        self.assertEqual(built.payload['entries'][2]['client']['id'], 'client-999')

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
        self.assertEqual(built.payload['entries'][0]['debit'], 50000.0)
        self.assertEqual(built.payload['entries'][0]['id'], 'cat-133005')
        self.assertEqual(built.payload['entries'][1]['credit'], 50000.0)

    @patch('alegra_integration.builders.consecutivos')
    def test_external_commission_builds_support_document(self, consecutivos):
        consecutivos.objects.using.return_value.get.return_value = SimpleNamespace(cuenta_capital='529505')
        asesor = SimpleNamespace(pk='222', nombre='ASESOR EXTERNO', tipo_asesor='Externo')
        commission = SimpleNamespace(
            idgestor='222',
            id_pago=88,
            idadjudicacion='ADJ1',
            comision=Decimal('120000'),
            retefuente=Decimal('13200'),
            fecha=datetime.date(2026, 4, 4),
        )

        built = ExternalCommissionSupportDocumentBuilder(self.empresa, self.proyecto, self.resolver).build(commission, asesor)

        self.assertEqual(built.operation, 'POST /bills')
        self.assertEqual(built.payload['provider']['id'], 'adviser-222')
        self.assertEqual(built.payload['purchases']['categories'][0]['id'], 'cat-529505')
        self.assertEqual(built.payload['retentions'][0]['id'], 'ret-commission_retefuente')


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
