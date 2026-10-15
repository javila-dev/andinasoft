"""
Motor de conciliación de saldos por tercero: Andinasoft vs contabilidad (Alegra / SIIGO).

Una línea por tercero:
- Andinasoft: lo recaudado de cada negocio repartido en partes iguales entre sus titulares, igual que
  `ReceiptPaymentBuilder` (ROUND_DOWN y el residuo al primero). Los desistidos al corte esperan $0.
- Contabilidad: la suma de sus saldos en las cuentas seleccionadas de cada empresa.
"""
import datetime
import re
from collections import defaultdict
from decimal import ROUND_DOWN, Decimal

from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from andinasoft.models import clientes
from andinasoft.shared_models import (
    Adjudicacion,
    Promesas,
    Recaudos,
    Recaudos_general,
    RecaudosNoradicados,
    timeline,
    ventas_nuevas,
)
from conciliacion_terceros.formatos import leer_fuente
from conciliacion_terceros.models import AjusteConciliacion, ConciliacionLinea
from conciliacion_terceros.parser import norm_ident

ZERO = Decimal('0')
CENT = Decimal('0.01')

SIT_ACTIVA = 'activa'
SIT_DESISTIDA = 'desistida'
SIT_ESCRITURADA = 'escriturada'
SIT_VENTA_PENDIENTE = 'venta_pendiente'
SIT_VENTA_ANULADA = 'venta_anulada'

SIT_LABEL = {
    SIT_ACTIVA: 'Activa',
    SIT_DESISTIDA: 'Desistida',
    SIT_ESCRITURADA: 'Escriturada',
    SIT_VENTA_PENDIENTE: 'Venta sin adjudicar',
    SIT_VENTA_ANULADA: 'Venta anulada',
}


def _q(value):
    return Decimal(value or 0).quantize(CENT)


def _split(total, n):
    """Mismo reparto que ReceiptPaymentBuilder: partes iguales, residuo al primer titular."""
    n = max(1, n)
    base = (total / Decimal(n)).quantize(CENT, rounding=ROUND_DOWN)
    amounts = [base] * n
    amounts[0] = (amounts[0] + (total - base * n)).quantize(CENT)
    return amounts


def _parse_date(value):
    if isinstance(value, datetime.date):
        return value
    text = str(value or '').strip()[:10]
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _titulares(*values):
    out = []
    for v in values:
        t = norm_ident(v)
        if t and t not in out:
            out.append(t)
    return out


# ---------------------------------------------------------------------------
# Foto de Andinasoft
# ---------------------------------------------------------------------------

