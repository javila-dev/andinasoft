"""Piezas comunes para convertir una venta nueva en adjudicacion (plan de pagos)."""
from dateutil.relativedelta import relativedelta

from andinasoft.shared_models import PlanPagos
from andinasoft.utilities import Utilidades

PERIODOS_CE = {
    'Mensual': 1,
    'Trimestral': 3,
    'Semestral': 6,
    'Anual': 12,
}


def _meses_periodo_ce(periodo):
    try:
        return PERIODOS_CE[periodo]
    except KeyError:
        return int(periodo)


def crear_plan_pagos(proyecto, venta, adj):
    """Crea en ``proyecto`` las cuotas CI, FN/CO y CE de ``venta`` para la adjudicacion ``adj`` (p. ej. 'ADJ123')."""
    plan = PlanPagos.objects.using(proyecto)

    # Cuota inicial: hasta 7 tramos de cuotas mensuales iguales, numeradas en secuencia.
    nro_ci = 1
    for tramo in range(1, 8):
        cantidad = getattr(venta, f'cant_ci{tramo}')
        if cantidad is None:
            continue
        fecha = getattr(venta, f'fecha_ci{tramo}')
        valor = getattr(venta, f'valor_ci{tramo}')
        for j in range(cantidad):
            plan.create(idcta=f'CI{nro_ci}{adj}', tipocta='CI', nrocta=nro_ci, adj=adj,
                        capital=valor, intcte=0, cuota=valor,
                        fecha=fecha + relativedelta(months=j))
            nro_ci += 1

    # Saldo
    tasa = venta.tasa
    capital_fn = 0
    cantidad = venta.nro_cuotas_fn
    if cantidad is not None:
        fecha = venta.inicio_fn
        valor = venta.valor_ctas_fn
        tipocta = 'CO' if venta.forma_saldo == 'CONTADO' else 'FN'
        if venta.forma_saldo == 'Regular':
            valor_presente = venta.saldo
        else:
            valor_presente = Utilidades().CalcularVP(valor, tasa, cantidad)
        capital_fn = valor_presente
        for i in range(cantidad):
            interes = round(tasa * valor_presente, 0)
            capital = valor - interes
            if i == cantidad - 1:
                capital = valor_presente
                valor = capital + interes
            valor_presente -= capital
            plan.create(idcta=f'{tipocta}{i + 1}{adj}', tipocta=tipocta, nrocta=i + 1, adj=adj,
                        capital=capital, intcte=interes, cuota=valor,
                        fecha=fecha + relativedelta(months=i))

    # Extraordinarias
    cantidad = venta.nro_cuotas_ce
    if cantidad is not None:
        fecha = venta.inicio_ce
        valor = venta.valor_ctas_ce
        meses = _meses_periodo_ce(venta.period_ce)
        valor_presente = venta.saldo - capital_fn
        for i in range(cantidad):
            interes = round(tasa * meses * valor_presente, 0)
            capital = valor - interes
            if i == cantidad - 1:
                capital = valor_presente
                valor = capital + interes
            valor_presente -= capital
            plan.create(idcta=f'CE{i + 1}{adj}', tipocta='CE', nrocta=i + 1, adj=adj,
                        capital=capital, intcte=interes, cuota=valor,
                        fecha=fecha + relativedelta(months=i * meses))


def total_cuota_inicial(venta):
    """Suma de las cuotas CI pactadas en la venta (lo que el plan de pagos generara como CI)."""
    total = 0
    for tramo in range(1, 8):
        cantidad = getattr(venta, f'cant_ci{tramo}')
        valor = getattr(venta, f'valor_ci{tramo}')
        if cantidad and valor:
            total += cantidad * valor
    return total
