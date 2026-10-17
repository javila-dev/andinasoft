"""Tests de telefonía (sin BD: el ORM y Chatwoot van simulados)."""
import json
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import jwt as pyjwt
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.utils import timezone
from twilio.request_validator import RequestValidator

from telefonia import numeros, servicio, twilio_service, views
from telefonia.models import Llamada

TWILIO = dict(
    TWILIO_ACCOUNT_SID='AC' + 'a' * 32,
    TWILIO_AUTH_TOKEN='secreto-de-prueba',
    TWILIO_API_KEY_SID='SK' + 'b' * 32,
    TWILIO_API_KEY_SECRET='clave-de-prueba',
    TWILIO_TWIML_APP_SID='AP' + 'c' * 32,
    TELEFONIA_CALLER_ID='+576041234567',
    TELEFONIA_PUBLIC_BASE_URL='https://andinasoft.example.co',
    TELEFONIA_GRABAR=False,
)


def _user(pk=7, perm=True, active=True):
    return SimpleNamespace(
        pk=pk, is_active=active, is_authenticated=True,
        has_perm=lambda p: perm and p == servicio.PERMISO,
        get_full_name=lambda: 'Ana Pérez', get_username=lambda: 'ana',
    )


def _llamada(**kw):
    datos = dict(
        pk=12, user=_user(), user_id=7, estado=Llamada.INICIANDO, numero='+573505810975', fuente='celular1',
        caller_id='', linea_nombre='', call_sid='', dial_sid='', duracion=0, grabada=False, nota_privada=False, contestada_at=None,
        chatwoot_account_id='1', chatwoot_conversation_id='99', created_at=timezone.now(),
    )
    datos.update(kw)
    return SimpleNamespace(**datos)


class NumerosTests(SimpleTestCase):
    def test_formatos_libres(self):
        self.assertEqual(numeros.numeros_en('350 581 09 75'), ['3505810975'])
        self.assertEqual(numeros.numeros_en('+57 350-581-0975'), ['3505810975'])
        self.assertEqual(numeros.numeros_en('573505810975'), ['3505810975'])
        self.assertEqual(numeros.numeros_en('3001234567 ELLA'), ['3001234567'])
        self.assertEqual(numeros.numeros_en('6044441234'), ['6044441234'])

    def test_dos_numeros_en_un_campo(self):
        self.assertEqual(numeros.numeros_en('3001234567 / 310 987 6543'), ['3001234567', '3109876543'])

    def test_descarta_basura_y_no_colombianos(self):
        for valor in ('NO TIENE', '', None, '0000000000', '4441234', '+1 305 555 1234', '5551234567'):
            self.assertEqual(numeros.numeros_en(valor), [], valor)

    def test_enmascarar(self):
        self.assertEqual(numeros.enmascarar('3505810975'), '350 ••• 0975')
        self.assertEqual(numeros.e164('3505810975'), '+573505810975')


class VerificarConversacionTests(SimpleTestCase):
    def _conv(self, sender_id=5, conv_id=99, phone='+573505810975'):
        return {'id': conv_id, 'meta': {'sender': {'id': sender_id, 'name': 'Pedro', 'phone_number': phone}}}

    def test_ok(self):
        with patch.object(servicio, 'obtener_conversacion', return_value=self._conv()):
            c = servicio.verificar_conversacion('1', '99', '5')
        self.assertEqual(c, {'id': '5', 'nombre': 'Pedro', 'telefono': '+573505810975'})

    def test_contacto_distinto(self):
        with patch.object(servicio, 'obtener_conversacion', return_value=self._conv(sender_id=6)):
            with self.assertRaises(servicio.NoPermitido):
                servicio.verificar_conversacion('1', '99', '5')

    def test_chatwoot_no_responde(self):
        with patch.object(servicio, 'obtener_conversacion', return_value=None):
            with self.assertRaises(servicio.NoPermitido) as ctx:
                servicio.verificar_conversacion('1', '99', '5')
        self.assertEqual(ctx.exception.status, 502)

    def test_ids_no_numericos(self):
        with patch.object(servicio, 'obtener_conversacion') as obtener:
            with self.assertRaises(servicio.NoPermitido):
                servicio.verificar_conversacion('1', '99 OR 1', '5')
        obtener.assert_not_called()