def snapshot_proyecto(proyecto, corte):
    """Lista de negocios (adjudicaciones y ventas sin adjudicar) con lo recaudado al corte."""
    totales = dict(
        Recaudos_general.objects.using(proyecto).filter(fecha__lte=corte)
        .values_list('idadjudicacion').annotate(s=Sum('valor'))
    )
    componentes = {
        r['idadjudicacion']: r for r in
        Recaudos.objects.using(proyecto).filter(fecha__lte=corte)
        .values('idadjudicacion').annotate(cap=Sum('capital'), cte=Sum('interescte'), mora=Sum('interesmora'))
    }
    pagadores = defaultdict(set)
    for adj, tercero in Recaudos_general.objects.using(proyecto).filter(fecha__lte=corte).values_list('idadjudicacion', 'idtercero').distinct():
        if adj and tercero:
            pagadores[adj].add(norm_ident(tercero))
    escrituras = {
        p['idadjudicacion']: p['fechaescritura']
        for p in Promesas.objects.using(proyecto).filter(escriturado=True).values('idadjudicacion', 'fechaescritura')
    }
    cesiones = defaultdict(list)
    for adj, fecha in timeline.objects.using(proyecto).filter(accion__icontains='cesi').values_list('adj', 'fecha'):
        cesiones[adj].append(_parse_date(fecha))

    negocios = []
    for a in Adjudicacion.objects.using(proyecto).values(
        'idadjudicacion', 'estado', 'fechadesistimiento', 'origenventa',
        'idtercero1', 'idtercero2', 'idtercero3', 'idtercero4',
    ):
        pk = a['idadjudicacion']
        tits = _titulares(a['idtercero1'], a['idtercero2'], a['idtercero3'], a['idtercero4'])
        if not tits:
            continue
        estado = a['estado'] or ''
        fdes = a['fechadesistimiento']
        fesc = escrituras.get(pk, 'no')
        if estado.startswith('Desistido') and (fdes is None or fdes <= corte):
            sit = SIT_DESISTIDA
        elif fesc != 'no' and (fesc is None or fesc <= corte):
            sit = SIT_ESCRITURADA
        else:
            sit = SIT_ACTIVA
        comp = componentes.get(pk) or {}
        negocios.append({
            'proyecto': proyecto,
            'ref': pk,
            'situacion': sit,
            'estado': estado,
            'origen': a['origenventa'] or '',
            'fecha_desistimiento': fdes.isoformat() if fdes else '',
            'titulares': tits,
            'total': _q(totales.get(pk)),
            'capital': _q(comp.get('cap')),
            'interes_cte': _q(comp.get('cte')),
            'interes_mora': _q(comp.get('mora')),
            'no_radicado': ZERO,
            'pagadores': sorted(pagadores.get(pk, set()) - set(tits)),
            'cesiones': sorted(d.isoformat() for d in cesiones.get(pk, []) if d),
        })

    no_radicado = defaultdict(lambda: ZERO)
    for contrato, fecha, valor in RecaudosNoradicados.objects.using(proyecto).values_list('contrato', 'fecha', 'valor'):
        f = _parse_date(fecha)
        if f is None or f <= corte:
            no_radicado[str(contrato)] += _q(valor)
    for v in ventas_nuevas.objects.using(proyecto).exclude(estado='Adjudicado').values(
        'id_venta', 'estado', 'inmueble', 'id_t1', 'id_t2', 'id_t3', 'id_t4',
    ):
        tits = _titulares(v['id_t1'], v['id_t2'], v['id_t3'], v['id_t4'])
        if not tits:
            continue
        nr = no_radicado.get(str(v['id_venta']), ZERO)
        negocios.append({
            'proyecto': proyecto,
            'ref': f'Venta {v["id_venta"]} ({v["inmueble"]})',
            'situacion': SIT_VENTA_ANULADA if (v['estado'] or '') == 'Anulado' else SIT_VENTA_PENDIENTE,
            'estado': v['estado'] or '',
            'origen': '',
            'fecha_desistimiento': '',
            'titulares': tits,
            'total': nr,
            'capital': nr,
            'interes_cte': ZERO,
            'interes_mora': ZERO,
            'no_radicado': nr,
            'pagadores': [],
            'cesiones': [],
        })
    return negocios


# ---------------------------------------------------------------------------
# Cruce por tercero
# ---------------------------------------------------------------------------

def _alerta(codigo, texto):
    return {'codigo': codigo, 'texto': texto}


def _fmt(v):
    return f'${Decimal(v):,.0f}'.replace(',', '.')


def _tokens(nombre):
    return {t for t in re.split(r'\W+', (nombre or '').upper()) if len(t) > 3}


def _participacion(n):
    """Lo que le corresponde a cada titular del negocio (mismo reparto que el journal)."""
    k = len(n['titulares'])
    return {
        'total': dict(zip(n['titulares'], _split(n['total'], k))),
        'capital': dict(zip(n['titulares'], _split(n['capital'], k))),
        'intereses': dict(zip(n['titulares'], _split(n['interes_cte'] + n['interes_mora'], k))),
    }


NO_SUMAN = (SIT_DESISTIDA, SIT_VENTA_ANULADA)


def _suma(n):
    """Si el negocio suma al saldo esperado: desistidos al corte y ventas anuladas esperan $0."""
    return n['situacion'] not in NO_SUMAN


