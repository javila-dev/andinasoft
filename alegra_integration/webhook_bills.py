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
from django.utils.dateparse import parse_date

from accounting.models import Facturas, Pagos, history_facturas
from andinasoft.models import empresas
from alegra_integration.bill_pdf import attach_bill_pdf_from_alegra

logger = logging.getLogger(__name__)


def composite_alegra_bill_id(empresa_nit, alegra_numeric_id):
    return f'{empresa_nit}:{alegra_numeric_id}'


def _schedule_bill_pdf_download(empresa_pk, alegra_numeric_id, factura_pk):
    """Tras commit: GET /bills/{id} en Alegra y guarda PDF en soporte_radicado."""

    def _after_commit():
        try:
            empresa_obj = empresas.objects.get(pk=empresa_pk)
            fac = Facturas.objects.get(pk=factura_pk)
            ok = attach_bill_pdf_from_alegra(empresa_obj, str(alegra_numeric_id), fac)
            if ok:
                user = _history_user()
                if user:
                    history_facturas.objects.create(
                        factura=fac,
                        usuario=user,
                        accion=f'PDF descargado desde Alegra (bill {alegra_numeric_id})',
                        ubicacion='Contabilidad',
                    )
        except Exception:
            logger.exception('Fallo descarga PDF Alegra factura_pk=%s bill=%s', factura_pk, alegra_numeric_id)

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


def _parse_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def map_bill_to_factura_fields(bill):
    """
    Campos locales derivados de message.bill (sin empresa, alegra_bill_id ni archivos).
    """
    nt = bill.get('numberTemplate') or {}
    if isinstance(nt, dict):
        raw_num = nt.get('number')
        number_str = str(raw_num).strip() if raw_num is not None else ''
    else:
        number_str = ''

    client = bill.get('client') or {}
    identification = (client.get('identification') or '').strip()
    if not identification and client.get('id') is not None:
        identification = str(client.get('id')).strip()

    nombre = (client.get('name') or '')[:255]
    bid = str(bill.get('id') or '').strip()

    total = _parse_int(bill.get('total'))
    subtotal = _parse_int(bill.get('subtotal'))
    valor = total if total else subtotal
    pago_neto = valor

    fecha_fact = parse_date(str(bill.get('date') or '')[:10]) if bill.get('date') else None
    if not fecha_fact:
        fecha_fact = timezone.now().date()
    fecha_venc = (
        parse_date(str(bill.get('dueDate') or '')[:10]) if bill.get('dueDate') else fecha_fact
    ) or fecha_fact
    fecha_causa = fecha_fact

    observations = bill.get('observations')
    if observations:
        desc = str(observations)[:255]
    else:
        desc = (f'Factura compra Alegra {number_str or bid}')[:255]

    nrocausa = (number_str or f'ALEGRA-{bid}')[:255]
    nrofactura = (number_str or f'ALEGRA-{bid}')[:255]

    idtercero = (identification or str(client.get('id') or ''))[:255]

    return {
        'nrofactura': nrofactura,
        'fechafactura': fecha_fact,
        'fechavenc': fecha_venc,
        'idtercero': idtercero,
        'nombretercero': (nombre or 'SIN NOMBRE')[:255],
        'descripcion': desc,
        'valor': valor,
        'pago_neto': pago_neto,
        'nrocausa': nrocausa,
        'fechacausa': fecha_causa,
        'origen': 'Alegra',
    }


def process_inbound_post(empresa_nit, payload):
    """
    empresa_nit: query param ?empresa= de la URL registrada en Alegra.
    """
    result = {'processed': False}
    subject = str((payload or {}).get('subject') or '').strip().lower()
    msg = (payload or {}).get('message') or {}
    bill = msg.get('bill') if isinstance(msg, dict) else None

    if not (empresa_nit or '').strip():
        result['skip_reason'] = 'missing_empresa_query_param'
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
    if Facturas.objects.filter(alegra_bill_id=composite_alegra_id).exists():
        fac = Facturas.objects.get(alegra_bill_id=composite_alegra_id)
        if not fac.soporte_radicado:
            _schedule_bill_pdf_download(str(empresa.pk), str(bill.get('id') or '').strip(), fac.pk)
        return {'processed': True, 'idempotent': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite_alegra_id}

    fields = map_bill_to_factura_fields(bill)
    idtercero = fields['idtercero']
    nrofactura = fields['nrofactura']
    if idtercero and Facturas.objects.filter(idtercero=idtercero, nrofactura=nrofactura).exists():
        fields['nrofactura'] = (nrofactura + f'-{composite_alegra_id}')[:255]

    fac = Facturas.objects.create(
        empresa=empresa,
        alegra_bill_id=composite_alegra_id,
        cuenta_por_pagar=None,
        secuencia_cxp=None,
        oficina=None,
        **fields,
    )

    user = _history_user()
    if user:
        history_facturas.objects.create(
            factura=fac,
            usuario=user,
            accion=f'Creada desde webhook Alegra new-bill ({composite_alegra_id})',
            ubicacion='Contabilidad',
        )
    _schedule_bill_pdf_download(str(empresa.pk), str(bill.get('id') or '').strip(), fac.pk)
    return {'processed': True, 'created': True, 'factura_pk': fac.pk, 'alegra_bill_id': composite_alegra_id}


@transaction.atomic
def _handle_edit_bill(composite_alegra_id, bill):
    fac = Facturas.objects.filter(alegra_bill_id=composite_alegra_id).first()
    if not fac:
        return {'processed': False, 'skip_reason': 'factura_not_found_for_edit', 'alegra_bill_id': composite_alegra_id}

    fields = map_bill_to_factura_fields(bill)
    fields.pop('origen', None)
    for key, value in fields.items():
        setattr(fac, key, value)
    fac.alegra_bill_deleted = False
    fac.alegra_bill_deleted_at = None
    fac.save()

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

    fac.delete()
    return {'processed': True, 'deleted_hard': True, 'factura_pk': None, 'alegra_bill_id': composite_alegra_id}