class DestinosTests(SimpleTestCase):
    def _destinos(self, fila, telefono='+573505810975', cedula='123'):
        with patch.object(servicio.clientes, 'objects') as objects:
            objects.filter.return_value.values.return_value.first.return_value = fila
            return servicio.destinos({'telefono': telefono}, cedula)

    def test_chatwoot_y_cliente_sin_repetir(self):
        lista = self._destinos({'celular1': '350 581 0975', 'celular2': '3001234567 / 3109876543',
                                'telefono1': 'NO TIENE', 'telefono2': '', 'celular_cony': '3157654321'})
        self.assertEqual([d['id'] for d in lista], ['chatwoot', 'celular2.1', 'celular2.2', 'celular_cony'])
        self.assertEqual(lista[1]['etiqueta'], 'Celular 2 (1)')

    def test_sin_cedula_solo_chatwoot(self):
        with patch.object(servicio.clientes, 'objects') as objects:
            lista = servicio.destinos({'telefono': '+573505810975'}, '')
        objects.filter.assert_not_called()
        self.assertEqual([d['numero'] for d in lista], ['3505810975'])

    def test_resolver_destino_inexistente(self):
        with patch.object(servicio, 'destinos', return_value=[{'id': 'chatwoot', 'etiqueta': 'x', 'numero': '3'}]):
            with self.assertRaises(servicio.NoPermitido):
                servicio.resolver_destino({}, '', 'celular1')


class IniciarTests(SimpleTestCase):
    def test_sin_permiso(self):
        with self.assertRaises(servicio.NoPermitido) as ctx:
            servicio.iniciar(_user(perm=False), account_id='1', conversation_id='9', contact_id='5', cedula='',
                             destino_id='chatwoot')
        self.assertEqual(ctx.exception.status, 403)

    def test_limite_por_hora(self):
        with patch.object(Llamada, 'objects') as objects, override_settings(TELEFONIA_MAX_LLAMADAS_HORA=3):
            objects.filter.return_value.count.return_value = 3
            with self.assertRaises(servicio.NoPermitido) as ctx:
                servicio.iniciar(_user(), account_id='1', conversation_id='9', contact_id='5', cedula='',
                                 destino_id='chatwoot')
        self.assertEqual(ctx.exception.status, 429)

    def test_crea_con_numero_del_servidor(self):
        contacto = {'id': '5', 'nombre': 'Pedro', 'telefono': '+573505810975'}
        linea = {'id': '2', 'nombre': 'Oficina Medellín', 'numero': '+576041111111'}
        with patch.object(Llamada, 'objects') as objects, \
                patch.object(servicio, 'verificar_conversacion', return_value=contacto), \
                patch.object(servicio, 'elegir_linea', return_value=linea) as elegir:
            objects.filter.return_value.count.return_value = 0
            servicio.iniciar(_user(), account_id='1', conversation_id='9', contact_id='5', cedula='',
                             destino_id='chatwoot', linea_id='2', ip='1.2.3.4')
        elegir.assert_called_once_with('2')
        kwargs = objects.create.call_args.kwargs
        self.assertEqual(kwargs['numero'], '+573505810975')
        self.assertEqual(kwargs['fuente'], 'chatwoot')
        self.assertEqual(kwargs['chatwoot_contact_id'], '5')
        self.assertEqual((kwargs['caller_id'], kwargs['linea_nombre']), ('+576041111111', 'Oficina Medellín'))


