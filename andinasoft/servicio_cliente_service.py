"""Expediente interno de servicio al cliente: ficha y dashboard del gestor."""
from urllib.parse import quote, urlencode

from django.db.models import Max, Sum, Q
from django.db.models.functions import Trim
from django.utils import timezone

from crm.compromiso_tipos import TIPO_CHOICES, TIPO_OTRO, resumen_linea, tipo_label
from crm.models import ActaReunion, CompromisoActa
from andinasoft.models import clientes, PromesaCumplimiento
from andinasoft.pqrs_service import listar_pqrs, pqrs_de_adj
from andinasoft.presupuesto_cartera_service import proyectos_accesibles
from andinasoft.promesas_service import (
    ESTADO_POR_VENCER,
    ESTADO_VENCIDO,
    PASO_LABEL,
    build_promesa_rows,
    documentos_contrato,
    listar_otrosi,
    paso_index,
)
from andinasoft.shared_models import (
    Adjudicacion,
    Vista_Adjudicacion,
    saldos_adj,
    titulares_por_adj,
    timeline,
    Inmuebles,
)


def url_ficha(cliente_id, proyecto=None, adj=None):
    cliente_id = str(cliente_id or '').strip()
    if not cliente_id:
        return '/servicio_cliente/dashboard'
    url = '/servicio_cliente/cliente/%s' % quote(cliente_id, safe='')
    params = {}
    if proyecto:
        params['proyecto'] = proyecto
    if adj:
        params['adj'] = str(adj).strip()
    if params:
        url += '?' + urlencode(params)
    return url


def _cliente_por_id(cliente_id):
    cliente_id = str(cliente_id or '').strip()
    if not cliente_id:
        return None
    cliente = clientes.objects.filter(pk=cliente_id).first()
    if cliente:
        return cliente
    return clientes.objects.annotate(_tid=Trim('idTercero')).filter(_tid=cliente_id).first()


def _adjs_de_cliente(proyecto, cliente_id):
    base = titulares_por_adj.objects.using(proyecto)
    exacto = base.filter(
        Q(IdTercero1=cliente_id) |
        Q(IdTercero2=cliente_id) |
        Q(IdTercero3=cliente_id) |
        Q(IdTercero4=cliente_id)
    )
    adjs = list(exacto.values_list('adj', flat=True))
    if adjs:
        return adjs
    return list(
        base.annotate(
            t1=Trim('IdTercero1'),
            t2=Trim('IdTercero2'),
            t3=Trim('IdTercero3'),
            t4=Trim('IdTercero4'),
        ).filter(
            Q(t1=cliente_id) | Q(t2=cliente_id) | Q(t3=cliente_id) | Q(t4=cliente_id)
        ).values_list('adj', flat=True)
    )


def negocios_de_cliente(cliente_id, proyectos=None):
    cliente_id = str(cliente_id).strip()
    out = []
    for proyecto in proyectos or []:
        try:
            adjs = _adjs_de_cliente(proyecto, cliente_id)
        except Exception:
            continue
        for adj in adjs:
            vista = Vista_Adjudicacion.objects.using(proyecto).filter(IdAdjudicacion=adj).first()
            out.append({
                'proyecto': proyecto,
                'adj': adj,
                'inmueble': getattr(vista, 'Inmueble', None) or '',
                'estado': getattr(vista, 'Estado', None) or '',
            })
    return out


def _titulares_de_adj(proyecto, adj):
    """Todos los titulares del negocio (1 a 4), con nombre y documento."""
    out = []
    row = titulares_por_adj.objects.using(proyecto).filter(adj=adj).first()
    if row:
        pares = (
            (row.IdTercero1, row.titular1),
            (row.IdTercero2, row.titular2),
            (row.IdTercero3, row.titular3),
            (row.IdTercero4, row.titular4),
        )
        for i, (tid, nombre) in enumerate(pares, 1):
            tid = str(tid).strip() if tid else ''
            nombre = (nombre or '').strip()
            if not tid and not nombre:
                continue
            out.append({'nro': i, 'id': tid, 'nombre': nombre or tid, 'celular': '', 'email': ''})
    else:
        obj = Adjudicacion.objects.using(proyecto).filter(pk=adj).first()
        if not obj:
            return out
        for i, tid in enumerate((obj.idtercero1, obj.idtercero2, obj.idtercero3, obj.idtercero4), 1):
            tid = str(tid).strip() if tid else ''
            if not tid:
                continue
            out.append({'nro': i, 'id': tid, 'nombre': tid, 'celular': '', 'email': ''})
    ids = [t['id'] for t in out if t['id']]
    if ids:
        by_id = {str(c.pk).strip(): c for c in clientes.objects.filter(pk__in=ids)}
        for t in out:
            c = by_id.get(t['id'])
            if not c:
                continue
            t['nombre'] = c.nombrecompleto or t['nombre']
            t['celular'] = c.celular1 or ''
            t['email'] = c.email or ''
    return out


