"""
Movimientos de la conciliación que un archivo contable ya trae, para no contarlos dos veces.

El saldo contable de un tercero es «saldo del archivo + movimientos aplicados desde la conciliación» (traslados
enviados a Alegra o registrados a mano, y cruces de anticipo de facturas). El archivo es un balance al corte: un
movimiento con fecha posterior al corte nunca está en él. Pero si el movimiento tiene fecha dentro del corte y el
archivo de esa empresa se exporta y se carga después de registrarlo, el archivo ya lo trae.

Al cargar un archivo, quien lo carga confirma cuáles de esos movimientos vienen incluidos. Como ayuda se compara el
archivo nuevo con el anterior de la misma empresa: si el saldo del tercero cambió justo en el valor del movimiento,
el archivo lo trae. La decisión se guarda en `FuenteConciliacion.incluidos` y el engine no los vuelve a sumar.
"""
import datetime
from collections import defaultdict
from decimal import Decimal

from django.db.models import Q

from conciliacion_terceros.models import AjusteConciliacion, FacturaConciliacion

TOL = Decimal('1')
VACIO = (frozenset(), frozenset())


def _ids(d, clave):
    out = set()
    for x in (d or {}).get(clave, []):
        try:
            out.add(int(x))
        except (TypeError, ValueError):
            continue
    return out


def por_empresa(fuentes):
    """{empresa_id: (ids de ajustes, ids de facturas)} que trae el archivo confirmado de cada empresa."""
    return {f.empresa_id: (_ids(f.incluidos, 'ajustes'), _ids(f.incluidos, 'facturas')) for f in fuentes if f.confirmada}


def ajuste_incluido(a, inc):
    return a.pk in inc.get(a.origen_empresa_id, VACIO)[0] or a.pk in inc.get(a.destino_empresa_id, VACIO)[0]


def factura_incluida(f, inc):
    return f.pk in inc.get(f.empresa_id, VACIO)[1]


def movimientos_en_corte(fuente):
    """Movimientos aplicados de la conciliación en la empresa del archivo, con fecha dentro del corte (o sin fecha)."""
    conc, emp, corte = fuente.conciliacion, fuente.empresa_id, fuente.conciliacion.fecha_corte
    out = []
    ajustes = conc.ajustes.filter(anulado=False, journal_estado__in=AjusteConciliacion.ESTADOS_APLICADOS) \
        .filter(Q(origen_empresa_id=emp) | Q(destino_empresa_id=emp)).order_by('created_at', 'id')
    for a in ajustes:
        if a.fecha and a.fecha > corte:
            continue
        efectos = []
        if a.origen_empresa_id == emp:
            efectos.append((a.origen_identificacion, a.origen_cuenta, -a.valor))
        if a.destino_empresa_id == emp:
            efectos.append((a.destino_identificacion, a.destino_cuenta, a.valor))
        quien = (f'{a.origen_identificacion} → {a.destino_identificacion}' if a.origen_identificacion != a.destino_identificacion
                 else a.origen_identificacion)
        out.append({
            'tipo': 'ajuste', 'id': a.pk, 'referencia': a.referencia, 'fecha': a.fecha, 'registrado_en': a.enviado_en or a.created_at,
            'descripcion': f'Traslado {quien} · {a.origen_cuenta} → {a.destino_cuenta}', 'valor': a.valor,
            'estado': a.get_journal_estado_display() + (f' · {a.journal_ref}' if a.journal_ref else ''), 'efectos': efectos,
        })
    facturas = conc.facturas.filter(empresa_id=emp).exclude(cruce_cuenta='').filter(
        Q(tipo=FacturaConciliacion.TIPO_ALEGRA, cruce_estado=FacturaConciliacion.CRUCE_REGISTRADO)
        | Q(tipo=FacturaConciliacion.TIPO_INFORMATIVA, cruce_estado=FacturaConciliacion.CRUCE_PENDIENTE)
    ).order_by('created_at', 'id')
    for f in facturas:
        if not f.vigente or f.fecha > corte:
            continue
        out.append({
            'tipo': 'factura', 'id': f.pk, 'referencia': f'FC-{f.pk}', 'fecha': f.fecha, 'registrado_en': f.created_at,
            'descripcion': f'Cruce de anticipo · factura {f.numero or "(sin número)"} · {f.identificacion} · {f.proyecto} {f.negocio_ref}',
            'valor': f.total, 'estado': f.get_cruce_estado_display() + (f' · {f.alegra_journal_id}' if f.alegra_journal_id else ''),
            'efectos': [(f.identificacion, f.cruce_cuenta, -f.total)],
        })
    return out


