"""
Listas y estados operativos del modulo Estados de Promesas.

La fuente de verdad de la lista son las adjudicaciones activas
(Aprobado / Pagado). La tabla `promesas` aporta fechas y flags
operativos; si falta, se crea al primer cambio (ensure_promesa).
"""
import datetime
from andinasoft.models import PromesaCumplimiento, PromesaHito, PromesaOtrosi, clientes
from andinasoft.shared_models import Adjudicacion, Promesas, timeline, ventas_nuevas

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

PASO_LABEL = dict(PromesaCumplimiento.PASO_CHOICES)
PASO_FECHA_FIELD = {
    PromesaCumplimiento.PASO_FIRMA_CLIENTE: 'fecha_firma_cliente',
    PromesaCumplimiento.PASO_FACTURA_NOTARIA: 'fecha_factura_notaria',
    PromesaCumplimiento.PASO_FIRMA_EMPRESA: 'fecha_firma_empresa',
    PromesaCumplimiento.PASO_CARGA: 'fecha_carga_escritura',
    PromesaCumplimiento.PASO_REGISTRO: 'fecha_registro',
    PromesaCumplimiento.PASO_FACTURADO: 'fecha_facturado',
}
PASOS_ARCHIVO = {
    PromesaCumplimiento.PASO_FACTURA_NOTARIA: (
        'Cargue el PDF de la factura de notaria',
        'Factura notaria',
    ),
    PromesaCumplimiento.PASO_CARGA: (
        'Cargue el PDF de la escritura',
        'Escritura',
    ),
}
PASOS_LINEA_UI = (
    (PromesaCumplimiento.PASO_FIRMA_CLIENTE, 'Firma cliente', 'fa-pen', False),
    (PromesaCumplimiento.PASO_FACTURA_NOTARIA, 'Factura notaria', 'fa-file-invoice', True),
    (PromesaCumplimiento.PASO_FIRMA_EMPRESA, 'Firma empresa', 'fa-building', False),
)
PASOS_RAMA_UI = (
    (PromesaCumplimiento.PASO_CARGA, 'Carga', 'fa-file-upload', True),
    (PromesaCumplimiento.PASO_REGISTRO, 'Registro', 'fa-stamp', False),
    (PromesaCumplimiento.PASO_FACTURADO, 'Facturado', 'fa-file-invoice-dollar', False),
)
REQUISITOS_PASO = {
    PromesaCumplimiento.PASO_FIRMA_CLIENTE: set(),
    PromesaCumplimiento.PASO_FACTURA_NOTARIA: {PromesaCumplimiento.PASO_FIRMA_CLIENTE},
    PromesaCumplimiento.PASO_FIRMA_EMPRESA: {PromesaCumplimiento.PASO_FACTURA_NOTARIA},
    PromesaCumplimiento.PASO_CARGA: {PromesaCumplimiento.PASO_FIRMA_EMPRESA},
    PromesaCumplimiento.PASO_REGISTRO: {PromesaCumplimiento.PASO_FIRMA_EMPRESA},
    PromesaCumplimiento.PASO_FACTURADO: {PromesaCumplimiento.PASO_FIRMA_EMPRESA},
}


def paso_index(paso):
    try:
        return PromesaCumplimiento.PASO_ORDEN.index(paso or PromesaCumplimiento.PASO_PENDIENTE)
    except ValueError:
        return 0


def hechos_hasta(actual):
    """Compat: infiere pasos hechos desde un puntero lineal viejo."""
    actual = actual or PromesaCumplimiento.PASO_PENDIENTE
    if actual == PromesaCumplimiento.PASO_PENDIENTE:
        return set()
    if actual == PromesaCumplimiento.PASO_FIRMA_CLIENTE:
        return {PromesaCumplimiento.PASO_FIRMA_CLIENTE}
    if actual == PromesaCumplimiento.PASO_FACTURA_NOTARIA:
        return {
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
        }
    if actual == PromesaCumplimiento.PASO_FIRMA_EMPRESA:
        return {
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
        }
    if actual == PromesaCumplimiento.PASO_CARGA:
        return {
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
            PromesaCumplimiento.PASO_CARGA,
        }
    if actual == PromesaCumplimiento.PASO_REGISTRO:
        return {
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
            PromesaCumplimiento.PASO_REGISTRO,
        }
    if actual == PromesaCumplimiento.PASO_FACTURADO:
        return {
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
            PromesaCumplimiento.PASO_REGISTRO,
            PromesaCumplimiento.PASO_FACTURADO,
        }
    return set()


