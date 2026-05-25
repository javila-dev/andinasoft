"""Polling in-app de nuevos gastos Alegra pendientes de asignación."""
from accounting.gasto_aprobacion import alegra_id_para_tabla
from accounting.models import Facturas, GastoContableNotificacion

POLL_ITEM_LIMIT = 20


def empresa_ids_notificacion_usuario(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    return list(
        GastoContableNotificacion.objects.filter(
            user=user,
            activo=True,
        ).values_list('empresa_id', flat=True).distinct()
    )


def _item_desde_factura(fac):
    alegra_bill = fac.alegra_bill_id or ''
    return {
        'pk': fac.pk,
        'nrofactura': fac.nrofactura,
        'nombretercero': fac.nombretercero,
        'empresa_nombre': getattr(fac.empresa, 'nombre', '') or str(fac.empresa_id),
        'empresa': fac.empresa_id,
        'valor': fac.valor,
        'alegra_id': alegra_id_para_tabla(alegra_bill),
    }


def poll_gastos_alegra_notificaciones(user, *, since_pk=0):
    empresa_ids = empresa_ids_notificacion_usuario(user)
    if not empresa_ids:
        return {'enabled': False}

    try:
        since_pk = max(0, int(since_pk or 0))
    except (TypeError, ValueError):
        since_pk = 0

    base_qs = Facturas.objects.filter(
        pk__gt=since_pk,
        origen='Alegra',
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
        empresa_id__in=empresa_ids,
    )
    max_pk = base_qs.order_by('-pk').values_list('pk', flat=True).first() or since_pk
    facturas = list(
        base_qs.select_related('empresa').order_by('pk')[:POLL_ITEM_LIMIT]
    )
    items = [_item_desde_factura(f) for f in facturas]
    return {
        'enabled': True,
        'max_pk': max_pk,
        'count': len(items),
        'items': items,
    }
