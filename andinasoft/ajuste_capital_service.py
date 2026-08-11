"""Ajuste del valor del contrato al capital ya pagado (descuento / pago total)."""
from decimal import Decimal

from django.db.models import Sum

from andinasoft.models import bk_bfchangeplan, bk_planpagos, bk_recaudodetallado, proyectos
from andinasoft.shared_models import Adjudicacion, PlanPagos, Recaudos, saldos_adj


def capital_pagado_adj(proyecto, adj):
    """Suma de capital recaudado de la adjudicacion (excluye SF)."""
    total = (
        Recaudos.objects.using(proyecto)
        .filter(idadjudicacion=adj)
        .exclude(idcta__startswith='SF')
        .aggregate(total=Sum('capital'))
        .get('total')
    )
    return total or Decimal('0')


def saldo_capital_adj(proyecto, adj):
    """Saldo de capital pendiente segun la vista de saldos."""
    total = (
        saldos_adj.objects.using(proyecto)
        .filter(adj=adj)
        .exclude(tipocta='SF')
        .exclude(idcta__startswith='SF')
        .aggregate(total=Sum('saldocapital'))
        .get('total')
    )
    return total or Decimal('0')


def backup_plan_y_recaudos(proyecto, adj, user):
    """Crea backup del plan de pagos y del detalle de recaudos."""
    obj_proyecto = proyectos.objects.get(pk=proyecto)
    obj_bk = bk_bfchangeplan.objects.create(
        proyecto=obj_proyecto,
        usuario_bk=user,
        adj=adj,
    )
    for i in PlanPagos.objects.using(proyecto).filter(adj=adj):
        bk_planpagos.objects.create(
            id_bk=obj_bk,
            proyecto=obj_proyecto,
            idcta=i.idcta,
            tipocta=i.tipocta,
            nrocta=i.nrocta,
            adj=i.adj,
            capital=i.capital,
            intcte=i.intcte,
            cuota=i.cuota,
            fecha=i.fecha,
        )
    for i in Recaudos.objects.using(proyecto).filter(idadjudicacion=adj):
        bk_recaudodetallado.objects.create(
            id_bk=obj_bk,
            proyecto=obj_proyecto,
            recibo=i.recibo,
            fecha=i.fecha,
            idcta=i.idcta,
            idadjudicacion=i.idadjudicacion,
            capital=i.capital,
            interescte=i.interescte,
            interesmora=i.interesmora,
            moralqd=i.moralqd,
            fechaoperacion=i.fechaoperacion,
            usuario=i.usuario,
            estado=i.estado,
        )
    return obj_bk


def recortar_plan_a_capital_pagado(proyecto, adj):
    """
    Ajusta el plan al capital ya recaudado:
    - cuota con abono parcial -> deja capital/interes/cuota = lo pagado
    - cuota sin abono -> la elimina
    """
    saldos = (
        saldos_adj.objects.using(proyecto)
        .filter(adj=adj, saldocuota__gt=0)
        .exclude(tipocta='SF')
        .exclude(idcta__startswith='SF')
    )

    for saldo in saldos:
        rcdo_cap = saldo.rcdocapital or Decimal('0')
        rcdo_int = saldo.rcdointcte or Decimal('0')
        if rcdo_cap > 0 or rcdo_int > 0:
            try:
                cta = PlanPagos.objects.using(proyecto).get(idcta=saldo.idcta)
            except PlanPagos.DoesNotExist:
                continue
            cta.capital = rcdo_cap
            cta.intcte = rcdo_int
            cta.cuota = rcdo_cap + rcdo_int
            cta.save()
        else:
            PlanPagos.objects.using(proyecto).filter(idcta=saldo.idcta).delete()


def aplicar_ajuste_valor_a_capital(proyecto, adj, user):
    """
    Baja el valor del contrato al capital pagado, recorta el plan y marca Pagado.
    No crea recibos. Retorna dict con resumen o lanza ValueError.
    """
    obj_adj = Adjudicacion.objects.using(proyecto).get(pk=adj)

    if obj_adj.estado == 'Desistido':
        raise ValueError('Este contrato esta desistido; no se puede ajustar.')
    if obj_adj.estado == 'Pagado':
        raise ValueError('Este contrato ya esta marcado como Pagado.')

    saldo = saldo_capital_adj(proyecto, adj)
    if saldo <= 0:
        raise ValueError('No hay saldo de capital pendiente para ajustar.')

    capital = capital_pagado_adj(proyecto, adj)
    if capital <= 0:
        raise ValueError('No hay capital pagado; no se puede ajustar el valor.')

    valor_anterior = obj_adj.valor or Decimal('0')
    descuento = valor_anterior - capital

    backup_plan_y_recaudos(proyecto, adj, user)
    recortar_plan_a_capital_pagado(proyecto, adj)

    obj_adj.valor = capital
    obj_adj.estado = 'Pagado'
    obj_adj.save()

    return {
        'valor_anterior': valor_anterior,
        'capital_pagado': capital,
        'descuento': descuento,
        'valor_nuevo': capital,
    }
