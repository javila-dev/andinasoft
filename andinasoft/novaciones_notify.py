"""Avisos de novaciones: correo Django + webhook n8n (WhatsApp).

- por_aprobar: solo al aprobador que se eligio al registrar la novacion.
- devuelta / aprobada / rechazada: a quien registro la novacion y a quien la envio.
"""
import logging

import requests
from django.conf import settings
from django.utils import timezone

from accounting.n8n_http import n8n_outbound_headers
from andinasoft.handlers_functions import envio_email_template
from andinasoft.models import Novacion, Profiles, clientes

logger = logging.getLogger(__name__)

EVENTOS = {
    'por_aprobar': ('novacion.por_aprobar', 'Novación por aprobar'),
    'devuelta': ('novacion.devuelta', 'Novación devuelta para corregir'),
    'aprobada': ('novacion.aprobada', 'Novación aprobada'),
    'rechazada': ('novacion.rechazada', 'Novación rechazada'),
}


def _public_url(path):
    base = (getattr(settings, 'ANDINA_PUBLIC_BASE_URL', None) or '').rstrip('/')
    return f'{base}{path}' if base else path


def _telefono(user):
    perfil = Profiles.objects.filter(user=user).first()
    return (perfil.telefono or '').strip() if perfil else ''


def _recipient(user, role):
    return {
        'role': role,
        'user_id': user.pk,
        'username': user.username,
        'email': (user.email or '').strip(),
        'name': (user.get_full_name() or '').strip() or user.username,
        'telefono': _telefono(user),
    }


def destinatarios(novacion, evento):
    if evento == 'por_aprobar':
        aprobador = novacion.aprobador
        return [_recipient(aprobador, 'aprobador')] if aprobador and aprobador.is_active else []
    usuarios = [novacion.usuario_solicita]
    if novacion.usuario_envia_id and novacion.usuario_envia_id != novacion.usuario_solicita_id:
        usuarios.append(novacion.usuario_envia)
    return [_recipient(u, 'solicitante') for u in usuarios if u.is_active]


def build_payload(novacion, evento, comentario=''):
    nombre_evento, asunto = EVENTOS[evento]
    cliente = clientes.objects.filter(pk=novacion.titular).first()
    return {
        'event': nombre_evento,
        'subject': asunto,
        'occurred_at': timezone.now().isoformat(),
        'comentario': comentario or '',
        'novacion': {
            'id': novacion.pk,
            'estado': novacion.estado,
            'estado_label': novacion.get_estado_display(),
            'total_trasladado': int(novacion.total_trasladado),
            'capital': int(novacion.capital_trasladado),
            'interes_cte': int(novacion.interes_cte_trasladado),
            'interes_mora': int(novacion.interes_mora_trasladado),
            'nro_nota': novacion.nro_nota,
            'solicitante': novacion.usuario_solicita.get_full_name() or novacion.usuario_solicita.username,
        },
        'origen': {
            'proyecto': novacion.proyecto_origen_id,
            'adj': novacion.adj_origen,
            'lote': novacion.inmueble_origen,
        },
        'destino': {
            'proyecto': novacion.proyecto_destino_id,
            'venta': novacion.venta_destino,
            'lote': novacion.inmueble_destino,
            'adj': novacion.adj_destino,
        },
        'cliente': {
            'id': novacion.titular,
            'nombre': cliente.nombrecompleto if cliente else novacion.titular,
        },
        'link': _public_url(f'/operaciones/novaciones/{novacion.pk}'),
        'recipients': destinatarios(novacion, evento),
    }


def _mensaje_html(payload, recipient):
    n = payload['novacion']
    comentario = f"<p><b>Comentario:</b> {payload['comentario']}</p>" if payload['comentario'] else ''
    destino = payload['destino']
    return (
        f"<p>Hola {recipient['name']},</p>"
        f"<p><b>{payload['subject']}</b> (#{n['id']})</p>"
        f"<ul>"
        f"<li>Cliente: {payload['cliente']['nombre']}</li>"
        f"<li>Origen: {payload['origen']['proyecto']} {payload['origen']['adj']} · lote {payload['origen']['lote']}</li>"
        f"<li>Destino: {destino['proyecto']} {destino['adj'] or 'venta ' + str(destino['venta'])} · lote {destino['lote']}</li>"
        f"<li>Trasladado: ${n['total_trasladado']:,}</li>"
        f"</ul>"
        f"{comentario}"
        f"<p><a href=\"{payload['link']}\">Abrir la novación</a></p>"
    )


def _post_n8n(payload):
    url = getattr(settings, 'N8N_WEBHOOK_NOVACION', '')
    if not url:
        logger.warning('n8n novacion: URL vacia, event=%s', payload['event'])
        return
    try:
        response = requests.post(
            url, json=payload, headers=n8n_outbound_headers(content_type_json=True), timeout=5,
        )
        if response.status_code >= 400:
            logger.warning(
                'n8n novacion HTTP %s event=%s novacion=%s body=%s',
                response.status_code, payload['event'], payload['novacion']['id'], (response.text or '')[:500],
            )
    except Exception:
        logger.exception('n8n novacion fallo event=%s novacion=%s', payload['event'], payload['novacion']['id'])


def notificar(novacion_id, evento, comentario=''):
    """Correo a cada destinatario y un POST a n8n con todos (para el WhatsApp). Nunca lanza."""
    try:
        novacion = Novacion.objects.select_related(
            'usuario_solicita', 'usuario_envia', 'aprobador',
        ).get(pk=novacion_id)
        payload = build_payload(novacion, evento, comentario)
    except Exception:
        logger.exception('novacion %s: no se pudo armar el aviso %s', novacion_id, evento)
        return None
    for recipient in payload['recipients']:
        if not recipient['email']:
            continue
        try:
            envio_email_template(
                f"{payload['subject']} #{novacion_id}",
                settings.EMAIL_HOST_USER,
                [recipient['email']],
                'emails/notificacion_aplicacion.html',
                {'mensaje': _mensaje_html(payload, recipient)},
            )
        except Exception:
            logger.exception('correo novacion fallo id=%s a %s', novacion_id, recipient['email'])
    if payload['recipients'] and getattr(settings, 'N8N_NOVACION_NOTIFICATIONS_ENABLED', False):
        _post_n8n(payload)
    return payload