def proyectos_conciliables():
    """Proyectos con base de datos y tabla de adjudicaciones (Alttum, p. ej., no la tiene)."""
    from django.conf import settings
    from django.db import connections
    from andinasoft.models import proyectos as Proyectos

    out = []
    for p in Proyectos.objects.order_by('proyecto').values_list('pk', flat=True):
        if p not in settings.DATABASES:
            continue
        try:
            if 'adjudicacion' in connections[p].introspection.table_names():
                out.append(p)
        except Exception:
            continue
    return out


def _negocios(conciliacion, usar_cache):
    """Foto de Andinasoft al corte. Se cachea para que registrar ajustes no vuelva a leer todos los proyectos."""
    excluidos = sorted(conciliacion.proyectos_excluidos or [])
    key = f'conciliacion_terceros:negocios:{conciliacion.pk}:{conciliacion.fecha_corte}:{"|".join(excluidos)}'
    if usar_cache:
        hit = cache.get(key)
        if hit is not None:
            return hit
    negocios = []
    for p in proyectos_conciliables():
        if p not in excluidos:
            negocios.extend(snapshot_proyecto(p, conciliacion.fecha_corte))
    cache.set(key, negocios, 60 * 60)
    return negocios


def catalogo_cuentas(conciliacion, balances=None):
    """Cuentas seleccionadas de todas las empresas: {(empresa, cuenta): {empresa, empresa_nombre, cuenta, cuenta_nombre}}."""
    out = {}
    for f in conciliacion.fuentes.filter(confirmada=True).select_related('empresa'):
        balance = (balances or {}).get(f.empresa_id) or leer_fuente(f.formato, f.archivo)
        for codigo in f.cuentas_usadas or []:
            cta = balance.cuentas.get(codigo)
            out[(f.empresa_id, codigo)] = {'empresa': f.empresa_id, 'empresa_nombre': f.empresa.nombre,
                                           'cuenta': codigo, 'cuenta_nombre': cta.nombre if cta else ''}
    return out


