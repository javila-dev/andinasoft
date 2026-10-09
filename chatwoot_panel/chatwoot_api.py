"""Escrituras en Chatwoot desde el servidor (el iframe no puede escribir en Chatwoot).

Sin CHATWOOT_API_TOKEN configurado no se escribe nada y el panel sigue funcionando.
"""
import logging

import requests
from django.conf import settings

from chatwoot_panel.identificacion import ATRIBUTO_CEDULA

logger = logging.getLogger(__name__)
TIMEOUT = 8


def configurado():
    return bool(getattr(settings, 'CHATWOOT_API_TOKEN', '') and _base_url())


def _base_url():
    return (getattr(settings, 'CHATWOOT_API_URL', '') or getattr(settings, 'CHATWOOT_ORIGIN', '') or '').rstrip('/')


def _request(method, path, **kwargs):
    url = f'{_base_url()}/api/v1/{path.lstrip("/")}'
    headers = {'api_access_token': settings.CHATWOOT_API_TOKEN, 'Content-Type': 'application/json'}
    response = requests.request(method, url, headers=headers, timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response


CONECTORES = {'de', 'del', 'la', 'las', 'los', 'y', 'e', 'da', 'van', 'von'}


def nombre_para_contacto(nombre):
    """'PATRICIA VELASQUEZ DE LA HOZ' → 'Patricia Velasquez de la Hoz'."""
    palabras = ' '.join(str(nombre or '').split()).lower().split(' ')
    return ' '.join(
        p if (i and p in CONECTORES) else p[:1].upper() + p[1:]
        for i, p in enumerate(palabras)
    ).strip()


def guardar_cedula_en_contacto(account_id, contact_id, cedula, nombre=''):
    """Escribe cedula_andinasoft y, si se da, el nombre del cliente en el contacto. True si se guardó."""
    if not configurado():
        return False
    datos = {'custom_attributes': {ATRIBUTO_CEDULA: cedula}}
    nombre = nombre_para_contacto(nombre)
    if nombre:
        datos['name'] = nombre
    try:
        _request('PUT', f'accounts/{int(account_id)}/contacts/{int(contact_id)}', json=datos)
        return True
    except Exception:
        logger.exception('chatwoot_panel: no se pudo guardar la cédula en el contacto %s/%s', account_id, contact_id)
        return False


def nota_privada(account_id, conversation_id, texto):
    """Deja una nota privada (solo la ven los agentes) en la conversación. True si se creó."""
    if not configurado() or not account_id or not conversation_id:
        return False
    try:
        _request('POST', f'accounts/{int(account_id)}/conversations/{int(conversation_id)}/messages',
                 json={'content': texto, 'message_type': 'outgoing', 'private': True})
        return True
    except Exception:
        logger.exception('chatwoot_panel: no se pudo crear la nota privada en %s/%s', account_id, conversation_id)
        return False


def borrar_cedula_de_contacto(account_id, contact_id):
    if not configurado():
        return False
    try:
        _request('POST', f'accounts/{int(account_id)}/contacts/{int(contact_id)}/destroy_custom_attributes',
                 json={'custom_attributes': [ATRIBUTO_CEDULA]})
        return True
    except Exception:
        logger.exception('chatwoot_panel: no se pudo borrar la cédula del contacto %s/%s', account_id, contact_id)
        return False
