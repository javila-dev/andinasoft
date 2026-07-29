"""
Listas y estados operativos del modulo Estados de Promesas.

La fuente de verdad de la lista son las adjudicaciones activas
(Aprobado / Pagado). La tabla `promesas` aporta fechas y flags
operativos; si falta, se crea al primer cambio (ensure_promesa).
"""
import datetime
from andinasoft.models import clientes, PromesaCumplimiento
from andinasoft.shared_models import Adjudicacion, Promesas

DIAS_POR_VENCER = 30

ESTADOS_ACTIVOS = ('Aprobado', 'Pagado')

ESTADO_CUMPLIDO = 'cumplido'
ESTADO_VENCIDO = 'vencido'
ESTADO_POR_VENCER = 'por_vencer'
ESTADO_AL_DIA = 'al_dia'
ESTADO_SIN_FECHA = 'sin_fecha'

ESTADO_CSS = {
    ESTADO_CUMPLIDO: 'table-secondary',
    ESTADO_VENCIDO: 'table-danger',
    ESTADO_POR_VENCER: 'table-warning',
    ESTADO_AL_DIA: 'table-success',
    ESTADO_SIN_FECHA: '',
}

ESTADO_BADGE = {
    ESTADO_CUMPLIDO: 'badge-secondary',
    ESTADO_VENCIDO: 'badge-danger',
    ESTADO_POR_VENCER: 'badge-warning',
    ESTADO_AL_DIA: 'badge-success',
    ESTADO_SIN_FECHA: 'badge-light',
}

ESTADO_LABEL = {
    ESTADO_CUMPLIDO: 'Cumplido',
    ESTADO_VENCIDO: 'Vencido',
    ESTADO_POR_VENCER: 'Por vencer',
    ESTADO_AL_DIA: 'Al dia',
    ESTADO_SIN_FECHA: 'Sin fecha',
}


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return None


def estado_fecha(fecha, cumplido, hoy=None, dias_por_vencer=DIAS_POR_VENCER):
    if cumplido:
        return ESTADO_CUMPLIDO
    fecha = _as_date(fecha)
    if not fecha:
        return ESTADO_SIN_FECHA
    hoy = hoy or datetime.date.today()
    days = (fecha - hoy).days
    if days < 0:
        return ESTADO_VENCIDO
    if days <= dias_por_vencer:
        return ESTADO_POR_VENCER
    return ESTADO_AL_DIA


def _boolish(value):
    if value is True or value == 1 or value == '1':
        return True
    if value is False or value == 0 or value == '0' or value is None:
        return False
    return bool(value)


def ensure_promesa(proyecto, adj, usuario=None):
    """
    Obtiene o crea la fila operativa en `promesas` para una adjudicacion.
    No inventa fechas de entrega/escritura; solo semilla basica desde el adj.
    """
    qs = Promesas.objects.using(proyecto).filter(idadjudicacion=adj)
    if qs.exists():
        return qs.get()

    obj_adj = Adjudicacion.objects.using(proyecto).get(idadjudicacion=adj)
    return Promesas.objects.using(proyecto).create(
        idadjudicacion=adj,
        nropromesa=obj_adj.contrato or '',
        fechapromesa=_as_date(obj_adj.fechacontrato),
        formapago=obj_adj.formapago or '',
        estado=obj_adj.estado or '',
        ciudad=obj_adj.oficina or '',
        usuariocrea=str(usuario) if usuario else '',
        entregado=False,
        escriturado=False,
    )


