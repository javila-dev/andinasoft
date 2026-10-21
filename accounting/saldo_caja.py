"""Saldo teórico de las cuentas de efectivo de tesorería (planilla diaria).

Única fórmula para el cuadre de caja: el saldo al cierre de un día parte del
último cierre registrado (saldo teórico + ajuste aprobado) y suma todos los
movimientos de la cuenta desde ese cierre. El arqueo físico no se usa como
saldo de partida; solo se compara contra el teórico.
"""
import datetime
from decimal import Decimal

from django.db.models import Sum, F

from andinasoft.models import clientes, proyectos
from andinasoft.shared_models import Recaudos_general, RecaudosNoradicados, formas_pago, ventas_nuevas
from accounting.models import (Anticipos, Pagos, gastos_caja, otros_ingresos,
                               transferencias_companias, CierreCaja)
from accounting.models_alttum import Pagos_facturas, Anticipos_hotels


CONCEPTOS = (
    ('ingresos', '(+) Ingresos', 1),
    ('otros_ingresos', '(+) Otros ingresos', 1),
    ('transferencias_entra', '(+) Transferencias entra', 1),
    ('transferencias_sale', '(-) Transferencias sale', -1),
    ('intercompania_entra', '(+) Intercompañia entra', 1),
    ('intercompania_sale', '(-) Intercompañia sale', -1),
    ('hoteles', '(+) Pagos hoteles', 1),
    ('anticipos', '(-) Anticipos', -1),
    ('pagos', '(-) Pagos', -1),
    ('gastos_caja', '(-) Gastos de caja', -1),
)


class CajaCerrada(Exception):
    """Se intentó mover una cuenta de efectivo en un día ya cerrado."""


def es_caja_planilla(cuenta):
    """Efectivo de tesorería que se cuadra en la planilla diaria.

    Las cajas con usuario responsable (cajas menores) se arquean en su propio módulo.
    """
    return cuenta.es_cuenta_caja_efectivo() and cuenta.usuario_responsable_id is None


def _fecha(valor):
    if isinstance(valor, datetime.datetime):
        return valor.date()
    if isinstance(valor, datetime.date):
        return valor
    return datetime.datetime.strptime(str(valor)[:10], '%Y-%m-%d').date()


def _suma(qs, campo='valor'):
    return Decimal(str(qs.aggregate(total=Sum(campo)).get('total') or 0))


def _sum_recaudos(cuenta_pk, desde, hasta):
    total = Decimal(0)
    for proy in proyectos.objects.exclude(proyecto__icontains='Alttum'):
        db = proy.proyecto
        formas = list(
            formas_pago.objects.using(db)
            .filter(cuenta_asociada=cuenta_pk)
            .exclude(descripcion__isnull=True).exclude(descripcion='')
            .values_list('descripcion', flat=True)
        )
        if not formas:
            continue
        for model in (Recaudos_general, RecaudosNoradicados):
            total += _suma(model.objects.using(db).filter(
                formapago__in=formas, fecha__range=(desde, hasta)))
    return total


