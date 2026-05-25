"""Webhooks salientes n8n para avisos de gastos Alegra (contables y aprobadores)."""
import logging

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from django.db.models import Q

from accounting.gasto_aprobacion_link import build_gasto_aprobacion_direct_link
from accounting.models import Facturas, GastoAprobador, GastoContableNotificacion
from accounting.n8n_http import n8n_outbound_headers

logger = logging.getLogger(__name__)


def contables_notificacion_para_empresa(empresa_id):
    return GastoContableNotificacion.objects.filter(
        empresa_id=str(empresa_id).strip(),
        activo=True,
        user__is_active=True,
    ).select_related('user', 'empresa')


def _user_recipient(user, role, *, telefono=''):
    name = (user.get_full_name() or '').strip() or user.username
    data = {
        'role': role,
        'user_id': user.pk,
        'username': user.username,
        'email': (user.email or '').strip(),
        'name': name,
        'telefono': (telefono or '').strip(),
    }
    return data


def _gasto_aprobador_entry(user, empresa_id):
    """Fila GastoAprobador: empresa específica o global (empresa vacía)."""
    if not user:
        return None
    empresa_id = str(empresa_id or '').strip()
    base = GastoAprobador.objects.filter(user=user, activo=True)
    if empresa_id:
        entry = base.filter(empresa_id=empresa_id).first()
        if entry:
            return entry
    return base.filter(empresa__isnull=True).first()


def _aprobador_recipient(user, empresa_id):
    entry = _gasto_aprobador_entry(user, empresa_id)
    telefono = (entry.telefono or '').strip() if entry else ''
    return _user_recipient(user, 'aprobador', telefono=telefono)


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


def _soporte_radicado_legible(field_file):
    """True si el FileField apunta a un objeto existente y legible en storage."""
    if not field_file or not getattr(field_file, 'name', None):
        return False
    try:
        if not field_file.storage.exists(field_file.name):
            return False
        with field_file.open('rb'):
            pass
        return True
    except Exception:
        return False


def _attach_soporte_from_alegra(factura, *, force=False):
    """
    Descarga PDF desde Alegra a soporte_radicado.
    force=True: reintenta aunque ya haya ruta en BD (p. ej. archivo ausente en S3).
    """
    if not force:
        if _soporte_radicado_legible(factura.soporte_radicado):
            return False
        if not getattr(settings, 'N8N_ALEGRA_ENSURE_SOPORTE_BEFORE_NOTIFY', False):
            return False
    elif _soporte_radicado_legible(factura.soporte_radicado):
        return False

    if (factura.origen or '').strip() != 'Alegra':
        return False
    from alegra_integration.bill_mapping import (
        ALEGRA_DOC_BILL,
        infer_alegra_document_type,
        parse_alegra_bill_id_for_api,
    )

    doc_type = (factura.alegra_document_type or '').strip() or infer_alegra_document_type(
        factura.alegra_bill_id,
    )
    if doc_type != ALEGRA_DOC_BILL:
        return False
    _, alegra_numeric_id = parse_alegra_bill_id_for_api(factura.alegra_bill_id)
    if not alegra_numeric_id:
        return False
    try:
        from alegra_integration.bill_pdf import attach_bill_pdf_from_alegra

        attach_bill_pdf_from_alegra(factura.empresa, alegra_numeric_id, factura)
        factura.refresh_from_db(fields=['soporte_radicado'])
        return _soporte_radicado_legible(factura.soporte_radicado)
    except Exception:
        logger.exception(
            'n8n gasto: no se pudo adjuntar soporte Alegra factura_pk=%s',
            factura.pk,
        )
        return False


def _try_attach_soporte_from_alegra(factura):
    """Opcional: descarga PDF de Alegra antes del POST a n8n (N8N_ALEGRA_ENSURE_SOPORTE_BEFORE_NOTIFY)."""
    _attach_soporte_from_alegra(factura, force=False)


def ensure_soporte_radicado_descargable(factura):
    """
    Devuelve (field_file, error_detail, http_status) listo para FileResponse.
    Reintenta descarga desde Alegra si la ruta en BD no es legible (p. ej. S3).
    """
    if _soporte_radicado_legible(factura.soporte_radicado):
        return factura.soporte_radicado, None, None

    _attach_soporte_from_alegra(factura, force=True)
    factura.refresh_from_db(fields=['soporte_radicado'])

    if not factura.soporte_radicado or not factura.soporte_radicado.name:
        return None, 'Este radicado no tiene soporte PDF.', 404

    if not _soporte_radicado_legible(factura.soporte_radicado):
        return None, (
            'No se pudo leer el archivo de soporte. '
            'Verifique storage (S3) o que Alegra tenga el PDF disponible.'
        ), 503

    return factura.soporte_radicado, None, None


