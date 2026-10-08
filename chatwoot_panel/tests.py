"""Tests del acceso del panel de Chatwoot (sin BD: el ORM va simulado)."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.http import JsonResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone

from chatwoot_panel import auth, views


def _user(active=True, perm=True, pk=7):
    return SimpleNamespace(
        pk=pk, is_active=active, is_authenticated=True, email='ana@andina.co',
        has_perm=lambda p: perm and p == auth.PERMISO,
        get_full_name=lambda: 'Ana Pérez', get_username=lambda: 'ana',
    )


def _token(user=None, expires_in=timedelta(days=3), revoked=False, last_used=None):
    return SimpleNamespace(
        pk=1, user=user or _user(), jti='abc',
        expires_at=timezone.now() + expires_in,
        revoked_at=timezone.now() if revoked else None,
        last_used_at=last_used,
    )


def _raw(jti='abc', user_id=7):
    return signing.dumps({'j': jti, 'u': user_id}, salt=auth.SALT)


class ValidarTokenTests(SimpleTestCase):
    def _validar(self, raw, found):
        with patch.object(auth.ChatwootPanelToken, 'objects') as objects:
            objects.select_related.return_value.filter.return_value.first.return_value = found
            return auth.validar_token(raw), objects

    def test_token_vigente(self):
        token = _token()
        result, objects = self._validar(_raw(), token)
        self.assertIs(result, token)
        objects.select_related.return_value.filter.assert_called_once_with(jti='abc', user_id=7)

    def test_firma_invalida_no_consulta_bd(self):
        result, objects = self._validar(_raw() + 'x', _token())
        self.assertIsNone(result)
        objects.select_related.assert_not_called()

    def test_firma_con_otra_sal(self):
        raw = signing.dumps({'j': 'abc', 'u': 7}, salt='otra')
        self.assertIsNone(self._validar(raw, _token())[0])

    def test_vacio(self):
        self.assertIsNone(self._validar('', _token())[0])

    def test_no_existe(self):
        self.assertIsNone(self._validar(_raw(), None)[0])

    def test_revocado(self):
        self.assertIsNone(self._validar(_raw(), _token(revoked=True))[0])

    def test_vencido(self):
        self.assertIsNone(self._validar(_raw(), _token(expires_in=timedelta(seconds=-1)))[0])

    def test_usuario_inactivo(self):
        self.assertIsNone(self._validar(_raw(), _token(user=_user(active=False)))[0])

    def test_usuario_sin_permiso(self):
        self.assertIsNone(self._validar(_raw(), _token(user=_user(perm=False)))[0])


@override_settings(CHATWOOT_PANEL_TOKEN_IDLE_DAYS=5)
class RenovarTests(SimpleTestCase):
    def test_renueva_cinco_dias_desde_el_uso(self):
        now = timezone.now()
        token = _token(last_used=now - timedelta(hours=2))
        with patch.object(auth.ChatwootPanelToken, 'objects') as objects:
            self.assertTrue(auth.renovar(token, now=now))
        self.assertEqual(token.expires_at, now + timedelta(days=5))
        objects.filter.return_value.update.assert_called_once_with(
            last_used_at=now, expires_at=now + timedelta(days=5),
        )

    def test_primer_uso_renueva(self):
        token = _token(last_used=None)
        with patch.object(auth.ChatwootPanelToken, 'objects'):
            self.assertTrue(auth.renovar(token))

    def test_no_escribe_si_se_uso_hace_menos_de_una_hora(self):
        now = timezone.now()
        token = _token(last_used=now - timedelta(minutes=20))
        with patch.object(auth.ChatwootPanelToken, 'objects') as objects:
            self.assertFalse(auth.renovar(token, now=now))
        objects.filter.assert_not_called()


class PanelApiDecoratorTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

        @auth.panel_api
        def vista(request):
            return JsonResponse({'user': request.user.get_username()})

        self.vista = vista

    def test_sin_header_responde_401(self):
        response = self.vista(self.rf.get('/chatwoot/api/yo/'))
        self.assertEqual(response.status_code, 401)

    def test_cookie_de_sesion_no_basta(self):
        request = self.rf.get('/chatwoot/api/yo/')
        request.user = _user()
        self.assertEqual(self.vista(request).status_code, 401)

    def test_bearer_valido_pasa_el_usuario(self):
        token = _token()
        request = self.rf.get('/chatwoot/api/yo/', HTTP_AUTHORIZATION='Bearer ' + _raw())
        with patch.object(auth, 'validar_token', return_value=token) as validar, \
                patch.object(auth, 'renovar') as renovar:
            response = self.vista(request)
        validar.assert_called_once_with(_raw())
        renovar.assert_called_once_with(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertIs(request.panel_token, token)

    def test_post_no_exige_csrf(self):
        self.assertTrue(getattr(self.vista, 'csrf_exempt', False))

    @override_settings(CHATWOOT_PANEL_RATE_LIMIT=2)
    def test_limite_de_consultas(self):
        token = _token()
        token.pk = 'rl-test'
        request = lambda: self.rf.get('/x', HTTP_AUTHORIZATION='Bearer t')
        with patch.object(auth, 'validar_token', return_value=token), patch.object(auth, 'renovar'):
            codes = [self.vista(request()).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])


class PanelViewTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    @override_settings(CHATWOOT_ORIGIN='https://chat.ejemplo.com')
    def test_solo_chatwoot_puede_embeberlo(self):
        response = views.panel(self.rf.get('/chatwoot/panel/'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('frame-ancestors https://chat.ejemplo.com', response['Content-Security-Policy'])
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertTrue(getattr(response, 'xframe_options_exempt', False))
        self.assertContains(response, 'data-chatwoot-origin="https://chat.ejemplo.com"')

    @override_settings(CHATWOOT_ORIGIN='')
    def test_sin_configurar_nadie_lo_embebe(self):
        response = views.panel(self.rf.get('/chatwoot/panel/'))
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])


class ConectarViewTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def _request(self, method='get', user=None):
        request = getattr(self.rf, method)('/chatwoot/conectar/')
        request.user = user or _user()
        request._dont_enforce_csrf_checks = True
        return request

    def test_get_pide_confirmacion_y_no_emite(self):
        with patch.object(views, 'emitir_token') as emitir:
            response = views.conectar(self._request())
        emitir.assert_not_called()
        self.assertContains(response, 'Autorizar')
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])
        self.assertFalse(getattr(response, 'xframe_options_exempt', False))

    def test_post_emite_y_entrega_token(self):
        token = _token()
        with patch.object(views, 'emitir_token', return_value=(token, 'firmado123')) as emitir, \
                patch.object(views, 'auditar') as auditar:
            response = views.conectar(self._request('post'))
        emitir.assert_called_once()
        auditar.assert_called_once()
        self.assertContains(response, 'data-token="firmado123"')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_sin_permiso_no_emite(self):
        with patch.object(views, 'emitir_token') as emitir:
            response = views.conectar(self._request('post', user=_user(perm=False)))
        emitir.assert_not_called()
        self.assertContains(response, 'Sin permiso')

    def test_anonimo_va_al_login(self):
        request = self.rf.get('/chatwoot/conectar/')
        request.user = SimpleNamespace(is_authenticated=False)
        response = views.conectar(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn('next=/chatwoot/conectar/', response['Location'])


class DesconectarTests(SimpleTestCase):
    def test_revoca_el_token_actual(self):
        token = _token()
        request = RequestFactory().post('/chatwoot/api/desconectar/', HTTP_AUTHORIZATION='Bearer t')
        with patch.object(auth, 'validar_token', return_value=token), patch.object(auth, 'renovar'), \
                patch.object(views, 'revocar') as revocar, patch.object(views, 'auditar'):
            response = views.api_desconectar(request)
        self.assertEqual(response.status_code, 200)
        revocar.assert_called_once_with(token)


class AuditarTests(SimpleTestCase):
    def test_falla_de_bd_no_rompe_la_respuesta(self):
        request = RequestFactory().get('/x')
        request.user = _user()
        with patch.object(auth.ChatwootPanelAudit, 'objects', MagicMock(create=MagicMock(side_effect=Exception('bd')))):
            auth.auditar(request, 'conectar', detalle='x' * 900)