def hechos_from_cumplimiento(cump):
    hechos = set()
    if not cump:
        return hechos
    if cump.fecha_firma_cliente:
        hechos.add(PromesaCumplimiento.PASO_FIRMA_CLIENTE)
    if getattr(cump, 'fecha_factura_notaria', None) or (getattr(cump, 'documento_factura_notaria', '') or ''):
        hechos.add(PromesaCumplimiento.PASO_FACTURA_NOTARIA)
    if cump.fecha_firma_empresa:
        hechos.add(PromesaCumplimiento.PASO_FIRMA_EMPRESA)
    if getattr(cump, 'fecha_carga_escritura', None) or (getattr(cump, 'documento_escritura', '') or ''):
        hechos.add(PromesaCumplimiento.PASO_CARGA)
    if cump.fecha_registro:
        hechos.add(PromesaCumplimiento.PASO_REGISTRO)
    if cump.fecha_facturado:
        hechos.add(PromesaCumplimiento.PASO_FACTURADO)
    tiene_fechas = bool(hechos)
    if not tiene_fechas:
        hechos |= hechos_hasta(cump.paso_escritura_actual)
    else:
        actual = cump.paso_escritura_actual or PromesaCumplimiento.PASO_PENDIENTE
        if actual in (
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
            PromesaCumplimiento.PASO_CARGA,
            PromesaCumplimiento.PASO_REGISTRO,
            PromesaCumplimiento.PASO_FACTURADO,
        ):
            hechos.add(PromesaCumplimiento.PASO_FIRMA_CLIENTE)
            hechos.add(PromesaCumplimiento.PASO_FACTURA_NOTARIA)
            hechos.add(PromesaCumplimiento.PASO_FIRMA_EMPRESA)
        elif actual == PromesaCumplimiento.PASO_FACTURA_NOTARIA:
            hechos.add(PromesaCumplimiento.PASO_FIRMA_CLIENTE)
            hechos.add(PromesaCumplimiento.PASO_FACTURA_NOTARIA)
        elif actual == PromesaCumplimiento.PASO_FIRMA_CLIENTE:
            hechos.add(PromesaCumplimiento.PASO_FIRMA_CLIENTE)
    return hechos


def escritura_completa(hechos):
    return (
        PromesaCumplimiento.PASO_REGISTRO in hechos
        and PromesaCumplimiento.PASO_FACTURADO in hechos
    )


def resumen_paso(hechos):
    if escritura_completa(hechos):
        return PromesaCumplimiento.PASO_FACTURADO
    if PromesaCumplimiento.PASO_FIRMA_EMPRESA in hechos:
        if PromesaCumplimiento.PASO_CARGA not in hechos:
            return PromesaCumplimiento.PASO_CARGA
        if PromesaCumplimiento.PASO_REGISTRO not in hechos:
            return PromesaCumplimiento.PASO_REGISTRO
        return PromesaCumplimiento.PASO_FACTURADO
    if PromesaCumplimiento.PASO_FACTURA_NOTARIA in hechos:
        return PromesaCumplimiento.PASO_FACTURA_NOTARIA
    if PromesaCumplimiento.PASO_FIRMA_CLIENTE in hechos:
        return PromesaCumplimiento.PASO_FACTURA_NOTARIA
    return PromesaCumplimiento.PASO_PENDIENTE


