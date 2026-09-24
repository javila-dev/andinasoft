from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from crm.compromiso_tipos import TIPO_CITA_VISITA, errores_detalle, normalizar_detalle
from andinasoft.promesas_service import puede_avanzar_paso
from andinasoft.models import PromesaCumplimiento
from andinasoft.pqrs_service import fecha_vencimiento_sugerida, plazo_info
from andinasoft.sac_n8n_notify import EVENT_CREADO, build_compromiso_payload, notify_compromiso
from andinasoft.servicio_cliente_service import url_ficha


class PqrsPlazoTests(SimpleTestCase):
    def test_vencimiento_sugerido_15_dias(self):
        fecha = timezone.datetime(2026, 9, 1).date()
        self.assertEqual(fecha_vencimiento_sugerida(fecha).isoformat(), '2026-09-16')

    def test_plazo_vencida(self):
        info = plazo_info('2026-09-01', 'Abierta', today=timezone.datetime(2026, 9, 16).date())
        self.assertEqual(info['codigo'], 'vencida')

    def test_plazo_cerrado(self):
        info = plazo_info('2026-09-01', 'Cerrado', today=timezone.datetime(2026, 9, 16).date())
        self.assertEqual(info['codigo'], 'cerrado')


class HitoEscrituraTests(SimpleTestCase):
    def test_no_salta_pasos(self):
        self.assertFalse(puede_avanzar_paso(
            PromesaCumplimiento.PASO_PENDIENTE,
            PromesaCumplimiento.PASO_REGISTRO,
        ))
        self.assertTrue(puede_avanzar_paso(
            PromesaCumplimiento.PASO_PENDIENTE,
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
        ))

    def test_nadie_puede_saltar(self):
        self.assertFalse(puede_avanzar_paso(
            PromesaCumplimiento.PASO_PENDIENTE,
            PromesaCumplimiento.PASO_REGISTRO,
            es_superuser=True,
        ))
        self.assertFalse(puede_avanzar_paso(
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURADO,
            es_superuser=True,
        ))

    def test_registro_y_facturado_en_paralelo(self):
        from andinasoft.promesas_service import hechos_hasta, siguientes_pasos
        hechos = hechos_hasta(PromesaCumplimiento.PASO_FIRMA_EMPRESA)
        self.assertTrue(puede_avanzar_paso(None, PromesaCumplimiento.PASO_CARGA, hechos=hechos))
        self.assertTrue(puede_avanzar_paso(None, PromesaCumplimiento.PASO_REGISTRO, hechos=hechos))
        self.assertTrue(puede_avanzar_paso(None, PromesaCumplimiento.PASO_FACTURADO, hechos=hechos))
        self.assertIn(PromesaCumplimiento.PASO_REGISTRO, siguientes_pasos(hechos))
        self.assertIn(PromesaCumplimiento.PASO_FACTURADO, siguientes_pasos(hechos))
        hechos_reg = set(hechos)
        hechos_reg.add(PromesaCumplimiento.PASO_REGISTRO)
        self.assertTrue(puede_avanzar_paso(None, PromesaCumplimiento.PASO_FACTURADO, hechos=hechos_reg))
        self.assertTrue(puede_avanzar_paso(None, PromesaCumplimiento.PASO_CARGA, hechos=hechos_reg))

    def test_stepper_solo_siguiente_accionable(self):
        from andinasoft.promesas_service import pasos_escritura_ui, siguiente_paso
        linea, rama = pasos_escritura_ui(PromesaCumplimiento.PASO_PENDIENTE)
        self.assertEqual(linea[0]['codigo'], PromesaCumplimiento.PASO_FIRMA_CLIENTE)
        self.assertEqual([s['codigo'] for s in linea], [
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
        ])
        self.assertEqual([s['estado'] for s in linea], ['next', 'locked', 'locked'])
        self.assertEqual([s['estado'] for s in rama], ['locked', 'locked', 'locked'])
        self.assertEqual(
            siguiente_paso(PromesaCumplimiento.PASO_FIRMA_CLIENTE),
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
        )
        self.assertEqual(
            siguiente_paso(PromesaCumplimiento.PASO_FACTURA_NOTARIA),
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
        )
        linea2, rama2 = pasos_escritura_ui(PromesaCumplimiento.PASO_FIRMA_EMPRESA)
        self.assertEqual([s['estado'] for s in linea2], ['done', 'done', 'done'])
        self.assertEqual([s['estado'] for s in rama2], ['next', 'next', 'next'])
        self.assertTrue(linea2[1]['interno'])
        self.assertTrue(rama2[0]['interno'])

    def test_factura_notaria_bloquea_firma_empresa(self):
        from andinasoft.promesas_service import hechos_hasta, siguientes_pasos
        hechos = hechos_hasta(PromesaCumplimiento.PASO_FIRMA_CLIENTE)
        self.assertTrue(puede_avanzar_paso(
            None, PromesaCumplimiento.PASO_FACTURA_NOTARIA, hechos=hechos,
        ))
        self.assertFalse(puede_avanzar_paso(
            None, PromesaCumplimiento.PASO_FIRMA_EMPRESA, hechos=hechos,
        ))
        self.assertIn(PromesaCumplimiento.PASO_FACTURA_NOTARIA, siguientes_pasos(hechos))
        self.assertNotIn(PromesaCumplimiento.PASO_FIRMA_EMPRESA, siguientes_pasos(hechos))

    def test_factura_pendiente_despues_de_cliente(self):
        from andinasoft.promesas_service import pipeline_escritura
        cump = SimpleNamespace(
            fecha_firma_cliente=timezone.datetime(2026, 9, 1).date(),
            fecha_factura_notaria=None,
            documento_factura_notaria='',
            fecha_firma_empresa=None,
            fecha_carga_escritura=None,
            documento_escritura='',
            fecha_registro=None,
            fecha_facturado=None,
            paso_escritura_actual=PromesaCumplimiento.PASO_FIRMA_CLIENTE,
        )
        pipe = pipeline_escritura(cump)
        self.assertTrue(pipe['factura_pendiente'])
        self.assertEqual(pipe['paso_siguiente'], PromesaCumplimiento.PASO_FACTURA_NOTARIA)
        self.assertTrue(pipe['siguientes'][0]['requiere_archivo'])
        self.assertFalse(puede_avanzar_paso(
            None, PromesaCumplimiento.PASO_FIRMA_EMPRESA, hechos=pipe['hechos'],
        ))

    def test_nombre_documento_factura_requiere_pdf(self):
        from andinasoft.promesas_service import nombre_documento_paso
        with self.assertRaises(ValueError):
            nombre_documento_paso(PromesaCumplimiento.PASO_FACTURA_NOTARIA, None)
        with self.assertRaises(ValueError):
            nombre_documento_paso(
                PromesaCumplimiento.PASO_FACTURA_NOTARIA,
                SimpleNamespace(name='foto.jpg'),
            )
        nombre = nombre_documento_paso(
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            SimpleNamespace(name='factura.pdf'),
        )
        self.assertTrue(nombre.startswith('Factura notaria_'))
        self.assertEqual(nombre_documento_paso(PromesaCumplimiento.PASO_FIRMA_CLIENTE, None), '')

    def test_fechas_incompletas_no_registran(self):
        from andinasoft.promesas_service import registrar_fechas_firmadas
        with self.assertRaises(ValueError):
            registrar_fechas_firmadas('Oasis', 'ADJ-1', '2026-09-01', '', '2026-10-01', 'ana')

    def test_otrosi_exige_pdf(self):
        from andinasoft.promesas_service import registrar_otrosi
        with self.assertRaises(ValueError):
            registrar_otrosi('Oasis', 'ADJ-1', 'entrega', 'ana', fecha_entrega_nueva='2026-12-01')

    def test_entrega_bloqueada_sin_pactada(self):
        from andinasoft.promesas_service import entrega_ui
        ui = entrega_ui(None, False)
        self.assertEqual(ui[0]['estado'], 'next')
        self.assertEqual(ui[1]['estado'], 'locked')
        ui2 = entrega_ui(timezone.datetime(2026, 9, 1).date(), False)
        self.assertEqual(ui2[0]['estado'], 'done')
        self.assertEqual(ui2[1]['estado'], 'next')