def _soporte_pdf_url(factura):
    """
    URL para que n8n descargue el PDF vía la app (lee S3 privado con credenciales del servidor).
    GET con el mismo Authorization Bearer que el webhook saliente.
    """
    _try_attach_soporte_from_alegra(factura)
    factura.refresh_from_db(fields=['soporte_radicado'])
    if not factura.soporte_radicado or not factura.soporte_radicado.name:
        return ''
    return _public_url(f'/accounting/webhooks/n8n/gastos-alegra/soporte-pdf/{factura.pk}')


def _alegra_bill_snapshot_from_factura(factura):
    """Snapshot mínimo para n8n (p. ej. plantillas que usan alegra_bill.total)."""
    from accounting.gasto_aprobacion import alegra_id_para_tabla

    alegra_id = alegra_id_para_tabla(factura.alegra_bill_id or '')
    if not alegra_id:
        return None
    valor = int(factura.valor or 0)
    return {
        'id': alegra_id,
        'total': valor,
        'number': (factura.nrofactura or '').strip(),
        'provider_name': (factura.nombretercero or '').strip(),
        'provider_identification': (factura.idtercero or '').strip(),
    }


def _factura_payload(factura):
    from accounting.gasto_aprobacion import factura_a_dict

    data = dict(factura_a_dict(factura))
    data['idtercero'] = factura.idtercero or ''
    data['origen'] = factura.origen or ''
    data['soporte_pdf_url'] = _soporte_pdf_url(factura)
    data['soporte_pdf_listo'] = bool(data['soporte_pdf_url'])
    return data


def _notification_links(factura, *, base_links):
    links = dict(base_links)
    direct = build_gasto_aprobacion_direct_link(factura, public_url_fn=_public_url)
    if direct:
        links['aprobar'] = direct
    url = _soporte_pdf_url(factura)
    if url:
        links['soporte_pdf'] = url
    return links


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
        timeout = 25 if getattr(settings, 'N8N_ALEGRA_ENSURE_SOPORTE_BEFORE_NOTIFY', False) else 5
        response = requests.post(
            url, json=payload, headers=n8n_outbound_headers(content_type_json=True), timeout=timeout,
        )
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
            'links': _notification_links(
                factura, base_links={'asignar': _public_url('/accounting/gastos-alegra/asignar/')},
            ),
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


def _send_gasto_pendiente_aprobacion_webhook(factura_pk, *, assigned_by_user_id, trigger='asignacion_contable'):
    """
    POST a N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION (mismo evento/trigger que asignación inicial).
    Retorna True si se envió el POST, False si se omitió (aprobador inactivo, sin fila, etc.).
    """
    factura = Facturas.objects.select_related(
        'empresa', 'gasto_aprobador_asignado', 'gasto_asignado_por',
    ).filter(pk=factura_pk).first()
    if not factura or not factura.gasto_aprobador_asignado_id:
        logger.warning(
            'n8n gasto pendiente_aprobacion: sin factura o aprobador pk=%s',
            factura_pk,
        )
        return False
    aprobador = factura.gasto_aprobador_asignado
    if not aprobador or not aprobador.is_active:
        logger.warning(
            'n8n gasto pendiente_aprobacion: aprobador inactivo factura_pk=%s',
            factura_pk,
        )
        return False
    assigned_by = None
    if assigned_by_user_id:
        User = get_user_model()
        u = User.objects.filter(pk=assigned_by_user_id).first()
        if u:
            assigned_by = _user_recipient(u, 'contabilidad')
    extra = {
        'links': _notification_links(
            factura,
            base_links={'aprobar_ui': _public_url('/accounting/gastos-alegra/aprobar/')},
        ),
    }
    if assigned_by:
        extra['assigned_by'] = assigned_by
    bill_snap = _alegra_bill_snapshot_from_factura(factura)
    if bill_snap:
        extra['alegra_bill'] = bill_snap
    payload = build_gasto_notification_payload(
        factura,
        event='gasto_alegra.pendiente_aprobacion',
        trigger=trigger,
        recipients=[_aprobador_recipient(aprobador, factura.empresa_id)],
        extra=extra,
    )
    url = settings.N8N_WEBHOOK_ALEGRA_GASTO_PENDIENTE_APROBACION
    logger.info(
        'n8n gasto pendiente_aprobacion: enviando pk=%s trigger=%s url=%s aprobador=%s',
        factura_pk,
        trigger,
        url,
        aprobador.pk,
    )
    _post_n8n(url, payload)
    return True


def notify_gasto_pendiente_aprobacion(factura_pk, *, assigned_by_user_id, trigger='asignacion_contable'):
    if not _notifications_enabled():
        return

    def _after_commit():
        _send_gasto_pendiente_aprobacion_webhook(
            factura_pk,
            assigned_by_user_id=assigned_by_user_id,
            trigger=trigger,
        )

    transaction.on_commit(_after_commit)
