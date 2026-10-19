"""Tests de los links de pago Wompi (sin BD ni red: ORM, Chatwoot y Wompi simulados)."""
import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from chatwoot_panel import pagos_wompi

CIFRAS = {'total_vencido': 350000, 'pago_total_hoy': 2000000, 'inmueble': 'Lote 14', 'estado': 'Aprobado',
          'titular': 'PEDRO GOMEZ DE LA HOZ'}


def _user(perm=True):
    return SimpleNamespace(pk=7, is_active=True, has_perm=lambda p: perm and p == pagos_wompi.PERMISO)


def _respuesta(status=201, data=None):
    r = MagicMock(status_code=status, text='{}')
    r.json.return_value = {'data': data if data is not None else {'id': 'Ab3Cd9'}}
    return r


@override_settings(WOMPI_LLAVES_PRIVADAS='andina=prv_prod_abc; venecia = prv_test_xyz ;roto', WOMPI_LINK_VALOR_MINIMO=1500)
class CrearLinkTests(SimpleTestCase):
    def _crear(self, valor='350.000', user=None, cifras=None, comercio='andina', existente=None, respuesta=None,
               enviado=True, conversacion=True, logo=None):
        creado = {}

        def create(**kw):
            obj = SimpleNamespace(link_id='', url='', enviado=False, save=MagicMock(), delete=MagicMock(), **kw)
            creado['link'] = obj
            return obj

        with patch.object(pagos_wompi, 'comercio_de', return_value=SimpleNamespace(alias=comercio) if comercio else None), \
                patch.object(pagos_wompi, 'puede_ver_proyecto', return_value=True), \
                patch.object(pagos_wompi, 'logo_url', return_value=logo), \
                patch.object(pagos_wompi, 'obtener_conversacion', return_value={'id': 9} if conversacion else None), \
                patch.object(pagos_wompi, 'cifras', return_value=dict(CIFRAS, **(cifras or {}))), \
                patch.object(pagos_wompi.transaction, 'atomic', MagicMock()), \
                patch.object(pagos_wompi.LinkPagoWompi, 'objects') as objects, \
                patch.object(pagos_wompi.requests, 'post', **(
                    {'side_effect': respuesta} if isinstance(respuesta, list)
                    else {'return_value': respuesta or _respuesta()})) as post, \
                patch.object(pagos_wompi, 'enviar_mensaje', return_value=enviado) as enviar:
            objects.filter.return_value.first.return_value = existente
            objects.create.side_effect = create
            resultado = pagos_wompi.crear_link(
                user or _user(), 'Oasis', 'ADJ0231', valor=valor, account_id='1', conversation_id='9',
                idempotency_key='clave-12345',
            )
        return resultado, post, enviar, creado.get('link')

    def test_llaves(self):
        self.assertEqual(pagos_wompi.llaves_privadas(), {'andina': 'prv_prod_abc', 'venecia': 'prv_test_xyz'})

    @override_settings(WOMPI_LLAVES_PRIVADAS='"ANDINA:prv_test_a;STATUS:prv_test_b"')
    def test_llaves_con_dos_puntos_y_mayusculas(self):
        self.assertEqual(pagos_wompi.llaves_privadas(), {'andina': 'prv_test_a', 'status': 'prv_test_b'})
        self.assertEqual(pagos_wompi.llave_de(SimpleNamespace(alias='Andina')), 'prv_test_a')
        self.assertIsNone(pagos_wompi.llave_de(SimpleNamespace(alias='otro')))

    def test_crea_link_de_un_solo_uso_y_lo_envia(self):
        (link, mensaje, enviado), post, enviar, _ = self._crear()
        url = post.call_args.args[0]
        body = post.call_args.kwargs['json']
        self.assertEqual(url, 'https://production.wompi.co/v1/payment_links')
        self.assertEqual(post.call_args.kwargs['headers']['Authorization'], 'Bearer prv_prod_abc')
        self.assertEqual((body['amount_in_cents'], body['single_use'], body['currency'], body['sku']),
                         (35000000, True, 'COP', 'ADJ0231'))
        self.assertEqual(link.url, 'https://checkout.wompi.co/l/Ab3Cd9')
        self.assertTrue(enviado and link.enviado)
        self.assertIn('Hola Pedro, este es tu link de pago de Oasis (Lote 14) por $350.000:', mensaje)
        self.assertEqual(enviar.call_args.args[:2], ('1', '9'))
        self.assertIsNone(body['image_url'])

    def test_lleva_el_logo_del_proyecto(self):
        _, post, _, _ = self._crear(logo='https://storages.somosandina.co/wompi_logos/oasis.png')
        self.assertEqual(post.call_args.kwargs['json']['image_url'],
                         'https://storages.somosandina.co/wompi_logos/oasis.png')

    def test_si_wompi_rechaza_el_logo_crea_sin_logo(self):
        rechazo = _respuesta(status=422)
        rechazo.text = '{"error":{"type":"UNPROCESSABLE","reason":"Image url no permitida"}}'
        (link, _, _), post, _, _ = self._crear(logo='https://otro.example/logo.png', respuesta=[rechazo, _respuesta()])
        self.assertEqual([c.kwargs['json']['image_url'] for c in post.call_args_list],
                         ['https://otro.example/logo.png', None])
        self.assertTrue(link.sin_logo)
        self.assertEqual(link.url, 'https://checkout.wompi.co/l/Ab3Cd9')

    def _logo(self, url, base='', visible=True):
        asignacion = SimpleNamespace(logo=SimpleNamespace(url=url) if url else None)
        with patch.object(pagos_wompi, '_asignacion', return_value=asignacion), \
                patch.object(pagos_wompi, 'logo_visible', return_value=visible), \
                override_settings(ANDINA_PUBLIC_BASE_URL=base):
            return pagos_wompi.logo_url('Oasis')

    def test_url_del_logo(self):
        self.assertEqual(self._logo('https://s3.example/wompi_logos/a.png'), 'https://s3.example/wompi_logos/a.png')
        self.assertEqual(self._logo('/media/wompi_logos/a.png', 'https://andinasoft.somosandina.co/'),
                         'https://andinasoft.somosandina.co/media/wompi_logos/a.png')
        # Local con base de otro servidor (p. ej. producción) que no tiene el archivo: sin logo.
        self.assertIsNone(self._logo('/media/wompi_logos/a.png', 'https://app.somosandina.co', visible=False))
        self.assertIsNone(self._logo('/media/wompi_logos/a.png'))  # sin base pública Wompi no la vería
        self.assertIsNone(self._logo('/media/a.png', 'http://localhost:8000'))  # solo https
        self.assertIsNone(self._logo(None))

    def test_llave_de_pruebas_usa_sandbox(self):
        _, post, _, _ = self._crear(comercio='venecia')
        self.assertTrue(post.call_args.args[0].startswith('https://sandbox.wompi.co/v1/'))

    def test_chatwoot_no_envia(self):
        (link, _, enviado), _, _, _ = self._crear(enviado=False)
        self.assertFalse(enviado or link.enviado)
        self.assertEqual(link.url, 'https://checkout.wompi.co/l/Ab3Cd9')

    def test_wompi_rechaza_borra_el_registro(self):
        with self.assertRaises(pagos_wompi.LinkError) as ctx:
            self._crear(respuesta=_respuesta(status=422))
        self.assertEqual(ctx.exception.status, 502)

    def test_reintento_devuelve_el_mismo_link(self):
        existente = SimpleNamespace(proyecto='Oasis', adj='ADJ0231', link_id='Zz1', enviado=True)
        (link, _, enviado), post, _, _ = self._crear(existente=existente)
        post.assert_not_called()
        self.assertIs(link, existente)

    def test_validaciones(self):
        casos = [
            (dict(user=_user(perm=False)), 403),
            (dict(comercio='sin-llave'), 503),
            (dict(comercio=None), 503),
            (dict(conversacion=False), 502),
            (dict(cifras={'estado': 'Desistido'}), 400),
            (dict(valor='1000'), 400),
            (dict(valor='2.000.001'), 400),
            (dict(valor='abc'), 400),
        ]
        for kwargs, status in casos:
            with self.assertRaises(pagos_wompi.LinkError, msg=kwargs) as ctx:
                self._crear(**kwargs)
            self.assertEqual(ctx.exception.status, status, kwargs)


