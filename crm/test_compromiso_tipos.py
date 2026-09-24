from django.test import SimpleTestCase

from crm.compromiso_tipos import (
    TIPO_CAMBIO_PROYECTO,
    TIPO_ENVIO_INFORMACION,
    TIPO_OTRO,
    errores_detalle,
    normalizar_detalle,
    resumen_linea,
    titulo_por_tipo,
)


class CompromisoTiposTests(SimpleTestCase):
    def test_titulo_cambio_incluye_destino(self):
        titulo = titulo_por_tipo(
            TIPO_CAMBIO_PROYECTO,
            {'proyecto_destino': 'Oasis'},
        )
        self.assertEqual(titulo, 'Cambio a Oasis')

    def test_resumen_cambio(self):
        linea = resumen_linea(
            TIPO_CAMBIO_PROYECTO,
            {
                'proyecto_destino': 'Oasis',
                'lotes_prospecto': 'lote 12',
                'fecha_estimada_entrega': '2027-03-01',
                'expectativa_cliente': 'descuento de escritura',
            },
        )
        self.assertIn('Oasis', linea)
        self.assertIn('lote 12', linea)
        self.assertIn('espera: descuento de escritura', linea)

    def test_envio_requiere_items(self):
        detalle = normalizar_detalle(TIPO_ENVIO_INFORMACION, {'canal': 'correo'})
        errores = errores_detalle(TIPO_ENVIO_INFORMACION, detalle)
        self.assertIn('items', errores)

    def test_envio_resumen(self):
        detalle = normalizar_detalle(
            TIPO_ENVIO_INFORMACION,
            {'items': ['brochure', 'licencias'], 'canal': 'whatsapp'},
        )
        linea = resumen_linea(TIPO_ENVIO_INFORMACION, detalle)
        self.assertIn('Brochure', linea)
        self.assertIn('WhatsApp', linea)

    def test_otro_usa_titulo_libre(self):
        self.assertEqual(titulo_por_tipo(TIPO_OTRO, {}, 'Llamar al cliente'), 'Llamar al cliente')