def movimientos_caja(cuenta_pk, desde, hasta):
    """Totales por concepto de los movimientos de la cuenta entre dos fechas (inclusive)."""
    desde, hasta = _fecha(desde), _fecha(hasta)
    if desde > hasta:
        return {clave: Decimal(0) for clave, _, _ in CONCEPTOS}

    transf = transferencias_companias.objects.filter(fecha__range=(desde, hasta))
    misma_empresa = transf.filter(empresa_entra=F('empresa_sale'))
    entre_empresas = transf.exclude(empresa_entra=F('empresa_sale'))
    return {
        'ingresos': _sum_recaudos(cuenta_pk, desde, hasta),
        'otros_ingresos': _suma(otros_ingresos.objects.filter(
            cuenta=cuenta_pk, fecha_ing__range=(desde, hasta))),
        'transferencias_entra': _suma(misma_empresa.filter(cuenta_entra=cuenta_pk)),
        'transferencias_sale': _suma(misma_empresa.filter(cuenta_sale=cuenta_pk)),
        'intercompania_entra': _suma(entre_empresas.filter(cuenta_entra=cuenta_pk)),
        'intercompania_sale': _suma(entre_empresas.filter(cuenta_sale=cuenta_pk)),
        'hoteles': (
            _suma(Pagos_facturas.objects.using('Alttum').filter(
                forma_pago__cuenta_andinasoft=cuenta_pk, fecha__range=(desde, hasta)))
            + _suma(Anticipos_hotels.objects.using('Alttum').filter(
                forma_pago__cuenta_andinasoft=cuenta_pk, fecha__range=(desde, hasta)))
        ),
        'anticipos': _suma(Anticipos.objects.filter(
            cuenta=cuenta_pk, fecha_pago__range=(desde, hasta))),
        'pagos': _suma(Pagos.objects.filter(
            cuenta=cuenta_pk, fecha_pago__range=(desde, hasta))),
        'gastos_caja': _suma(gastos_caja.objects.filter(
            forma_pago=cuenta_pk, fecha_gasto__range=(desde, hasta))),
    }


def neto(movimientos):
    return sum((signo * Decimal(str(movimientos.get(clave, 0))) for clave, _, signo in CONCEPTOS), Decimal(0))


ORDEN_CONCEPTO = {clave: i for i, (clave, _, _) in enumerate(CONCEPTOS)}
NOMBRE_CONCEPTO = {clave: etiqueta[4:] for clave, etiqueta, _ in CONCEPTOS}
SIGNO_CONCEPTO = {clave: signo for clave, _, signo in CONCEPTOS}


def _fila(fecha, clave, documento, detalle, valor):
    valor = Decimal(str(valor or 0))
    entra = SIGNO_CONCEPTO[clave] > 0
    return {
        'fecha': _fecha(fecha),
        'clave': clave,
        'concepto': NOMBRE_CONCEPTO[clave],
        'documento': str(documento or ''),
        'detalle': (detalle or '').strip(),
        'entrada': valor if entra else Decimal(0),
        'salida': Decimal(0) if entra else valor,
    }


def _detalle_recaudos(cuenta_pk, desde, hasta):
    filas = []
    for proy in proyectos.objects.exclude(proyecto__icontains='Alttum'):
        db = proy.proyecto
        formas = list(
            formas_pago.objects.using(db)
            .filter(cuenta_asociada=cuenta_pk)
            .exclude(descripcion__isnull=True).exclude(descripcion='')
            .values_list('descripcion', flat=True)
        )
        if not formas:
            continue
        radicados = list(Recaudos_general.objects.using(db).filter(
            formapago__in=formas, fecha__range=(desde, hasta)))
        noradicados = list(RecaudosNoradicados.objects.using(db).filter(
            formapago__in=formas, fecha__range=(desde, hasta)))
        contratos = ventas_nuevas.objects.using(db).in_bulk(
            {r.contrato for r in noradicados if r.contrato})
        terceros = clientes.objects.in_bulk(
            {r.idtercero for r in radicados if r.idtercero}
            | {c.id_t1 for c in contratos.values() if c.id_t1})
        for r in radicados:
            cliente = terceros.get(r.idtercero)
            nombre = cliente.nombrecompleto if cliente else r.idtercero
            filas.append(_fila(r.fecha, 'ingresos', f'RC {r.numrecibo}',
                               f'{db} · {(nombre or "").upper()}', r.valor))
        for r in noradicados:
            contrato = contratos.get(r.contrato)
            cliente = terceros.get(contrato.id_t1) if contrato else None
            nombre = cliente.nombrecompleto if cliente else f'Contrato {r.contrato}'
            filas.append(_fila(r.fecha, 'ingresos', f'RC {r.recibo}',
                               f'{db} · {(nombre or "").upper()} (no radicado)', r.valor))
    return filas


