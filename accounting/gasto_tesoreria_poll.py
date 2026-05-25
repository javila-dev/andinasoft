"""Polling in-app: gastos Alegra recién aprobados para usuarios de tesorería."""
from datetime import datetime

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounting.gasto_aprobacion import alegra_id_para_tabla
from accounting.models import Facturas, GastoTesoreriaNotificacion

POLL_ITEM_LIMIT = 20


def _config_tesoreria_usuario(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    entry = (
        GastoTesoreriaNotificacion.objects.filter(user=user, activo=True)
        .prefetch_related('empresas', 'oficinas')
        .first()
    )
    if not entry:
        return None
    empresa_ids = list(entry.empresas.values_list('pk', flat=True))
    oficinas = list(entry.oficinas.values_list('codigo', flat=True))
    if not empresa_ids or not oficinas:
        return None
    return {'empresa_ids': empresa_ids, 'oficinas': oficinas}


def _parse_since_ts(since_ts):
    if not since_ts:
        return None
    if hasattr(since_ts, 'tzinfo'):
        dt = since_ts
    else:
        dt = parse_datetime(str(since_ts).strip())
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _item_desde_factura(fac):
    alegra_bill = fac.alegra_bill_id or ''
    return {
        'pk': fac.pk,
        'nrofactura': fac.nrofactura,
        'nombretercero': fac.nombretercero,
        'empresa_nombre': getattr(fac.empresa, 'nombre', '') or str(fac.empresa_id),
        'empresa': fac.empresa_id,
        'oficina': fac.oficina or '',
        'valor': int(fac.valor or 0),
        'alegra_id': alegra_id_para_tabla(alegra_bill),
        'gasto_aprobado_en': fac.gasto_aprobado_en.isoformat() if fac.gasto_aprobado_en else '',
    }


def poll_gastos_tesoreria_aprobados(user, *, since_ts=None):
    """
    Radicados Alegra que pasaron a aprobado después de since_ts,
    filtrados por empresas y oficinas configuradas en Admin.
    """
    cfg = _config_tesoreria_usuario(user)
    if not cfg:
        return {'enabled': False}

    since_dt = _parse_since_ts(since_ts)
    if since_dt is None:
        since_dt = datetime(1970, 1, 1, tzinfo=timezone.utc)

    base_qs = Facturas.objects.filter(
        origen='Alegra',
        gasto_aprobacion_estado=Facturas.GASTO_APROB_APROBADO,
        gasto_aprobado=True,
        gasto_aprobado_en__gt=since_dt,
        gasto_aprobado_en__isnull=False,
        empresa_id__in=cfg['empresa_ids'],
        oficina__in=cfg['oficinas'],
    )
    max_en = base_qs.order_by('-gasto_aprobado_en').values_list('gasto_aprobado_en', flat=True).first()
    max_ts = max_en.isoformat() if max_en else since_dt.isoformat()

    facturas = list(
        base_qs.select_related('empresa').order_by('gasto_aprobado_en', 'pk')[:POLL_ITEM_LIMIT]
    )
    items = [_item_desde_factura(f) for f in facturas]
    return {
        'enabled': True,
        'max_ts': max_ts,
        'count': len(items),
        'items': items,
    }
