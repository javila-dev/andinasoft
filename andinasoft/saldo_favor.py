"""Saldo a favor interno (tipocta SF) al liquidar un credito con sobrante."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.db.models import Max, Q, Sum

from andinasoft.shared_models import PlanPagos, Recaudos, saldos_adj

TIPOCTA_SF = 'SF'
IDCTA_SF_PREFIX = 'SF'


def is_sf_idcta(idcta) -> bool:
    return str(idcta or '').startswith(IDCTA_SF_PREFIX)


def exclude_sf_filter():
    """Q para excluir cuotas/recaudos de saldo a favor."""
    return ~Q(idcta__startswith=IDCTA_SF_PREFIX) & ~Q(tipocta=TIPOCTA_SF)


def exclude_sf_recaudos_filter():
    return ~Q(idcta__startswith=IDCTA_SF_PREFIX)


def plan_tiene_deuda_pendiente(proyecto: str, adj: str) -> bool:
    """True si quedan cuotas de deuda (no SF) con saldo > 0."""
    qs = saldos_adj.objects.using(proyecto).filter(adj=adj, saldocuota__gt=0)
    qs = qs.exclude(tipocta=TIPOCTA_SF).exclude(idcta__startswith=IDCTA_SF_PREFIX)
    return qs.exists()


def _next_sf_nro_idcta(proyecto: str, adj: str) -> tuple[int, str]:
    existing = PlanPagos.objects.using(proyecto).filter(adj=adj, tipocta=TIPOCTA_SF)
    nro = existing.aggregate(Max('nrocta'))['nrocta__max'] or 0
    nro = int(nro) + 1
    idcta = f'{IDCTA_SF_PREFIX}{nro}{adj}'
    if len(idcta) > 20:
        # IdCta max 20: conservar prefijo + nro y truncar adj
        prefix = f'{IDCTA_SF_PREFIX}{nro}'
        idcta = (prefix + adj)[:20]
    return nro, idcta


def registrar_saldo_favor(
    *,
    proyecto: str,
    adj: str,
    nro_recibo: str,
    fecha,
    remanente,
    usuario,
    ledger_user=None,
) -> dict | None:
    """
    Crea PlanPagos SF + Recaudos por el remanente para cuadrar con Recaudos_general.
    Retorna info del movimiento o None si remanente <= 0.
    """
    remanente = Decimal(str(remanente or 0))
    if remanente <= 0:
        return None

    nro, idcta = _next_sf_nro_idcta(proyecto, adj)
    if isinstance(fecha, datetime.datetime):
        fecha = fecha.date()

    PlanPagos.objects.using(proyecto).create(
        adj=adj,
        fecha=fecha,
        tipocta=TIPOCTA_SF,
        idcta=idcta,
        capital=remanente,
        cuota=remanente,
        nrocta=nro,
        intcte=0,
    )
    Recaudos.objects.using(proyecto).create(
        recibo=nro_recibo,
        fecha=fecha,
        idcta=idcta,
        idadjudicacion=adj,
        capital=remanente,
        interescte=0,
        interesmora=0,
        moralqd=0,
        fechaoperacion=datetime.datetime.today(),
        usuario=usuario,
        estado='Aprobado',
    )

    try:
        from finance.models import SaldoFavorCliente

        usuario_label = None
        if ledger_user is not None:
            usuario_label = getattr(ledger_user, 'username', None) or str(ledger_user)
        SaldoFavorCliente.objects.create(
            proyecto=proyecto,
            adjudicacion=adj,
            recibo=nro_recibo,
            valor=int(remanente),
            usuario=usuario_label,
            nota='Saldo a favor por mayor valor pagado al liquidar el credito',
        )
    except Exception:
        # Ledger es auxiliar; no debe tumbar el recibo si falla
        pass

    return {
        'idcta': idcta,
        'valor': remanente,
        'nrocta': nro,
    }


def remanente_recibo(proyecto: str, nro_recibo: str, valor_recibo) -> Decimal:
    """valor_recibo - suma de detalle (incluye SF ya registrados)."""
    det = (
        Recaudos.objects.using(proyecto)
        .filter(recibo=nro_recibo)
        .aggregate(
            cap=Sum('capital'),
            icte=Sum('interescte'),
            imora=Sum('interesmora'),
        )
    )
    aplicado = (
        Decimal(str(det.get('cap') or 0))
        + Decimal(str(det.get('icte') or 0))
        + Decimal(str(det.get('imora') or 0))
    )
    return Decimal(str(valor_recibo or 0)) - aplicado
