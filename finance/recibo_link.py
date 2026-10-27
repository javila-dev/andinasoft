"""
Enlace público firmado al PDF de un recibo de caja.

Sirve para enviar el recibo en plantillas de WhatsApp: la plataforma descarga el PDF sin iniciar sesión, así que
el enlace lleva un token firmado (no se puede adivinar ni cambiar el proyecto o el número) que vence en DIAS_VIGENCIA.
"""
import re

from django.conf import settings
from django.core import signing
from django.urls import reverse

SALT = 'finance.recibo-publico'
DIAS_VIGENCIA = 90


def token_recibo(proyecto, recibo):
    return signing.dumps({'p': str(proyecto), 'r': str(recibo)}, salt=SALT, compress=True)


def leer_token(token):
    """Devuelve (proyecto, recibo). Lanza signing.BadSignature / signing.SignatureExpired."""
    data = signing.loads(str(token or ''), salt=SALT, max_age=DIAS_VIGENCIA * 24 * 3600)
    return data['p'], data['r']


def nombre_archivo(recibo):
    return 'Recibo_caja_%s.pdf' % re.sub(r'[^\w-]', '', str(recibo))


def url_recibo(request, proyecto, recibo):
    path = reverse('recibo-publico', args=[token_recibo(proyecto, recibo), nombre_archivo(recibo)])
    base = (getattr(settings, 'ANDINA_PUBLIC_BASE_URL', None) or '').rstrip('/')
    return f'{base}{path}' if base else request.build_absolute_uri(path)
