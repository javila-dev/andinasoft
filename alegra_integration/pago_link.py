"""Enlace pago local (accounting.Pagos) ↔ id pago en Alegra."""


def sync_pago_from_alegra_document(doc):
    """
    Tras envío exitoso a Alegra (AlegraDocument sent + alegra_id).
    Retorna True si actualizó un Pagos.
    """
    if (getattr(doc, 'source_model', None) or '') != 'accounting.Pagos':
        return False
    alegra_id = str(getattr(doc, 'alegra_id', None) or '').strip()
    if not alegra_id:
        return False
    source_pk = str(getattr(doc, 'source_pk', None) or '').strip()
    if not source_pk or not source_pk.isdigit():
        return False
    from accounting.models import Pagos

    updated = Pagos.objects.filter(pk=int(source_pk)).update(alegra_payment_id=alegra_id)
    return updated > 0
