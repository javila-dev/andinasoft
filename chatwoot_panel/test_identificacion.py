"""Tests de la Etapa 2: teléfonos, identificación del cliente y permisos de cartera (sin BD)."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from chatwoot_panel import auth, identificacion, telefonos, views
from chatwoot_panel.tests import _token, _user


class LlaveColombiaTests(SimpleTestCase):
    def test_formatos_libres_dan_la_misma_llave(self):
        for valor in ('3505810975', '350 581 09 75', '350-581-0975', '(350) 581.09.75', '+573505810975',
                      '573505810975', '+57 350 581 0975', '0057 3505810975', '3505810975 ELLA',
                      '3505810975  WHATSAPP'):
            self.assertEqual(telefonos.llave_colombia(valor), '3505810975', valor)

    def test_sin_numero_o_basura(self):
        for valor in ('NO TIENE', 'None', '', None, '0000000000', '5810975', '3332333'):
            self.assertIsNone(telefonos.llave_colombia(valor), valor)


class LlavesChatwootTests(SimpleTestCase):
    def test_colombia(self):
        self.assertEqual(telefonos.llaves_chatwoot('+573505810975'), {'contiene': ['3505810975'], 'exacto': []})

    def test_extranjero_busca_completo_y_nacional(self):
        llaves = telefonos.llaves_chatwoot('+13055551234')
        self.assertEqual(llaves['contiene'], ['13055551234'])
        self.assertIn('3055551234', llaves['exacto'])
        espana = telefonos.llaves_chatwoot('+34612345678')
        self.assertEqual(espana['contiene'], ['34612345678'])
        self.assertIn('612345678', espana['exacto'])

    def test_vacio(self):
        self.assertIsNone(telefonos.llaves_chatwoot(''))
        self.assertIsNone(telefonos.llaves_chatwoot('+57'))


class CoincidenciaExtranjeraTests(SimpleTestCase):
    def test_nacional_de_10_que_empieza_por_3_es_celular_colombiano(self):
        llaves = telefonos.llaves_chatwoot('+13055551234')
        fila = {'_celular1': '3055551234'}
        self.assertTrue(telefonos._es_coincidencia_posible(fila, ('celular1',), llaves))
        self.assertTrue(telefonos._choca_con_celular_colombiano(fila, ('celular1',), llaves))

    def test_extranjero_guardado_sin_indicativo_es_posible(self):
        llaves = telefonos.llaves_chatwoot('+34612345678')
        fila = {'_celular1': '612345678'}
        self.assertTrue(telefonos._es_coincidencia_posible(fila, ('celular1',), llaves))
        self.assertFalse(telefonos._choca_con_celular_colombiano(fila, ('celular1',), llaves))

    def test_extranjero_guardado_completo_no_es_posible(self):
        llaves = telefonos.llaves_chatwoot('+13055551234')
        self.assertFalse(telefonos._es_coincidencia_posible({'_celular1': '13055551234'}, ('celular1',), llaves))


def _neg(proyecto, adj, *cedulas):
    return {'proyecto': proyecto, 'adj': adj, 'inmueble': 'L1', 'estado': 'Aprobado', 'valor': 1,
            'titulares': [{'cedula': c, 'nombre': c} for c in cedulas]}


def _cli(cedula, nombre, posible=False):
    return {'cedula': cedula, 'nombre': nombre, 'posible': posible}


@patch.object(identificacion, 'proyectos_activos', return_value=['A', 'B'])
@patch.object(identificacion, 'proyectos_del_usuario', return_value=['A'])
class ResolverContextoTests(SimpleTestCase):
    user = _user()

    def _resolver(self, titulares, negocios, conyuges=(), es_asesor=False):
        with patch.object(identificacion, 'buscar_clientes', return_value=(list(titulares), list(conyuges), es_asesor)), \
                patch.object(identificacion, 'negocios_de', return_value=list(negocios)), \
                patch.object(identificacion.ChatwootContactLink, 'objects') as links:
            links.filter.return_value.first.return_value = None
            return identificacion.resolver_contexto(self.user, account_id='7', contact_id='1', telefono='+573001112233')

    def test_un_titular_queda_sugerido(self, *_):
        r = self._resolver([_cli('1', 'Ana')], [_neg('A', 'ADJ1', '1')])
        self.assertEqual((r['estado'], r['via']), ('sugerido', 'telefono'))
        self.assertEqual([n['adj'] for n in r['negocios']], ['ADJ1'])

    def test_cotitulares_son_un_solo_cliente(self, *_):
        r = self._resolver([_cli('1', 'Ana'), _cli('2', 'Luis')], [_neg('A', 'ADJ1', '1', '2')])
        self.assertEqual(r['estado'], 'sugerido')
        self.assertEqual(r['cliente']['nombre'], 'Ana y Luis')

    def test_personas_distintas_con_negocios_piden_elegir(self, *_):
        r = self._resolver([_cli('1', 'Ana'), _cli('2', 'Luis')], [_neg('A', 'ADJ1', '1'), _neg('A', 'ADJ2', '2')])
        self.assertEqual(r['estado'], 'varias')
        self.assertEqual(len(r['candidatos']), 2)

    def test_sin_negocio_se_descarta(self, *_):
        r = self._resolver([_cli('1', 'Ana'), _cli('2', 'Luis')], [_neg('A', 'ADJ1', '1')])
        self.assertEqual((r['estado'], r['cliente']['cedula']), ('sugerido', '1'))

    def test_numero_de_asesor_no_se_identifica_solo(self, *_):
        r = self._resolver([_cli('1', 'Ana')], [_neg('A', 'ADJ1', '1')], es_asesor=True)
        self.assertEqual(r['estado'], 'varias')
        self.assertTrue(any('asesor' in a for a in r['avisos']))

    def test_coincidencia_posible_no_se_identifica_sola(self, *_):
        r = self._resolver([_cli('1', 'Ana', posible=True)], [_neg('A', 'ADJ1', '1')])
        self.assertEqual(r['estado'], 'varias')

    def test_negocios_de_otros_proyectos_no_se_muestran(self, *_):
        r = self._resolver([_cli('1', 'Ana')], [_neg('A', 'ADJ1', '1'), _neg('B', 'ADJ9', '1')])
        self.assertEqual([n['proyecto'] for n in r['negocios']], ['A'])
        self.assertEqual(r['negocios_otros_proyectos'], 1)

    def test_sin_coincidencias(self, *_):
        self.assertEqual(self._resolver([], [])['estado'], 'ninguno')

    def test_vinculo_guardado_gana_al_telefono(self, *_):
        with patch.object(identificacion.ChatwootContactLink, 'objects') as links, \
                patch.object(identificacion, 'resolver_cliente', return_value=({'cedula': '9', 'nombre': 'Eva'}, [])), \
                patch.object(identificacion, 'buscar_clientes') as buscar:
            links.filter.return_value.first.return_value = SimpleNamespace(cliente_id='9')
            r = identificacion.resolver_contexto(self.user, account_id='7', contact_id='1', telefono='+573001112233')
        buscar.assert_not_called()
        self.assertEqual((r['estado'], r['via']), ('identificado', 'vinculo'))

    def test_atributo_de_chatwoot_gana_a_todo(self, *_):
        with patch.object(identificacion, 'resolver_cliente', return_value=({'cedula': '5', 'nombre': 'Sol'}, [])), \
                patch.object(identificacion, 'buscar_clientes') as buscar:
            r = identificacion.resolver_contexto(self.user, cedula_atributo='5', telefono='+573001112233')
        buscar.assert_not_called()
        self.assertEqual(r['via'], 'atributo')


class CarteraPermisoTests(SimpleTestCase):
    def test_proyecto_no_asignado_responde_403(self):
        request = RequestFactory().get('/x', HTTP_AUTHORIZATION='Bearer t')
        with patch.object(auth, 'validar_token', return_value=_token()), patch.object(auth, 'renovar'), \
                patch.object(views, 'puede_ver_proyecto', return_value=False), \
                patch.object(views, 'build_estado_cuenta_context') as build:
            response = views.api_cartera(request, 'Oasis', 'ADJ1')
        self.assertEqual(response.status_code, 403)
        build.assert_not_called()

    def test_promesa_tambien_valida_proyecto(self):
        request = RequestFactory().get('/x', HTTP_AUTHORIZATION='Bearer t')
        with patch.object(auth, 'validar_token', return_value=_token()), patch.object(auth, 'renovar'), \
                patch.object(views, 'puede_ver_proyecto', return_value=False), \
                patch.object(views, 'resumen_promesa') as resumen:
            response = views.api_promesa(request, 'Oasis', 'ADJ1')
        self.assertEqual(response.status_code, 403)
        resumen.assert_not_called()


class EstadoCuentaViewTests(SimpleTestCase):
    def _get(self, permitido=True, respuesta=None, error=None):
        request = RequestFactory().get('/x', HTTP_AUTHORIZATION='Bearer t')
        build = patch.object(views, 'build_account_statement_response', return_value=respuesta, side_effect=error)
        with patch.object(auth, 'validar_token', return_value=_token()), patch.object(auth, 'renovar'),                 patch.object(views, 'puede_ver_proyecto', return_value=permitido),                 patch.object(views, 'auditar') as auditar, build as gen:
            return views.api_estado_cuenta(request, 'Oasis', 'ADJ1'), gen, auditar

    def test_proyecto_no_asignado_no_genera(self):
        response, gen, _ = self._get(permitido=False)
        self.assertEqual(response.status_code, 403)
        gen.assert_not_called()

    def test_entrega_el_pdf_y_audita(self):
        from django.http import HttpResponse
        pdf = HttpResponse(b'%PDF-1.4', content_type='application/pdf')
        response, gen, auditar = self._get(respuesta=pdf)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        auditar.assert_called_once()

    def test_falla_del_generador_responde_502(self):
        response, _, auditar = self._get(error=Exception('pisa'))
        self.assertEqual(response.status_code, 502)
        auditar.assert_not_called()


class DocumentosViewTests(SimpleTestCase):
    def _call(self, vista, *args, permitido=True, **patches):
        request = RequestFactory().get('/x', HTTP_AUTHORIZATION='Bearer t')
        extra = [patch.object(views, k, **v) for k, v in patches.items()]
        with patch.object(auth, 'validar_token', return_value=_token()), patch.object(auth, 'renovar'), \
                patch.object(views, 'puede_ver_proyecto', return_value=permitido), patch.object(views, 'auditar'):
            for p in extra:
                p.start()
            try:
                return vista(request, 'Oasis', 'ADJ1', *args)
            finally:
                for p in extra:
                    p.stop()

    def test_proyecto_no_asignado(self):
        self.assertEqual(self._call(views.api_documentos, permitido=False).status_code, 403)
        self.assertEqual(self._call(views.api_documento, 5, permitido=False).status_code, 403)

    def test_documento_de_otro_negocio_no_se_sirve(self):
        docs = MagicMock()
        docs.filter.return_value.values.return_value.first.return_value = None
        response = self._call(views.api_documento, 5, _documentos={'return_value': docs},
                              abrir_documento_contrato={'side_effect': AssertionError('no debe abrir')})
        self.assertEqual(response.status_code, 404)

    def test_sirve_el_pdf_inline(self):
        import io
        docs = MagicMock()
        docs.filter.return_value.values.return_value.first.return_value = {'descripcion_doc': 'Promesa'}
        response = self._call(views.api_documento, 5, _documentos={'return_value': docs},
                              abrir_documento_contrato={'return_value': io.BytesIO(b'%PDF-1.4')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('inline', response['Content-Disposition'])
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_csp_permite_el_visor_de_blob(self):
        from django.test import override_settings
        with override_settings(CHATWOOT_ORIGIN='https://app.lyvio.io'):
            response = views.panel(RequestFactory().get('/chatwoot/panel/'))
        self.assertIn('frame-src blob:', response['Content-Security-Policy'])


class NombreDocumentoTests(SimpleTestCase):
    def test_quita_el_sello_de_carga(self):
        self.assertEqual(views._nombre_documento('Otros_2022-11-16 15:50:08.627873'), 'Otros')
        self.assertEqual(views._nombre_documento('Carta de Cobro 2021-03-16 15:53:56'), 'Carta de Cobro')
        self.assertEqual(views._nombre_documento('Promesa firmada'), 'Promesa firmada')


class PromesaFichaTests(SimpleTestCase):
    def test_incluye_enlace_a_la_ficha_de_servicio_al_cliente(self):
        import datetime
        resumen = {
            'cliente_id': 'ALT-123', 'tiene_promesa': True, 'nropromesa': '301', 'fechapromesa': datetime.date(2022, 2, 24),
            'entrega': {'pactada': None, 'real': None, 'entregado': False, 'estado': 'sin_fecha', 'estado_label': 'Sin fecha'},
            'escritura': {'pactada': None, 'real': None, 'completa': False, 'estado': 'sin_fecha', 'estado_label': 'Sin fecha',
                          'paso_label': 'Pendiente', 'siguiente_label': 'Firma cliente', 'alerta_firma_empresa': False,
                          'dias_firma_cliente': None, 'pasos': []},
            'otrosi': [], 'observaciones': '',
        }
        request = RequestFactory().get('/x', HTTP_AUTHORIZATION='Bearer t')
        with patch.object(auth, 'validar_token', return_value=_token()), patch.object(auth, 'renovar'), \
                patch.object(views, 'puede_ver_proyecto', return_value=True), patch.object(views, 'auditar'), \
                patch.object(views, 'resumen_promesa', return_value=resumen):
            response = views.api_promesa(request, 'Perla del Mar', 'ADJ204')
        import json
        self.assertEqual(json.loads(response.content)['ficha_url'],
                         '/servicio_cliente/cliente/ALT-123?proyecto=Perla+del+Mar&adj=ADJ204')
