"""
Construcción optimizada del contexto para PDF de estado de cuenta.

Réplica la lógica de PlanPagos.pendiente() / mora() y los accesos del template
statement_of_account.html, con pocas consultas SQL por adjudicación.
"""
from __future__ import annotations

import calendar
import datetime
from collections import defaultdict
from decimal import Decimal
from types import SimpleNamespace

from dateutil import relativedelta
from django.db.models import Sum

from andinasoft.models import clientes
from andinasoft.shared_models import (
    Adjudicacion,
    PlanPagos,
    Recaudos,
    Vista_Adjudicacion,
    saldos_adj,
)

RECAUDADOR_POR_PROYECTO = {
    'Tesoro Escondido': 'STATUS COMERCIALIZADORA S.A.S. NIT: 901018375-4',
    'Vegas de Venecia': 'STATUS COMERCIALIZADORA S.A.S. NIT: 901018375-4',
    'Perla del Mar': 'ANDINA CONCEPTOS INMOBILIARIOS S.A.S. NIT: 900993044-9',
    'Sandville Beach': 'ANDINA CONCEPTOS INMOBILIARIOS S.A.S. NIT: 900993044-9',
    'Carmelo Reservado': 'ANDINA CONCEPTOS INMOBILIARIOS S.A.S. NIT: 900993044-9',
}

_LOGO_PATHS = {
    'Sandville Beach': ('img/sandville_beach.png', 'img/conceptos_inmob_beach.png'),
    'Tesoro Escondido': ('img/logo-Tesoro-Escondido.png', 'img/conceptos_inmob_bugambilias.png'),
    'Perla del Mar': ('img/logo-perla-mar-nuevo.png', 'img/conceptos_inmobiliarios_suenos_extraord.png'),
    'Vegas de Venecia': ('img/logo_vegas_de_venecia.png', 'img/conceptos_inmob_vegas_de_venecia.png'),
    'Carmelo Reservado': ('img/logo_carmelo_reservado.png', 'img/conceptos_inmob_carmelo.png'),
}

_TASA_MV = Decimal('2')
_DIAS_GRACIA = 15


def _d(x) -> Decimal:
    if x is None:
        return Decimal('0')
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _load_recaudos_index(proyecto: str, adj: str) -> dict:
    """Agregados de recaudos por idcta en una sola consulta."""
    index = defaultdict(
        lambda: {
            'capital': Decimal('0'),
            'interes': Decimal('0'),
            'mora': Decimal('0'),
            'max_fecha_cap_int': None,
            'max_fecha_solo_mora': None,
            'moras_por_fecha': [],
        }
    )
    rows = (
        Recaudos.objects.using(proyecto)
        .filter(idadjudicacion=adj)
        .values('idcta', 'capital', 'interescte', 'interesmora', 'fecha')
    )
    for row in rows:
        idcta = row['idcta']
        if not idcta:
            continue
        bucket = index[idcta]
        cap = _d(row['capital'])
        icte = _d(row['interescte'])
        imora = _d(row['interesmora'])
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


def _pendiente_cuota(cuota: PlanPagos, pagado: dict) -> dict:
    pendiente_capital = _d(cuota.capital) - pagado['capital']
    pendiente_interes = _d(cuota.intcte) - pagado['interes']
    return {
        'capital': pendiente_capital,
        'interes': pendiente_interes,
        'total': pendiente_capital + pendiente_interes,
    }


def _mora_cuota(cuota: PlanPagos, pagado: dict, rec: dict, dia_pago=None) -> dict:
    """Misma lógica que PlanPagos.mora() usando datos precargados."""
    if dia_pago is None:
        dia_pago = datetime.date.today()
    if isinstance(dia_pago, datetime.datetime):
        dia_pago = dia_pago.date()

    pendiente = _pendiente_cuota(cuota, pagado)
    total_pendiente = pendiente['total']

    ultima_fecha_pago = rec.get('max_fecha_cap_int')
    if ultima_fecha_pago is None:
        ultima_fecha_pago = cuota.fecha

    ultimo_rcdo_solo_mora = rec.get('max_fecha_solo_mora')
    fecha_con_gracia = cuota.fecha + relativedelta.relativedelta(days=_DIAS_GRACIA)
    dias_totales = 0
    if cuota.fecha and cuota.fecha < dia_pago:
        dias_totales = (dia_pago - cuota.fecha).days

    if fecha_con_gracia >= dia_pago or total_pendiente <= 0:
        dias = 0
        valor = 0
    elif ultimo_rcdo_solo_mora and ultimo_rcdo_solo_mora > ultima_fecha_pago:
        dias = (dia_pago - ultima_fecha_pago).days
        total_mora = total_pendiente * dias * (_TASA_MV / 30) / 100
        mora_pagada = Decimal('0')
        for f, m in rec.get('moras_por_fecha', []):
            if ultima_fecha_pago <= f <= ultimo_rcdo_solo_mora:
                mora_pagada += _d(m)
        valor = int(total_mora - mora_pagada)
    else:
        if ultima_fecha_pago < cuota.fecha:
            ultima_fecha_pago = cuota.fecha
        dias = (dia_pago - ultima_fecha_pago).days
        if dias < 0:
            dias = 0
        valor = total_pendiente * dias * (_TASA_MV / 30) / 100
        valor = int(valor)

    dias_reales = (datetime.date.today() - cuota.fecha).days if cuota.fecha else 0
    return {
        'dias_totales': dias_totales,
        'dias': dias,
        'dias_reales': dias_reales,
        'valor': valor,
    }