def puede_avanzar_paso(actual, nuevo, *, hechos=None, es_superuser=False):
    """Firma cliente → firma empresa. Luego carga, registro y facturado son independientes."""
    if nuevo not in REQUISITOS_PASO:
        return False
    if hechos is None:
        hechos = hechos_hasta(actual)
    if nuevo in hechos:
        return False
    return REQUISITOS_PASO[nuevo].issubset(hechos)


def siguientes_pasos(hechos):
    return [
        codigo for codigo in (
            PromesaCumplimiento.PASO_FIRMA_CLIENTE,
            PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            PromesaCumplimiento.PASO_FIRMA_EMPRESA,
            PromesaCumplimiento.PASO_CARGA,
            PromesaCumplimiento.PASO_REGISTRO,
            PromesaCumplimiento.PASO_FACTURADO,
        )
        if puede_avanzar_paso(None, codigo, hechos=hechos)
    ]


def siguientes_detalle(hechos):
    out = []
    for codigo in siguientes_pasos(hechos):
        out.append({
            'codigo': codigo,
            'label': PASO_LABEL.get(codigo, codigo),
            'requiere_archivo': codigo in PASOS_ARCHIVO,
            'archivo_label': PASOS_ARCHIVO[codigo][1] if codigo in PASOS_ARCHIVO else '',
            'interno': codigo in (
                PromesaCumplimiento.PASO_CARGA,
                PromesaCumplimiento.PASO_FACTURA_NOTARIA,
            ),
        })
    return out


def nombre_documento_paso(paso, archivo):
    """Valida PDF y arma el nombre de archivo interno. '' si el paso no pide documento."""
    if paso not in PASOS_ARCHIVO:
        return ''
    msg, prefijo = PASOS_ARCHIVO[paso]
    if not archivo:
        raise ValueError(msg)
    name = str(getattr(archivo, 'name', '') or '')
    if not name.lower().endswith('.pdf'):
        raise ValueError('%s debe ser PDF' % prefijo)
    return '%s_%s' % (prefijo, datetime.datetime.today())


def siguiente_paso(actual, hechos=None):
    if hechos is None:
        hechos = hechos_hasta(actual)
    pendientes = siguientes_pasos(hechos)
    return pendientes[0] if pendientes else None


def _step_ui(codigo, label, icon, hechos, fechas, unlocked, interno=False):
    if codigo in hechos:
        estado = 'done'
    elif unlocked:
        estado = 'next'
    else:
        estado = 'locked'
    return {
        'codigo': codigo,
        'label': label,
        'icon': icon,
        'estado': estado,
        'fecha': fechas.get(codigo),
        'interno': interno,
    }


def pasos_escritura_ui(paso_actual=None, fechas=None, hechos=None):
    """Linea: firmas. Rama (tras firma empresa): carga interna, registro y facturado en paralelo."""
    fechas = fechas or {}
    if hechos is None:
        hechos = hechos_hasta(paso_actual)
    linea = []
    prev_done = True
    for codigo, label, icon, interno in PASOS_LINEA_UI:
        unlocked = prev_done and codigo not in hechos
        linea.append(_step_ui(codigo, label, icon, hechos, fechas, unlocked, interno=interno))
        prev_done = codigo in hechos
    rama_unlocked = PromesaCumplimiento.PASO_FIRMA_EMPRESA in hechos
    rama = []
    for codigo, label, icon, interno in PASOS_RAMA_UI:
        unlocked = rama_unlocked and codigo not in hechos
        rama.append(_step_ui(codigo, label, icon, hechos, fechas, unlocked, interno=interno))
    return linea, rama


def serialize_steps(steps):
    """Fechas a ISO para JSON (modales / AJAX)."""
    out = []
    for s in steps or []:
        fecha = s.get('fecha')
        if hasattr(fecha, 'strftime'):
            fecha_s = fecha.strftime('%Y-%m-%d')
        else:
            fecha_s = str(fecha) if fecha else ''
        item = {
            'codigo': s.get('codigo'),
            'label': s.get('label'),
            'icon': s.get('icon'),
            'estado': s.get('estado'),
            'fecha': fecha_s,
            'interno': bool(s.get('interno')),
        }
        out.append(item)
    return out


