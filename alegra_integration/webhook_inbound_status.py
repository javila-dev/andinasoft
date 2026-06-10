"""
Estado de procesamiento de webhooks entrantes (¿creó radicado?).
"""
from django.db.models import Q

from accounting.models import Facturas
from alegra_integration.webhook_bills import composite_alegra_bill_id

INBOUND_CONSOLE_PAGE_SIZE = 50

INBOUND_EVENT_CHOICES = (
    ('new-bill', 'Factura nueva'),
    ('edit-bill', 'Factura editada'),
    ('delete-bill', 'Factura eliminada'),
)

INBOUND_STATUS_FILTER_CHOICES = (
    ('', 'Todos'),
    ('ok', 'Procesado'),
    ('error', 'Error'),
    ('skip', 'Omitido'),
    ('missing', 'Sin radicado'),
)

SKIP_REASON_LABELS = {
    'missing_empresa': 'Sin empresa en URL',
    'missing_empresa_query_param': 'Sin empresa en URL',
    'no_message.bill': 'Sin factura en payload',
    'missing_bill_id': 'Sin id de bill',
    'empresa_not_found': 'Empresa no encontrada',
    'factura_not_found_for_edit': 'Radicado no existe (edit)',
    'factura_not_found_for_delete': 'Radicado no existe (delete)',
    'unknown_subject': 'Evento no soportado',
    'not_processed': 'No procesado',
    'radicado_not_created': 'No creado',
}

def resolve_empresa_nit_for_log(log, empresa_filter='', bill_id=''):
    """
    NIT usado en ingesta: campo guardado, ?empresa=, path /bills/<NIT>/ (al persistir),
    filtro de la consola, o inferido desde Facturas.alegra_bill_id existente.
    """
    stored = (getattr(log, 'empresa_nit', None) or '').strip()
    if stored:
        return stored
    qs = (getattr(log, 'query_string', None) or '').strip()
    if qs:
        from urllib.parse import parse_qs
        vals = parse_qs(qs, keep_blank_values=False).get('empresa') or []
        if vals and str(vals[0]).strip():
            return str(vals[0]).strip()
    filt = (empresa_filter or '').strip()
    if filt:
        return filt
    bill_id = (bill_id or '').strip()
    if bill_id:
        suffix = f':{bill_id}'
        fac = (
            Facturas.objects.filter(alegra_bill_id__endswith=suffix)
            .only('alegra_bill_id')
            .order_by('-pk')
            .first()
        )
        if fac and fac.alegra_bill_id and fac.alegra_bill_id.endswith(suffix):
            prefix = fac.alegra_bill_id[: -len(suffix)]
            if prefix:
                return prefix
    return ''


PROCESS_DETAIL_LABELS = {
    'created': 'Radicado creado',
    'idempotent': 'Ya existía',
    'updated': 'Radicado actualizado',
    'deleted_soft': 'Marcado eliminado (con pagos)',
    'deleted_hard': 'Radicado eliminado',
}


def extract_bill_from_payload(payload):
    payload = payload if isinstance(payload, dict) else {}
    msg = payload.get('message')
    if not isinstance(msg, dict):
        return None, ''
    bill = msg.get('bill')
    if not isinstance(bill, dict):
        return None, str(payload.get('subject') or '').strip().lower()
    return bill, str(payload.get('subject') or '').strip().lower()


def extract_bill_display_fields(bill):
    """
    Campos legibles para la tabla de recepciones (proveedor y valor a pagar).
    """
    empty = {
        'tercero_nombre': '',
        'tercero_nit': '',
        'nro_factura': '',
        'valor': None,
        'valor_display': '',
    }
    if not isinstance(bill, dict):
        return empty

    from alegra_integration.bill_mapping import map_bill_to_factura_fields

    mapped = map_bill_to_factura_fields(bill)
    valor = mapped.get('valor')
    valor_display = ''
    if valor is not None and int(valor) > 0:
        valor_display = f'${int(valor):,}'

    nt = bill.get('numberTemplate') or {}
    nro_factura = ''
    if isinstance(nt, dict) and nt.get('number') is not None:
        nro_factura = str(nt.get('number')).strip()

    nombre = (mapped.get('nombretercero') or '').strip()
    if nombre.upper() == 'SIN NOMBRE':
        nombre = ''

    return {
        'tercero_nombre': nombre,
        'tercero_nit': (mapped.get('idtercero') or '').strip(),
        'nro_factura': nro_factura,
        'valor': valor,
        'valor_display': valor_display,
    }