class ElegirLineaTests(SimpleTestCase):
    def _elegir(self, linea_id, encontrada=None, hay_activas=False):
        with patch.object(servicio.transaction, 'atomic', MagicMock()), \
                patch.object(servicio.LineaSaliente, 'objects') as objects:
            activas = objects.select_for_update.return_value.filter.return_value
            activas.order_by.return_value.first.return_value = encontrada
            activas.filter.return_value.first.return_value = encontrada
            objects.filter.return_value.exists.return_value = hay_activas
            return servicio.elegir_linea(linea_id), activas, objects

    def test_automatico_usa_la_menos_usada_y_marca_el_uso(self):
        linea = SimpleNamespace(pk=3, nombre='Bogotá', numero='+576011111111')
        elegida, activas, objects = self._elegir('auto', linea)
        self.assertEqual(elegida, {'id': '3', 'nombre': 'Bogotá', 'numero': '+576011111111'})
        self.assertEqual(activas.order_by.call_args.args[1:], ('orden', 'pk'))
        self.assertIn('ultimo_uso', objects.filter.return_value.update.call_args.kwargs)

    def test_linea_elegida(self):
        linea = SimpleNamespace(pk=4, nombre='Cali', numero='+576021111111')
        elegida, activas, _ = self._elegir('4', linea)
        activas.filter.assert_called_with(pk='4')
        self.assertEqual(elegida['numero'], '+576021111111')

    @override_settings(TELEFONIA_CALLER_ID='+573505810975')
    def test_sin_lineas_usa_el_numero_del_env(self):
        elegida, _, _ = self._elegir('auto')
        self.assertEqual(elegida, {'id': 'defecto', 'nombre': 'Línea principal', 'numero': '+573505810975'})

    @override_settings(TELEFONIA_CALLER_ID='+573505810975')
    def test_linea_desactivada_no_cae_al_env(self):
        with self.assertRaises(servicio.NoPermitido):
            self._elegir('4', None, hay_activas=True)

    @override_settings(TELEFONIA_CALLER_ID='')
    def test_sin_ninguna_linea(self):
        with self.assertRaises(servicio.NoPermitido) as ctx:
            self._elegir('auto')
        self.assertEqual(ctx.exception.status, 503)


class FinalizarTests(SimpleTestCase):
    def test_cierra_una_vez_y_anota(self):
        llamada = _llamada(estado=Llamada.EN_CURSO)
        with patch.object(Llamada, 'objects') as objects, \
                patch.object(servicio, 'nota_privada', return_value=True) as nota:
            objects.filter.return_value.update.return_value = 1
            self.assertTrue(servicio.finalizar(llamada, Llamada.COMPLETADA, '192'))
        self.assertEqual(llamada.duracion, 192)
        texto = nota.call_args.args[2]
        self.assertIn('350 ••• 0975 (Celular 1) por Ana Pérez: contestada · 3:12', texto)

    def test_nota_dice_desde_que_linea(self):
        llamada = _llamada(estado=Llamada.SIN_RESPUESTA, linea_nombre='Oficina Medellín')
        self.assertEqual(servicio.texto_nota(llamada),
                         '📞 Llamada saliente a 350 ••• 0975 (Celular 1) desde Oficina Medellín por Ana Pérez: no contestó')

    def test_webhook_repetido_no_anota(self):
        with patch.object(Llamada, 'objects') as objects, patch.object(servicio, 'nota_privada') as nota:
            objects.filter.return_value.update.return_value = 0
            self.assertFalse(servicio.finalizar(_llamada(), Llamada.COMPLETADA, 10))
        nota.assert_not_called()

    def test_si_chatwoot_falla_libera_la_marca(self):
        with patch.object(Llamada, 'objects') as objects, patch.object(servicio, 'nota_privada', return_value=False):
            objects.filter.return_value.update.return_value = 1
            self.assertFalse(servicio.anotar(_llamada()))
        objects.filter.return_value.update.assert_called_with(nota_privada=False)


