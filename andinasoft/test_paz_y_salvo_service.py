from types import SimpleNamespace
from datetime import date

from django.test import SimpleTestCase

from andinasoft.paz_y_salvo_service import (
    fecha_expedicion_texto,
    format_nit,
    frase_titulares,
    logos_proyecto,
    paleta_proyecto,
)


class PazYSalvoHelpersTests(SimpleTestCase):
    def test_format_nit_con_digito(self):
        self.assertEqual(format_nit('900993044-9'), '900.993.044-9')
        self.assertEqual(format_nit('9009930449'), '900.993.044-9')

    def test_format_nit_sin_digito(self):
        self.assertEqual(format_nit('900993044'), '900.993.044')

    def test_fecha_expedicion(self):
        self.assertEqual(fecha_expedicion_texto(date(2026, 9, 18)), '18 de septiembre de 2026')

    def test_frase_un_titular(self):
        titular = SimpleNamespace(pk='123', nombrecompleto='Ana Perez', tipo_doc='13')
        texto = frase_titulares([titular])
        self.assertIn('ANA PEREZ', texto)
        self.assertIn('No. 123', texto)
        self.assertIn('cédula de ciudadanía', texto.lower())

    def test_frase_dos_titulares(self):
        t1 = SimpleNamespace(pk='1', nombrecompleto='Ana', tipo_doc='13')
        t2 = SimpleNamespace(pk='2', nombrecompleto='Luis', tipo_doc='31')
        texto = frase_titulares([t1, t2])
        self.assertIn(' y ', texto)
        self.assertIn('ANA', texto)
        self.assertIn('LUIS', texto)

    def test_logos_proyecto_conocido(self):
        self.assertEqual(logos_proyecto('Oasis'), ['img/logo_oasis.png'])

    def test_logos_carmelo_solo_proyecto(self):
        self.assertEqual(logos_proyecto('Carmelo Reservado'), ['img/logo_carmelo_reservado.png'])

    def test_logos_proyecto_desconocido_usa_andina(self):
        self.assertEqual(logos_proyecto('Proyecto Inventado'), ['img/Andina-Conceptos.png'])

    def test_paleta_carmelo_usa_colores_del_logo(self):
        paleta = paleta_proyecto('Carmelo Reservado')
        self.assertEqual(paleta['acento'], '#C8963E')
        self.assertNotEqual(paleta['principal'], paleta_proyecto('Oasis')['acento'])
