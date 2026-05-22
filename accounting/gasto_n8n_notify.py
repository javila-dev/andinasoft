"""Webhooks salientes n8n para avisos de gastos Alegra (contables y aprobadores)."""
import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounting.models import Facturas, GastoContableNotificacion

logger = logging.getLogger(__name__)


def contables_notificacion_para_empresa(empresa_id):
    return GastoContableNotificacion.objects.filter(
        empresa_id=str(empresa_id).strip(),
        activo=True,
        user__is_active=True,
    ).select_related('user', 'empresa')


def _user_recipient(user, role):
    name = (user.get_full_name() or '').strip() or user.username
    return {
        'role': role,
        'user_id': user.pk,
        'username': user.username,
        'email': (user.email or '').strip(),
        'name': name,
    }


def _public_url(path):
    base = (getattr(settings, 'ANDINA_PUBLIC_BASE_URL', None) or '').rstrip('/')
    if not base:
        return path
    if not path.startswith('/'):
        path = '/' + path
    return f'{base}{path}'


def _empresa_payload(factura):
    emp = factura.empresa
    return {
        'nit': str(factura.empresa_id),
        'nombre': getattr(emp, 'nombre', '') or str(factura.empresa_id),
    }


def _factura_payload(factura):
    from accounting.gasto_aprobacion import factura_a_dict

    data = dict(factura_a_dict(factura))
    data['idtercero'] = factura.idtercero or ''
    data['origen'] = factura.origen or ''
    data['soporte_pdf_listo'] = bool(factura.soporte_radicado)
    return data


def build_alegra_bill_snapshot(bill):
    if not isinstance(bill, dict):
        return None
    client = bill.get('client') or bill.get('provider') or {}
    if not isinstance(client, dict):
        client = {}
    number_tpl = bill.get('numberTemplate') or {}
    nro = ''
    if isinstance(number_tpl, dict):
        nro = str(number_tpl.get('number') or '').strip()
    return {
        'id': str(bill.get('id') or '').strip(),
        'total': bill.get('total'),
        'state': bill.get('state'),
        'provider_name': (client.get('name') or '').strip(),
        'provider_identification': str(client.get('identification') or '').strip(),
        'number': nro,
    }


def build_gasto_notification_payload(
    factura,
    *,
    event,
    trigger,
    recipients,
    extra=None,
):
    payload = {
        'event': event,
        'occurred_at': timezone.now().isoformat(),
        'trigger': trigger,
        'empresa': _empresa_payload(factura),
        'factura': _factura_payload(factura),
        'recipients': recipients,
    }
    if extra:
        payload.update(extra)
    return payload


def _notifications_enabled():
    return bool(getattr(settings, 'N8N_ALEGRA_NOTIFICATIONS_ENABLED', False))


def _post_n8n(url, payload):
    if not url:
        logger.warning('n8n gasto notify: URL vacía, event=%s', payload.get('event'))
        return
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code >= 400:
            logger.warning(
                'n8n gasto notify HTTP %s event=%s factura_pk=%s body=%s',
                response.status_code,
                payload.get('event'),
                (payload.get('factura') or {}).get('pk'),
                (response.text or '')[:500],
            )
    except Exception:
        logger.exception(
            'n8n gasto notify falló event=%s factura_pk=%s',
            payload.get('event'),
            (payload.get('factura') or {}).get('pk'),
        )


def notify_gasto_pendiente_asignacion(factura_pk, *, trigger, alegra_bill_snapshot=None):
    if not _notifications_enabled():
        return

    def _after_commit():
        factura = Facturas.objects.select_related('empresa').filter(pk=factura_pk).first()
        if not factura:
            return
        entries = list(contables_notificacion_para_empresa(factura.empresa_id))
        if not entries:
            logger.warning(
                'n8n gasto pendiente_asignacion: sin destinatarios empresa=%s factura_pk=%s',
                factura.empresa_id,
                factura_pk,
            )
            return
        recipients = [_user_recipient(e.user, 'contabilidad') for e in entries]
        extra = {
            'links': {'asignar': _public_url('/accounting/gastos-alegra/asignar/')},
        }
        if alegra_bill_snapshot:
            extra['alegra_bill'] = alegra_bill_snapshot
        payload = build_gasto_notification_payload(
            factura,
            event='gasto_alegra.pendiente_asignacion',
            trigger=trigger,
            recipients=recipients,
            extra=extra,
        )
        _post_n8n(settings.N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_ASIGNACION, payload)

    transaction.on_commit(_after_commit)


def notify_gasto_pendiente_aprobacion(factura_pk, *, assigned_by_user_id, trigger='asignacion_contable'):
    if not _notifications_enabled():
        return

    def _after_commit():
        factura = Facturas.objects.select_related(
            'empresa', 'gasto_aprobador_asignado', 'gasto_asignado_por',
        ).filter(pk=factura_pk).first()
        if not factura or not factura.gasto_aprobador_asignado_id:
            return
        aprobador = factura.gasto_aprobador_asignado
        if not aprobador or not aprobador.is_active:
            logger.warning(
                'n8n gasto pendiente_aprobacion: aprobador inactivo factura_pk=%s',
                factura_pk,
            )
            return
        assigned_by = None
        if assigned_by_user_id:
            User = get_user_model()
            u = User.objects.filter(pk=assigned_by_user_id).first()
            if u:
                assigned_by = _user_recipient(u, 'contabilidad')
        extra = {
            'links': {'aprobar': _public_url('/accounting/gastos-alegra/aprobar/')},
        }
        if assigned_by:
            extra['assigned_by'] = assigned_by
        payload = build_gasto_notification_payload(
            factura,
            event='gasto_alegra.pendiente_aprobacion',
            trigger=trigger,
            recipients=[_user_recipient(aprobador, 'aprobador')],
            extra=extra,
        )
        _post_n8n(settings.N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION, payload)

    transaction.on_commit(_after_commit)