def pipeline_escritura(cump):
    hechos = hechos_from_cumplimiento(cump)
    fechas = {}
    if cump:
        for codigo, field in PASO_FECHA_FIELD.items():
            fechas[codigo] = getattr(cump, field, None)
    linea, rama = pasos_escritura_ui(hechos=hechos, fechas=fechas)
    siguientes = siguientes_detalle(hechos)
    paso = resumen_paso(hechos)
    next_paso = siguientes[0]['codigo'] if siguientes else None
    return {
        'paso': paso,
        'pasos_ui': linea + rama,
        'pasos_linea': linea,
        'pasos_rama': rama,
        'siguientes': siguientes,
        'paso_siguiente': next_paso,
        'paso_siguiente_label': PASO_LABEL.get(next_paso, '') if next_paso else '',
        'completa': escritura_completa(hechos),
        'carga_pendiente': (
            PromesaCumplimiento.PASO_FIRMA_EMPRESA in hechos
            and PromesaCumplimiento.PASO_CARGA not in hechos
        ),
        'factura_pendiente': (
            PromesaCumplimiento.PASO_FIRMA_CLIENTE in hechos
            and PromesaCumplimiento.PASO_FACTURA_NOTARIA not in hechos
        ),
        'hechos': hechos,
    }


def pasos_from_cumplimiento(cump):
    pipe = pipeline_escritura(cump)
    return pipe['paso'], pipe['pasos_ui']


def entrega_ui(fecha_pactada, entregado, fecha_real=None):
    """Pactada → Entregada. Sin fecha pactada no se puede marcar entregada."""
    pactada = {
        'codigo': 'pactada',
        'label': 'Pactada',
        'icon': 'fa-calendar-check',
        'estado': 'done' if fecha_pactada else 'next',
        'fecha': fecha_pactada,
    }
    if entregado:
        ent_estado = 'done'
    elif fecha_pactada:
        ent_estado = 'next'
    else:
        ent_estado = 'locked'
    entregada = {
        'codigo': 'entregada',
        'label': 'Entregada',
        'icon': 'fa-key',
        'estado': ent_estado,
        'fecha': fecha_real if entregado else None,
    }
    return [pactada, entregada]


def _as_date(value):
    if value is None or value == '':
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
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


def texto_forma_pago_venta(proyecto, contrato):
    """Texto automatico de forma CI / saldo, igual que en la impresion de venta."""
    if not contrato:
        return '', ''
    try:
        venta = ventas_nuevas.objects.using(proyecto).get(pk=contrato)
    except (ventas_nuevas.DoesNotExist, ValueError, TypeError):
        return '', ''
    try:
        fci, fsaldo = venta.fp()
    except Exception:
        return '', ''
    return (fci or ''), (fsaldo or '')


def resolver_forma_pago_impresion(proyecto, promesa, adj=None, override_ci='', override_saldo=''):
    """
    Texto de forma de pago para el PDF de promesa.

    Prioridad: override de impresion (no se guarda) > texto en promesa >
    texto automatico de la venta original.
    """
    posted_ci = (override_ci or '').strip()
    posted_saldo = (override_saldo or '').strip()
    stored_ci = ((getattr(promesa, 'formaci', None) or '') if promesa else '').strip()
    stored_saldo = ((getattr(promesa, 'formasaldo', None) or '') if promesa else '').strip()

    contrato = None
    adj_id = adj or getattr(promesa, 'idadjudicacion', None)
    if adj_id:
        try:
            obj_adj = Adjudicacion.objects.using(proyecto).get(idadjudicacion=adj_id)
            contrato = obj_adj.contrato
        except Adjudicacion.DoesNotExist:
            contrato = None
    auto_ci, auto_saldo = texto_forma_pago_venta(proyecto, contrato)
    return posted_ci or stored_ci or auto_ci, posted_saldo or stored_saldo or auto_saldo