@override_settings(**TWILIO)
class TwilioServiceTests(SimpleTestCase):
    def test_identidad(self):
        self.assertEqual(twilio_service.identidad(_user(pk=7)), 'andina-7')
        self.assertEqual(twilio_service.user_id_de('client:andina-7'), 7)
        for valor in ('client:otro-7', 'client:andina-x', '+573001234567', None):
            self.assertIsNone(twilio_service.user_id_de(valor))

    def test_token_solo_salientes(self):
        data = pyjwt.decode(twilio_service.token_de_acceso(_user()), TWILIO['TWILIO_API_KEY_SECRET'],
                            algorithms=['HS256'])
        voz = data['grants']['voice']
        self.assertEqual(data['grants']['identity'], 'andina-7')
        self.assertEqual(voz['outgoing']['application_sid'], TWILIO['TWILIO_TWIML_APP_SID'])
        self.assertFalse(voz.get('incoming', {}).get('allow', False))

    def test_twiml_sin_grabar(self):
        xml = twilio_service.twiml_marcar(_llamada())
        self.assertIn('callerId="+576041234567"', xml)
        self.assertIn('+573505810975</Number>', xml)
        self.assertIn('statusCallback="https://andinasoft.example.co/telefonia/twilio/estado/?l=12"', xml)
        self.assertNotIn('record', xml)

    def test_twiml_usa_la_linea_de_la_llamada(self):
        xml = twilio_service.twiml_marcar(_llamada(caller_id='+576041111111'))
        self.assertIn('callerId="+576041111111"', xml)

    @override_settings(TELEFONIA_GRABAR=True)
    def test_twiml_grabando_avisa(self):
        xml = twilio_service.twiml_marcar(_llamada())
        self.assertIn('record="record-from-answer-dual"', xml)
        self.assertIn('url="https://andinasoft.example.co/telefonia/twilio/aviso/"', xml)

    def test_firma(self):
        url = 'https://andinasoft.example.co/telefonia/twilio/estado/?l=12'
        params = {'CallSid': 'CA1', 'CallStatus': 'completed'}
        firma = RequestValidator(TWILIO['TWILIO_AUTH_TOKEN']).compute_signature(url, params)
        request = RequestFactory().post('/telefonia/twilio/estado/?l=12', params, HTTP_X_TWILIO_SIGNATURE=firma)
        self.assertTrue(twilio_service.firma_valida(request))
        request = RequestFactory().post('/telefonia/twilio/estado/?l=13', params, HTTP_X_TWILIO_SIGNATURE=firma)
        self.assertFalse(twilio_service.firma_valida(request))


@override_settings(**TWILIO)
class WebhooksTests(SimpleTestCase):
    def setUp(self):
        self.rf = RequestFactory()

    def test_sin_firma_rechaza(self):
        response = views.twilio_voz(self.rf.post('/telefonia/twilio/voz/', {'llamada': '12'}))
        self.assertEqual(response.status_code, 403)

    def _voz(self, llamada, from_='client:andina-7'):
        request = self.rf.post('/telefonia/twilio/voz/', {'llamada': '12', 'From': from_, 'CallSid': 'CA1'})
        with patch.object(twilio_service, 'firma_valida', return_value=True), \
                patch.object(Llamada, 'objects') as objects, patch.object(servicio, 'finalizar') as finalizar:
            objects.select_related.return_value.filter.return_value.first.return_value = llamada
            response = views.twilio_voz(request)
        return response.content.decode(), objects, finalizar

    def test_voz_marca_la_llamada_creada(self):
        xml, objects, _ = self._voz(_llamada())
        self.assertIn('<Dial', xml)
        self.assertIn('+573505810975', xml)
        objects.filter.return_value.update.assert_called_with(call_sid='CA1', estado=Llamada.EN_CURSO, grabada=False)

    def test_voz_de_otro_usuario_rechaza(self):
        xml, _, finalizar = self._voz(_llamada(), from_='client:andina-8')
        self.assertNotIn('<Dial', xml)
        self.assertIn('<Hangup', xml)
        finalizar.assert_called_once()

    def test_voz_vencida_o_repetida_rechaza(self):
        for llamada in (_llamada(created_at=timezone.now() - timedelta(minutes=5)),
                        _llamada(call_sid='CA0'), _llamada(estado=Llamada.COMPLETADA)):
            xml, _, _ = self._voz(llamada)
            self.assertNotIn('<Dial', xml)

    def _estado(self, data, query='?l=12', llamada=None):
        request = self.rf.post('/telefonia/twilio/estado/' + query, data)
        with patch.object(twilio_service, 'firma_valida', return_value=True), \
                patch.object(Llamada, 'objects') as objects, patch.object(servicio, 'finalizar') as finalizar:
            objects.select_related.return_value.filter.return_value.first.return_value = llamada or _llamada()
            views.twilio_estado(request)
        return objects, finalizar

    def test_estado_cliente_completada(self):
        _, finalizar = self._estado({'CallSid': 'CA2', 'CallStatus': 'completed', 'CallDuration': '75'})
        self.assertEqual(finalizar.call_args.args[1:], (Llamada.COMPLETADA, '75'))

    def test_estado_cliente_ocupado(self):
        _, finalizar = self._estado({'CallSid': 'CA2', 'CallStatus': 'busy'})
        self.assertEqual(finalizar.call_args.args[1], Llamada.OCUPADO)

    def test_estado_contestada_no_cierra(self):
        objects, finalizar = self._estado({'CallSid': 'CA2', 'CallStatus': 'in-progress'})
        finalizar.assert_not_called()
        self.assertEqual(objects.filter.return_value.update.call_args.kwargs['dial_sid'], 'CA2')

    def test_tramo_del_navegador_sin_marcar_cancela(self):
        _, finalizar = self._estado({'CallSid': 'CA1', 'CallStatus': 'completed'}, query='')
        self.assertEqual(finalizar.call_args.args[1], Llamada.CANCELADA)


