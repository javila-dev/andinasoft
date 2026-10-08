"""Tests de la Etapa 3: validación e idempotencia de seguimientos, recibos (sin BD)."""
import datetime
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db import IntegrityError
from django.test import RequestFactory, SimpleTestCase

from chatwoot_panel import auth, seguimientos_service as svc, views
from chatwoot_panel.tests import _token, _user

HOY = datetime.date(2026, 10, 8)
LLAVE = 'b7a1c2d3-0000-4000-8000-000000000001'


def _datos(**extra):
    base = {'tipo': 'Cobro', 'forma': 'Whatsapp', 'comentario': 'Paga el viernes', 'idempotency_key': LLAVE}
    base.update(extra)
    return base


class ValidarTests(SimpleTestCase):
    def test_opciones_salen_del_formulario_de_andinasoft(self):
        self.assertIn('Cobro', svc.TIPOS)
        self.assertIn('Whatsapp', svc.FORMAS)

    def test_sin_compromiso_guarda_cero_como_el_formulario_original(self):
        datos = svc.validar(_datos(), hoy=HOY)
        self.assertEqual((datos['valor_compromiso'], datos['fecha_compromiso']), (0, None))

    def test_compromiso_valido(self):
        datos = svc.validar(_datos(compromiso=True, fecha_compromiso='2026-10-15', valor_compromiso='1.500.000'), hoy=HOY)
        self.assertEqual((datos['valor_compromiso'], datos['fecha_compromiso']), (1500000, datetime.date(2026, 10, 15)))

    def test_errores_para_el_agente(self):
        casos = [
            _datos(tipo='Otro'),
            _datos(forma='Fax'),
            _datos(comentario='   '),
            _datos(comentario='x' * 501),
            _datos(compromiso=True, fecha_compromiso='', valor_compromiso='100'),
            _datos(compromiso=True, fecha_compromiso='2026-10-01', valor_compromiso='100'),
            _datos(compromiso=True, fecha_compromiso='2026-10-15', valor_compromiso='0'),
            _datos(idempotency_key=''),
        ]
        for datos in casos:
            with self.assertRaises(svc.DatosInvalidos, msg=datos):
                svc.validar(datos, hoy=HOY)

    def test_comentario_se_limpia(self):
        self.assertEqual(svc.validar(_datos(comentario='  hola \n  mundo '), hoy=HOY)['comentario'], 'hola mundo')


class RegistrarTests(SimpleTestCase):
    def setUp(self):
        self.datos = svc.validar(_datos(), hoy=HOY)
        self.user = SimpleNamespace(get_username=lambda: 'ana')

    def test_crea_una_vez_y_guarda_el_id(self):
        ref = MagicMock(proyecto='Oasis', adj='ADJ1')
        with patch.object(svc.ChatwootSeguimientoRef, 'objects') as refs, \
                patch.object(svc, 'seguimientos') as seg, patch.object(svc.transaction, 'atomic', MagicMock()):
            refs.create.return_value = ref
            seg.objects.using.return_value.filter.return_value.order_by.return_value.values_list.return_value.first.return_value = 77
            result, creado = svc.registrar('Oasis', 'ADJ1', self.datos, self.user, conversation_id='2', hoy=HOY)
        self.assertTrue(creado)
        seg.objects.using.return_value.create.assert_called_once()
        kwargs = seg.objects.using.return_value.create.call_args.kwargs
        self.assertEqual((kwargs['usuario'], kwargs['valor_compromiso'], kwargs['fecha']), ('ana', 0, HOY))
        self.assertEqual(ref.seguimiento_id, 77)

    def test_doble_envio_no_duplica(self):
        existente = SimpleNamespace(proyecto='Oasis', adj='ADJ1', seguimiento_id=77)
        with patch.object(svc.ChatwootSeguimientoRef, 'objects') as refs, \
                patch.object(svc, 'seguimientos') as seg, patch.object(svc.transaction, 'atomic', MagicMock()):
            refs.create.side_effect = IntegrityError('duplicada')
            refs.get.return_value = existente
            result, creado = svc.registrar('Oasis', 'ADJ1', self.datos, self.user, hoy=HOY)
        self.assertFalse(creado)
        self.assertIs(result, existente)
        seg.objects.using.return_value.create.assert_not_called()

    def test_llave_de_otro_negocio_se_rechaza(self):
        with patch.object(svc.ChatwootSeguimientoRef, 'objects') as refs, \
                patch.object(svc, 'seguimientos'), patch.object(svc.transaction, 'atomic', MagicMock()):
            refs.create.side_effect = IntegrityError('duplicada')
            refs.get.return_value = SimpleNamespace(proyecto='Oasis', adj='ADJ9')
            with self.assertRaises(svc.DatosInvalidos):
                svc.registrar('Oasis', 'ADJ1', self.datos, self.user, hoy=HOY)

    def test_si_falla_la_insercion_libera_la_llave(self):
        ref = MagicMock()
        with patch.object(svc.ChatwootSeguimientoRef, 'objects') as refs, \
                patch.object(svc, 'seguimientos') as seg, patch.object(svc.transaction, 'atomic', MagicMock()):
            refs.create.return_value = ref
            seg.objects.using.return_value.create.side_effect = Exception("Table 'seguimientos' doesn't exist")
            with self.assertRaises(svc.NoDisponible):
                svc.registrar('Alttum', 'ADJ1', self.datos, self.user, hoy=HOY)
        ref.delete.assert_called_once()