def _is_pending_cuota(cuota: PlanPagos, pagado: dict) -> bool:
    capital_pagado = pagado['capital']
    return _d(cuota.capital) != capital_pagado


def _titulares_for_adj(adj: Adjudicacion) -> dict:
    try:
        empty = clientes.objects.get(pk='')
    except Exception:
        empty = SimpleNamespace(
            pk='',
            nombrecompleto='',
            domicilio='',
            ciudad='',
            celular1='',
            telefono1='',
            email='',
        )
    ids = [x for x in (adj.idtercero1, adj.idtercero2, adj.idtercero3, adj.idtercero4) if x not in (None, '')]
    found = {c.pk: c for c in clientes.objects.filter(pk__in=ids)} if ids else {}
    return {
        'titular_1': found.get(adj.idtercero1, empty),
        'titular_2': found.get(adj.idtercero2, empty),
        'titular_3': found.get(adj.idtercero3, empty),
        'titular_4': found.get(adj.idtercero4, empty),
    }


def _recaudo_detallado_snapshot(proyecto: str, adj: Adjudicacion, on_date=None) -> SimpleNamespace:
    if on_date is None:
        on_date = datetime.date.today()
    agg = (
        Recaudos.objects.using(proyecto)
        .filter(idadjudicacion=adj.pk)
        .aggregate(
            cap=Sum('capital'),
            intcte=Sum('interescte'),
            intmora=Sum('interesmora'),
        )
    )
    cap = agg.get('cap') or 0
    intcte = agg.get('intcte') or 0
    intmora = agg.get('intmora') or 0
    return SimpleNamespace(
        capital=cap,
        interescte=intcte,
        interesmora=intmora,
        total=cap + intcte + intmora,
        saldo_cap=_d(adj.valor) - _d(cap),
        date=on_date,
    )


def _saldos_por_cartera_snapshot(proyecto: str, adj_pk: str) -> SimpleNamespace:
    rows = list(
        saldos_adj.objects.using(proyecto).filter(adj=adj_pk).values(
            'tipocta', 'rcdocapital', 'saldocapital', 'saldointcte', 'saldocuota', 'fecha', 'capital'
        )
    )
    today = datetime.date.today()
    abonado_ci = saldo_ci = abonado_fn = saldo_fn = Decimal('0')
    cap_vencido = int_vencido = Decimal('0')
    total_valor_futuro = Decimal('0')

    for r in rows:
        tipocta = r.get('tipocta')
        rcdo = _d(r.get('rcdocapital'))
        saldo_cap = _d(r.get('saldocapital'))
        fecha = r.get('fecha')
        if tipocta == 'CI':
            abonado_ci += rcdo
            saldo_ci += saldo_cap
        else:
            abonado_fn += rcdo
            saldo_fn += saldo_cap
        if fecha and fecha <= today:
            cap_vencido += saldo_cap
            int_vencido += _d(r.get('saldointcte'))
        elif fecha and fecha > today:
            total_valor_futuro += _d(r.get('capital'))

    total_pago_hoy = cap_vencido + int_vencido + total_valor_futuro
    return SimpleNamespace(
        abonado_ci=abonado_ci,
        saldo_ci=saldo_ci,
        abonado_fn=abonado_fn,
        saldo_fn=saldo_fn,
        pago_hoy=SimpleNamespace(
            cap_vencido=cap_vencido,
            int_vencido=int_vencido,
            cap_futuro=total_valor_futuro,
            total_pago_hoy=total_pago_hoy,
        ),
    )


def _tiempos_pagos_snapshot(plan: list, fechacontrato) -> SimpleNamespace:
    ci = [q for q in plan if q.tipocta == 'CI']
    fn = [q for q in plan if q.tipocta != 'CI']
    numero_ctas_ci = len(ci)
    numero_ctas_fn = len(fn)
    months_to_pay_ci = 0
    months_to_pay_fn = 0
    if numero_ctas_ci > 0 and fechacontrato:
        fechas_ci = [q.fecha for q in ci if q.fecha]
        if fechas_ci:
            max_date_ci = max(fechas_ci)
            min_date_ci = fechacontrato
            months_to_pay_ci = (max_date_ci.year - min_date_ci.year) * 12 + (
                max_date_ci.month - min_date_ci.month
            )
    if numero_ctas_fn > 0:
        fechas_fn = [q.fecha for q in fn if q.fecha]
        if fechas_fn:
            min_date_fn = min(fechas_fn)
            max_date_fn = max(fechas_fn)
            months_to_pay_fn = (max_date_fn.year - min_date_fn.year) * 12 + (
                max_date_fn.month - min_date_fn.month + 1
            )
    return SimpleNamespace(
        numero_ctas_ci=numero_ctas_ci,
        months_to_pay_ci=months_to_pay_ci,
        numero_ctas_fn=numero_ctas_fn,
        months_to_pay_fn=months_to_pay_fn,
    )


