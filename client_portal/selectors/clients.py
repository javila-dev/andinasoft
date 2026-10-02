from andinasoft.models import clientes


def get_client_by_document(document):
    return clientes.objects.using('default').filter(idTercero=str(document).strip()).first()
