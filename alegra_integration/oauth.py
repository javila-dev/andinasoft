"""
OAuth 2.1 (authorization code + PKCE) contra auth-api.alegra.com.

El servidor MCP de Alegra (https://mcp.alegra.com/) dejó de aceptar Basic auth y exige un
Bearer emitido por este servidor de autorización. La API REST sigue con Basic
(`empresas.alegra_token`), así que esto solo se usa para los reportes contables por MCP.

Flujo:
1. `build_authorize_url` registra (una vez) el cliente público y arma la URL de autorización.
   El `state` y el `code_verifier` quedan en la sesión del usuario.
2. El usuario inicia sesión en Alegra y autoriza; Alegra redirige al callback con `code`.
3. `exchange_code` cambia el código por access/refresh token y lo guarda por empresa.
4. `get_access_token` entrega un token vigente, renovándolo con el refresh token si expiró.
"""
import base64
import hashlib
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import requests
from django.db import transaction
from django.utils import timezone

from alegra_integration.exceptions import AlegraClientError, AlegraConfigurationError
from alegra_integration.models import AlegraOAuthClient, AlegraOAuthToken

logger = logging.getLogger('alegra_integration')

AUTH_BASE = 'https://auth-api.alegra.com'
REGISTER_URL = f'{AUTH_BASE}/oauth/register'
AUTHORIZE_URL = f'{AUTH_BASE}/oauth/authorize'
TOKEN_URL = f'{AUTH_BASE}/oauth/token'
SCOPE = 'owner'
CLIENT_NAME = 'Andinasoft - Conciliación de terceros'
SESSION_KEY = 'alegra_oauth_pending'
TIMEOUT = 30


def _post_form(url, data):
    try:
        resp = requests.post(url, data=data, headers={'Accept': 'application/json'}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise AlegraClientError(f'No fue posible conectar con {url}: {exc}') from exc
    try:
        body = resp.json()
    except ValueError:
        body = {'raw': resp.text[:500]}
    if resp.status_code >= 400:
        detail = body.get('error_description') or body.get('error') or body
        raise AlegraClientError(f'Alegra OAuth respondió {resp.status_code}: {detail}')
    return body


def get_or_register_client(redirect_uri):
    existing = AlegraOAuthClient.objects.filter(redirect_uri=redirect_uri).first()
    if existing:
        return existing
    payload = {
        'client_name': CLIENT_NAME,
        'redirect_uris': [redirect_uri],
        'grant_types': ['authorization_code', 'refresh_token'],
        'response_types': ['code'],
        'token_endpoint_auth_method': 'none',
        'scope': SCOPE,
    }
    try:
        resp = requests.post(REGISTER_URL, json=payload, headers={'Accept': 'application/json'}, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise AlegraClientError(f'No fue posible registrar el cliente OAuth en Alegra: {exc}') from exc
    try:
        body = resp.json()
    except ValueError:
        body = {'raw': resp.text[:500]}
    if resp.status_code >= 400 or not body.get('client_id'):
        raise AlegraClientError(f'Alegra rechazó el registro del cliente OAuth ({resp.status_code}): {body}')
    obj, _ = AlegraOAuthClient.objects.get_or_create(
        redirect_uri=redirect_uri,
        defaults={'client_id': body['client_id'], 'raw': body},
    )
    return obj


def _pkce_pair():
    verifier = secrets.token_urlsafe(64)[:96]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
    return verifier, challenge


def build_authorize_url(request, empresa, redirect_uri, next_url=''):
    client = get_or_register_client(redirect_uri)
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(32)
    request.session[SESSION_KEY] = {
        'state': state,
        'verifier': verifier,
        'empresa': empresa.pk,
        'client_id': client.client_id,
        'redirect_uri': redirect_uri,
        'next': next_url,
    }
    params = {
        'response_type': 'code',
        'client_id': client.client_id,
        'redirect_uri': redirect_uri,
        'scope': SCOPE,
        'state': state,
        'code_challenge': challenge,
        'code_challenge_method': 'S256',
        'resource': 'https://mcp.alegra.com',
    }
    return f'{AUTHORIZE_URL}?{urlencode(params)}'


def _save_token(empresa_id, client_id, body, user=None):
    access = body.get('access_token')
    if not access:
        raise AlegraClientError(f'Alegra no devolvió access_token: {body}')
    expires_in = body.get('expires_in')
    expires_at = timezone.now() + timedelta(seconds=int(expires_in)) if expires_in else None
    defaults = {
        'client_id': client_id,
        'access_token': access,
        'token_type': body.get('token_type') or 'Bearer',
        'scope': body.get('scope') or '',
        'expires_at': expires_at,
    }
    # Algunos servidores no rotan el refresh token: conservar el anterior si no llega uno nuevo.
    if body.get('refresh_token'):
        defaults['refresh_token'] = body['refresh_token']
    if user is not None:
        defaults['connected_by'] = user
    obj, _ = AlegraOAuthToken.objects.update_or_create(empresa_id=empresa_id, defaults=defaults)
    return obj


def exchange_code(request, code, state):
    pending = request.session.pop(SESSION_KEY, None)
    if not pending or not state or not secrets.compare_digest(str(pending.get('state')), str(state)):
        raise AlegraConfigurationError('La autorización de Alegra expiró o no corresponde a esta sesión. Inténtalo de nuevo.')
    body = _post_form(TOKEN_URL, {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': pending['redirect_uri'],
        'client_id': pending['client_id'],
        'code_verifier': pending['verifier'],
    })
    token = _save_token(pending['empresa'], pending['client_id'], body, user=request.user)
    return token, pending.get('next') or ''


def refresh(token):
    if not token.refresh_token:
        raise AlegraConfigurationError(
            f'La conexión de reportes de Alegra para la empresa {token.empresa_id} expiró. Vuelve a conectarla.'
        )
    body = _post_form(TOKEN_URL, {
        'grant_type': 'refresh_token',
        'refresh_token': token.refresh_token,
        'client_id': token.client_id,
    })
    return _save_token(token.empresa_id, token.client_id, body)


def get_access_token(empresa, force_refresh=False):
    with transaction.atomic():
        token = AlegraOAuthToken.objects.select_for_update().filter(empresa_id=empresa.pk).first()
        if token is None:
            raise AlegraConfigurationError(
                f'La empresa {empresa.pk} no tiene conectados los reportes de Alegra (OAuth).'
            )
        if force_refresh or token.is_expired():
            token = refresh(token)
        return token.access_token
