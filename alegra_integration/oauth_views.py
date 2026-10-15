import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from alegra_integration import oauth
from alegra_integration.exceptions import AlegraIntegrationError
from alegra_integration.models import AlegraOAuthToken
from andina.decorators import check_groups
from andinasoft.models import empresas

logger = logging.getLogger('alegra_integration')


def _redirect_uri(request):
    return request.build_absolute_uri(reverse('alegra-oauth-callback'))


@login_required
@require_http_methods(['GET'])
def oauth_connections(request):
    check_groups(request, ('Contabilidad',))
    tokens = {t.empresa_id: t for t in AlegraOAuthToken.objects.select_related('connected_by')}
    rows = []
    for emp in empresas.objects.filter(alegra_enabled=True).order_by('nombre'):
        rows.append({'empresa': emp, 'token': tokens.get(emp.pk)})
    return render(request, 'alegra_integration/oauth_connections.html', {
        'rows': rows,
        'redirect_uri': _redirect_uri(request),
        'status': request.GET.get('status', ''),
        'message': request.GET.get('message', ''),
    })


@login_required
@require_http_methods(['GET'])
def oauth_start(request):
    check_groups(request, ('Contabilidad',))
    emp = get_object_or_404(empresas, pk=request.GET.get('empresa'), alegra_enabled=True)
    next_url = request.GET.get('next') or ''
    if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = ''
    try:
        url = oauth.build_authorize_url(request, emp, _redirect_uri(request), next_url=next_url)
    except AlegraIntegrationError as exc:
        logger.warning('Alegra OAuth start failed for %s: %s', emp.pk, exc)
        return redirect(f'{reverse("alegra-oauth-connections")}?status=error&message={exc}')
    return redirect(url)


@login_required
@require_http_methods(['GET'])
def oauth_callback(request):
    check_groups(request, ('Contabilidad',))
    back = reverse('alegra-oauth-connections')
    if request.GET.get('error'):
        msg = request.GET.get('error_description') or request.GET.get('error')
        return redirect(f'{back}?status=error&message=Alegra no autorizó la conexión: {msg}')
    try:
        token, next_url = oauth.exchange_code(request, request.GET.get('code'), request.GET.get('state'))
    except AlegraIntegrationError as exc:
        logger.warning('Alegra OAuth callback failed: %s', exc)
        return redirect(f'{back}?status=error&message={exc}')
    if next_url:
        return redirect(next_url)
    return redirect(f'{back}?status=ok&message=Empresa {token.empresa_id} conectada.')

