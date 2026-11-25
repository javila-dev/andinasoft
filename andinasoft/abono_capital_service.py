"""Abono a capital: paga lo vencido, crea la cuota CO y recalcula el plan.

Lo usan el recibo nuevo (`_guardar_recaudo`) y la reaplicación de recaudos.

Reglas que mantiene:
- El capital total del plan no cambia: lo que entra como cuota CO sale de las cuotas
  futuras. El plan conserva su propio total aunque no coincida con
  `adjudicacion.valor` (hay contratos con diferencias de redondeo o de negociación);
  en ese caso se avisa pero no se toca la diferencia.
- La cuota fija se mantiene y el plazo se acorta; las cuotas que sobran se eliminan.
- Lo ya pagado en una cuota futura (anticipos) se respeta: esa cuota nunca queda con
  capital o interés por debajo de lo recaudado.
- El abono nunca supera el capital pendiente; el excedente se devuelve para que el
  llamador lo registre como saldo a favor.

`plan_pagos` es MyISAM: `transaction.atomic` revierte los recaudos (InnoDB) pero no el
plan. Si algo falla, el plan se restaura desde la foto tomada al inicio, después de
salir del bloque atómico.
"""
import datetime
import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Sum

from andinasoft.ajuste_capital_service import backup_plan_y_recaudos
from andinasoft.shared_models import Adjudicacion, PlanPagos, Recaudos, saldos_adj, usuario_corto

logger = logging.getLogger(__name__)

TOLERANCIA = Decimal('1')  # pesos, por redondeos
CERO = Decimal('0')


class AbonoCapitalError(Exception):
    """El abono no se aplicó; el plan y los recaudos quedaron como estaban."""

    def __init__(self, mensaje, errores=None):
        super().__init__(mensaje)
        self.errores = errores or []


def _d(valor):
    return Decimal(str(valor or 0))


def _sin_sf(qs):
    return qs.exclude(tipocta='SF').exclude(idcta__startswith='SF')


def _a_fecha(valor):
    if isinstance(valor, datetime.datetime):
        return valor.date()
    return valor


# ---------------------------------------------------------------------------
# Cálculos puros (sin BD)
# ---------------------------------------------------------------------------

def distribuir_en_vencidas(cuotas, valor):
    """Reparte `valor` en las cuotas vencidas: mora, luego interés, luego capital.

    `cuotas`: dicts con idcta, saldocapital, saldointcte, mora (ya con condonación).
    Retorna (lineas, sobrante); cada línea trae capital/interes/mora pagados.
    """
    disponible = _d(valor)
    lineas = []
    for cuota in cuotas:
        if disponible <= 0:
            break
        pagos = {}
        for campo, pendiente in (('mora', cuota['mora']),
                                 ('interes', cuota['saldointcte']),
                                 ('capital', cuota['saldocapital'])):
            pendiente = max(_d(pendiente), CERO)
            pagado = min(disponible, pendiente)
            pagos[campo] = pagado
            disponible -= pagado
        if pagos['mora'] > 0 or pagos['interes'] > 0 or pagos['capital'] > 0:
            lineas.append({'idcta': cuota['idcta'], **pagos})
    return lineas, disponible


def recalcular_cuotas(cuotas, pendiente, tasa):
    """Redistribuye `pendiente` (capital que queda tras el abono) en las cuotas vivas.

    `cuotas`: dicts ordenados por fecha con idcta, cuota, intcte (originales) y
    rcdocapital, rcdointcte (lo ya recaudado en cada una).

    Amortización con cuota fija: el interés de cada cuota se calcula sobre el capital
    que se debía al empezar ese periodo, que incluye lo que ya se anticipó a esa cuota.
    Retorna (cambios, sobrante): cambios = [('update', idcta, capital, intcte, cuota)
    | ('delete', idcta)]. `sobrante` > 0 significa que las cuotas no alcanzaron.
    """
    tasa = _d(tasa)
    restante = _d(pendiente)
    cambios = []
    for cta in cuotas:
        pagado_cap = _d(cta['rcdocapital'])
        pagado_int = _d(cta['rcdointcte'])

        if restante <= 0:
            if pagado_cap > 0 or pagado_int > 0:
                # Se deja la cuota con lo que ya se pagó; no se borra un recaudo.
                cambios.append(('update', cta['idcta'], pagado_cap, pagado_int, pagado_cap + pagado_int))
            else:
                cambios.append(('delete', cta['idcta']))
            continue

        if _d(cta['intcte']) > 0:
            interes = Decimal(round((restante + pagado_cap) * tasa))
        else:
            interes = CERO
        interes = max(interes, pagado_int)

        capital = _d(cta['cuota']) - interes
        capital_nuevo = capital - pagado_cap  # lo que esta cuota aporta a `restante`

        if capital_nuevo >= restante:
            capital = pagado_cap + restante
            cambios.append(('update', cta['idcta'], capital, interes, capital + interes))
            restante = CERO
        elif capital_nuevo <= 0:
            raise AbonoCapitalError(
                f'La cuota {cta["idcta"]} no alcanza a cubrir su interés con el nuevo saldo; '
                'el plan no se puede recalcular automáticamente.'
            )
        else:
            cambios.append(('update', cta['idcta'], capital, interes, _d(cta['cuota'])))
            restante -= capital_nuevo
    return cambios, restante


