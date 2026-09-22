from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from andinasoft.promesas_service import (
    aplicar_forma_pago_impresion,
    resolver_forma_pago_impresion,
    texto_forma_pago_venta,
)


class TextoFormaPagoVentaTests(SimpleTestCase):
    def test_sin_contrato_queda_vacio(self):
        self.assertEqual(texto_forma_pago_venta('Oasis', None), ('', ''))
        self.assertEqual(texto_forma_pago_venta('Oasis', ''), ('', ''))

    @patch('andinasoft.promesas_service.ventas_nuevas')
    def test_usa_texto_automatico_de_la_venta(self, mock_ventas):
        mock_ventas.DoesNotExist = type('DoesNotExist', (Exception,), {})
        venta = Mock()
        venta.fp.return_value = ('3 cuotas de CI', '36 cuotas de saldo')
        mock_ventas.objects.using.return_value.get.return_value = venta

        self.assertEqual(
            texto_forma_pago_venta('Oasis', '12'),
            ('3 cuotas de CI', '36 cuotas de saldo'),
        )

    @patch('andinasoft.promesas_service.ventas_nuevas')
    def test_venta_inexistente_queda_vacio(self, mock_ventas):
        mock_ventas.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_ventas.objects.using.return_value.get.side_effect = mock_ventas.DoesNotExist
        self.assertEqual(texto_forma_pago_venta('Oasis', '999'), ('', ''))


class ResolverFormaPagoImpresionTests(SimpleTestCase):
    def _adj(self, contrato='8'):
        mock_adj = Mock()
        mock_adj.DoesNotExist = type('DoesNotExist', (Exception,), {})
        mock_adj.objects.using.return_value.get.return_value = SimpleNamespace(contrato=contrato)
        return mock_adj

    @patch('andinasoft.promesas_service.texto_forma_pago_venta', return_value=('auto CI', 'auto saldo'))
    def test_override_de_impresion_gana(self, _auto):
        with patch('andinasoft.promesas_service.Adjudicacion', self._adj()):
            promesa = SimpleNamespace(
                formaci='guardado CI', formasaldo='guardado saldo', idadjudicacion='ADJ1',
            )
            ci, saldo = resolver_forma_pago_impresion(
                'Oasis', promesa, override_ci='  manual CI ', override_saldo='',
            )
        self.assertEqual(ci, 'manual CI')
        self.assertEqual(saldo, 'guardado saldo')

    @patch('andinasoft.promesas_service.texto_forma_pago_venta', return_value=('auto CI', 'auto saldo'))
    def test_sin_override_usa_texto_guardado(self, _auto):
        with patch('andinasoft.promesas_service.Adjudicacion', self._adj()):
            promesa = SimpleNamespace(
                formaci='guardado CI', formasaldo='guardado saldo', idadjudicacion='ADJ1',
            )
            ci, saldo = resolver_forma_pago_impresion('Oasis', promesa)
        self.assertEqual(ci, 'guardado CI')
        self.assertEqual(saldo, 'guardado saldo')

    @patch('andinasoft.promesas_service.texto_forma_pago_venta', return_value=('auto CI', 'auto saldo'))
    def test_sin_texto_guardado_usa_venta(self, _auto):
        with patch('andinasoft.promesas_service.Adjudicacion', self._adj()):
            promesa = SimpleNamespace(formaci='', formasaldo=None, idadjudicacion='ADJ1')
            ci, saldo = resolver_forma_pago_impresion('Oasis', promesa, adj='ADJ1')
        self.assertEqual(ci, 'auto CI')
        self.assertEqual(saldo, 'auto saldo')

    def test_aplicar_override_solo_en_memoria(self):
        promesa = SimpleNamespace()
        aplicar_forma_pago_impresion(promesa, 'CI editada', 'saldo editado')
        self.assertEqual(promesa._fp_ci_override, 'CI editada')
        self.assertEqual(promesa._fp_saldo_override, 'saldo editado')
        self.assertEqual(promesa.general_info['fp_ci'], 'CI editada')
        self.assertEqual(promesa.general_info['fp_saldo'], 'saldo editado')
        aplicar_forma_pago_impresion(None, 'x', 'y')

    def test_congela_general_info_y_no_deja_el_metodo_con_texto_viejo(self):
        class Ctr:
            formaci = 'GUARDADO CI'
            formasaldo = 'GUARDADO SALDO'

            def general_info(self):
                return {
                    'fp_ci': self.formaci,
                    'fp_saldo': self.formasaldo,
                    'valor': 1,
                    'ci': 1,
                    'saldo': 0,
                    'inmueble': None,
                    'valor_en_letras': 'X',
                }

        ctr = Ctr()
        aplicar_forma_pago_impresion(ctr, 'OVERRIDE CI', 'OVERRIDE SALDO')
        self.assertFalse(callable(ctr.general_info))
        self.assertEqual(ctr.general_info['fp_ci'], 'OVERRIDE CI')
        self.assertEqual(ctr.formaci, 'OVERRIDE CI')
        self.assertEqual(ctr.formasaldo, 'OVERRIDE SALDO')