def aplicar_forma_pago_impresion(promesa, formaci, formasaldo, general_info=None):
    """Pisa el texto en memoria para plantillas HTML (ctr.general_info). No persiste."""
    from andinasoft.promesa_pdf import aplicar_texto_forma_pago_pdf

    return aplicar_texto_forma_pago_pdf(
        promesa, formaci, formasaldo, general_info=general_info,
    )


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
        pipe = pipeline_escritura(cump)
        paso_escritura = pipe['paso']
        pasos_ui = pipe['pasos_ui']
        next_paso = pipe['paso_siguiente']
        ent_ui = entrega_ui(fechaentrega, entregado, fecha_entrega_real)

        est_entrega = estado_fecha(fechaentrega, entregado, hoy=hoy)
        est_escritura = estado_fecha(fechaescritura, pipe['completa'], hoy=hoy)

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
            'cliente_id': tid1,
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
            'paso_escritura': paso_escritura,
            'paso_escritura_label': PASO_LABEL.get(paso_escritura, paso_escritura),
            'paso_escritura_idx': paso_index(paso_escritura),
            'paso_siguiente': next_paso,
            'paso_siguiente_label': pipe['paso_siguiente_label'],
            'pasos_ui': pasos_ui,
            'pasos_linea': pipe['pasos_linea'],
            'pasos_rama': pipe['pasos_rama'],
            'pasos_siguientes': pipe['siguientes'],
            'escritura_completa': pipe['completa'],
            'carga_pendiente': pipe['carga_pendiente'],
            'factura_pendiente': pipe['factura_pendiente'],
            'entrega_ui': ent_ui,
            'puede_marcar_entrega': bool(fechaentrega),
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


def ensure_cumplimiento(proyecto, adj):
    from andinasoft.models import proyectos as ProyectosModel
    proy, _ = ProyectosModel.objects.get_or_create(proyecto=proyecto, defaults={'activo': True})
    obj, _ = PromesaCumplimiento.objects.get_or_create(proyecto=proy, adj=adj)
    return obj


def marcar_hito_escritura(proyecto, adj, paso, fecha, usuario, *, nota='', documento='', es_superuser=False):
    cumplimiento = ensure_cumplimiento(proyecto, adj)
    hechos = hechos_from_cumplimiento(cumplimiento)
    if not puede_avanzar_paso(None, paso, hechos=hechos, es_superuser=es_superuser):
        raise ValueError('No se puede marcar ese paso todavia. Complete el anterior.')
    if paso in PASOS_ARCHIVO and not (documento or '').strip():
        raise ValueError(PASOS_ARCHIVO[paso][0])
    fecha = _as_date(fecha)
    if not fecha:
        raise ValueError('Indique la fecha del paso.')
    field = PASO_FECHA_FIELD.get(paso)
    if field:
        setattr(cumplimiento, field, fecha)
    if paso == PromesaCumplimiento.PASO_CARGA:
        cumplimiento.documento_escritura = documento or cumplimiento.documento_escritura
    if paso == PromesaCumplimiento.PASO_FACTURA_NOTARIA:
        cumplimiento.documento_factura_notaria = documento or cumplimiento.documento_factura_notaria
    hechos.add(paso)
    cumplimiento.paso_escritura_actual = resumen_paso(hechos)
    if paso in (
        PromesaCumplimiento.PASO_CARGA,
        PromesaCumplimiento.PASO_REGISTRO,
        PromesaCumplimiento.PASO_FACTURADO,
    ):
        if not cumplimiento.fecha_escritura_real:
            cumplimiento.fecha_escritura_real = fecha
        cumplimiento.usuario_escritura = str(usuario or '')
    cumplimiento.save()

    PromesaHito.objects.create(
        proyecto=cumplimiento.proyecto,
        adj=adj,
        paso=paso,
        fecha=fecha,
        usuario=str(usuario or ''),
        nota=nota or '',
        documento=documento or '',
    )

    if paso in (
        PromesaCumplimiento.PASO_CARGA,
        PromesaCumplimiento.PASO_REGISTRO,
    ):
        promesa = ensure_promesa(proyecto, adj, usuario=usuario)
        promesa.escriturado = True
        promesa.save()
    return cumplimiento