# ---------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------

def validar_integridad_plan(proyecto, adj, capital_plan_antes=None):
    """Valida el plan después del abono. Retorna (es_valido, errores)."""
    errores = []

    cap_plan = _sin_sf(PlanPagos.objects.using(proyecto).filter(adj=adj)).aggregate(
        s=Sum('capital'))['s'] or CERO
    cap_saldos = _sin_sf(saldos_adj.objects.using(proyecto).filter(adj=adj)).aggregate(
        s=Sum('capital'))['s'] or CERO
    if abs(cap_plan - cap_saldos) > TOLERANCIA:
        errores.append({
            'code': 'CAPITAL_PLAN_MISMATCH',
            'message': f'Capital del plan ({cap_plan:,.0f}) no coincide con saldos ({cap_saldos:,.0f}).',
            'severity': 'critical',
        })

    if capital_plan_antes is not None and abs(cap_plan - _d(capital_plan_antes)) > TOLERANCIA:
        errores.append({
            'code': 'CAPITAL_TOTAL_CAMBIO',
            'message': (f'El capital total del plan cambió de {_d(capital_plan_antes):,.0f} '
                        f'a {cap_plan:,.0f}.'),
            'severity': 'critical',
        })

    cap_recaudado = Recaudos.objects.using(proyecto).filter(
        idadjudicacion=adj, estado='Aprobado'
    ).exclude(idcta__startswith='SF').aggregate(s=Sum('capital'))['s'] or CERO
    cap_rcdo_saldos = _sin_sf(saldos_adj.objects.using(proyecto).filter(adj=adj)).aggregate(
        s=Sum('rcdocapital'))['s'] or CERO
    if abs(cap_recaudado - cap_rcdo_saldos) > TOLERANCIA:
        errores.append({
            'code': 'CAPITAL_RECAUDADO_MISMATCH',
            'message': (f'Capital recaudado ({cap_recaudado:,.0f}) no coincide con lo aplicado '
                        f'a cuotas del plan ({cap_rcdo_saldos:,.0f}); hay recaudos sin cuota.'),
            'severity': 'critical',
        })

    descuadradas = [
        c.idcta for c in _sin_sf(PlanPagos.objects.using(proyecto).filter(adj=adj))
        if abs(_d(c.capital) + _d(c.intcte) - _d(c.cuota)) > TOLERANCIA
    ]
    if descuadradas:
        errores.append({
            'code': 'CUOTAS_DESCUADRADAS',
            'message': f'{len(descuadradas)} cuotas descuadradas (capital + interés ≠ cuota): {", ".join(descuadradas[:5])}',
            'severity': 'critical',
        })

    negativas = list(_sin_sf(saldos_adj.objects.using(proyecto).filter(adj=adj)).filter(
        saldocapital__lt=-TOLERANCIA).values_list('idcta', flat=True)[:5])
    if negativas:
        errores.append({
            'code': 'SALDO_CAPITAL_NEGATIVO',
            'message': f'Cuotas con saldo de capital negativo: {", ".join(negativas)}',
            'severity': 'critical',
        })

    int_negativo = list(_sin_sf(saldos_adj.objects.using(proyecto).filter(adj=adj)).filter(
        saldointcte__lt=-TOLERANCIA).values_list('idcta', flat=True)[:5])
    if int_negativo:
        errores.append({
            'code': 'SALDO_INTERES_NEGATIVO',
            'message': f'Cuotas con saldo de interés negativo: {", ".join(int_negativo)}',
            'severity': 'critical',
        })

    return len(errores) == 0, errores


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