class UrlsTests(SimpleTestCase):
    def test_webhooks_con_y_sin_barra(self):
        from django.urls import resolve
        for ruta in ('/telefonia/twilio/voz/', '/telefonia/twilio/voz'):
            self.assertIs(resolve(ruta).func, views.twilio_voz)
        for ruta in ('/telefonia/twilio/estado/', '/telefonia/twilio/estado'):
            self.assertIs(resolve(ruta).func, views.twilio_estado)


class SoftphoneApiTests(SimpleTestCase):
    def test_sin_sesion_responde_json(self):
        request = RequestFactory().post('/telefonia/api/destinos/', '{}', content_type='application/json')
        request.user = SimpleNamespace(is_authenticated=False)
        response = views.api_destinos(request)
        self.assertEqual(response.status_code, 401)

    def test_sin_permiso(self):
        request = RequestFactory().post('/telefonia/api/destinos/', '{}', content_type='application/json')
        request.user = _user(perm=False)
        request._dont_enforce_csrf_checks = True
        self.assertEqual(views.api_destinos(request).status_code, 403)

    def test_destinos_enmascarados(self):
        request = RequestFactory().post('/telefonia/api/destinos/', '{"account_id": "1", "conversation_id": "9"}',
                                        content_type='application/json')
        request.user = _user()
        contacto = {'id': '5', 'nombre': 'Pedro', 'telefono': '+573505810975'}
        lineas = [{'id': '1', 'nombre': 'Medellín', 'numero': '+576041111111'},
                  {'id': '2', 'nombre': 'Bogotá', 'numero': '+576011111111'}]
        with patch.object(servicio, 'verificar_conversacion', return_value=contacto), \
                patch.object(servicio, 'lineas', return_value=lineas):
            response = views.api_destinos(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual((data['lineas'], data['linea_auto']), (lineas, True))
        self.assertEqual(json.loads(response.content)['destinos'][0]['numero'], '350 ••• 0975')
        self.assertNotIn('3505810975', response.content.decode('utf-8'))

    @override_settings(TWILIO_ACCOUNT_SID='')
    def test_llamar_sin_configurar(self):
        request = RequestFactory().post('/telefonia/api/llamar/', '{}', content_type='application/json')
        request.user = _user()
        self.assertEqual(views.api_llamar(request).status_code, 503)

    def test_llamada_ajena_no_se_ve(self):
        request = RequestFactory().get('/telefonia/api/llamadas/12/')
        request.user = _user()
        with patch.object(Llamada, 'objects') as objects:
            objects.filter.return_value.first.return_value = None
            self.assertEqual(views.api_llamada(request, 12).status_code, 404)
        objects.filter.assert_called_with(pk=12, user=request.user)
