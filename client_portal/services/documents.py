import datetime

from django.http import FileResponse
from django.shortcuts import redirect
from django.core.files.storage import default_storage

from andinasoft.shared_models import Adjudicacion
from andinasoft.estado_cuenta_service import build_estado_cuenta_context
from andinasoft.utilities import pdf_gen


STATEMENT_TEMPLATE_BY_PROJECT = {
    'Fractal': 'pdf/Fractal/statement_of_account.html',
    'Casas de Verano': 'pdf/Casas de Verano/statement_of_account.html',
}


def list_business_documents(project_alias, adj_id):
    adj = Adjudicacion.objects.using(project_alias).filter(pk=adj_id).first()
    if not adj:
        return []

    documents = [
        {
            'id': 'statement',
            'kind': 'generated',
            'title': 'Estado de cuenta',
            'description': 'Generado al momento con la información actual del negocio.',
            'action_label': 'Descargar PDF',
            'download_url': f'/portal/negocio/{project_alias}/{adj_id}/documentos/estado-cuenta',
        }
    ]

    for doc in adj.documents():
        doc_id = doc.get('id_model')
        if doc_id is None:
            continue
        name = doc.get('descripcion_doc') or f'Documento {doc_id}'
        documents.append({
            'id': str(doc_id),
            'kind': 'stored',
            'title': _humanize_document_name(name),
            'description': f'Cargado el {doc.get("fecha_carga") or "sin fecha"}',
            'action_label': 'Ver documento',
            'download_url': f'/portal/negocio/{project_alias}/{adj_id}/documentos/{doc_id}/descargar',
        })

    return documents


def download_business_document(project_alias, adj_id, document_id):
    adj = Adjudicacion.objects.using(project_alias).filter(pk=adj_id).first()
    if not adj:
        return None

    for doc in adj.documents():
        if str(doc.get('id_model')) == str(document_id):
            url = doc.get('url')
            if not url:
                return None
            return redirect(url)
    return None


def build_account_statement_response(project_alias, adj_id, actor_label='Portal clientes'):
    context, err_ec = build_estado_cuenta_context(project_alias, adj_id, actor_label)
    if err_ec or not context:
        return None

    template_path = STATEMENT_TEMPLATE_BY_PROJECT.get(
        project_alias, 'pdf/statement_of_account.html'
    )
    filename = f'Estado_de_cuenta_{adj_id}_{project_alias}.pdf'.replace(' ', '_')
    pdf = pdf_gen(template_path, context, filename)

    ruta = pdf.get('root')
    if not ruta:
        return None
    ruta_str = str(ruta or '').replace('\\', '/')
    if ruta_str.startswith('tmp/'):
        return FileResponse(default_storage.open(ruta, 'rb'), as_attachment=True, filename=filename)
    return FileResponse(open(ruta, 'rb'), as_attachment=True, filename=filename)


def _humanize_document_name(raw_name):
    base = str(raw_name).replace('_', ' ').strip()
    if base.lower().startswith('pqrs'):
        return f'PQRS {base[4:].strip()}'.strip()
    return base