def _ctr_html_promesa(fp_ci, fp_saldo):
    from datetime import date

    inmueble = SimpleNamespace(
        etapa='1',
        lotenumero='12',
        manzananumero='A',
        area_lt=120,
        areaprivada=95,
        porcentaje_derecho=9.5,
        nro_fraccion='1',
        norte=10, sur=10, este=12, oeste=12,
        colindante_norte='Calle 1',
        colindante_sur='Calle 2',
        colidante_este='Lote 13',
        colindante_oeste='Lote 11',
    )
    info = {
        'valor': 150000000,
        'inmueble': inmueble,
        'valor_en_letras': 'CIENTO CINCUENTA MILLONES',
        'ci': 45000000,
        'saldo': 105000000,
        'fp_ci': 'TEXTO VIEJO CI',
        'fp_saldo': 'TEXTO VIEJO SALDO',
    }
    titular = SimpleNamespace(
        pk='123',
        nombrecompleto='Ana Perez',
        telefono1='300',
        domicilio='Calle 1',
        oficina='',
        ciudad='Medellin',
        email='ana@example.com',
    )
    ctr = SimpleNamespace(
        titulares=[titular],
        forma_pago='Credicontado',
        formapago='Credicontado',
        observaciones='',
        general_info=info,
        formaci='TEXTO VIEJO CI',
        formasaldo='TEXTO VIEJO SALDO',
        fecha_contrato=date(2026, 9, 22),
        fechapromesa=date(2026, 9, 22),
    )
    aplicar_forma_pago_impresion(ctr, fp_ci, fp_saldo, general_info=info)
    return ctr


class PdfHtmlOverrideTests(SimpleTestCase):
    def _render(self, template_name, fp_ci, fp_saldo):
        from datetime import date
        from django.template.loader import get_template

        ctr = _ctr_html_promesa(fp_ci, fp_saldo)
        return get_template(template_name).render({
            'ctr': ctr,
            'es_promesa': True,
            'proyecto': 'Perla del Mar',
            'oficina': 'Medellin',
            'fecha_escritura': date(2027, 3, 22),
            'meses_entrega': 6,
            'formaCI': fp_ci,
            'formaFN': fp_saldo,
        })

    def test_plantilla_xhtml2pdf_incluye_override_no_el_texto_guardado(self):
        html = self._render(
            'pdf/Perla del Mar/contrato.html',
            'OVERRIDE-CI-TOKEN',
            'OVERRIDE-SALDO-TOKEN',
        )
        self.assertIn('OVERRIDE-CI-TOKEN', html)
        self.assertIn('OVERRIDE-SALDO-TOKEN', html)
        self.assertNotIn('TEXTO VIEJO CI', html)
        self.assertNotIn('TEXTO VIEJO SALDO', html)

    def test_plantilla_weasy_incluye_override(self):
        html = self._render(
            'pdf/Oasis/contrato.html',
            'OVERRIDE-CI-TOKEN',
            'OVERRIDE-SALDO-TOKEN',
        )
        self.assertIn('OVERRIDE-CI-TOKEN', html)
        self.assertIn('OVERRIDE-SALDO-TOKEN', html)
        self.assertNotIn('TEXTO VIEJO CI', html)

    def test_xhtml2pdf_pisa_deja_el_override_en_el_pdf(self):
        try:
            from xhtml2pdf import pisa
        except ImportError:
            self.skipTest('xhtml2pdf no esta instalado')
        import re
        import zlib
        from base64 import a85decode
        from io import BytesIO

        html = self._render(
            'pdf/Perla del Mar/contrato.html',
            'OVERRIDE-CI-TOKEN',
            'OVERRIDE-SALDO-TOKEN',
        )
        dest = BytesIO()
        status = pisa.CreatePDF(html, dest=dest)
        self.assertFalse(getattr(status, 'err', 1))
        pdf_bytes = dest.getvalue()
        extraido = []
        for match in re.finditer(rb'stream\r?\n(.*?)endstream', pdf_bytes, re.S):
            raw = match.group(1).strip()
            payload = raw
            try:
                payload = a85decode(raw.replace(b'~>', b''), adobe=False, ignorechars=b' \t\r\n')
            except Exception:
                try:
                    payload = a85decode(b'<~' + raw, adobe=True, ignorechars=b' \t\r\n')
                except Exception:
                    payload = raw
            try:
                extraido.append(zlib.decompress(payload))
            except Exception:
                extraido.append(payload)
        contenido = b'\n'.join(extraido)
        self.assertTrue(contenido, 'No se pudo leer el contenido del PDF generado')
        self.assertIn(b'OVERRIDE-CI-TOKEN', contenido)
        self.assertIn(b'OVERRIDE-SALDO-TOKEN', contenido)
        self.assertNotIn(b'TEXTO VIEJO CI', contenido)

