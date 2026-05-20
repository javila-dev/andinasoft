import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from alegra_integration.builders import (
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
        self.assertEqual(built.payload['entries'][0]['id'], 'mapped-id')
        self.assertEqual(built.payload['entries'][0]['client'], 'client-123')
        self.assertEqual(built.payload['entries'][1]['credit'], 51150.0)
        self.assertEqual(built.payload['entries'][1]['debit'], 0)
        self.assertEqual(built.payload['entries'][1]['client'], 'client-123')
        self.assertEqual(built.payload['entries'][2]['credit'], 51150.0)
        self.assertEqual(built.payload['entries'][2]['client'], 'client-999')

    @patch('alegra_integration.builders.cuentas_intercompanias')
    @patch('alegra_integration.builders.Recaudos')
    @patch('alegra_integration.builders.formas_pago')
    @patch('alegra_integration.builders.cuentas_pagos')
    @patch('alegra_integration.builders.MappingResolver')
    @patch('alegra_integration.builders.clientes')
    def test_receipt_intercompany_bank_uses_cxc_not_bank_mapping(
        self, clientes_model, resolver_cls, cuentas_pagos_model, formas_pago, recaudos, interco_model,
    ):
        class IntercoResolver(ResolverStub):
            def get(self, mapping_type, **kwargs):
                local_code = kwargs.get('local_code', '')
                if local_code == 'receipt_client_advance':
                    return 'cat-advance'
                if local_code == 'interco_cxc:900999111':
                    return 'cat-interco-cxc'
                return super().get(mapping_type, **kwargs)

        resolver_cls.return_value = IntercoResolver()
        clientes_model.objects.filter.return_value.first.return_value = SimpleNamespace(nombrecompleto='Titular')
        cuenta = SimpleNamespace(pk=6, nro_cuentacontable='110505', nit_empresa_id=SimpleNamespace(pk='900999111'))
        cuentas_pagos_model.objects.filter.return_value.first.return_value = cuenta
        formas_pago.objects.using.return_value.filter.return_value.first.return_value = SimpleNamespace(
            cuenta_asociada_id=6,
        )
        rel = SimpleNamespace(pk=1, cuenta_por_cobrar=13051001, cuenta_por_pagar=22051001)
        interco_qs = Mock()
        interco_qs.first.return_value = rel
        interco_model.objects.filter.return_value = interco_qs

        receipt = SimpleNamespace(
            pk=10989,
            valor=Decimal('500000'),
            idtercero='123',
            numrecibo='RC-99',
            fecha=datetime.date(2026, 5, 1),
            fecha_pago=datetime.date(2026, 5, 1),
            formapago='TRANSFERENCIA',
            concepto='',
        )
        receipt.info_adj = lambda: SimpleNamespace(idtercero1='123', idtercero2='', idtercero3='', idtercero4='')

        built = ReceiptPaymentBuilder(self.empresa, self.proyecto).build(receipt)

        self.assertEqual(built.payload['entries'][0]['id'], 'cat-interco-cxc')
        self.assertIn('INTERCO banco 900999111', built.payload['observations'])
        self.assertEqual(built.payload['entries'][1]['id'], 'cat-advance')

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
        self.assertEqual(built.payload['purchases']['categories'][0]['id'], 'cat-gtt-expense')
        self.assertEqual(built.payload['__local']['gtt_cxp_category_id'], 'cat-gtt-cxp')
        self.assertEqual(built.payload['retentions'][0]['id'], 'ret-commission_retefuente')

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