def detalle_movimientos_caja(cuenta_pk, desde, hasta):
    """Cada movimiento de la cuenta entre dos fechas (inclusive), como entrada o salida.

    Usa las mismas fuentes y filtros que movimientos_caja, así que los totales coinciden.
    """
    desde, hasta = _fecha(desde), _fecha(hasta)
    if desde > hasta:
        return []
    filas = _detalle_recaudos(cuenta_pk, desde, hasta)

    for m in otros_ingresos.objects.filter(cuenta=cuenta_pk, fecha_ing__range=(desde, hasta)):
        filas.append(_fila(m.fecha_ing, 'otros_ingresos', f'OI {m.pk}',
                           f'{m.nombre_tercero} · {m.descripcion}', m.valor))

    transf = (transferencias_companias.objects.filter(fecha__range=(desde, hasta))
              .select_related('cuenta_entra', 'cuenta_sale', 'empresa_entra', 'empresa_sale'))
    for m in transf.filter(cuenta_entra=cuenta_pk) | transf.filter(cuenta_sale=cuenta_pk):
        misma = m.empresa_entra_id == m.empresa_sale_id
        if misma:
            detalle = f'{m.cuenta_sale.cuentabanco} → {m.cuenta_entra.cuentabanco}'
        else:
            detalle = (f'{m.empresa_sale.nombre} ({m.cuenta_sale.cuentabanco}) → '
                       f'{m.empresa_entra.nombre} ({m.cuenta_entra.cuentabanco})')
        prefijo = 'transferencias' if misma else 'intercompania'
        if m.cuenta_entra_id == int(cuenta_pk):
            filas.append(_fila(m.fecha, f'{prefijo}_entra', f'TR {m.pk}', detalle, m.valor))
        if m.cuenta_sale_id == int(cuenta_pk):
            filas.append(_fila(m.fecha, f'{prefijo}_sale', f'TR {m.pk}', detalle, m.valor))

    for m in Pagos_facturas.objects.using('Alttum').filter(
            forma_pago__cuenta_andinasoft=cuenta_pk, fecha__range=(desde, hasta)):
        filas.append(_fila(m.fecha, 'hoteles', f'FH {m.factura_id}', 'Pago factura hotel', m.valor))
    for m in Anticipos_hotels.objects.using('Alttum').filter(
            forma_pago__cuenta_andinasoft=cuenta_pk, fecha__range=(desde, hasta)):
        filas.append(_fila(m.fecha, 'hoteles', f'AH {m.pk}', f'Anticipo hotel ({m.origen})', m.valor))

    for m in Anticipos.objects.filter(cuenta=cuenta_pk, fecha_pago__range=(desde, hasta)):
        filas.append(_fila(m.fecha_pago, 'anticipos', f'ANT {m.pk}',
                           f'{m.nombre_tercero or m.id_tercero} · {m.descripcion}', m.valor))

    pagos = (Pagos.objects.filter(cuenta=cuenta_pk, fecha_pago__range=(desde, hasta))
             .select_related('nroradicado'))
    for m in pagos:
        filas.append(_fila(m.fecha_pago, 'pagos', f'RAD {m.nroradicado_id}',
                           f'{m.nroradicado.nombretercero} · {m.nroradicado.descripcion}', m.valor))

    gastos = (gastos_caja.objects.filter(forma_pago=cuenta_pk, fecha_gasto__range=(desde, hasta))
              .select_related('tercero'))
    for m in gastos:
        filas.append(_fila(m.fecha_gasto, 'gastos_caja', f'GC {m.pk}',
                           f'{m.tercero} · {m.descripcion}', m.valor))

    # Sin hora común entre las fuentes, dentro de cada día van primero las entradas:
    # así el saldo acumulado no muestra negativos que no ocurrieron.
    filas.sort(key=lambda f: (f['fecha'], not f['entrada'], ORDEN_CONCEPTO[f['clave']], f['documento']))
    return filas