def _wrap_adj_for_template(adj: Adjudicacion, proyecto: str) -> SimpleNamespace:
    """Objeto adj con propiedades precalculadas que usa statement_of_account.html."""
    plan = list(PlanPagos.objects.using(proyecto).filter(adj=adj.pk))
    try:
        extra_info = Vista_Adjudicacion.objects.using(proyecto).get(IdAdjudicacion=adj.pk)
    except Vista_Adjudicacion.DoesNotExist:
        extra_info = SimpleNamespace(cta_inicial=Decimal('0'), saldo=Decimal('0'))

    logo = _LOGO_PATHS.get(proyecto, (None, None))
    return SimpleNamespace(
        pk=adj.pk,
        idinmueble=adj.idinmueble,
        valor=adj.valor,
        fechacontrato=adj.fechacontrato,
        titulares=_titulares_for_adj(adj),
        recaudo_detallado=_recaudo_detallado_snapshot(proyecto, adj),
        saldos_por_cartera=_saldos_por_cartera_snapshot(proyecto, adj.pk),
        extra_info=extra_info,
        tiempos_pagos=_tiempos_pagos_snapshot(plan, adj.fechacontrato),
        logo=logo,
    )


def build_estado_cuenta_context(
    proyecto: str,
    adj_id: str,
    user=None,
    *,
    today: datetime.date | None = None,
):
    """
    Contexto listo para pdf_gen(statement_of_account.html).

    Returns:
        (context_dict, error_message)
    """
    if today is None:
        today = datetime.date.today()
    next_30_days = today + datetime.timedelta(days=30)

    try:
        obj_adj = Adjudicacion.objects.using(proyecto).get(pk=adj_id)
    except Adjudicacion.DoesNotExist:
        return None, f'Adjudicación {adj_id} no encontrada en {proyecto}.'

    rec_index = _load_recaudos_index(proyecto, adj_id)
    empty_rec = {
        'capital': Decimal('0'),
        'interes': Decimal('0'),
        'mora': Decimal('0'),
        'max_fecha_cap_int': None,
        'max_fecha_solo_mora': None,
        'moras_por_fecha': [],
    }

    cuotas_historicas = list(
        PlanPagos.objects.using(proyecto).filter(adj=adj_id, fecha__lte=today).order_by('fecha')
    )
    cuotas_futuras_qs = list(
        PlanPagos.objects.using(proyecto)
        .filter(adj=adj_id, fecha__gt=today, fecha__lte=next_30_days)
        .order_by('fecha')
    )

    cuotas_vencidas = []
    total_cuotas_vencidas = {'valor': 0, 'intereses_mora': 0, 'total': 0}

    for q in cuotas_historicas:
        rec = rec_index.get(q.idcta, empty_rec)
        pagado = {
            'capital': rec['capital'],
            'interes': rec['interes'],
            'mora': rec['mora'],
            'total': rec['capital'] + rec['interes'] + rec['mora'],
        }
        pendiente = _pendiente_cuota(q, pagado)
        if pendiente['total'] > 0:
            mora = _mora_cuota(q, pagado, rec)
            cuotas_vencidas.append(
                SimpleNamespace(
                    fecha=q.fecha,
                    idcta=q.pk.split('ADJ')[0] if q.pk else '',
                    pendiente=pendiente,
                    mora=mora,
                )
            )
            total_cuotas_vencidas['valor'] += float(pendiente['total'])
            total_cuotas_vencidas['intereses_mora'] += mora.get('valor', 0)
            total_cuotas_vencidas['total'] += float(pendiente['total']) + mora.get('valor', 0)

    cuotas_futuras = []
    for q in cuotas_futuras_qs:
        rec = rec_index.get(q.idcta, empty_rec)
        pagado = {
            'capital': rec['capital'],
            'interes': rec['interes'],
            'mora': rec['mora'],
            'total': rec['capital'] + rec['interes'] + rec['mora'],
        }
        pendiente = _pendiente_cuota(q, pagado)
        cuotas_futuras.append(
            SimpleNamespace(
                fecha=q.fecha,
                pk=q.pk,
                cuota=q.cuota,
                is_pending=_is_pending_cuota(q, pagado),
                pendiente=pendiente,
            )
        )

    context = {
        'adj': _wrap_adj_for_template(obj_adj, proyecto),
        'cuotas_a_la_fecha': cuotas_vencidas,
        'cuotas_futuras': cuotas_futuras,
        'user': user,
        'now': datetime.datetime.now(),
        'totals': total_cuotas_vencidas,
        'recaudador': RECAUDADOR_POR_PROYECTO.get(proyecto),
    }
    return context, ''
