from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from unittest.mock import patch
import json

from accounting.gasto_aprobacion import (
    aprobar_gasto_alegra,
    asignar_gasto_alegra,
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