def infer_inbound_process_result(empresa_nit, payload):
    """
    Calcula el resultado de procesamiento sin escribir Facturas (solo para backfill de logs).
    """
    empresa_nit = (empresa_nit or '').strip()
    bill, subject = extract_bill_from_payload(payload)
    bill_id = str((bill or {}).get('id') or '').strip()

    if not empresa_nit:
        return {'processed': False, 'skip_reason': 'missing_empresa'}
    if not isinstance(bill, dict):
        return {'processed': False, 'skip_reason': 'no_message.bill'}
    if not bill_id:
        return {'processed': False, 'skip_reason': 'missing_bill_id'}

    from andinasoft.models import empresas
    try:
        empresas.objects.get(pk=empresa_nit)
    except empresas.DoesNotExist:
        return {'processed': False, 'skip_reason': 'empresa_not_found'}

    composite = composite_alegra_bill_id(empresa_nit, bill_id)
    fac = Facturas.objects.filter(alegra_bill_id=composite).first()

    if subject == 'new-bill':
        if fac:
            return {
                'processed': True,
                'idempotent': True,
                'factura_pk': fac.pk,
                'alegra_bill_id': composite,
            }
        return {'processed': False, 'skip_reason': 'radicado_not_created'}

    if subject == 'edit-bill':
        if fac:
            return {'processed': True, 'updated': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite}
        return {'processed': False, 'skip_reason': 'factura_not_found_for_edit', 'alegra_bill_id': composite}

    if subject == 'delete-bill':
        if fac:
            return {'processed': True, 'deleted_soft': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite}
        return {'processed': False, 'skip_reason': 'factura_not_found_for_delete', 'alegra_bill_id': composite}

    return {'processed': False, 'skip_reason': 'unknown_subject', 'subject': subject}


def log_matches_empresa_backfill(log, empresa_nit, *, include_unassigned=False):
    """
    ¿Este log entrante corresponde al NIT del path /bills/<NIT>/?
    """
    empresa_nit = (empresa_nit or '').strip()
    current = (getattr(log, 'empresa_nit', None) or '').strip()
    if current and current != empresa_nit:
        return False
    if current == empresa_nit:
        return True

    payload = log.payload if isinstance(log.payload, dict) else {}
    if payload.get('_json_parse_error'):
        return False

    bill, _subject = extract_bill_from_payload(payload)
    bill_id = str((bill or {}).get('id') or '').strip()
    if not bill_id:
        return bool(include_unassigned)

    composite = composite_alegra_bill_id(empresa_nit, bill_id)
    if Facturas.objects.filter(alegra_bill_id=composite).exists():
        return True

    suffix = f':{bill_id}'
    other = (
        Facturas.objects.filter(alegra_bill_id__endswith=suffix)
        .exclude(alegra_bill_id=composite)
        .exists()
    )
    if other:
        return False
    return bool(include_unassigned)


