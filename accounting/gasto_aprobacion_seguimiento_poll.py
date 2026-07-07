"""Polling in-app: gastos Alegra pendientes de aprobacion (seguimiento contabilidad)."""
from accounting.gasto_aprobacion import (
    alegra_id_para_tabla,
    gasto_aprobacion_atraso_cutoff,
    gasto_aprobacion_atraso_horas,
    dias_pendiente_aprobacion,
)
from accounting.gasto_poll import empresa_ids_notificacion_usuario
from accounting.models import Facturas

POLL_ITEM_LIMIT = 20


def _parse_known_pks(raw):
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        parts = raw
    else:
        parts = str(raw).split(',')
    known = set()
    for part in parts:
        part = str(part).strip()
        if not part:
            continue
        try:
            known.add(int(part))
        except (TypeError, ValueError):
            continue
    return known


def _item_desde_factura(fac):
    alegra_bill = fac.alegra_bill_id or ''
    aprobador = fac.gasto_aprobador_asignado
    return {
        'pk': fac.pk,
        'nrofactura': fac.nrofactura,
        'nombretercero': fac.nombretercero,
        'empresa_nombre': getattr(fac.empresa, 'nombre', '') or str(fac.empresa_id),
        'empresa': fac.empresa_id,
        'valor': int(fac.valor or 0),
        'alegra_id': alegra_id_para_tabla(alegra_bill),
        'dias_pendiente': dias_pendiente_aprobacion(fac),
        'gasto_aprobador_asignado': (
            aprobador.get_full_name() or aprobador.username
        ) if aprobador else '',
        'gasto_asignado_en': fac.gasto_asignado_en.isoformat() if fac.gasto_asignado_en else '',
    }


def poll_gastos_aprobacion_seguimiento(user, *, known_pks=None):
    """
    Gastos en pendiente_aprobacion que superan el umbral de atraso,
    para usuarios configurados en GastoContableNotificacion.
    """
    empresa_ids = empresa_ids_notificacion_usuario(user)
    if not empresa_ids:
        return {'enabled': False}

    cutoff = gasto_aprobacion_atraso_cutoff()
    atrasados_qs = Facturas.objects.filter(
        origen='Alegra',
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_APROBACION,
        empresa_id__in=empresa_ids,
        gasto_asignado_en__isnull=False,
        gasto_asignado_en__lte=cutoff,
    )
    all_pks = list(atrasados_qs.order_by('pk').values_list('pk', flat=True))
    known = _parse_known_pks(known_pks)
    nuevos_qs = atrasados_qs.exclude(pk__in=known).select_related(
        'empresa', 'gasto_aprobador_asignado',
    ).order_by('gasto_asignado_en', 'pk')[:POLL_ITEM_LIMIT]
    items = [_item_desde_factura(f) for f in nuevos_qs]

    return {
        'enabled': True,
        'atraso_horas': gasto_aprobacion_atraso_horas(),
        'total_atrasados': len(all_pks),
        'all_atrasados_pks': all_pks,
        'count': len(items),
        'items': items,
    }
