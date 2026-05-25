"""Headers y auth compartidos para llamadas HTTP a n8n (saliente) y webhooks entrantes."""
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone


def n8n_outbound_headers(*, content_type_json=False):
    """
    Headers para POST/GET desde Andina hacia webhooks n8n.
    Configurar N8N_WEBHOOK_AUTH_TOKEN en .env (mismo token que exige el nodo Webhook en n8n).
    """
    headers = {}
    if content_type_json:
        headers['Content-Type'] = 'application/json'
    token = (getattr(settings, 'N8N_WEBHOOK_AUTH_TOKEN', None) or '').strip()
    if not token:
        return headers
    prefix = (getattr(settings, 'N8N_WEBHOOK_AUTH_PREFIX', None) or 'Bearer').strip()
    headers['Authorization'] = f'{prefix} {token}'.strip()
    return headers


def _n8n_outbound_bearer_matches(request):
    """Mismo Authorization que POST saliente hacia n8n (N8N_WEBHOOK_AUTH_TOKEN)."""
    token = (getattr(settings, 'N8N_WEBHOOK_AUTH_TOKEN', None) or '').strip()
    if not token:
        return False
    prefix = (getattr(settings, 'N8N_WEBHOOK_AUTH_PREFIX', None) or 'Bearer').strip()
    expected = f'{prefix} {token}'.strip()
    got = (request.META.get('HTTP_AUTHORIZATION', '') or '').strip()
    return bool(got) and got == expected


def n8n_inbound_authorized(request):
    """
    True si la petición entrante desde n8n es válida:
    - Authorization: {N8N_WEBHOOK_AUTH_PREFIX} {N8N_WEBHOOK_AUTH_TOKEN} (mismo que webhooks salientes), o
    - Header X-Andina-Webhook-Secret (N8N_WEBHOOK_GASTO_APROBACION_SECRET), o
    - Authorization: Token <APIToken> activo (api_auth).
    """
    if _n8n_outbound_bearer_matches(request):
        return True, None

    expected_secret = (getattr(settings, 'N8N_WEBHOOK_GASTO_APROBACION_SECRET', None) or '').strip()
    if expected_secret:
        got = (
            request.headers.get('X-Andina-Webhook-Secret')
            or request.META.get('HTTP_X_ANDINA_WEBHOOK_SECRET')
            or ''
        ).strip()
        if got and got == expected_secret:
            return True, None

    header = request.META.get('HTTP_AUTHORIZATION', '')
    if header.startswith('Token '):
        token_key = header.split(' ', 1)[1].strip()
        from api_auth.models import APIToken
        from ipaddress import ip_address

        try:
            token = APIToken.objects.select_related('user').get(key=token_key, is_active=True)
        except APIToken.DoesNotExist:
            return False, JsonResponse({'detail': 'Token inválido o inactivo'}, status=401)

        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
        if token.allowed_ips:
            allowed = [ip.strip() for ip in token.allowed_ips.split(',') if ip.strip()]
            try:
                client_ip_obj = ip_address(client_ip) if client_ip else None
                allowed_match = client_ip_obj and any(
                    client_ip_obj == ip_address(ip) for ip in allowed
                )
            except ValueError:
                allowed_match = False
            if allowed and not allowed_match:
                return False, JsonResponse({'detail': 'Token no autorizado para esta IP'}, status=403)

        request.user = token.user
        request.api_token = token
        token.last_used = timezone.now()
        token.save(update_fields=['last_used'])
        return True, None

    if expected_secret:
        return False, JsonResponse(
            {
                'detail': (
                    'No autorizado (Authorization Bearer N8N_WEBHOOK_AUTH_TOKEN, '
                    'X-Andina-Webhook-Secret o Authorization: Token).'
                ),
            },
            status=401,
        )
    return False, JsonResponse(
        {'detail': 'Webhook no configurado (N8N_WEBHOOK_GASTO_APROBACION_SECRET o APIToken).'},
        status=401,
    )