def update_inbound_log_from_process_result(log, empresa_nit, result):
    if not log or not getattr(log, 'pk', None):
        return
    result = result or {}
    empresa_nit = (empresa_nit or '')[:32]
    process_status = ''
    process_detail = ''
    factura_id = None

    if result.get('processing_error'):
        process_status = 'error'
        process_detail = str(result.get('processing_error'))[:128]
    elif result.get('skip_reason'):
        process_status = 'skip'
        process_detail = str(result.get('skip_reason'))[:128]
    elif result.get('processed'):
        process_status = 'ok'
        factura_id = result.get('factura_pk')
        if result.get('created'):
            process_detail = 'created'
        elif result.get('idempotent'):
            process_detail = 'idempotent'
        elif result.get('updated'):
            process_detail = 'updated'
        elif result.get('deleted_soft'):
            process_detail = 'deleted_soft'
        elif result.get('deleted_hard'):
            process_detail = 'deleted_hard'
        else:
            process_detail = 'processed'
    else:
        process_status = 'skip'
        process_detail = 'not_processed'

    type(log).objects.filter(pk=log.pk).update(
        empresa_nit=empresa_nit,
        process_status=process_status,
        process_detail=process_detail,
        factura_id=factura_id,
    )
    log.empresa_nit = empresa_nit
    log.process_status = process_status
    log.process_detail = process_detail
    log.factura_id = factura_id


def radicado_status_display(log, empresa_nit, bill_id, subject, factura=None):
    """
    Devuelve dict para la UI: kind, label, detail, factura_pk.
    kind: ok | missing | skip | error | unknown | na
    """
    bill_id = (bill_id or '').strip()
    empresa_nit = (empresa_nit or '').strip()
    subject = (subject or '').strip().lower()

    if not bill_id:
        return {'kind': 'na', 'label': '—', 'detail': '', 'factura_pk': None}

    stored_status = (getattr(log, 'process_status', None) or '').strip()
    stored_detail = (getattr(log, 'process_detail', None) or '').strip()
    stored_factura_id = getattr(log, 'factura_id', None)

    if stored_status == 'error':
        return {
            'kind': 'error',
            'label': 'Error',
            'detail': stored_detail[:120],
            'factura_pk': None,
        }
    if stored_status == 'skip':
        stale_missing_empresa = stored_detail in ('missing_empresa_query_param', 'missing_empresa')
        if not (stale_missing_empresa and empresa_nit):
            label = SKIP_REASON_LABELS.get(stored_detail, stored_detail or 'No procesado')
            return {'kind': 'skip', 'label': label, 'detail': stored_detail, 'factura_pk': None}
    if stored_status == 'ok':
        pk = stored_factura_id
        if pk:
            label = PROCESS_DETAIL_LABELS.get(stored_detail, 'Procesado')
            if stored_detail == 'created':
                label = f'Creado #{pk}'
            elif stored_detail in ('idempotent', 'updated'):
                label = f'{PROCESS_DETAIL_LABELS.get(stored_detail, "OK")} #{pk}'
            elif stored_detail == 'deleted_hard':
                label = 'Eliminado'
                pk = None
            else:
                label = f'{label} #{pk}' if pk else label
            return {
                'kind': 'ok',
                'label': label,
                'detail': stored_detail,
                'factura_pk': pk,
            }
        if stored_detail == 'deleted_hard':
            return {'kind': 'ok', 'label': 'Eliminado', 'detail': stored_detail, 'factura_pk': None}

    if not empresa_nit:
        return {
            'kind': 'unknown',
            'label': 'Sin empresa',
            'detail': 'Falta NIT (path /bills/<NIT>/ o filtro arriba)',
            'factura_pk': None,
        }

    if factura is None and bill_id:
        composite = composite_alegra_bill_id(empresa_nit, bill_id)
        factura = Facturas.objects.filter(alegra_bill_id=composite).only('pk').first()

    if factura:
        return {
            'kind': 'ok',
            'label': f'Radicado #{factura.pk}',
            'detail': 'Existe en BD',
            'factura_pk': factura.pk,
        }

    if subject == 'new-bill':
        return {
            'kind': 'missing',
            'label': 'No creado',
            'detail': 'No hay radicado con ese alegra_bill_id',
            'factura_pk': None,
        }
    if subject in ('edit-bill', 'delete-bill'):
        return {
            'kind': 'missing',
            'label': 'Sin radicado',
            'detail': 'No encontrado para este evento',
            'factura_pk': None,
        }
    return {
        'kind': 'unknown',
        'label': 'No verificado',
        'detail': '',
        'factura_pk': None,
    }