def _siguiente_idcta_co(proyecto, adj):
    nro = PlanPagos.objects.using(proyecto).filter(adj=adj, tipocta='CO').aggregate(
        m=Max('nrocta'))['m'] or 0
    nro += 1
    while PlanPagos.objects.using(proyecto).filter(idcta=f'CO{nro}{adj}').exists():
        nro += 1
    return nro, f'CO{nro}{adj}'


def _restaurar_plan(proyecto, adj, foto):
    PlanPagos.objects.using(proyecto).filter(adj=adj).delete()
    PlanPagos.objects.using(proyecto).bulk_create([PlanPagos(**fila) for fila in foto])


def aplicar_abono_capital(*, proyecto, adj, nro_recibo, fecha, fecha_corte, valor,
                          cobro_mora, user):
    """Aplica un recibo como abono a capital.

    - `fecha`: fecha de los recaudos y de la cuota CO (la del recibo).
    - `fecha_corte`: hasta qué fecha se consideran cuotas vencidas (la del pago).
    - `cobro_mora`: fracción de la mora a cobrar (1 = toda, 0 = nada).

    No crea Recaudos_general ni registra saldo a favor: eso es del llamador.
    Lanza AbonoCapitalError si no se pudo aplicar; en ese caso no queda nada aplicado.
    """
    fecha = _a_fecha(fecha)
    fecha_corte = _a_fecha(fecha_corte) or fecha
    valor = _d(valor)
    cobro_mora = _d(cobro_mora)
    usuario = usuario_corto(user)

    obj_adj = Adjudicacion.objects.using(proyecto).get(pk=adj)
    tasa = _d(obj_adj.tasafnc)

    foto = list(PlanPagos.objects.using(proyecto).filter(adj=adj).values())
    capital_plan_antes = sum(
        (_d(f['capital']) for f in foto
         if f['tipocta'] != 'SF' and not str(f['idcta']).startswith('SF')),
        CERO,
    )
    alertas = []
    if obj_adj.valor is not None and abs(capital_plan_antes - _d(obj_adj.valor)) > TOLERANCIA:
        alertas.append({
            'code': 'PLAN_DIFIERE_DEL_CONTRATO',
            'message': (f'El plan suma {capital_plan_antes:,.0f} y el contrato vale '
                        f'{_d(obj_adj.valor):,.0f}. El abono conserva el total del plan; '
                        'revisa la diferencia aparte.'),
            'severity': 'warning',
        })

    backup_plan_y_recaudos(proyecto, adj, user)

    resultado = None
    error = None
    try:
        with transaction.atomic(using=proyecto):
            resultado = _aplicar(proyecto, adj, nro_recibo, fecha, fecha_corte, valor,
                                 cobro_mora, usuario, tasa)
            es_valido, errores = validar_integridad_plan(proyecto, adj, capital_plan_antes)
            det = Recaudos.objects.using(proyecto).filter(
                recibo=nro_recibo, idadjudicacion=adj
            ).aggregate(c=Sum('capital'), i=Sum('interescte'), m=Sum('interesmora'))
            aplicado = _d(det['c']) + _d(det['i']) + _d(det['m'])
            if abs(aplicado + resultado['excedente'] - valor) > TOLERANCIA:
                errores.append({
                    'code': 'RECIBO_DESCUADRADO',
                    'message': (f'El detalle del recibo suma {aplicado:,.0f} más un excedente de '
                                f'{resultado["excedente"]:,.0f}, pero el recibo vale {valor:,.0f}.'),
                    'severity': 'critical',
                })
                es_valido = False
            if not es_valido:
                raise AbonoCapitalError('La validación del plan falló.', errores)
    except Exception as exc:  # noqa: BLE001 - se restaura el plan ante cualquier fallo
        error = exc

    if error is not None:
        try:
            _restaurar_plan(proyecto, adj, foto)
        except Exception:
            logger.exception('abono_capital: no se pudo restaurar plan_pagos de %s %s', proyecto, adj)
            raise AbonoCapitalError(
                f'El abono falló y NO se pudo restaurar el plan de pagos de {adj}. '
                'Hay una copia en el respaldo de planes (bk_planpagos); avisa a sistemas.',
                getattr(error, 'errores', []),
            ) from error
        if isinstance(error, AbonoCapitalError):
            raise error
        logger.exception('abono_capital: error inesperado en %s %s', proyecto, adj, exc_info=error)
        raise AbonoCapitalError(f'Error inesperado: {error}') from error

    resultado['alertas'] = alertas + resultado.get('alertas', [])
    return resultado