def build_promesa_rows(proyecto):
    """Lista enriquecida: adjudicaciones activas + datos de promesa si existen."""
    hoy = datetime.date.today()
    rows = []

    adjs = list(
        Adjudicacion.objects.using(proyecto)
        .filter(estado__in=ESTADOS_ACTIVOS)
        .order_by('idadjudicacion')
    )
    if not adjs:
        return rows

    adj_ids = [a.idadjudicacion for a in adjs]
    promesas = {
        p.idadjudicacion: p
        for p in Promesas.objects.using(proyecto).filter(idadjudicacion__in=adj_ids)
    }
    cumplimientos = {
        c.adj: c
        for c in PromesaCumplimiento.objects.filter(proyecto_id=proyecto, adj__in=adj_ids)
    }

    tercero_ids = set()
    for a in adjs:
        for tid in (a.idtercero1, a.idtercero2, a.idtercero3, a.idtercero4):
            if tid:
                tercero_ids.add(str(tid).strip())
    clientes_map = {}
    if tercero_ids:
        # MySQL CHAR puede devolver el PK con espacios; clave normalizada para el lookup
        for c in clientes.objects.filter(idTercero__in=list(tercero_ids)):
            clientes_map[str(c.idTercero).strip()] = c

    for adj in adjs:
        p = promesas.get(adj.idadjudicacion)
        cump = cumplimientos.get(adj.idadjudicacion)
        titular = ''
        tid1 = str(adj.idtercero1).strip() if adj.idtercero1 else ''
        if tid1 and tid1 in clientes_map:
            titular = clientes_map[tid1].nombrecompleto or ''
        inmueble_txt = (adj.idinmueble or '').strip()

        fechapromesa = _as_date(p.fechapromesa) if p else _as_date(adj.fechacontrato)
        fechaentrega = _as_date(p.fechaentrega) if p else None
        fechaescritura = _as_date(p.fechaescritura) if p else None
        entregado = _boolish(p.entregado) if p else False
        escriturado = _boolish(p.escriturado) if p else False
        fecha_entrega_real = _as_date(cump.fecha_entrega_real) if cump else None
        fecha_escritura_real = _as_date(cump.fecha_escritura_real) if cump else None

        est_entrega = estado_fecha(fechaentrega, entregado, hoy=hoy)
        est_escritura = estado_fecha(fechaescritura, escriturado, hoy=hoy)

        prioridad = {
            ESTADO_VENCIDO: 0,
            ESTADO_POR_VENCER: 1,
            ESTADO_SIN_FECHA: 2,
            ESTADO_AL_DIA: 3,
            ESTADO_CUMPLIDO: 4,
        }
        peor = est_entrega if prioridad[est_entrega] <= prioridad[est_escritura] else est_escritura

        rows.append({
            'adj': adj.idadjudicacion,
            'nropromesa': (p.nropromesa if p and p.nropromesa else None) or (adj.contrato or ''),
            'titular': titular,
            'inmueble': inmueble_txt,
            'oficina': adj.oficina or (p.ciudad if p else '') or '',
            'estado': adj.estado or '',
            'tipocontrato': adj.tipocontrato or '',
            'tiene_promesa': p is not None,
            'fechapromesa': fechapromesa,
            'fechaentrega': fechaentrega,
            'fechaescritura': fechaescritura,
            'entregado': entregado,
            'escriturado': escriturado,
            'fecha_entrega_real': fecha_entrega_real,
            'fecha_escritura_real': fecha_escritura_real,
            'estado_entrega': est_entrega,
            'estado_escritura': est_escritura,
            'estado_entrega_label': ESTADO_LABEL[est_entrega],
            'estado_escritura_label': ESTADO_LABEL[est_escritura],
            'estado_entrega_badge': ESTADO_BADGE[est_entrega],
            'estado_escritura_badge': ESTADO_BADGE[est_escritura],
            'row_class': ESTADO_CSS[peor],
            'formaci': (p.formaci if p else '') or '',
            'formasaldo': (p.formasaldo if p else '') or '',
            'formapago': (p.formapago if p else None) or (adj.formapago or ''),
            'observaciones': (p.observaciones if p else '') or '',
            'ciudad': (p.ciudad if p else None) or (adj.oficina or ''),
            # Fechas iniciales solo si aún no hay entrega ni escritura; luego cambios van por otrosi
            'puede_editar_fechas': not fechaentrega and not fechaescritura,
        })

    rows.sort(key=lambda r: (r['fechaentrega'] or datetime.date.max, r['adj']))
    return rows


def filter_rows(rows, *, entrega_estado=None, escritura_estado=None):
    out = rows
    if entrega_estado:
        out = [r for r in out if r['estado_entrega'] == entrega_estado]
    if escritura_estado:
        out = [r for r in out if r['estado_escritura'] == escritura_estado]
    return out