def queryset_inbound_logs_for_console(*, empresa='', evento='', estado='', buscar=''):
    """
    Filtra AlegraWebhookInboundLog para la pestaña Recepciones de la consola webhooks.
    """
    from alegra_integration.models import AlegraWebhookInboundLog

    qs = AlegraWebhookInboundLog.objects.filter(http_method='POST').order_by('-created_at')
    empresa = (empresa or '').strip()
    if empresa:
        qs = qs.filter(empresa_nit=empresa)
    evento = (evento or '').strip()
    if evento:
        qs = qs.filter(payload__subject=evento)
    buscar = (buscar or '').strip()
    if buscar:
        qs = qs.filter(
            Q(payload__message__bill__client__name__icontains=buscar)
            | Q(payload__message__bill__provider__name__icontains=buscar)
            | Q(payload__message__bill__client__identification__icontains=buscar)
            | Q(payload__message__bill__provider__identification__icontains=buscar)
            | Q(payload__message__bill__numberTemplate__number__icontains=buscar)
            | Q(payload__message__bill__id__icontains=buscar)
            | Q(raw_body__icontains=buscar)
        )
    estado = (estado or '').strip()
    if estado == 'ok':
        qs = qs.filter(process_status='ok').exclude(process_detail='deleted_hard')
    elif estado == 'error':
        qs = qs.filter(process_status='error')
    elif estado == 'skip':
        qs = qs.filter(process_status='skip')
    elif estado == 'missing':
        qs = qs.filter(payload__subject='new-bill').filter(
            Q(process_status='skip', process_detail='radicado_not_created')
            | Q(process_status='skip', process_detail='not_processed')
            | Q(process_status='', factura_id__isnull=True)
            | Q(process_status='ok', process_detail='deleted_hard')
        )
    return qs


def build_inbound_log_rows(logs, empresa_filter=''):
    """
    Enriquece filas de AlegraWebhookInboundLog para la consola webhooks.
    """
    rows = []
    composites = []
    for log in logs:
        payload = log.payload if isinstance(log.payload, dict) else {}
        bill, subject_raw = extract_bill_from_payload(payload)
        bill = bill if isinstance(bill, dict) else {}
        bill_id = str(bill.get('id') or '').strip()
        subject = str(subject_raw or payload.get('subject') or '').strip()
        display = extract_bill_display_fields(bill)
        empresa_nit = resolve_empresa_nit_for_log(log, empresa_filter, bill_id=bill_id)
        empresa_hint = (getattr(log, 'empresa_nit', None) or '').strip() or empresa_nit
        composite = composite_alegra_bill_id(empresa_nit, bill_id) if empresa_nit and bill_id else ''
        if composite:
            composites.append(composite)
        rows.append({
            'log': log,
            'subject': subject[:60],
            'bill_id': bill_id,
            'nro_factura': display['nro_factura'],
            'tercero_nombre': display['tercero_nombre'],
            'tercero_nit': display['tercero_nit'],
            'valor': display['valor'],
            'valor_display': display['valor_display'],
            'empresa_hint': empresa_hint,
            'empresa_nit': empresa_nit,
            'payload_ok': bool(payload) and not payload.get('_json_parse_error'),
            '_composite': composite,
        })

    fac_by_comp = {}
    if composites:
        for fac in Facturas.objects.filter(alegra_bill_id__in=composites).only('pk', 'alegra_bill_id'):
            fac_by_comp[fac.alegra_bill_id] = fac

    for row in rows:
        fac = fac_by_comp.get(row.pop('_composite', ''))
        row['radicado'] = radicado_status_display(
            row['log'],
            row['empresa_nit'],
            row['bill_id'],
            row['subject'],
            factura=fac,
        )
    return rows