def calcular(conciliacion, usar_cache=False):
    corte = conciliacion.fecha_corte
    tol = Decimal(conciliacion.tolerancia)
    fuentes = list(conciliacion.fuentes.filter(confirmada=True).select_related('empresa'))

    # Lado contable: saldo por tercero en cada cuenta seleccionada de cada empresa (archivo + ajustes).
    contable = defaultdict(dict)  # ident -> {(empresa, cuenta): entrada}
    nombres_contables = {}
    balances = {}
    # Contactos corregidos en Alegra después de cargar el archivo: el archivo aún trae el Id viejo.
    alias = {}
    from conciliacion_terceros.models import CorreccionIdentificacion
    for c in CorreccionIdentificacion.objects.exclude(estado=CorreccionIdentificacion.ESTADO_REVERTIDA).order_by('created_at'):
        for a in c.alegra or []:
            if a.get('estado') == 'ok' and a.get('accion') == 'corregir_contacto':
                alias[(a['empresa'], c.id_errado)] = c.id_correcto
    for f in fuentes:
        balance = leer_fuente(f.formato, f.archivo)
        balances[f.empresa_id] = balance
        usadas = set(f.cuentas_usadas or [])
        for codigo, cta in balance.cuentas.items():
            if codigo not in usadas:
                continue
            for ident, t in cta.terceros.items():
                if t['saldo'] == 0:
                    continue
                ident = alias.get((f.empresa_id, ident), ident)
                contable[ident][(f.empresa_id, codigo)] = {
                    'empresa': f.empresa_id, 'empresa_nombre': f.empresa.nombre, 'cuenta': codigo,
                    'cuenta_nombre': cta.nombre, 'saldo_archivo': t['saldo'], 'ajustes': ZERO,
                }
                nombres_contables.setdefault(ident, t['nombre'])
    catalogo = catalogo_cuentas(conciliacion, balances)
    nombres_empresa = {f.empresa_id: f.empresa.nombre for f in fuentes}

    def entrada(ident, emp, cuenta, nombre_cuenta):
        e = contable[ident].get((emp, cuenta))
        if e is None:
            info = catalogo.get((emp, cuenta)) or {'empresa': emp, 'empresa_nombre': nombres_empresa.get(emp, emp),
                                                  'cuenta': cuenta, 'cuenta_nombre': nombre_cuenta}
            e = contable[ident][(emp, cuenta)] = dict(info, saldo_archivo=ZERO, ajustes=ZERO)
        return e

    for a in conciliacion.ajustes.filter(anulado=False):
        entrada(a.origen_identificacion, a.origen_empresa_id, a.origen_cuenta, a.origen_cuenta_nombre)['ajustes'] -= a.valor
        entrada(a.destino_identificacion, a.destino_empresa_id, a.destino_cuenta, a.destino_cuenta_nombre)['ajustes'] += a.valor

    # Facturas: cierran el anticipo. Si el cruce no está en el archivo contable, se resta de la cuenta de anticipos.
    facturas = defaultdict(list)
    from conciliacion_terceros.models import FacturaConciliacion
    for fac in conciliacion.facturas.select_related('empresa'):
        if not fac.vigente:
            continue
        facturas[fac.identificacion].append(fac)
        if fac.cruce_estado != FacturaConciliacion.CRUCE_NO_APLICA and fac.cruce_cuenta:
            entrada(fac.identificacion, fac.empresa_id, fac.cruce_cuenta, fac.cruce_cuenta_nombre)['ajustes'] -= fac.total

    # Lado Andinasoft: negocios de todos los proyectos.
    negocios = _negocios(conciliacion, usar_cache)
    por_tercero = defaultdict(list)
    pagador_de = defaultdict(list)
    partes = {}
    for n in negocios:
        partes[id(n)] = _participacion(n)
        for t in n['titulares']:
            por_tercero[t].append(n)
        for t in n['pagadores']:
            pagador_de[t].append(n)
    nombres_locales = dict(clientes.objects.filter(pk__in=list(por_tercero) + list(contable)).values_list('pk', 'nombrecompleto'))

    lineas = {}
    for ident in set(contable) | set(facturas) | {t for t, ns in por_tercero.items() if any(_suma(n) and n['total'] for n in ns)}:
        refs = por_tercero.get(ident, [])
        lado_a, esperado, capital, intereses = [], ZERO, ZERO, ZERO
        for n in refs:
            p = partes[id(n)]
            valor = p['total'][ident]
            suma = _suma(n)
            if suma:
                esperado += valor
                capital += p['capital'][ident]
                intereses += p['intereses'][ident]
            lado_a.append({
                'proyecto': n['proyecto'], 'ref': n['ref'], 'situacion': n['situacion'], 'situacion_label': SIT_LABEL.get(n['situacion'], n['situacion']),
                'estado': n['estado'], 'origen': n['origen'], 'fecha_desistimiento': n['fecha_desistimiento'],
                'titulares': n['titulares'], 'total_negocio': str(n['total']), 'valor': str(valor), 'suma': suma,
                'capital': str(p['capital'][ident]), 'intereses': str(p['intereses'][ident]),
                'no_radicado': str(n['no_radicado']), 'pagadores': n['pagadores'], 'cesiones': n['cesiones'],
            })
        for fac in facturas.get(ident, []):
            esperado -= fac.total
            capital -= fac.valor_venta
            intereses -= fac.valor_intereses
            lado_a.append({
                'proyecto': fac.proyecto, 'ref': f'Factura {fac.numero or "(sin número)"}', 'situacion': 'factura',
                'situacion_label': 'Facturado', 'estado': fac.get_estado_display(), 'origen': fac.get_tipo_display(),
                'fecha_desistimiento': '', 'titulares': [ident], 'total_negocio': str(-fac.total), 'valor': str(-fac.total),
                'suma': True, 'capital': str(-fac.valor_venta), 'intereses': str(-fac.valor_intereses), 'no_radicado': '0',
                'pagadores': [], 'cesiones': [], 'factura_id': fac.pk, 'negocio_ref': fac.negocio_ref,
            })
        lado_c = []
        for e in sorted(contable.get(ident, {}).values(), key=lambda e: (e['empresa_nombre'], e['cuenta'])):
            e['saldo'] = e['saldo_archivo'] + e['ajustes']
            lado_c.append(e)
        saldo_c = sum((c['saldo'] for c in lado_c), ZERO)
        dif = saldo_c - esperado
        l = ConciliacionLinea(
            identificacion=ident, nombre=nombres_contables.get(ident) or nombres_locales.get(ident, ''),
            saldo_andina=esperado, saldo_contable=saldo_c, diferencia=dif, capital=capital, intereses=intereses,
            negocios=lado_a, alertas=[], sugerencia={},
            cuentas=[dict(c, saldo=str(c['saldo']), saldo_archivo=str(c['saldo_archivo']), ajustes=str(c['ajustes'])) for c in lado_c],
        )
        if abs(dif) <= tol:
            l.estado = ConciliacionLinea.ESTADO_CUADRADO
        elif esperado == 0:
            l.estado = ConciliacionLinea.ESTADO_SOLO_CONTABLE
        elif saldo_c == 0:
            l.estado = ConciliacionLinea.ESTADO_SOLO_ANDINA
        else:
            l.estado = ConciliacionLinea.ESTADO_DIFERENCIA
        _observaciones(l, refs, tol, corte, pagador_de.get(ident, []))
        lineas[ident] = l

    _regla_adjudicacion(lineas, negocios, partes, tol)
    _regla_mismo_valor(lineas, tol)
    _regla_nombre(lineas)
    return balances, list(lineas.values()), catalogo


