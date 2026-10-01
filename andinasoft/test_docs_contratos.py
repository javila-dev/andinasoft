"""Reemplazo y borrado de documentos de contrato, incluida la copia en storage."""
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from andinasoft.handlers_functions import (
    eliminar_documento_contrato,
    guardar_documento_contrato,
    upload_docs_contratos,
)


@override_settings(MEDIA_ROOT='/tmp/media', DIR_DOCS='/tmp/media/docs_andinasoft')
class DocumentosContratoStorageTests(SimpleTestCase):
    @patch('andinasoft.handlers_functions.media_service')
    def test_reemplazar_borra_el_pdf_y_la_copia_con_sufijo(self, media):
        media.list_private_filenames.return_value = [
            'Cedula_2026-10-01.pdf',
            'Cedula_2026-10-01_Ab12Cd3.pdf',
            'Cedula_2026-10-02.pdf',
            'Promesa_2026-10-01.pdf',
        ]
        upload_docs_contratos(Mock(), 'V1', 'Oasis', 'Cedula_2026-10-01')

        deleted = {call.args[0] for call in media.delete_private.call_args_list}
        canonical = 'docs_andinasoft/doc_contratos/Oasis/V1/Cedula_2026-10-01.pdf'
        self.assertIn(canonical, deleted)
        self.assertIn(
            'docs_andinasoft/doc_contratos/Oasis/V1/Cedula_2026-10-01_Ab12Cd3.pdf',
            deleted,
        )
        self.assertNotIn(
            'docs_andinasoft/doc_contratos/Oasis/V1/Cedula_2026-10-02.pdf',
            deleted,
        )
        self.assertNotIn(
            'docs_andinasoft/doc_contratos/Oasis/V1/Promesa_2026-10-01.pdf',
            deleted,
        )
        self.assertEqual(media.save_private.call_args.args[0], canonical)

    @patch('andinasoft.handlers_functions.media_service')
    @patch('andinasoft.handlers_functions.sm')
    def test_guardar_actualiza_la_fila_existente(self, sm, media):
        existente = Mock()
        qs = sm.documentos_contratos.objects.using.return_value.filter.return_value
        qs.order_by.return_value.first.return_value = existente

        resultado = guardar_documento_contrato(
            'Oasis', 'V1', 'Cedula_2026-10-01', Mock(), 'ana',
        )

        self.assertEqual(resultado, 'reemplazado')
        existente.save.assert_called_once()
        qs.exclude.return_value.delete.assert_called_once()
        sm.documentos_contratos.objects.using.return_value.create.assert_not_called()
        self.assertEqual(media.save_private.call_args.args[0].rsplit('/', 1)[-1], 'Cedula_2026-10-01.pdf')

    @patch('andinasoft.handlers_functions.media_service')
    @patch('andinasoft.handlers_functions.sm')
    def test_eliminar_quita_fila_y_archivo(self, sm, media):
        media.list_private_filenames.return_value = ['Contrato.pdf']
        eliminar_documento_contrato('Oasis', 'V1', 'Contrato')
        sm.documentos_contratos.objects.using.return_value.filter.return_value.delete.assert_called_once()
        self.assertIn(
            'docs_andinasoft/doc_contratos/Oasis/V1/Contrato.pdf',
            {call.args[0] for call in media.delete_private.call_args_list},
        )

    def test_nombre_con_ruta_no_borra_storage(self):
        with patch('andinasoft.handlers_functions.media_service') as media:
            with self.assertRaises(ValueError):
                eliminar_documento_contrato('Oasis', 'V1', '../otro')
            media.delete_private.assert_not_called()
