from functools import wraps
from django.http import JsonResponse
from django.utils import timezone
from ipaddress import ip_address
from api_auth.models import APIToken


def _client_ip(request):
    header = request.META.get('HTTP_X_FORWARDED_FOR')
    if header:
        return header.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def api_token_auth(view_func):
    """
    Permite autenticar un endpoint mediante header Authorization: Token <key>
    sin reemplazar la autenticación por sesión existente.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        if header.startswith('Token '):
            token_key = header.split(' ', 1)[1].strip()
            try:
                token = APIToken.objects.select_related('user').get(key=token_key, is_active=True)
            except APIToken.DoesNotExist:
                return JsonResponse({'detail': 'Token inválido o inactivo'}, status=401)

            client_ip = _client_ip(request)
            if token.allowed_ips:
                allowed = [ip.strip() for ip in token.allowed_ips.split(',') if ip.strip()]
                try:
                    client_ip_obj = ip_address(client_ip) if client_ip else None
                except ValueError:
                    client_ip_obj = None
                if client_ip_obj:
                    allowed_match = any(client_ip_obj == ip_address(ip) for ip in allowed)
                else:
                    allowed_match = False
                if allowed and not allowed_match:
                    return JsonResponse({'detail': 'Token no autorizado para esta IP'}, status=403)

            request.user = token.user
            request.api_token = token
            token.last_used = timezone.now()
            token.save(update_fields=['last_used'])
        return view_func(request, *args, **kwargs)
    return _wrapped