def _observaciones(l, refs, tol, corte, pagador_de):
    obs, alertas = [], []
    cuadra = l.estado == ConciliacionLinea.ESTADO_CUADRADO
    if l.estado == ConciliacionLinea.ESTADO_DIFERENCIA and l.intereses > 0:
        if abs(l.saldo_contable - l.capital) <= tol:
            obs.append(f'La contabilidad coincide solo con el capital: intereses por {_fmt(l.intereses)} no están en las cuentas (¿facturados?).')
            l.sugerencia = {'regla': 'solo_capital'}
        elif l.capital < l.saldo_contable < l.saldo_andina:
            pct = ((l.saldo_contable - l.capital) / l.intereses * 100).quantize(Decimal('0.1'))
            obs.append(f'La contabilidad tiene el capital más el {pct}% de los intereses.')
            l.sugerencia = {'regla': 'intereses_parciales'}

    sits = {n['situacion'] for n in refs}
    if l.saldo_contable != 0 and refs and sits <= set(NO_SUMAN):
        alertas.append(_alerta('aplicar_desistimiento', 'Desistido o anulado en Andinasoft con saldo en contabilidad: aplicar el desistimiento ('
                               + ', '.join(f'{n["proyecto"]} {n["ref"]} {n["fecha_desistimiento"]}'.strip() for n in refs) + ').'))
    if l.saldo_contable != 0 and not refs:
        ex = sorted({f'{n["proyecto"]} {n["ref"]}' for n in pagador_de})
        if ex:
            alertas.append(_alerta('ex_titular', f'Aparece como tercero en recibos de {", ".join(ex)} pero hoy no es titular (posible cesión).'))
        else:
            alertas.append(_alerta('sin_negocio', 'Sin negocios en Andinasoft.'))

    for n in refs:
        for f in n['cesiones']:
            if f > corte.isoformat():
                alertas.append(_alerta('cesion_posterior', f'{n["ref"]}: cesión registrada el {f}, después del corte; el saldo puede estar en el titular anterior.'))
            elif not cuadra:
                alertas.append(_alerta('cesion_registrada', f'{n["ref"]}: cesión registrada el {f}.'))
        if n['pagadores'] and not cuadra:
            alertas.append(_alerta('pagador_distinto', f'{n["ref"]}: hay recibos a nombre de {", ".join(n["pagadores"])}, que no es titular hoy.'))
        if n['situacion'] == SIT_VENTA_PENDIENTE and n['no_radicado'] == 0 and l.saldo_contable != 0 and l.saldo_andina == 0:
            alertas.append(_alerta('venta_sin_recaudo', f'{n["ref"]}: venta sin adjudicar sin recaudo no radicado en Andinasoft; '
                                                        f'el saldo contable no tiene otro negocio que lo explique.'))
        if n['situacion'] == SIT_VENTA_ANULADA and n['no_radicado'] > 0:
            alertas.append(_alerta('venta_anulada_con_saldo', f'{n["ref"]}: venta anulada con {_fmt(n["no_radicado"])} de recaudo no radicado '
                                                              f'(¿devolución pendiente?).'))
    vistos = set()
    for a in alertas:
        if a['texto'] not in vistos:
            vistos.add(a['texto'])
            l.alertas.append(a)
    l.observacion = ' '.join(obs)


