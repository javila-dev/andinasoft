"""
Mapeo webhook Alegra (bills) -> accounting.Facturas.

La URL de ingesta debe incluir ?empresa=<NIT> (se añade al suscribir) para saber qué fila
`andinasoft.empresas` asociar. `alegra_bill_id` se guarda como "{NIT}:{id_bill}" para unicidad global.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounting.gasto_n8n_notify import (
    build_alegra_bill_snapshot,
    notify_gasto_pendiente_asignacion,
)
from accounting.models import Facturas, Pagos, history_facturas
from andinasoft.models import empresas
from alegra_integration.bill_mapping import (
    ALEGRA_DOC_BILL,
    deactivate_alegra_bill_mapping,
    enrich_factura_from_bill_data,
    link_alegra_document,
    map_bill_to_factura_fields,
)
from alegra_integration.bill_pdf import (
    _attach_pdf_from_bill_data,
    _fetch_bill_from_alegra,
    sync_factura_from_alegra_bill,
)

logger = logging.getLogger(__name__)


def composite_alegra_bill_id(empresa_nit, alegra_numeric_id):
    return f'{empresa_nit}:{alegra_numeric_id}'


@transaction.atomic
def import_factura_from_alegra_bill(empresa, alegra_numeric_id, *, sync_pdf=True):
    """
    Crea (o reconcilia) un radicado local desde GET /bills/{id}.
    Para bills emitidos en Alegra antes de activar webhooks / integración.
    """
    alegra_numeric = str(alegra_numeric_id or '').strip()
    if not alegra_numeric:
        raise ValueError('bill_id es requerido')

    bill_data, auth_header, fields_str = _fetch_bill_from_alegra(empresa, alegra_numeric)
    if not bill_data:
        raise ValueError(f'No se pudo obtener el bill {alegra_numeric} desde Alegra (GET /bills).')

    alegra_numeric = str(bill_data.get('id') or alegra_numeric).strip()
    composite = composite_alegra_bill_id(empresa.pk, alegra_numeric)

    existing = Facturas.objects.filter(alegra_bill_id=composite).first()
    if existing:
        enriched = enrich_factura_from_bill_data(existing, bill_data)
        pdf_saved = False
        if sync_pdf:
            pdf_saved = _attach_pdf_from_bill_data(
                empresa, alegra_numeric, existing, bill_data, auth_header, fields_str
            )
        link_alegra_document(empresa, existing, document_type=ALEGRA_DOC_BILL, alegra_numeric_id=alegra_numeric)
        existing.save(update_fields=['alegra_document_type'])
        user = _history_user()
        if user and (enriched or pdf_saved):
            parts = []
            if enriched:
                parts.append('datos: ' + ', '.join(enriched))
            if pdf_saved:
                parts.append('PDF adjunto')
            history_facturas.objects.create(
                factura=existing,
                usuario=user,
                accion=f'Reconciliado desde Alegra GET /bills/{alegra_numeric} ({"; ".join(parts)})',
                ubicacion='Contabilidad',
            )
        return {
            'created': False,
            'factura_pk': existing.pk,
            'alegra_bill_id': composite,
            'enriched_fields': enriched,
            'pdf_saved': pdf_saved,
        }

    fields = map_bill_to_factura_fields(bill_data)
    idtercero = fields['idtercero']
    nrofactura = fields['nrofactura']
    if idtercero and Facturas.objects.filter(idtercero=idtercero, nrofactura=nrofactura).exists():
        fields['nrofactura'] = (nrofactura + f'-{composite}')[:255]

    fac = Facturas.objects.create(
        empresa=empresa,
        alegra_bill_id=composite,
        alegra_document_type=ALEGRA_DOC_BILL,
        cuenta_por_pagar=None,
        secuencia_cxp=None,
        oficina=None,
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
        gasto_aprobacion_comentario_contable='',
        gasto_aprobado=False,
        **fields,
    )

    enriched = enrich_factura_from_bill_data(fac, bill_data)
    pdf_saved = False
    if sync_pdf:
        pdf_saved = _attach_pdf_from_bill_data(
            empresa, alegra_numeric, fac, bill_data, auth_header, fields_str
        )
    link_alegra_document(empresa, fac, document_type=ALEGRA_DOC_BILL, alegra_numeric_id=alegra_numeric)
    fac.save(update_fields=['alegra_document_type'])

    user = _history_user()
    if user:
        history_facturas.objects.create(
            factura=fac,
            usuario=user,
            accion=(
                f'Creada desde Alegra GET /bills/{alegra_numeric} ({composite}); '
                'pendiente asignación oficina/aprobador'
            ),
            ubicacion='Contabilidad',
        )

    notify_gasto_pendiente_asignacion(
        fac.pk,
        trigger='import_bill',
        alegra_bill_snapshot=build_alegra_bill_snapshot(bill_data),
    )

    return {
        'created': True,
        'factura_pk': fac.pk,
        'alegra_bill_id': composite,
        'enriched_fields': enriched,
        'pdf_saved': pdf_saved,
    }


def _schedule_bill_pdf_download(empresa_pk, alegra_numeric_id, factura_pk):
    """Tras commit: GET /bills/{id} — enriquece campos y descarga PDF (un solo request)."""

    def _after_commit():
        try:
            empresa_obj = empresas.objects.get(pk=empresa_pk)
            fac = Facturas.objects.get(pk=factura_pk)
            result = sync_factura_from_alegra_bill(empresa_obj, str(alegra_numeric_id), fac)
            user = _history_user()
            if not user:
                return
            parts = []
            if result.get('enriched_fields'):
                parts.append('datos: ' + ', '.join(result['enriched_fields']))
            if result.get('pdf_saved'):
                parts.append('PDF adjunto')
            if parts:
                history_facturas.objects.create(
                    factura=fac,
                    usuario=user,
                    accion=f'Sincronizado desde Alegra GET /bills/{alegra_numeric_id} ({"; ".join(parts)})',
                    ubicacion='Contabilidad',
                )
        except Exception:
            logger.exception('Fallo sync Alegra bill factura_pk=%s bill=%s', factura_pk, alegra_numeric_id)

    transaction.on_commit(_after_commit)


def _history_user():
    User = get_user_model()
    uid = getattr(settings, 'ALEGRA_WEBHOOK_HISTORY_USER_ID', None)
    if uid is not None and str(uid).strip():
        u = User.objects.filter(pk=int(uid)).first()
        if u:
            return u
    username = (getattr(settings, 'ALEGRA_WEBHOOK_HISTORY_USERNAME', None) or '').strip()
    if username:
        u = User.objects.filter(username=username, is_active=True).first()
        if u:
            return u
    return User.objects.filter(is_active=True).order_by('pk').first()


def process_inbound_post(empresa_nit, payload):
    """
    empresa_nit: NIT de la empresa, desde path /webhooks/bills/<NIT>/ o ?empresa=<NIT>.
    """
    result = {'processed': False}
    subject = str((payload or {}).get('subject') or '').strip().lower()
    msg = (payload or {}).get('message') or {}
    bill = msg.get('bill') if isinstance(msg, dict) else None

    if not (empresa_nit or '').strip():
        result['skip_reason'] = 'missing_empresa'
        return result
    if not isinstance(bill, dict):
        result['skip_reason'] = 'no_message.bill'
        return result

    alegra_numeric = str(bill.get('id') or '').strip()
    if not alegra_numeric:
        result['skip_reason'] = 'missing_bill_id'
        return result

    try:
        empresa = empresas.objects.get(pk=str(empresa_nit).strip())
    except empresas.DoesNotExist:
        result['skip_reason'] = 'empresa_not_found'
        return result

    composite = composite_alegra_bill_id(empresa.pk, alegra_numeric)

    try:
        if subject == 'new-bill':
            result.update(_handle_new_bill(empresa, composite, bill))
        elif subject == 'edit-bill':
            result.update(_handle_edit_bill(composite, bill))
        elif subject == 'delete-bill':
            result.update(_handle_delete_bill(composite))
        else:
            result['skip_reason'] = 'unknown_subject'
            result['subject'] = subject
    except Exception as exc:
        logger.exception('alegra webhook bill processing')
        result['processing_error'] = str(exc)
    return result


@transaction.atomic
def _handle_new_bill(empresa, composite_alegra_id, bill):
    alegra_numeric = str(bill.get('id') or '').strip()
    if Facturas.objects.filter(alegra_bill_id=composite_alegra_id).exists():
        fac = Facturas.objects.get(alegra_bill_id=composite_alegra_id)
        entered_asignacion = False
        if (
            fac.origen == 'Alegra'
            and not fac.gasto_aprobado
            and fac.gasto_aprobacion_estado == Facturas.GASTO_APROB_NO_APLICA
        ):
            fac.gasto_aprobacion_estado = Facturas.GASTO_APROB_PENDIENTE_ASIGNACION
            fac.save(update_fields=['gasto_aprobacion_estado'])
            entered_asignacion = True
        if not fac.soporte_radicado:
            _schedule_bill_pdf_download(str(empresa.pk), str(bill.get('id') or '').strip(), fac.pk)
        link_alegra_document(empresa, fac, document_type=ALEGRA_DOC_BILL, alegra_numeric_id=alegra_numeric)
        fac.save(update_fields=['alegra_document_type'])
        if entered_asignacion:
            notify_gasto_pendiente_asignacion(
                fac.pk,
                trigger='webhook_new_bill',
                alegra_bill_snapshot=build_alegra_bill_snapshot(bill),
            )
        return {'processed': True, 'idempotent': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite_alegra_id}

    fields = map_bill_to_factura_fields(bill)
    idtercero = fields['idtercero']
    nrofactura = fields['nrofactura']
    if idtercero and Facturas.objects.filter(idtercero=idtercero, nrofactura=nrofactura).exists():
        fields['nrofactura'] = (nrofactura + f'-{composite_alegra_id}')[:255]

    fac = Facturas.objects.create(
        empresa=empresa,
        alegra_bill_id=composite_alegra_id,
        alegra_document_type=ALEGRA_DOC_BILL,
        cuenta_por_pagar=None,
        secuencia_cxp=None,
        oficina=None,
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
        gasto_aprobacion_comentario_contable='',
        gasto_aprobado=False,
        **fields,
    )

    user = _history_user()
    if user:
        history_facturas.objects.create(
            factura=fac,
            usuario=user,
            accion=f'Creada desde webhook Alegra new-bill ({composite_alegra_id}); pendiente asignación oficina/aprobador',
            ubicacion='Contabilidad',
        )
    _schedule_bill_pdf_download(str(empresa.pk), alegra_numeric, fac.pk)
    link_alegra_document(empresa, fac, document_type=ALEGRA_DOC_BILL, alegra_numeric_id=alegra_numeric)
    fac.save(update_fields=['alegra_document_type'])
    notify_gasto_pendiente_asignacion(
        fac.pk,
        trigger='webhook_new_bill',
        alegra_bill_snapshot=build_alegra_bill_snapshot(bill),
    )
    return {'processed': True, 'created': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite_alegra_id}


@transaction.atomic
def _handle_edit_bill(composite_alegra_id, bill):
    fac = Facturas.objects.filter(alegra_bill_id=composite_alegra_id).first()
    if not fac:
        return {'processed': False, 'skip_reason': 'factura_not_found_for_edit', 'alegra_bill_id': composite_alegra_id}

    fields = map_bill_to_factura_fields(bill)
    fields.pop('origen', None)
    for key, value in fields.items():
        if key == 'pago_neto' and getattr(fac, 'gasto_es_canje', False):
            continue
        setattr(fac, key, value)
    fac.alegra_bill_deleted = False
    fac.alegra_bill_deleted_at = None
    fac.alegra_document_type = ALEGRA_DOC_BILL
    fac.save()
    link_alegra_document(fac.empresa, fac, document_type=ALEGRA_DOC_BILL, alegra_numeric_id=str(bill.get('id') or '').strip())

    user = _history_user()
    if user:
        history_facturas.objects.create(
            factura=fac,
            usuario=user,
            accion=f'Actualizada desde webhook Alegra edit-bill ({composite_alegra_id})',
            ubicacion='Contabilidad',
        )
    _schedule_bill_pdf_download(str(fac.empresa_id), str(bill.get('id') or '').strip(), fac.pk)
    return {'processed': True, 'updated': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite_alegra_id}


@transaction.atomic
def _handle_delete_bill(composite_alegra_id):
    fac = Facturas.objects.filter(alegra_bill_id=composite_alegra_id).first()
    if not fac:
        return {'processed': False, 'skip_reason': 'factura_not_found_for_delete', 'alegra_bill_id': composite_alegra_id}

    if Pagos.objects.filter(nroradicado=fac).exists():
        fac.alegra_bill_deleted = True
        fac.alegra_bill_deleted_at = timezone.now()
        fac.save(update_fields=['alegra_bill_deleted', 'alegra_bill_deleted_at'])
        user = _history_user()
        if user:
            history_facturas.objects.create(
                factura=fac,
                usuario=user,
                accion=f'Marcada eliminada en Alegra (delete-bill); hay pagos. {composite_alegra_id}',
                ubicacion='Contabilidad',
            )
        return {'processed': True, 'deleted_soft': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite_alegra_id}

    deactivate_alegra_bill_mapping(fac.empresa_id, fac.pk)
    fac.delete()
    return {'processed': True, 'deleted_hard': True, 'factura_pk': None, 'alegra_bill_id': composite_alegra_id}
