from andinasoft.models import clientes


EDITABLE_FIELDS = (
    'celular1',
    'celular2',
    'telefono1',
    'telefono2',
    'domicilio',
    'email',
    'ciudad',
)


def get_client_profile(client_id):
    return clientes.objects.using('default').filter(pk=client_id).first()