class MensajeTests(SimpleTestCase):
    def test_texto(self):
        vence = timezone.make_aware(datetime.datetime(2026, 10, 20, 17, 30))
        link = SimpleNamespace(valor=1250000, vence=vence, proyecto='Oasis', url='https://checkout.wompi.co/l/X')
        texto = pagos_wompi.texto_mensaje(link, '', '')
        self.assertEqual(texto, 'Hola, este es tu link de pago de Oasis por $1.250.000:\nhttps://checkout.wompi.co/l/X\n'
                                'Es de un solo uso y vence el 20/10/2026 a las 05:30 PM.')


class BucketPublicoTests(SimpleTestCase):
    def test_bucket(self):
        casos = [
            (dict(USE_S3_MEDIA=False), True),
            (dict(USE_S3_MEDIA=True, AWS_PUBLIC_BUCKET_NAME='andina-media-public', AWS_STORAGE_BUCKET_NAME='andina-media'), True),
            (dict(USE_S3_MEDIA=True, AWS_PUBLIC_BUCKET_NAME='andina-media', AWS_STORAGE_BUCKET_NAME='andina-media'), False),
            (dict(USE_S3_MEDIA=True, AWS_PUBLIC_BUCKET_NAME='', AWS_STORAGE_BUCKET_NAME='andina-media'), False),
        ]
        for ajustes, esperado in casos:
            with override_settings(**ajustes):
                self.assertEqual(pagos_wompi.bucket_publico_configurado(), esperado, ajustes)

    @override_settings(USE_S3_MEDIA=True, AWS_PUBLIC_BUCKET_NAME='andina-media', AWS_STORAGE_BUCKET_NAME='andina-media')
    def test_bucket_privado_no_manda_logo(self):
        asignacion = SimpleNamespace(logo=SimpleNamespace(url='https://storages.somosandina.co/andina-media/x.png'))
        with patch.object(pagos_wompi, '_asignacion', return_value=asignacion):
            self.assertIsNone(pagos_wompi.logo_url('Oasis'))

    def test_logo_visible(self):
        for status, tipo, esperado in ((200, 'image/png', True), (403, 'application/xml', False),
                                       (200, 'text/html', False)):
            r = MagicMock(status_code=status, headers={'Content-Type': tipo})
            with patch.object(pagos_wompi.requests, 'get', return_value=r):
                self.assertEqual(pagos_wompi.logo_visible('https://x/y.png'), esperado)