def _abierta(l):
    return l.estado != ConciliacionLinea.ESTADO_CUADRADO


def _regla_adjudicacion(lineas, negocios, partes, tol):
    """La adjudicación cuadra sumando a todos sus titulares, pero el saldo está mal repartido entre ellos."""
    for n in negocios:
        if not _suma(n) or len(n['titulares']) < 2:
            continue
        ls = [lineas.get(t) for t in n['titulares']]
        if any(x is None for x in ls) or not any(_abierta(x) for x in ls):
            continue
        # Solo si los titulares no tienen otros negocios que sumen (si no, la suma no es comparable).
        if any(sum(1 for r in x.negocios if r['suma'] and r.get('situacion') != 'factura') != 1 for x in ls):
            continue
        suma_c = sum((x.saldo_contable for x in ls), ZERO)
        if abs(suma_c - n['total']) > tol:
            continue
        traslados = [{'identificacion': x.identificacion, 'nombre': x.nombre, 'ajuste': str(-x.diferencia)}
                     for x in ls if abs(x.diferencia) > tol]
        for x in ls:
            if not _abierta(x):
                continue
            x.observacion = (x.observacion + ' ' if x.observacion else '') + (
                f'{n["ref"]} cuadra en conjunto ({_fmt(suma_c)}) pero el saldo está mal repartido entre sus {len(ls)} titulares.')
            x.sugerencia = {'regla': 'adjudicacion_conjunta', 'adj': n['ref'], 'traslados': traslados}


def _regla_mismo_valor(lineas, tol):
    """Otro tercero sin conciliar con la diferencia opuesta: posible cesión no registrada o tercero errado."""
    abiertas = [x for x in lineas.values() if _abierta(x) and (x.sugerencia or {}).get('regla') != 'adjudicacion_conjunta']
    sobrantes = [x for x in abiertas if x.diferencia > tol]
    faltantes = [x for x in abiertas if x.diferencia < -tol]
    for s in sobrantes:
        candidatos = [f for f in faltantes if abs(s.diferencia + f.diferencia) <= tol]
        if not candidatos:
            continue

        def score(f):
            refs_f = {r['ref'] for r in f.negocios}
            pag = any(s.identificacion in r.get('pagadores', []) for r in f.negocios)
            return (2 if pag else 0) + (1 if refs_f & {r['ref'] for r in s.negocios} else 0)

        candidatos.sort(key=score, reverse=True)
        top = candidatos[:3]
        texto = ', '.join(f'{c.identificacion} {c.nombre}'.strip() for c in top)
        s.sugerencia = {'regla': 'mismo_valor', 'contrapartes': [c.identificacion for c in top],
                        'traslados': [{'desde': s.identificacion, 'hacia': top[0].identificacion, 'valor': str(s.diferencia)}]}
        s.observacion = (s.observacion + ' ' if s.observacion else '') + (
            f'Le sobran {_fmt(s.diferencia)} y a {texto} le falta el mismo valor: posible cesión no registrada o tercero errado.')
        for c in top:
            c.sugerencia = c.sugerencia or {}
            c.sugerencia.setdefault('regla', 'mismo_valor')
            c.sugerencia.setdefault('contrapartes', [])
            if s.identificacion not in c.sugerencia['contrapartes']:
                c.sugerencia['contrapartes'].append(s.identificacion)
            c.observacion = (c.observacion + ' ' if c.observacion else '') + (
                f'Le faltan {_fmt(-c.diferencia)} y {s.identificacion} {s.nombre} tiene ese valor de más en contabilidad.')