def _aplicar(proyecto, adj, nro_recibo, fecha, fecha_corte, valor, cobro_mora, usuario, tasa):
    hoy = datetime.datetime.today()

    def crear_recaudo(idcta, capital, interes, mora, moralqd):
        Recaudos.objects.using(proyecto).create(
            recibo=nro_recibo, fecha=fecha, idcta=idcta, idadjudicacion=adj,
            capital=capital, interescte=interes, interesmora=mora, moralqd=moralqd,
            fechaoperacion=hoy, usuario=usuario, estado='Aprobado',
        )

    # PASO 1: cuotas vencidas a la fecha de corte.
    vencidas = list(_sin_sf(saldos_adj.objects.using(proyecto).filter(
        adj=adj, saldocuota__gt=0, fecha__lte=fecha_corte)).order_by('fecha'))
    entrada = []
    for cuota in vencidas:
        mora = CERO
        if cobro_mora > 0:
            datos = PlanPagos.objects.using(proyecto).get(idcta=cuota.idcta).mora(dia_pago=fecha_corte)
            mora = Decimal(round(_d(datos.get('valor')) * cobro_mora))
        entrada.append({'idcta': cuota.idcta, 'saldocapital': cuota.saldocapital,
                        'saldointcte': cuota.saldointcte, 'mora': mora,
                        'saldomora': cuota.saldomora})
    lineas, disponible = distribuir_en_vencidas(entrada, valor)
    moralqd = {c['idcta']: c['saldomora'] for c in entrada}
    for linea in lineas:
        crear_recaudo(linea['idcta'], linea['capital'], linea['interes'], linea['mora'],
                      moralqd.get(linea['idcta']) or 0)

    tipos = {linea['idcta'][:2] for linea in lineas}
    resultado = {
        'lineas_vencidas': lineas,
        'es_ci': 'CI' in tipos, 'es_fn': 'FN' in tipos,
        'es_ce': 'CE' in tipos, 'es_co': 'CO' in tipos,
        'abono': CERO, 'excedente': CERO, 'idcta_co': None,
        'cuotas_eliminadas': [], 'cuotas_recalculadas': [],
    }
    if disponible <= 0:
        return resultado

    # PASO 2: abono a capital sobre las cuotas futuras.
    vivas = list(_sin_sf(saldos_adj.objects.using(proyecto).filter(
        adj=adj, saldocapital__gt=0, fecha__gt=fecha_corte)).order_by('fecha'))
    pendiente = sum((_d(c.saldocapital) for c in vivas), CERO)
    abono = min(disponible, pendiente)
    resultado['excedente'] = disponible - abono
    if abono <= 0:
        return resultado

    planes = {p.idcta: p for p in PlanPagos.objects.using(proyecto).filter(
        adj=adj, idcta__in=[c.idcta for c in vivas])}
    entrada = [{
        'idcta': c.idcta,
        'cuota': planes[c.idcta].cuota,
        'intcte': planes[c.idcta].intcte,
        'rcdocapital': c.rcdocapital,
        'rcdointcte': c.rcdointcte,
    } for c in vivas]
    cambios, sobrante = recalcular_cuotas(entrada, pendiente - abono, tasa)
    if sobrante > TOLERANCIA:
        raise AbonoCapitalError(
            f'Las cuotas del plan no alcanzan para cubrir el saldo; quedarían {sobrante:,.0f} sin cuota.'
        )

    nro, idcta_co = _siguiente_idcta_co(proyecto, adj)
    PlanPagos.objects.using(proyecto).create(
        adj=adj, fecha=fecha, tipocta='CO', idcta=idcta_co,
        capital=abono, cuota=abono, nrocta=nro, intcte=0,
    )
    crear_recaudo(idcta_co, abono, 0, 0, 0)

    for cambio in cambios:
        if cambio[0] == 'delete':
            PlanPagos.objects.using(proyecto).filter(adj=adj, idcta=cambio[1]).delete()
            resultado['cuotas_eliminadas'].append(cambio[1])
        else:
            _, idcta, capital, intcte, cuota = cambio
            PlanPagos.objects.using(proyecto).filter(adj=adj, idcta=idcta).update(
                capital=capital, intcte=intcte, cuota=cuota)
            resultado['cuotas_recalculadas'].append(idcta)

    resultado.update({'abono': abono, 'idcta_co': idcta_co})
    return resultado
