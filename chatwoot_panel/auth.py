"""Acceso del panel de Chatwoot: token Bearer de corta vida, sin cookies.

Chatwoot y Andinasoft están en dominios distintos, así que dentro del iframe la
cookie de sesión no viaja. El agente se conecta en una ventana aparte (login
normal) y el panel guarda un token que vence tras N días sin uso.
"""
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from chatwoot_panel.models import ChatwootPanelAudit, ChatwootPanelToken

PERMISO = 'chatwoot_panel.usar_panel_chatwoot'
SALT = 'chatwoot_panel.token'
RENOVAR_CADA = timedelta(hours=1)


def idle_days():
    return int(getattr(settings, 'CHATWOOT_PANEL_TOKEN_IDLE_DAYS', 5) or 5)


def rate_limit_per_minute():
    return int(getattr(settings, 'CHATWOOT_PANEL_RATE_LIMIT', 120) or 120)


def client_ip(request):
    header = request.META.get('HTTP_X_FORWARDED_FOR')
    if header:
        return header.split(',')[0].strip()[:64]
    return (request.META.get('REMOTE_ADDR') or '')[:64]


def puede_usar_panel(user):
    return bool(user and user.is_active and user.has_perm(PERMISO))


def emitir_token(user, request):
    """Crea la conexión y devuelve (registro, cadena firmada para el navegador)."""
    jti = secrets.token_urlsafe(32)
    token = ChatwootPanelToken.objects.create(
        user=user,
        jti=jti,
        expires_at=timezone.now() + timedelta(days=idle_days()),
        ip=client_ip(request),
        user_agent=(request.META.get('HTTP_USER_AGENT') or '')[:255],
    )
    return token, signing.dumps({'j': jti, 'u': user.pk}, salt=SALT)


def validar_token(raw):
    """Devuelve el ChatwootPanelToken vigente o None."""
    if not raw:
        return None
    try:
        data = signing.loads(raw, salt=SALT)
    except signing.BadSignature:
        return None
    if not isinstance(data, dict) or not data.get('j') or not data.get('u'):
        return None

    token = (
        ChatwootPanelToken.objects.select_related('user')
        .filter(jti=data['j'], user_id=data['u'])
        .first()
    )
    if token is None or token.revoked_at is not None:
        return None
    if token.expires_at <= timezone.now():
        return None
    if not puede_usar_panel(token.user):
        return None
    return token


def renovar(token, now=None):
    """Corre el vencimiento a ahora + N días; escribe como máximo una vez por hora."""
    now = now or timezone.now()
    if token.last_used_at and now - token.last_used_at < RENOVAR_CADA:
        return False
    token.last_used_at = now
    token.expires_at = now + timedelta(days=idle_days())
    ChatwootPanelToken.objects.filter(pk=token.pk).update(
        last_used_at=token.last_used_at, expires_at=token.expires_at,
    )
    return True


def revocar(token):
    token.revoked_at = timezone.now()
    ChatwootPanelToken.objects.filter(pk=token.pk, revoked_at__isnull=True).update(revoked_at=token.revoked_at)


def auditar(request, accion, token=None, **campos):
    """Registra una acción del panel. Nunca rompe la respuesta si falla."""
    token = token or getattr(request, 'panel_token', None)
    user = getattr(token, 'user', None) or getattr(request, 'user', None)
    if user is not None and not getattr(user, 'is_authenticated', False):
        user = None
    datos = {k: str(v)[:500 if k == 'detalle' else 60] for k, v in campos.items() if v not in (None, '')}
    try:
        ChatwootPanelAudit.objects.create(user=user, token=token, accion=accion, ip=client_ip(request), **datos)
    except Exception:
        pass


def _bearer(request):
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if not header.startswith('Bearer '):
        return ''
    return header[7:].strip()


def _no_autorizado(detalle, codigo='token_invalido'):
    return JsonResponse({'detail': detalle, 'code': codigo}, status=401)


def _excede_limite(token):
    key = f'chatwoot_panel:rl:{token.pk}:{timezone.now():%Y%m%d%H%M}'
    try:
        if cache.add(key, 1, timeout=70):
            return False
        return cache.incr(key) > rate_limit_per_minute()
    except Exception:
        return False


def panel_api(view_func):
    """Rutas /chatwoot/api/: solo Bearer (sin cookies, por eso sin CSRF)."""

    @csrf_exempt
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        token = validar_token(_bearer(request))
        if token is None:
            return _no_autorizado('Conecta el panel con Andinasoft.')
        if _excede_limite(token):
            return JsonResponse({'detail': 'Demasiadas consultas, espera un momento.', 'code': 'limite'}, status=429)
        renovar(token)
        request.user = token.user
        request.panel_token = token
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    return _wrapped