def _regla_nombre(lineas):
    """Tercero solo en contabilidad con nombre parecido a uno solo en Andinasoft: posible identificación errada."""
    solo_c = [x for x in lineas.values() if x.estado == ConciliacionLinea.ESTADO_SOLO_CONTABLE]
    tok_b = [(x, _tokens(x.nombre)) for x in lineas.values() if x.estado == ConciliacionLinea.ESTADO_SOLO_ANDINA]
    for a in solo_c:
        ta = _tokens(a.nombre)
        if len(ta) < 2:
            continue
        parecidos = [x for x, tb in tok_b if len(ta & tb) >= 2]
        if parecidos:
            a.alertas = list(a.alertas) + [_alerta('nombre_parecido', 'Nombre parecido a tercero solo en Andinasoft: ' + ', '.join(
                f'{x.identificacion} {x.nombre} ({_fmt(x.saldo_andina)})' for x in parecidos[:3]))]


# ---------------------------------------------------------------------------
# Persistencia
# ---------------------------------------------------------------------------

def _resumen(lineas, balances, fuentes):
    """Totales por empresa/cuenta (lado contable) y por proyecto (lado Andinasoft)."""
    cuentas, proyectos, estados = {}, {}, defaultdict(int)
    for l in lineas:
        estados[l.estado] += 1
        for c in l.cuentas:
            k = (c['empresa'], c['cuenta'])
            r = cuentas.setdefault(k, {'empresa': c['empresa'], 'empresa_nombre': c['empresa_nombre'], 'cuenta': c['cuenta'],
                                       'cuenta_nombre': c['cuenta_nombre'], 'saldo': ZERO, 'terceros': 0})
            r['saldo'] += Decimal(c['saldo'])
            r['terceros'] += 1
        for n in l.negocios:
            if not n['suma']:
                continue
            r = proyectos.setdefault(n['proyecto'], {'proyecto': n['proyecto'], 'valor': ZERO, 'terceros': 0})
            r['valor'] += Decimal(n['valor'])
            r['terceros'] += 1
    return {
        'cuentas': [dict(r, saldo=str(r['saldo'])) for r in sorted(cuentas.values(), key=lambda r: (r['empresa_nombre'], r['cuenta']))],
        'proyectos': [dict(r, valor=str(r['valor'])) for r in sorted(proyectos.values(), key=lambda r: r['proyecto'])],
        'estados': dict(estados),
        'total_andina': str(sum((l.saldo_andina for l in lineas), ZERO)),
        'total_contable': str(sum((l.saldo_contable for l in lineas), ZERO)),
    }


def ejecutar(conciliacion, usar_cache=False):
    """Calcula y guarda una línea por tercero. Conserva la revisión y notas de una ejecución anterior."""
    balances, lineas, catalogo = calcular(conciliacion, usar_cache=usar_cache)
    previas = {p.identificacion: p for p in conciliacion.lineas.exclude(revision=ConciliacionLinea.REVISION_PENDIENTE, nota='')}
    for l in lineas:
        l.conciliacion = conciliacion
        p = previas.get(l.identificacion)
        if p:
            l.revision, l.nota, l.revisado_por_id, l.revisado_en = p.revision, p.nota, p.revisado_por_id, p.revisado_en
    fuentes = list(conciliacion.fuentes.all())
    with transaction.atomic():
        conciliacion.lineas.all().delete()
        ConciliacionLinea.objects.bulk_create(lineas, batch_size=500)
        conciliacion.resumen = dict(
            _resumen(lineas, balances, fuentes), calculado_en=timezone.now().isoformat(),
            catalogo=sorted(catalogo.values(), key=lambda c: (c['empresa_nombre'], c['cuenta'])),
        )
        conciliacion.save(update_fields=['resumen', 'updated_at'])
    return conciliacion
