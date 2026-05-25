"""Links firmados de un clic para aprobar gastos Alegra (WhatsApp / n8n)."""
import base64

from django.conf import settings
from django.core import signing

SALT = 'gasto-alegra-aprob-link-v1'


def _link_signing_key():
    for attr in ('GASTO_APROBACION_LINK_SECRET', 'N8N_WEBHOOK_GASTO_APROBACION_SECRET'):
        raw = (getattr(settings, attr, None) or '').strip()
        if raw:
            return raw
    return settings.SECRET_KEY


def _link_max_age_seconds():
    raw = getattr(settings, 'GASTO_APROBACION_LINK_MAX_AGE', 72 * 3600)
    try:
        return max(int(raw), 60)
    except (TypeError, ValueError):
        return 72 * 3600


def _signer():
    return signing.TimestampSigner(key=_link_signing_key(), salt=SALT)


def _urlsafe_encode(value):
    return base64.urlsafe_b64encode(value.encode('utf-8')).decode('ascii').rstrip('=')


def _urlsafe_decode(value):
    pad = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(f'{value}{pad}').decode('utf-8')


def build_gasto_aprobacion_link_token(radicado_pk, aprobador_user_id):
    """Token URL-safe para /aprobar-link/<radicado>/<token>/"""
    signed = _signer().sign(f'{int(radicado_pk)}:{int(aprobador_user_id)}')
    return _urlsafe_encode(signed)


def verify_gasto_aprobacion_link_token(radicado_pk, aprobador_user_id, token):
    """
    Valida token firmado. Lanza signing.BadSignature o signing.SignatureExpired.
    """
    signed = _urlsafe_decode(str(token or '').strip())
    value = _signer().unsign(signed, max_age=_link_max_age_seconds())
    expected = f'{int(radicado_pk)}:{int(aprobador_user_id)}'
    if value != expected:
        raise signing.BadSignature('El token no corresponde a este radicado.')
    return True


def build_gasto_aprobacion_direct_link(factura, *, public_url_fn):
    """URL absoluta o relativa de aprobación en un clic."""
    aprobador_id = getattr(factura, 'gasto_aprobador_asignado_id', None)
    if not aprobador_id:
        return ''
    token = build_gasto_aprobacion_link_token(factura.pk, aprobador_id)
    path = f'/accounting/gastos-alegra/aprobar-link/{factura.pk}/{token}/'
    return public_url_fn(path)