class SeguimientosViewTests(SimpleTestCase):
    def _post(self, body):
        request = RequestFactory().post('/x', data=json.dumps(body), content_type='application/json',
                                        HTTP_AUTHORIZATION='Bearer t')
        return request

    def _patches(self, permitido=True):
        return [
            patch.object(auth, 'validar_token', return_value=_token(user=_user())),
            patch.object(auth, 'renovar'),
            patch.object(views, 'puede_ver_proyecto', return_value=permitido),
            patch.object(views, 'auditar'),
        ]

    def _run(self, request, permitido=True, **mocks):
        ps = self._patches(permitido) + [patch.object(*m) for m in mocks.values()]
        for p in ps:
            p.start()
        try:
            return views.api_seguimientos(request, 'Oasis', 'ADJ1')
        finally:
            for p in reversed(ps):
                p.stop()

    def test_proyecto_no_asignado(self):
        with patch.object(svc, 'registrar') as registrar:
            response = self._run(self._post(_datos()), permitido=False)
        self.assertEqual(response.status_code, 403)
        registrar.assert_not_called()

    def test_datos_invalidos_responden_400(self):
        response = self._run(self._post(_datos(tipo='Nada')))
        self.assertEqual(response.status_code, 400)

    def test_creado_responde_201_y_deja_nota(self):
        ref = MagicMock(nota_privada=False, chatwoot_account_id='7', chatwoot_conversation_id='2', seguimiento_id=5)
        with patch.object(svc, 'registrar', return_value=(ref, True)), patch.object(svc, 'listar', return_value=[]), \
                patch.object(views, 'nota_privada', return_value=True) as nota:
            response = self._run(self._post(_datos(account_id=7, conversation_id=2)))
        self.assertEqual(response.status_code, 201)
        nota.assert_called_once()
        self.assertTrue(json.loads(response.content)['nota_privada'])

    def test_reenvio_no_vuelve_a_dejar_nota(self):
        ref = MagicMock(nota_privada=True, chatwoot_account_id='7', chatwoot_conversation_id='2')
        with patch.object(svc, 'registrar', return_value=(ref, False)), patch.object(svc, 'listar', return_value=[]), \
                patch.object(views, 'nota_privada') as nota:
            response = self._run(self._post(_datos()))
        self.assertEqual(response.status_code, 200)
        nota.assert_not_called()
        self.assertFalse(json.loads(response.content)['creado'])

    def test_proyecto_sin_tabla_responde_409(self):
        request = RequestFactory().get('/x', HTTP_AUTHORIZATION='Bearer t')
        with patch.object(svc, 'listar', side_effect=svc.NoDisponible('Alttum')):
            response = self._run(request)
        self.assertEqual(response.status_code, 409)