def _cartera_adj(proyecto, adj):
    vista = Vista_Adjudicacion.objects.using(proyecto).filter(IdAdjudicacion=adj).first()
    obj_adj = Adjudicacion.objects.using(proyecto).filter(pk=adj).first()
    saldos = saldos_adj.objects.using(proyecto).filter(adj=adj)
    capital_pagado = saldos.aggregate(total=Sum('rcdocapital')).get('total') or 0
    capital_pendiente = saldos.aggregate(total=Sum('saldocapital')).get('total') or 0
    saldos_mora = saldos.filter(saldocuota__gt=0)
    agg = saldos_mora.aggregate(
        dias=Max('diasmora'),
        int_mora=Sum('saldomora'),
        saldo_cuotas=Sum('saldocuota'),
    )
    inmueble = None
    if obj_adj and obj_adj.idinmueble:
        inmueble = Inmuebles.objects.using(proyecto).filter(pk=obj_adj.idinmueble).first()
    fecha_contrato = getattr(obj_adj, 'fechacontrato', None) if obj_adj else None
    if not fecha_contrato:
        fecha_contrato = getattr(vista, 'FechaContrato', None)
    return {
        'adj_id': adj,
        'proyecto': proyecto,
        'estado': getattr(vista, 'Estado', None) or (getattr(obj_adj, 'estado', None) if obj_adj else None),
        'inmueble': getattr(vista, 'Inmueble', None) or (getattr(inmueble, 'idinmueble', '') if inmueble else ''),
        'capital_pagado': capital_pagado,
        'capital_pendiente': capital_pendiente,
        'dias_mora': agg.get('dias') or 0,
        'total_mora': (agg.get('saldo_cuotas') or 0) + (agg.get('int_mora') or 0),
        'cuotas_en_mora': saldos_mora.count(),
        'fecha_contrato': fecha_contrato,
        'estado_cuenta_url': f'/andinasoftajx/estadodecuenta?proyecto={proyecto}&adj={adj}',
    }


def _compromiso_card(comp):
    return {
        'id': comp.pk,
        'tipo': comp.tipo,
        'tipo_label': tipo_label(comp.tipo),
        'titulo': comp.titulo,
        'resumen': resumen_linea(comp.tipo, comp.detalle, comp.titulo),
        'estado': comp.estado,
        'fecha_compromiso': comp.fecha_compromiso,
        'responsable': comp.responsable.get_full_name() or comp.responsable.username,
        'acta_id': comp.acta_id,
        'cliente_id': comp.acta.cliente_id,
        'proyecto': comp.acta.proyecto_id,
        'adj': comp.acta.adj or '',
        'href': url_ficha(comp.acta.cliente_id, comp.acta.proyecto_id, comp.acta.adj),
    }