def registrar_fechas_firmadas(proyecto, adj, fecha_promesa, fecha_entrega, fecha_escritura, usuario):
    """Registra por unica vez las fechas pactadas. Cambios posteriores van por otrosi."""
    fecha_promesa = _as_date(fecha_promesa)
    fecha_entrega = _as_date(fecha_entrega)
    fecha_escritura = _as_date(fecha_escritura)
    if not (fecha_promesa and fecha_entrega and fecha_escritura):
        raise ValueError('Indique fecha de promesa, entrega y escritura.')
    promesa = ensure_promesa(proyecto, adj, usuario=usuario)
    if promesa.fechaentrega or promesa.fechaescritura:
        raise ValueError('Las fechas ya estan registradas. Para modificarlas use un otrosi.')
    promesa.fechapromesa = fecha_promesa
    promesa.fechaentrega = fecha_entrega
    promesa.fechaescritura = fecha_escritura
    promesa.save()
    timeline.objects.using(proyecto).create(
        adj=adj, fecha=datetime.date.today(), usuario=usuario,
        accion='Registro las fechas firmadas de la promesa',
    )
    return promesa


def marcar_entrega(proyecto, adj, entregado, fecha_real, usuario, *, documento=''):
    promesa = ensure_promesa(proyecto, adj, usuario=usuario)
    fecha_real = _as_date(fecha_real)
    if entregado and not promesa.fechaentrega:
        raise ValueError('Registre primero la fecha pactada de entrega.')
    if entregado and not fecha_real:
        raise ValueError('Indique la fecha real de entrega.')
    promesa.entregado = bool(entregado)
    promesa.save()
    cumplimiento = ensure_cumplimiento(proyecto, adj)
    if entregado:
        cumplimiento.fecha_entrega_real = fecha_real
        cumplimiento.usuario_entrega = str(usuario or '')
    else:
        cumplimiento.fecha_entrega_real = None
        cumplimiento.usuario_entrega = ''
    cumplimiento.save()
    accion = (
        'Marco la promesa como entregada el %s' % fecha_real.isoformat()
        if entregado else 'Marco la promesa como no entregada'
    )
    if documento:
        accion += ' y cargo acta de entrega'
    timeline.objects.using(proyecto).create(
        adj=adj, fecha=datetime.date.today(), usuario=usuario, accion=accion,
    )
    return promesa


