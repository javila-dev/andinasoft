"""Expediente interno de servicio al cliente: ficha y dashboard del gestor."""
import datetime

from django.db.models import Max, Sum, Q
from django.utils import timezone

from crm.compromiso_tipos import TIPO_CHOICES, resumen_linea, tipo_label
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
    if not cliente_id:
        return '/servicio_cliente/dashboard'
    url = f'/servicio_cliente/cliente/{cliente_id}'
    qs = []
    if proyecto:
        qs.append(f'proyecto={proyecto}')
    if adj:
        qs.append(f'adj={adj}')
    if qs:
        url += '?' + '&'.join(qs)
    return url


def negocios_de_cliente(cliente_id, proyectos=None):
    cliente_id = str(cliente_id).strip()
    out = []
    for proyecto in proyectos or []:
        try:
            adjs = list(
                titulares_por_adj.objects.using(proyecto).filter(
                    Q(IdTercero1=cliente_id) |
                    Q(IdTercero2=cliente_id) |
                    Q(IdTercero3=cliente_id) |
                    Q(IdTercero4=cliente_id)
                ).values_list('adj', flat=True)
            )
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
    cliente = clientes.objects.filter(pk=cliente_id).first()
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


def dashboard_sac(user, *, proyecto=None, tipo='', today=None):
    today = today or timezone.localdate()
    semana = today + datetime.timedelta(days=7)
    proyectos = proyectos_accesibles(user)
    if proyecto:
        if proyecto not in proyectos and not user.is_superuser:
            proyectos = []
        else:
            proyectos = [proyecto]

    reuniones_qs = ActaReunion.objects.filter(fecha_reunion=today).exclude(estado='Cancelada')
    reuniones_semana = ActaReunion.objects.filter(
        fecha_reunion__gte=today, fecha_reunion__lte=semana
    ).exclude(estado='Cancelada')
    comps_qs = CompromisoActa.objects.exclude(estado__in=['Cumplido', 'Cancelado']).select_related(
        'responsable', 'acta', 'acta__cliente'
    )
    if proyecto:
        reuniones_qs = reuniones_qs.filter(proyecto_id=proyecto)
        reuniones_semana = reuniones_semana.filter(proyecto_id=proyecto)
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
        'reuniones_semana': reuniones_semana.count(),
        'compromisos_hoy': len(comps_hoy),
        'compromisos_vencidos': len(comps_vencidos),
        'pqrs_abiertas': 0,
        'pqrs_vencidas': 0,
        'pqrs_juridica': 0,
        'entregas_vencidas': 0,
        'entregas_por_vencer': 0,
        'escrituras_pendientes': 0,
    }
    cola_hoy = []
    for c in comps_hoy[:8]:
        cola_hoy.append(_item(
            'compromiso', tipo_label(c.tipo), resumen_linea(c.tipo, c.detalle, c.titulo),
            cliente_id=c.acta.cliente_id or '',
            cliente=c.acta.cliente.nombrecompleto if c.acta.cliente_id else '',
            proyecto=c.acta.proyecto_id or '',
            adj=c.acta.adj or '',
            fecha=c.fecha_compromiso,
            acta_id=c.acta_id,
        ))
    for r in reuniones_qs.select_related('cliente')[:8]:
        cola_hoy.append(_item(
            'reunion', 'Reunion', r.asunto,
            cliente_id=r.cliente_id or '',
            cliente=r.cliente.nombrecompleto if r.cliente_id else '',
            proyecto=r.proyecto_id or '',
            adj=r.adj or '',
            fecha=r.fecha_reunion,
            acta_id=r.pk,
        ))

    cola_atrasados = []
    for c in comps_vencidos[:8]:
        cola_atrasados.append(_item(
            'compromiso', tipo_label(c.tipo), resumen_linea(c.tipo, c.detalle, c.titulo),
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
            _, pqrs_kpis = listar_pqrs(proy)
            kpis['pqrs_abiertas'] += pqrs_kpis['abiertas']
            kpis['pqrs_vencidas'] += pqrs_kpis['vencidas']
            kpis['pqrs_juridica'] += pqrs_kpis['juridica']
            vencidas_rows, _ = listar_pqrs(proy, vencimiento='vencidas')
            for row in vencidas_rows[:4]:
                cola_atrasados.append(_item(
                    'pqrs', 'PQRS', f"#{row['id']} {row['asunto']}",
                    cliente_id=row['cliente_id'] or '',
                    cliente=row['titular'],
                    proyecto=proy,
                    adj=row['adj'],
                    fecha=row['fecha_vencimiento'],
                    pqrs_id=row['id'],
                ))
        except Exception:
            pass
        try:
            rows = build_promesa_rows(proy)
        except Exception:
            rows = []
        for r in rows:
            cliente_id = r.get('cliente_id') or ''
            if r['estado_entrega'] == ESTADO_VENCIDO:
                kpis['entregas_vencidas'] += 1
                cola_atrasados.append(_item(
                    'entrega', 'Entrega', f"{r['inmueble']} vencida",
                    cliente_id=cliente_id,
                    cliente=r['titular'],
                    proyecto=proy,
                    adj=r['adj'],
                    fecha=r['fechaentrega'],
                    entrega_ui=r.get('entrega_ui'),
                ))
            elif r['estado_entrega'] == ESTADO_POR_VENCER:
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
            if not r.get('escritura_completa'):
                if paso != PromesaCumplimiento.PASO_PENDIENTE or r.get('fechaescritura'):
                    kpis['escrituras_pendientes'] += 1
                    if len(escrituras) < 8:
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
                        ))

    cola_atrasados = cola_atrasados[:12]
    return {
        'kpis': kpis,
        'hoy': cola_hoy[:10],
        'atrasados': cola_atrasados,
        'escrituras': escrituras,
        'proyectos': proyectos_accesibles(user),
        'proyecto': proyecto,
        'tipo': tipo,
        'tipos': TIPO_CHOICES,
        'today': today,
    }