def libro_caja(cuenta_pk, fecha):
    """Movimientos desde el cierre anterior a `fecha` hasta `fecha`, con saldo acumulado.

    Sin cierre anterior (día de apertura) solo trae los movimientos del día y parte
    del saldo inicial guardado en el cierre de apertura, si existe.
    """
    fecha = _fecha(fecha)
    base = ultimo_cierre(cuenta_pk, antes_de=fecha)
    if base is not None:
        desde = base.fecha + datetime.timedelta(days=1)
        saldo = base.saldo_base_siguiente
    else:
        desde = fecha
        apertura = CierreCaja.objects.filter(cuenta=cuenta_pk, fecha=fecha, es_apertura=True).first()
        saldo = apertura.saldo_inicial if apertura else None
    saldo_inicial = saldo
    filas = detalle_movimientos_caja(cuenta_pk, desde, fecha)
    for fila in filas:
        if saldo is not None:
            saldo += fila['entrada'] - fila['salida']
        fila['saldo'] = saldo
    return {
        'cierre_base': base,
        'desde': desde,
        'saldo_inicial': saldo_inicial,
        'filas': filas,
        'total_entradas': sum((f['entrada'] for f in filas), Decimal(0)),
        'total_salidas': sum((f['salida'] for f in filas), Decimal(0)),
        'saldo_final': saldo,
    }


def ultimo_cierre(cuenta_pk, antes_de=None, hasta=None):
    qs = CierreCaja.objects.filter(cuenta=cuenta_pk)
    if antes_de is not None:
        qs = qs.filter(fecha__lt=_fecha(antes_de))
    if hasta is not None:
        qs = qs.filter(fecha__lte=_fecha(hasta))
    return qs.order_by('-fecha').first()


def saldo_al_cierre(cuenta_pk, fecha):
    """Saldo teórico de la cuenta al final del día `fecha`, con los ajustes aprobados.

    Devuelve (saldo, cierre_base). Sin un cierre previo no hay saldo de
    partida y se devuelve (None, None): la cuenta necesita un cierre de apertura.
    """
    fecha = _fecha(fecha)
    base = ultimo_cierre(cuenta_pk, hasta=fecha)
    if base is None:
        return None, None
    if base.fecha == fecha:
        return base.saldo_base_siguiente, base
    movs = movimientos_caja(cuenta_pk, base.fecha + datetime.timedelta(days=1), fecha)
    return base.saldo_base_siguiente + neto(movs), base


def cuadre_del_dia(cuenta_pk, fecha):
    """Saldo inicial, movimientos y saldo final teórico de la cuenta en `fecha`."""
    fecha = _fecha(fecha)
    saldo_inicial, base = saldo_al_cierre(cuenta_pk, fecha - datetime.timedelta(days=1))
    movs = movimientos_caja(cuenta_pk, fecha, fecha)
    saldo_final = None if saldo_inicial is None else saldo_inicial + neto(movs)
    return {
        'saldo_inicial': saldo_inicial,
        'cierre_base': base,
        'movimientos': movs,
        'saldo_final': saldo_final,
    }


def validar_recaudo_caja_abierta(proyecto_db, forma_pago, fecha):
    """Valida un recibo nuevo de proyecto contra la caja asociada a su forma de pago."""
    if not forma_pago:
        return
    cuentas = list(
        formas_pago.objects.using(proyecto_db)
        .filter(descripcion=str(forma_pago), cuenta_asociada__isnull=False)
        .values_list('cuenta_asociada', flat=True)
    )
    validar_caja_abierta(cuentas, fecha)


def validar_caja_abierta(cuentas, fecha):
    """Lanza CajaCerrada si alguna de las cuentas ya tiene un cierre en `fecha` o después."""
    try:
        fecha = _fecha(fecha)
    except (TypeError, ValueError):
        return  # sin fecha válida no hay nada que validar; el formulario lo rechaza aparte
    pks = [c.pk if hasattr(c, 'pk') else c for c in cuentas if c]
    cierre = (CierreCaja.objects.filter(cuenta__in=pks, fecha__gte=fecha)
              .select_related('cuenta').order_by('-fecha').first())
    if cierre is not None:
        raise CajaCerrada(
            f'La caja {cierre.cuenta.cuentabanco} está cerrada hasta el '
            f'{cierre.fecha:%d/%m/%Y}. No se pueden registrar ni modificar '
            f'movimientos de efectivo en esa fecha o antes; pide que reabran el cierre.'
        )