class CitaDetalleTests(SimpleTestCase):
    def test_cita_requiere_lugar(self):
        detalle = normalizar_detalle(TIPO_CITA_VISITA, {'lugar_tipo': 'obra'})
        self.assertIn('lugar', errores_detalle(TIPO_CITA_VISITA, detalle))


class FichaUrlTests(SimpleTestCase):
    def test_url_ficha(self):
        self.assertEqual(
            url_ficha('123', 'Oasis', 'ADJ-1'),
            '/servicio_cliente/cliente/123?proyecto=Oasis&adj=ADJ-1',
        )


def _compromiso_stub():
    responsable = MagicMock()
    responsable.pk = 9
    responsable.username = 'gestor'
    responsable.email = 'gestor@test.co'
    responsable.get_full_name.return_value = 'Ana Gomez'
    cliente = SimpleNamespace(nombrecompleto='Juan Perez')
    acta = SimpleNamespace(
        pk=3,
        asunto='Reunion de prueba',
        cliente_id='100',
        proyecto_id='Oasis',
        adj='ADJ-1',
        cliente=cliente,
    )
    compromiso = SimpleNamespace(
        pk=11,
        tipo='envio_informacion',
        detalle={'items': ['brochure'], 'canal': 'whatsapp'},
        titulo='Enviar Brochure',
        fecha_compromiso=timezone.datetime(2026, 9, 20).date(),
        estado='Pendiente',
        prioridad='Media',
        responsable=responsable,
        acta=acta,
    )
    return compromiso


class SacN8nPayloadTests(SimpleTestCase):
    @patch('andinasoft.sac_n8n_notify._telefono_user', return_value='573001112233')
    def test_payload_incluye_tipo_y_recipient(self, _tel):
        payload = build_compromiso_payload(_compromiso_stub(), event=EVENT_CREADO, trigger='test')
        self.assertEqual(payload['event'], EVENT_CREADO)
        self.assertEqual(payload['compromiso']['tipo'], 'envio_informacion')
        self.assertIn('Brochure', payload['compromiso']['resumen'])
        self.assertEqual(payload['recipients'][0]['email'], 'gestor@test.co')
        self.assertEqual(payload['recipients'][0]['telefono'], '573001112233')
        self.assertIn('/servicio_cliente/cliente/100', payload['link_ficha'])

    @override_settings(
        N8N_SAC_NOTIFICATIONS_ENABLED=True,
        N8N_WEBHOOK_SAC_COMPROMISO='http://n8n.test/sac',
        EMAIL_HOST_USER='noreply@test.co',
    )
    @patch('andinasoft.sac_n8n_notify._telefono_user', return_value='')
    @patch('andinasoft.sac_n8n_notify.envio_email_template')
    @patch('andinasoft.sac_n8n_notify.requests.post')
    def test_notify_envia_correo_y_webhook(self, mock_post, mock_mail, _tel):
        mock_post.return_value.status_code = 200
        notify_compromiso(_compromiso_stub())
        mock_mail.assert_called_once()
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'http://n8n.test/sac')
        self.assertEqual(kwargs['json']['event'], EVENT_CREADO)
