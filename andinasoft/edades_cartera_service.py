"""
Snapshot en tiempo real de edades de cartera.

Réplica la lógica de Adjudicacion.presupuesto() (PlanPagos + mora al día de la consulta)
con consultas agrupadas. No usa PresupuestoCartera.
"""
from __future__ import annotations

import calendar
import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Max

from andinasoft.estado_cuenta_service import _mora_cuota, _pendiente_cuota
from andinasoft.shared_models import (
    Adjudicacion,
    InfoCartera,
    PlanPagos,
    Recaudos,
    Vista_Adjudicacion,
)


def _empty_recaudo_bucket():
    return {
        'capital': Decimal('0'),
        'interes': Decimal('0'),
        'mora': Decimal('0'),
        'max_fecha_cap_int': None,
        'max_fecha_solo_mora': None,
        'moras_por_fecha': [],
    }


def _load_recaudos_by_idcta(proyecto: str, adj_ids: list) -> dict:
    """Índice idcta -> agregados de recaudos (una consulta por proyecto)."""
    index = defaultdict(_empty_recaudo_bucket)
    if not adj_ids:
        return index

    rows = (
        Recaudos.objects.using(proyecto)
        .filter(idadjudicacion__in=adj_ids)
        .values('idcta', 'capital', 'interescte', 'interesmora', 'fecha')
    )
    for row in rows:
        idcta = row['idcta']
        if not idcta:
            continue
        bucket = index[idcta]
        cap = row['capital'] or Decimal('0')
        icte = row['interescte'] or Decimal('0')
        imora = row['interesmora'] or Decimal('0')
        fecha = row['fecha']
        bucket['capital'] += cap
        bucket['interes'] += icte
        bucket['mora'] += imora
        if cap > 0 or icte > 0:
            if fecha and (bucket['max_fecha_cap_int'] is None or fecha > bucket['max_fecha_cap_int']):
                bucket['max_fecha_cap_int'] = fecha
        if cap == 0 and icte == 0 and imora > 0:
            if fecha and (bucket['max_fecha_solo_mora'] is None or fecha > bucket['max_fecha_solo_mora']):
                bucket['max_fecha_solo_mora'] = fecha
            bucket['moras_por_fecha'].append((fecha, imora))
    return index


def _presupuesto_buckets(cuotas, rec_by_idcta: dict, today: datetime.date) -> dict:
    """Misma lógica que Adjudicacion.presupuesto() para una adjudicación."""
    dias_mora = 0
    por_vencer = Decimal('0')
    lt30 = lt60 = lt90 = lt120 = gt120 = Decimal('0')

    for q in cuotas:
        rec = rec_by_idcta.get(q.idcta) or _empty_recaudo_bucket()
        pagado = {'capital': rec['capital'], 'interes': rec['interes'], 'mora': rec['mora']}
        pendiente = _pendiente_cuota(q, pagado)
        total_pend = pendiente['total']
        if total_pend <= 0:
            continue
        mora = _mora_cuota(q, pagado, rec, dia_pago=today)
        m = mora['dias_totales']
        dias_mora = m if m > dias_mora else dias_mora
        if m <= 0:
            por_vencer += total_pend
        elif 0 < m <= 30:
            lt30 += total_pend
        elif 30 < m <= 60:
            lt60 += total_pend
        elif 60 < m <= 90:
            lt90 += total_pend
        elif 90 < m <= 120:
            lt120 += total_pend
        elif 120 < m:
            gt120 += total_pend

    total_pendiente = por_vencer + lt30 + lt60 + lt90 + lt120 + gt120
    return {
        'dias_mora': dias_mora,
        'por_vencer': por_vencer,
        'lt30': lt30,
        'lt60': lt60,
        'lt90': lt90,
        'lt120': lt120,
        'gt120': gt120,
        'total_pendiente': total_pendiente,
    }


def edades_cartera_snapshot(proyecto: str, *, today: datetime.date | None = None):
    """
    Devuelve (lista de filas para el template, fecha de consulta).

    Cada fila es un dict con las claves que espera edades_cartera.html.
    """
    today = today or datetime.date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_month = datetime.date(today.year, today.month, last_day)

    adj_ids = list(
        Adjudicacion.objects.using(proyecto)
        .filter(estado='Aprobado')
        .exclude(origenventa='Canje')
        .values_list('pk', flat=True)
    )
    if not adj_ids:
        return [], today

    rec_by_idcta = _load_recaudos_by_idcta(proyecto, adj_ids)

    plan_by_adj = defaultdict(list)
    for q in PlanPagos.objects.using(proyecto).filter(adj__in=adj_ids, fecha__lte=end_month):
        plan_by_adj[q.adj].append(q)

    info_map = {
        row['IdAdjudicacion']: row
        for row in Vista_Adjudicacion.objects.using(proyecto)
        .filter(IdAdjudicacion__in=adj_ids)
        .values('IdAdjudicacion', 'Nombre', 'tipo_cartera')
    }
    gestor_map = {
        row['idadjudicacion']: (row.get('gestorasignado') or 'Sin Gestor')
        for row in InfoCartera.objects.using(proyecto)
        .filter(idadjudicacion__in=adj_ids)
        .values('idadjudicacion', 'gestorasignado')
    }
    ultimo_pago_map = {
        row['idadjudicacion']: row['ultimo_pago']
        for row in Recaudos.objects.using(proyecto)
        .filter(idadjudicacion__in=adj_ids)
        .values('idadjudicacion')
        .annotate(ultimo_pago=Max('fecha'))
    }

    adjudicaciones = []
    for adj_id in adj_ids:
        p = _presupuesto_buckets(plan_by_adj.get(adj_id, []), rec_by_idcta, today)
        info = info_map.get(adj_id) or {}
        adjudicaciones.append({
            'adj': adj_id,
            'cliente': (info.get('Nombre') or ''),
            'cartera': (info.get('tipo_cartera') or ''),
            'gestor': gestor_map.get(adj_id, 'Sin Gestor'),
            'dias_mora': p['dias_mora'],
            'ultimo_pago': ultimo_pago_map.get(adj_id),
            'por_vencer': p['por_vencer'],
            'lt30': p['lt30'],
            'lt60': p['lt60'],
            'lt90': p['lt90'],
            'lt120': p['lt120'],
            'gt120': p['gt120'],
            'total_pendiente': p['total_pendiente'],
        })

    return adjudicaciones, today