def ficha_cliente(cliente_id, user, *, proyecto=None, adj=None):
    cliente_id = str(cliente_id or '').strip()
    adj = str(adj).strip() if adj else adj
    cliente = _cliente_por_id(cliente_id)
    if not cliente:
        return None
    proyectos = proyectos_accesibles(user)
    if proyecto:
        if user.is_superuser or proyecto in proyectos:
            proyectos = [proyecto]
        else:
            proyectos = []
    negocios = negocios_de_cliente(cliente_id, proyectos)
    seleccionado = None
    if adj and proyecto:
        seleccionado = next((n for n in negocios if n['adj'] == adj and n['proyecto'] == proyecto), None)
    if not seleccionado and negocios:
        seleccionado = negocios[0]
        proyecto = seleccionado['proyecto']
        adj = seleccionado['adj']
    cartera = _cartera_adj(proyecto, adj) if proyecto and adj else None
    titulares = _titulares_de_adj(proyecto, adj) if proyecto and adj else []
    actas = ActaReunion.objects.filter(cliente_id=cliente_id).select_related('proyecto', 'lider_reunion')
    if proyecto:
        actas = actas.filter(proyecto_id=proyecto)
    actas = list(actas.order_by('-fecha_reunion', '-id_acta')[:15])
    comps = CompromisoActa.objects.filter(
        acta__cliente_id=cliente_id,
    ).exclude(estado__in=['Cumplido', 'Cancelado']).select_related('responsable', 'acta')
    if proyecto:
        comps = comps.filter(acta__proyecto_id=proyecto)
    compromisos = [_compromiso_card(c) for c in comps.order_by('fecha_compromiso')[:20]]
    pqrs = pqrs_de_adj(proyecto, adj) if proyecto and adj else []
    promesa = None
    otrosi_historial = []
    documentos_promesa = []
    if proyecto and adj:
        rows = [r for r in build_promesa_rows(proyecto) if r['adj'] == adj]
        promesa = rows[0] if rows else None
        otrosi_historial = listar_otrosi(proyecto, adj)
        documentos_promesa = documentos_contrato(proyecto, adj)
    hist = []
    if proyecto and adj:
        for fecha, accion, usuario in timeline.objects.using(proyecto).filter(adj=adj).order_by('-fecha', '-id_line').values_list('fecha', 'accion', 'usuario')[:12]:
            hist.append({'fecha': fecha, 'texto': accion, 'usuario': usuario, 'tipo': 'timeline'})
    return {
        'cliente': cliente,
        'negocios': negocios,
        'proyecto': proyecto,
        'adj': adj,
        'cartera': cartera,
        'titulares': titulares,
        'actas': actas,
        'compromisos': compromisos,
        'pqrs': pqrs,
        'promesa': promesa,
        'otrosi_historial': otrosi_historial,
        'documentos_promesa': documentos_promesa,
        'puede_gestionar_promesa': bool(
            user and (user.is_superuser or user.has_perm('andinasoft.change_promesas'))
        ),
        'historial': hist,
        'pasos_escritura': [
            (codigo, label)
            for codigo, label in PromesaCumplimiento.PASO_CHOICES
            if codigo != PromesaCumplimiento.PASO_PENDIENTE
        ],
    }


CHIP_SLUG = {
    'Reunion': 'reunion',
    'PQRS': 'pqrs',
    'Entrega': 'entrega',
    'Escritura': 'escritura',
    'Pendiente': 'pendiente',
    'Firma cliente': 'firma-cliente',
    'Factura notaria': 'factura',
    'Firma empresa': 'firma-empresa',
    'Carga escritura': 'carga',
    'Registro': 'registro',
    'Facturado': 'facturado',
    'Cambio a otro proyecto': 'cambio',
    'Envio de informacion': 'envio',
    'Cita / visita': 'cita',
    'Respuesta formal': 'respuesta',
    'Gestion interna': 'gestion',
    'Otro': 'otro',
    'Acta': 'acta',
}


def _chip_compromiso(tipo):
    """El tipo generico del acta se muestra como Acta, no como Otro."""
    if not tipo or tipo == TIPO_OTRO:
        return 'Acta'
    return tipo_label(tipo)


def _item(tipo_item, chip, titulo, *, cliente_id='', cliente='', proyecto='', adj='', fecha=None, **extra):
    href = '#'
    if extra.get('pqrs_id') and proyecto:
        href = f"/servicio_cliente/pqrs/{proyecto}/{extra['pqrs_id']}"
    elif cliente_id:
        href = url_ficha(cliente_id, proyecto, adj)
    elif proyecto and adj:
        href = f'/adjudicaciones/{proyecto}/{adj}/'
    data = {
        'tipo_item': tipo_item,
        'chip': chip,
        'chip_slug': CHIP_SLUG.get(chip, 'otro'),
        'titulo': titulo,
        'cliente_id': cliente_id,
        'cliente': cliente,
        'proyecto': proyecto,
        'adj': adj,
        'fecha': fecha,
        'href': href,
    }
    data.update(extra)
    return data


