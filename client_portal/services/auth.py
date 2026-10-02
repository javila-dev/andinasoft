from django.utils import timezone
from andinasoft.models import clientes


def start_session(request, document, birth_date):
    client = clientes.objects.using('default').filter(
        idTercero=str(document).strip(),
        fecha_nac=birth_date,
    ).first()
    if not client:
        return None

    now = timezone.now().isoformat()
    request.session['portal_client_id'] = client.pk
    request.session['portal_authenticated_at'] = now
    request.session['portal_last_seen_at'] = now
    request.session['portal_allowed_businesses'] = []
    return client


def get_current_client(request):
    client_id = request.session.get('portal_client_id')
    if not client_id:
        return None
    return clientes.objects.using('default').filter(pk=client_id).first()


def logout_session(request):
    request.session.pop('portal_client_id', None)
    request.session.pop('portal_authenticated_at', None)
    request.session.pop('portal_last_seen_at', None)
    request.session.pop('portal_allowed_businesses', None)
