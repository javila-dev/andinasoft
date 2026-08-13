"""Devolución de un gasto que ya pertenece a un reembolso.

Tras corregir y re-aprobar (o revisar a mano) debe volver a estado Reembolso,
no quedarse en Aprobado bloqueado por el FK.
"""
from datetime import date
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, SimpleTestCase, TestCase

from accounting.models import (
    Partners,
    Cities,
    Countries,
    States,
    conceptos_legalizacion,
    gastos_caja,
    reembolsos_caja,
)
from accounting.views import _estado_destino_tras_correccion, _volver_gasto_a_reembolso
from andinasoft.models import cuentas_pagos


class EstadoDestinoTrasCorreccionTests(SimpleTestCase):
    def test_con_reembolso_vuelve_a_reembolso(self):
        gasto = SimpleNamespace(
            reembolso_id=99,
            estado_antes_devolver=gastos_caja.ESTADO_PENDIENTE,
        )
        self.assertEqual(
            _estado_destino_tras_correccion(gasto),
            gastos_caja.ESTADO_REEMBOLSO,
        )

    def test_sin_reembolso_restaura_estado_previo(self):
        gasto = SimpleNamespace(
            reembolso_id=None,
            estado_antes_devolver=gastos_caja.ESTADO_REVISADO,
        )
        self.assertEqual(
            _estado_destino_tras_correccion(gasto),
            gastos_caja.ESTADO_REVISADO,
        )

    def test_sin_reembolso_ni_previo_queda_pendiente(self):
        gasto = SimpleNamespace(reembolso_id=None, estado_antes_devolver='')
        self.assertEqual(
            _estado_destino_tras_correccion(gasto),
            gastos_caja.ESTADO_PENDIENTE,
        )


class CajaGastoReembolsoViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser('caja_admin', 'a@a.com', 'x')
        self.responsable = User.objects.create_user('caja_resp', password='x')
        self.aprobador = User.objects.create_user('caja_apr', password='x')
        self.caja = cuentas_pagos.objects.create(
            cuentabanco='Caja test reembolso',
            es_caja=True,
            activo=True,
            usuario_responsable=self.responsable,
            usuario_aprobador=self.aprobador,
        )
        self.concepto = conceptos_legalizacion.objects.create(
            descripcion='Papeleria test',
            naturaleza_cuenta='D',
        )
        pais = Countries.objects.create(id_country='CO-TEST', country_name='Colombia')
        depto = States.objects.create(
            id_state='ANT-TEST', country=pais, state_name='Antioquia',
        )
        ciudad = Cities.objects.create(
            id_city='MDE-TEST', state=depto, city_name='Medellin',
        )
        self.tercero = Partners.objects.create(
            idTercero='900111222-test',
            document_type='13',
            nombres='Tercero',
            apellidos='Test',
            pais=pais,
            estado=depto,
            ciudad=ciudad,
            email='tercero@test.com',
        )
        self.reembolso = reembolsos_caja.objects.create(
            caja=self.caja,
            usuario_solicita=self.responsable,
            valor=50000,
        )
        self.gasto = gastos_caja.objects.create(
            concepto=self.concepto,
            fecha_gasto=date.today(),
            descripcion='GASTO TEST REEMBOLSO',
            tercero=self.tercero,
            valor=50000,
            soporte=SimpleUploadedFile('soporte.pdf', b'%PDF-1.4 test', content_type='application/pdf'),
            usuario_carga=self.responsable,
            forma_pago=self.caja,
            estado=gastos_caja.ESTADO_APROBADO,
            reembolso=self.reembolso,
            estado_antes_devolver=gastos_caja.ESTADO_REEMBOLSO,
        )
        self.client = Client()
        self.client.force_login(self.admin)

    def _post(self, data):
        return self.client.post(
            '/accounting/cajasefectivo',
            data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

    def test_approve_gasto_ligado_vuelve_a_reembolso(self):
        self.gasto.estado = gastos_caja.ESTADO_PENDIENTE
        self.gasto.save(update_fields=['estado'])
        resp = self._post({'to_do': 'approve', 'gasto': self.gasto.pk})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['class'], 'alert-success')
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.estado, gastos_caja.ESTADO_REEMBOLSO)
        self.assertEqual(self.gasto.estado_antes_devolver, '')
        self.assertEqual(self.gasto.reembolso_id, self.reembolso.pk)

    def test_marcar_revisado_gasto_ligado_restaura_reembolso(self):
        resp = self._post({'to_do': 'marcar_revisado', 'gasto': self.gasto.pk})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body['class'], 'alert-success')
        self.assertIn('Reembolso', body['msj'])
        self.gasto.refresh_from_db()
        self.assertEqual(self.gasto.estado, gastos_caja.ESTADO_REEMBOLSO)
        self.assertEqual(self.gasto.reembolso_id, self.reembolso.pk)

    def test_volver_helper_recalcula_valor_reembolso(self):
        self.gasto.valor = 75000
        self.gasto.save(update_fields=['valor'])
        ok = _volver_gasto_a_reembolso(self.gasto)
        self.assertTrue(ok)
        self.reembolso.refresh_from_db()
        self.assertEqual(self.reembolso.valor, 75000)