KPI_DETALLE = (
    'reuniones_hoy',
    'compromisos_hoy',
    'compromisos_vencidos',
    'pqrs_abiertas',
    'pqrs_vencidas',
    'pqrs_juridica',
    'entregas_vencidas',
    'escrituras_vencidas',
    'escrituras_tramite',
)
KPI_TITULO = {
    'reuniones_hoy': 'Reuniones hoy',
    'compromisos_hoy': 'Compromisos hoy',
    'compromisos_vencidos': 'Compromisos vencidos',
    'pqrs_abiertas': 'PQRS abiertas',
    'pqrs_vencidas': 'PQRS vencidas',
    'pqrs_juridica': 'Juridica',
    'entregas_vencidas': 'Entregas vencidas',
    'escrituras_vencidas': 'Escrituras vencidas',
    'escrituras_tramite': 'Escrituras en tramite',
}
DETALLE_PAGINA = 50


def _como_fecha(value):
    if value is None or value == '':
        return None
    if hasattr(value, 'hour'):
        return value.date()
    if hasattr(value, 'year'):
        return value
    return None


def _fecha_txt(fecha):
    fecha = _como_fecha(fecha)
    if fecha is not None:
        return fecha.strftime('%d/%m/%Y')
    return str(fecha) if fecha else ''


def _ordenar_recientes(items):
    """Lo que acaba de entrar queda primero. Sin fecha, al final."""
    def clave(item):
        fecha = _como_fecha(item.get('fecha'))
        ident = item.get('acta_id') or item.get('pqrs_id') or 0
        try:
            ident = int(ident)
        except (TypeError, ValueError):
            ident = 0
        if fecha is None:
            return (1, 0, 0)
        return (0, -fecha.toordinal(), -ident)
    return sorted(items, key=clave)


GRUPOS_ATRASADOS = (
    ('escritura', 'Escrituras'),
    ('entrega', 'Entregas'),
    ('pqrs', 'PQRS'),
    ('compromiso', 'Compromisos'),
)


def _clave_adj(item):
    adj = str(item.get('adj') or '').strip()
    if adj:
        return ('adj', item.get('proyecto') or '', adj)
    return (
        'solo',
        item.get('tipo_item') or '',
        item.get('pqrs_id') or item.get('acta_id') or item.get('titulo') or '',
    )


def _fila_adj(items):
    """Un negocio, con todos los avisos como badges."""
    primero = items[0]
    badges = []
    vistos = set()
    tipos = []
    icono = None
    fecha = None
    for item in items:
        chip = item.get('chip') or ''
        if chip and chip not in vistos:
            vistos.add(chip)
            badges.append({
                'chip': chip,
                'chip_slug': item.get('chip_slug') or 'otro',
            })
        tipo = item.get('tipo_item') or ''
        if tipo and tipo not in tipos:
            tipos.append(tipo)
        if icono is None and (item.get('entrega_ui') or item.get('pasos_ui')):
            icono = item
        dia = _como_fecha(item.get('fecha'))
        if dia and (fecha is None or dia > fecha):
            fecha = dia
    return {
        'href': primero.get('href') or '#',
        'cliente': primero.get('cliente') or '',
        'proyecto': primero.get('proyecto') or '',
        'adj': str(primero.get('adj') or '').strip(),
        'titulo': primero.get('titulo') or '',
        'fecha': fecha,
        'badges': badges,
        'tipos': tipos,
        'entrega_ui': icono.get('entrega_ui') if icono else None,
        'pasos_ui': None if (icono and icono.get('entrega_ui')) else (icono.get('pasos_ui') if icono else None),
    }


def _agrupar_por_adj(items):
    """El negocio mas reciente primero. Cada ADJ aparece una sola vez."""
    grupos = {}
    orden = []
    for item in _ordenar_recientes(items):
        clave = _clave_adj(item)
        if clave not in grupos:
            grupos[clave] = []
            orden.append(clave)
        grupos[clave].append(item)
    return [_fila_adj(grupos[clave]) for clave in orden]


def _filtros_atrasados(filas):
    conteo = {}
    for fila in filas:
        for tipo in fila.get('tipos') or []:
            conteo[tipo] = conteo.get(tipo, 0) + 1
    filtros = []
    for clave, titulo in GRUPOS_ATRASADOS:
        total = conteo.get(clave) or 0
        if total:
            filtros.append({'clave': clave, 'titulo': titulo, 'total': total})
    return filtros