def registrar_otrosi(
    proyecto, adj, tipo_otrosi, usuario, *,
    fecha_entrega_nueva=None, fecha_escritura_nueva=None,
    observaciones='', documento='',
):
    if tipo_otrosi not in (
        PromesaOtrosi.TIPO_ENTREGA,
        PromesaOtrosi.TIPO_ESCRITURA,
        PromesaOtrosi.TIPO_AMBOS,
    ):
        raise ValueError('Tipo de otrosi invalido.')
    if not (documento or '').strip():
        raise ValueError('Debe cargar el PDF del otrosi.')
    fecha_entrega_nueva = _as_date(fecha_entrega_nueva)
    fecha_escritura_nueva = _as_date(fecha_escritura_nueva)
    if tipo_otrosi in (PromesaOtrosi.TIPO_ENTREGA, PromesaOtrosi.TIPO_AMBOS) and not fecha_entrega_nueva:
        raise ValueError('Indique la nueva fecha de entrega.')
    if tipo_otrosi in (PromesaOtrosi.TIPO_ESCRITURA, PromesaOtrosi.TIPO_AMBOS) and not fecha_escritura_nueva:
        raise ValueError('Indique la nueva fecha de escritura.')
    promesa = ensure_promesa(proyecto, adj, usuario=usuario)
    if not promesa.fechaentrega and not promesa.fechaescritura:
        raise ValueError('Registre primero las fechas pactadas.')
    fe_ant = promesa.fechaentrega
    fs_ant = promesa.fechaescritura
    if tipo_otrosi in (PromesaOtrosi.TIPO_ENTREGA, PromesaOtrosi.TIPO_AMBOS):
        promesa.fechaentrega = fecha_entrega_nueva
        promesa.entregado = False
    if tipo_otrosi in (PromesaOtrosi.TIPO_ESCRITURA, PromesaOtrosi.TIPO_AMBOS):
        promesa.fechaescritura = fecha_escritura_nueva
        promesa.escriturado = False
    promesa.save()
    cumplimiento = ensure_cumplimiento(proyecto, adj)
    PromesaOtrosi.objects.create(
        proyecto=cumplimiento.proyecto,
        adj=adj,
        tipo=tipo_otrosi,
        fecha_entrega_anterior=fe_ant if tipo_otrosi in (PromesaOtrosi.TIPO_ENTREGA, PromesaOtrosi.TIPO_AMBOS) else None,
        fecha_entrega_nueva=fecha_entrega_nueva if tipo_otrosi in (PromesaOtrosi.TIPO_ENTREGA, PromesaOtrosi.TIPO_AMBOS) else None,
        fecha_escritura_anterior=fs_ant if tipo_otrosi in (PromesaOtrosi.TIPO_ESCRITURA, PromesaOtrosi.TIPO_AMBOS) else None,
        fecha_escritura_nueva=fecha_escritura_nueva if tipo_otrosi in (PromesaOtrosi.TIPO_ESCRITURA, PromesaOtrosi.TIPO_AMBOS) else None,
        observaciones=observaciones or '',
        documento=documento,
        usuario=str(usuario or ''),
    )
    timeline.objects.using(proyecto).create(
        adj=adj, fecha=datetime.date.today(), usuario=usuario,
        accion='Registro otrosi de %s' % tipo_otrosi,
    )
    return promesa


def listar_otrosi(proyecto, adj):
    rows = []
    for item in PromesaOtrosi.objects.filter(proyecto_id=proyecto, adj=adj).order_by('-fecha_registro'):
        rows.append({
            'id': item.pk,
            'tipo': item.tipo,
            'tipo_label': item.get_tipo_display(),
            'fecha_entrega_anterior': item.fecha_entrega_anterior,
            'fecha_entrega_nueva': item.fecha_entrega_nueva,
            'fecha_escritura_anterior': item.fecha_escritura_anterior,
            'fecha_escritura_nueva': item.fecha_escritura_nueva,
            'observaciones': item.observaciones or '',
            'documento': item.documento or '',
            'usuario': item.usuario or '',
            'fecha_registro': item.fecha_registro,
        })
    return rows


def documentos_contrato(proyecto, adj):
    from django.conf import settings
    from django.core.files.storage import default_storage
    from andinasoft.shared_models import documentos_contratos

    docs = list(
        documentos_contratos.objects.using(proyecto)
        .filter(adj=adj)
        .values('descripcion_doc', 'fecha_carga', 'usuario_carga')
    )
    for doc in docs:
        nombre = doc.get('descripcion_doc') or ''
        filename = nombre if str(nombre).lower().endswith('.pdf') else '%s.pdf' % nombre
        doc_path = 'docs_andinasoft/doc_contratos/%s/%s/%s' % (proyecto, adj, filename)
        try:
            doc['url'] = default_storage.url(doc_path)
        except Exception:
            doc['url'] = '%s%s' % (settings.MEDIA_URL, doc_path)
        doc['fecha_carga'] = str(doc.get('fecha_carga') or '')
        doc['usuario_carga'] = str(doc.get('usuario_carga') or '')
    docs.sort(key=lambda d: d.get('fecha_carga') or '', reverse=True)
    return docs


def filter_rows(rows, *, entrega_estado=None, escritura_estado=None):
    out = rows
    if entrega_estado:
        out = [r for r in out if r['estado_entrega'] == entrega_estado]
    if escritura_estado:
        out = [r for r in out if r['estado_escritura'] == escritura_estado]
    return out
