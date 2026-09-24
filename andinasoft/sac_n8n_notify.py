"""Avisos internos de SAC: correo Django + webhook n8n (WhatsApp al gestor)."""
import logging

import requests
from django.conf import settings
from django.utils import timezone

from accounting.n8n_http import n8n_outbound_headers
from crm.compromiso_tipos import resumen_linea, tipo_label
from andinasoft.handlers_functions import envio_email_template
from andinasoft.models import Profiles

logger = logging.getLogger(__name__)

EVENT_CREADO = 'sac.compromiso.creado'
EVENT_VENCE_HOY = 'sac.compromiso.vence_hoy'
EVENT_VENCIDO = 'sac.compromiso.vencido'

SUBJECTS = {
    EVENT_CREADO: 'Nuevo compromiso asignado',
    EVENT_VENCE_HOY: 'Compromiso vence hoy',
    EVENT_VENCIDO: 'Compromiso vencido',
}


def _public_url(path):
    base = (getattr(settings, 'ANDINA_PUBLIC_BASE_URL', None) or '').rstrip('/')
    if not path:
        return base or ''
    if not path.startswith('/'):
        path = '/' + path
    if not base:
        return path
    return f'{base}{path}'


def _telefono_user(user):
    try:
        perfil = Profiles.objects.filter(user=user).first()
        return (perfil.telefono or '').strip() if perfil else ''
    except Exception:
        return ''


def _recipient(user):
    name = (user.get_full_name() or '').strip() or user.username
    return {
        'role': 'gestor',
        'user_id': user.pk,
        'username': user.username,
        'email': (user.email or '').strip(),
        'name': name,
        'telefono': _telefono_user(user),
    }


def url_ficha(cliente_id, proyecto=None, adj=None):
    if not cliente_id:
        return '/servicio_cliente/dashboard'
    url = f'/servicio_cliente/cliente/{cliente_id}'
    qs = []
    if proyecto:
        qs.append(f'proyecto={proyecto}')
    if adj:
        qs.append(f'adj={adj}')
    if qs:
        url += '?' + '&'.join(qs)
    return url


def build_compromiso_payload(compromiso, *, event, trigger='manual'):
    acta = compromiso.acta
    cliente = acta.cliente
    resumen = resumen_linea(compromiso.tipo, compromiso.detalle, compromiso.titulo)
    ficha = url_ficha(
        acta.cliente_id,
        acta.proyecto_id,
        acta.adj or '',
    )
    recipient = _recipient(compromiso.responsable)
    return {
        'event': event,
        'occurred_at': timezone.now().isoformat(),
        'trigger': trigger,
        'compromiso': {
            'id': compromiso.pk,
            'tipo': compromiso.tipo,
            'tipo_label': tipo_label(compromiso.tipo),
            'titulo': compromiso.titulo,
            'resumen': resumen,
            'detalle': compromiso.detalle or {},
            'fecha_compromiso': compromiso.fecha_compromiso.isoformat() if compromiso.fecha_compromiso else '',
            'estado': compromiso.estado,
            'prioridad': compromiso.prioridad,
        },
        'acta': {
            'id': acta.pk,
            'asunto': acta.asunto,
        },
        'cliente': {
            'id': acta.cliente_id or '',
            'nombre': getattr(cliente, 'nombrecompleto', '') if cliente else '',
        },
        'proyecto': acta.proyecto_id or '',
        'adj': acta.adj or '',
        'link_ficha': _public_url(ficha),
        'link_acta': _public_url(f'/crm/actas/{acta.pk}'),
        'recipients': [recipient],
    }


def _post_n8n(url, payload):
    if not url:
        logger.warning('n8n sac notify: URL vacia, event=%s', payload.get('event'))
        return
    try:
        response = requests.post(
            url, json=payload, headers=n8n_outbound_headers(content_type_json=True), timeout=5,
        )
        if response.status_code >= 400:
            logger.warning(
                'n8n sac notify HTTP %s event=%s compromiso=%s body=%s',
                response.status_code,
                payload.get('event'),
                (payload.get('compromiso') or {}).get('id'),
                (response.text or '')[:500],
            )
    except Exception:
        logger.exception(
            'n8n sac notify fallo event=%s compromiso=%s',
            payload.get('event'),
            (payload.get('compromiso') or {}).get('id'),
        )


def _mensaje_html(payload):
    c = payload.get('compromiso') or {}
    cli = payload.get('cliente') or {}
    return (
        f"<p>Hola {payload['recipients'][0]['name']},</p>"
        f"<p><b>{SUBJECTS.get(payload['event'], 'Compromiso')}</b></p>"
        f"<ul>"
        f"<li>Tipo: {c.get('tipo_label') or ''}</li>"
        f"<li>Detalle: {c.get('resumen') or c.get('titulo') or ''}</li>"
        f"<li>Cliente: {cli.get('nombre') or cli.get('id') or ''}</li>"
        f"<li>Proyecto: {payload.get('proyecto') or ''}</li>"
        f"<li>Adj: {payload.get('adj') or '—'}</li>"
        f"<li>Vence: {c.get('fecha_compromiso') or ''}</li>"
        f"</ul>"
        f"<p><a href=\"{payload.get('link_ficha') or '#'}\">Abrir ficha del cliente</a></p>"
    )


def notify_compromiso(compromiso, *, event=EVENT_CREADO, trigger='alta'):
    payload = build_compromiso_payload(compromiso, event=event, trigger=trigger)
    recipient = (payload.get('recipients') or [{}])[0]
    email = recipient.get('email')
    if email:
        try:
            envio_email_template(
                SUBJECTS.get(event, 'Compromiso SAC'),
                settings.EMAIL_HOST_USER,
                [email],
                'emails/notificacion_aplicacion.html',
                {'mensaje': _mensaje_html(payload)},
            )
        except Exception:
            logger.exception('correo sac compromiso fallo id=%s', compromiso.pk)
    if getattr(settings, 'N8N_SAC_NOTIFICATIONS_ENABLED', False):
        _post_n8n(getattr(settings, 'N8N_WEBHOOK_SAC_COMPROMISO', ''), payload)
    return payload