def _ordenar_tramite(items):
    """Entra al tramite al firmar el cliente: la firma mas nueva va primero."""
    def clave(item):
        dias = item.get('dias_firma')
        if dias is None:
            return (1, 0)
        return (0, dias)
    return sorted(items, key=clave)


def _coincide_busqueda(item, q):
    q = (q or '').strip().lower()
    if not q:
        return True
    return q in str(item.get('adj') or '').lower() or q in (item.get('cliente') or '').lower()


def _modal_item(item):
    extra = ''
    if item.get('dias_firma') is not None:
        n = item['dias_firma']
        extra = '1 dia desde la firma del cliente' if n == 1 else '%s dias desde la firma del cliente' % n
        if item.get('alerta_registro'):
            extra += '. Mas de un mes sin firma de la empresa.'
    return {
        'chip': item.get('chip') or '',
        'chip_slug': item.get('chip_slug') or 'otro',
        'titulo': item.get('titulo') or '',
        'cliente': item.get('cliente') or '',
        'proyecto': item.get('proyecto') or '',
        'adj': item.get('adj') or '',
        'fecha': _fecha_txt(item.get('fecha')),
        'href': item.get('href') or '#',
        'extra': extra,
    }


def clasificar_promesa(r):
    """Estado de entrega/escritura de una fila de build_promesa_rows (reglas del tablero SAC)."""
    firma_cliente = any(
        s.get('codigo') == PromesaCumplimiento.PASO_FIRMA_CLIENTE and s.get('estado') == 'done'
        for s in (r.get('pasos_ui') or [])
    )
    return {
        'entrega_vencida': r['estado_entrega'] == ESTADO_VENCIDO,
        'entrega_por_vencer': r['estado_entrega'] == ESTADO_POR_VENCER,
        'escritura_tramite': not r.get('escritura_completa') and firma_cliente,
        'escritura_vencida': not firma_cliente and r.get('estado_escritura') == ESTADO_VENCIDO,
    }