def _saldo(balance, ident, cuenta):
    cta = balance.cuentas.get(cuenta)
    t = cta.terceros.get(ident) if cta else None
    return t['saldo'] if t else Decimal(0)


def sugerir(fuente, movs):
    """Agrega a cada movimiento `verificacion` (si / no / otro / ''), `explicacion` y `sugerido` (bool)."""
    from conciliacion_terceros.formatos import leer_fuente

    ant = fuente.anterior or {}
    ya_antes = (_ids(ant.get('incluidos'), 'ajustes'), _ids(ant.get('incluidos'), 'facturas'))
    viejo = nuevo = None
    if ant.get('archivo') and movs:
        try:
            viejo = leer_fuente(ant['formato'], ant['archivo'])
            nuevo = leer_fuente(fuente.formato, fuente.archivo)
        except Exception:
            viejo = nuevo = None

    def en_anterior(m):
        return m['id'] in (ya_antes[0] if m['tipo'] == 'ajuste' else ya_antes[1])

    # Cambio de saldo entre el archivo anterior y el nuevo por cada movimiento, según si el nuevo lo trae o no:
    # - el anterior no lo traía: si el nuevo lo trae, el saldo cambia en su valor; si no, no cambia.
    # - el anterior ya lo traía: si el nuevo lo trae, no cambia; si no, cambia en el valor contrario.
    def cambio(m, d, lo_trae):
        if en_anterior(m):
            return Decimal(0) if lo_trae else -d
        return d if lo_trae else Decimal(0)

    # Se supone que el nuevo trae todos; a cada movimiento se le prueba la hipótesis contraria.
    todos = defaultdict(Decimal)
    for m in movs:
        for ident, cuenta, d in m['efectos']:
            todos[(ident, cuenta)] += cambio(m, d, True)
    real = {k: _saldo(nuevo, *k) - _saldo(viejo, *k) for k in todos} if viejo is not None else {}

    cargado = fuente.cargado_en
    for m in movs:
        m['verificacion'] = ''
        if real:
            si = all(abs(real[(i, c)] - todos[(i, c)]) <= TOL for i, c, _ in m['efectos'])
            no = all(abs(real[(i, c)] - (todos[(i, c)] - cambio(m, d, True) + cambio(m, d, False))) <= TOL for i, c, d in m['efectos'])
            if si and not no:
                m['verificacion'] = 'si'
                m['explicacion'] = ('Ya venía en el archivo anterior y el saldo no cambió: el archivo lo trae.' if en_anterior(m)
                                    else 'Frente al archivo anterior, el saldo cambió justo en este valor: el archivo lo trae.')
            elif no and not si:
                m['verificacion'] = 'no'
                m['explicacion'] = ('Venía en el archivo anterior pero el saldo se devolvió en su valor: este archivo no lo trae.'
                                    if en_anterior(m) else 'Frente al archivo anterior, el saldo no cambió: el archivo no lo trae.')
            else:
                m['verificacion'] = 'otro'
                m['explicacion'] = 'Frente al archivo anterior, el saldo cambió en ' + ', '.join(
                    f'{i} {c}: ${real[(i, c)]:,.0f}' for i, c, _ in m['efectos']) + '; revisa si lo trae.'
        if m['verificacion'] in ('si', 'no'):
            m['sugerido'] = m['verificacion'] == 'si'
        else:
            antes = bool(cargado and m['registrado_en'] and m['registrado_en'] < cargado)
            m['sugerido'] = antes
            base = m.get('explicacion', '') + (' ' if m.get('explicacion') else '')
            m['explicacion'] = base + ('Se registró antes de cargar este archivo: probablemente lo trae.' if antes
                                       else 'Se registró después de cargar este archivo: no puede traerlo.') + \
                ('' if real else ' No hay archivo anterior para comparar.')
        m['fecha_txt'] = m['fecha'].strftime('%d/%m/%Y') if isinstance(m['fecha'], datetime.date) else 'sin fecha'
    return movs