def dashboard_sac(user, *, proyecto=None, tipo='', today=None):
    today = today or timezone.localdate()
    proyectos = proyectos_accesibles(user)
    if proyecto:
        if proyecto not in proyectos and not user.is_superuser:
            proyectos = []
        else:
            proyectos = [proyecto]

    reuniones_qs = ActaReunion.objects.filter(fecha_reunion=today).exclude(estado='Cancelada')
    comps_qs = CompromisoActa.objects.exclude(estado__in=['Cumplido', 'Cancelado']).select_related(
        'responsable', 'acta', 'acta__cliente'
    )
    if proyecto:
        reuniones_qs = reuniones_qs.filter(proyecto_id=proyecto)
        comps_qs = comps_qs.filter(acta__proyecto_id=proyecto)
    if tipo:
        comps_qs = comps_qs.filter(tipo=tipo)
    if not user.is_superuser:
        comps_mios = comps_qs.filter(responsable=user)
    else:
        comps_mios = comps_qs

    comps_hoy = [c for c in comps_mios if c.fecha_compromiso == today]
    comps_vencidos = [c for c in comps_mios if c.fecha_compromiso and c.fecha_compromiso < today]
    kpis = {
        'reuniones_hoy': reuniones_qs.count(),
        'compromisos_hoy': len(comps_hoy),
        'compromisos_vencidos': len(comps_vencidos),
        'pqrs_abiertas': 0,
        'pqrs_vencidas': 0,
        'pqrs_juridica': 0,
        'entregas_vencidas': 0,
        'entregas_por_vencer': 0,
        'escrituras_vencidas': 0,
        'escrituras_pendientes': 0,
    }
    fuentes = {key: [] for key in KPI_DETALLE}
    for c in comps_hoy:
        fuentes['compromisos_hoy'].append(_item(
            'compromiso', _chip_compromiso(c.tipo), resumen_linea(c.tipo, c.detalle, c.titulo),
            cliente_id=c.acta.cliente_id or '',
            cliente=c.acta.cliente.nombrecompleto if c.acta.cliente_id else '',
            proyecto=c.acta.proyecto_id or '',
            adj=c.acta.adj or '',
            fecha=c.fecha_compromiso,
            acta_id=c.acta_id,
        ))
    for r in reuniones_qs.select_related('cliente'):
        fuentes['reuniones_hoy'].append(_item(
            'reunion', 'Reunion', r.asunto,
            cliente_id=r.cliente_id or '',
            cliente=r.cliente.nombrecompleto if r.cliente_id else '',
            proyecto=r.proyecto_id or '',
            adj=r.adj or '',
            fecha=r.fecha_reunion,
            acta_id=r.pk,
        ))
    for c in comps_vencidos:
        fuentes['compromisos_vencidos'].append(_item(
            'compromiso', _chip_compromiso(c.tipo), resumen_linea(c.tipo, c.detalle, c.titulo),
            cliente_id=c.acta.cliente_id or '',
            cliente=c.acta.cliente.nombrecompleto if c.acta.cliente_id else '',
            proyecto=c.acta.proyecto_id or '',
            adj=c.acta.adj or '',
            fecha=c.fecha_compromiso,
            acta_id=c.acta_id,
        ))

    cola_atrasados = []
    for c in comps_vencidos:
        cola_atrasados.append(_item(
            'compromiso', _chip_compromiso(c.tipo), resumen_linea(c.tipo, c.detalle, c.titulo),
            cliente_id=c.acta.cliente_id or '',
            cliente=c.acta.cliente.nombrecompleto if c.acta.cliente_id else '',
            proyecto=c.acta.proyecto_id or '',
            adj=c.acta.adj or '',
            fecha=c.fecha_compromiso,
            acta_id=c.acta_id,
        ))

    escrituras = []
    for proy in proyectos:
        try:
            pqrs_rows, pqrs_kpis = listar_pqrs(proy)
            kpis['pqrs_abiertas'] += pqrs_kpis['abiertas']
            kpis['pqrs_vencidas'] += pqrs_kpis['vencidas']
            kpis['pqrs_juridica'] += pqrs_kpis['juridica']
            for row in pqrs_rows:
                item_pqrs = _item(
                    'pqrs', 'PQRS', f"#{row['id']} {row['asunto']}",
                    cliente_id=row['cliente_id'] or '',
                    cliente=row['titular'],
                    proyecto=proy,
                    adj=row['adj'],
                    fecha=row['fecha_vencimiento'],
                    pqrs_id=row['id'],
                )
                if row.get('estado') != 'Cerrado':
                    fuentes['pqrs_abiertas'].append(item_pqrs)
                if (row.get('plazo') or {}).get('codigo') == 'vencida':
                    fuentes['pqrs_vencidas'].append(item_pqrs)
                    cola_atrasados.append(item_pqrs)
                if row.get('relevante_juridica') and row.get('estado') != 'Cerrado':
                    fuentes['pqrs_juridica'].append(item_pqrs)
        except Exception:
            pass
        try:
            rows = build_promesa_rows(proy)
        except Exception:
            rows = []
        for r in rows:
            cliente_id = r.get('cliente_id') or ''
            estado = clasificar_promesa(r)
            if estado['entrega_vencida']:
                kpis['entregas_vencidas'] += 1
                item_entrega = _item(
                    'entrega', 'Entrega', f"{r['inmueble']} vencida",
                    cliente_id=cliente_id,
                    cliente=r['titular'],
                    proyecto=proy,
                    adj=r['adj'],
                    fecha=r['fechaentrega'],
                    entrega_ui=r.get('entrega_ui'),
                )
                fuentes['entregas_vencidas'].append(item_entrega)
                cola_atrasados.append(item_entrega)
            elif estado['entrega_por_vencer']:
                kpis['entregas_por_vencer'] += 1
            paso = r.get('paso_escritura') or PromesaCumplimiento.PASO_PENDIENTE
            if r.get('factura_pendiente'):
                cola_atrasados.append(_item(
                    'escritura', 'Factura notaria',
                    f"{r['inmueble']} — cargar factura de notaria",
                    cliente_id=cliente_id,
                    cliente=r['titular'],
                    proyecto=proy,
                    adj=r['adj'],
                    fecha=r.get('fechaescritura'),
                    pasos_ui=r.get('pasos_ui'),
                    factura_pendiente=True,
                ))
            if r.get('carga_pendiente'):
                cola_atrasados.append(_item(
                    'escritura', 'Carga escritura',
                    f"{r['inmueble']} — cargar escritura",
                    cliente_id=cliente_id,
                    cliente=r['titular'],
                    proyecto=proy,
                    adj=r['adj'],
                    fecha=r.get('fechaescritura'),
                    pasos_ui=r.get('pasos_ui'),
                    carga_pendiente=True,
                ))
            if estado['escritura_tramite']:
                kpis['escrituras_pendientes'] += 1
                chip = PASO_LABEL.get(paso, paso)
                if r.get('factura_pendiente'):
                    chip = 'Factura notaria'
                elif r.get('carga_pendiente'):
                    chip = 'Carga escritura'
                escrituras.append(_item(
                    'escritura', chip,
                    f"{r['inmueble']} — {chip}",
                    cliente_id=cliente_id,
                    cliente=r['titular'],
                    proyecto=proy,
                    adj=r['adj'],
                    fecha=r['fechaescritura'],
                    paso=paso,
                    paso_idx=paso_index(paso),
                    pasos_ui=r.get('pasos_ui'),
                    pasos_linea=r.get('pasos_linea'),
                    pasos_rama=r.get('pasos_rama'),
                    paso_siguiente=r.get('paso_siguiente'),
                    dias_firma=r.get('dias_firma_cliente'),
                    alerta_registro=r.get('alerta_firma_empresa'),
                ))
            elif estado['escritura_vencida']:
                kpis['escrituras_vencidas'] += 1
                item_esc = _item(
                    'escritura', 'Escritura',
                    f"{r['inmueble']} vencida",
                    cliente_id=cliente_id,
                    cliente=r['titular'],
                    proyecto=proy,
                    adj=r['adj'],
                    fecha=r.get('fechaescritura'),
                    pasos_ui=r.get('pasos_ui'),
                )
                fuentes['escrituras_vencidas'].append(item_esc)
                cola_atrasados.append(item_esc)

    hoy_filas = _agrupar_por_adj(fuentes['compromisos_hoy'] + fuentes['reuniones_hoy'])[:10]
    atrasados_filas = _agrupar_por_adj(cola_atrasados)
    atrasados_filtros = _filtros_atrasados(atrasados_filas)
    escrituras = _ordenar_tramite(escrituras)
    fuentes['escrituras_tramite'] = list(escrituras)
    escrituras = escrituras[:8]
    for key in (
        'reuniones_hoy', 'compromisos_hoy', 'compromisos_vencidos',
        'pqrs_abiertas', 'pqrs_vencidas', 'pqrs_juridica',
        'entregas_vencidas', 'escrituras_vencidas',
    ):
        fuentes[key] = _ordenar_recientes(fuentes[key])
    kpis['vencidos_total'] = (
        kpis['compromisos_vencidos'] + kpis['pqrs_vencidas']
        + kpis['entregas_vencidas'] + kpis['escrituras_vencidas']
    )
    return {
        'kpis': kpis,
        'hoy': hoy_filas,
        'atrasados': atrasados_filas,
        'atrasados_filtros': atrasados_filtros,
        'atrasados_total': len(atrasados_filas),
        'escrituras': escrituras,
        'fuentes': fuentes,
        'proyectos': proyectos_accesibles(user),
        'proyecto': proyecto,
        'tipo': tipo,
        'tipos': tuple((value, 'Acta' if value == TIPO_OTRO else label) for value, label in TIPO_CHOICES),
        'today': today,
    }


def detalle_kpi_sac(user, kpi, *, proyecto=None, tipo='', q='', offset=0, limit=DETALLE_PAGINA, today=None):
    if kpi not in KPI_DETALLE:
        raise ValueError(kpi)
    data = dashboard_sac(user, proyecto=proyecto, tipo=tipo or '', today=today)
    rows = [r for r in data['fuentes'].get(kpi, []) if _coincide_busqueda(r, q)]
    offset = max(0, int(offset or 0))
    limit = DETALLE_PAGINA if not limit else min(int(limit), DETALLE_PAGINA)
    page = rows[offset:offset + limit]
    return {
        'titulo': KPI_TITULO[kpi],
        'total': len(rows),
        'offset': offset,
        'has_more': offset + limit < len(rows),
        'items': [_modal_item(r) for r in page],
    }
