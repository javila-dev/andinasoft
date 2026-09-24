"""Tipos fijos de compromiso de acta y resumen para listados/notificaciones."""

TIPO_CAMBIO_PROYECTO = 'cambio_proyecto'
TIPO_ENVIO_INFORMACION = 'envio_informacion'
TIPO_CITA_VISITA = 'cita_visita'
TIPO_RESPUESTA_FORMAL = 'respuesta_formal'
TIPO_GESTION_INTERNA = 'gestion_interna'
TIPO_OTRO = 'otro'

TIPO_CHOICES = (
    (TIPO_CAMBIO_PROYECTO, 'Cambio a otro proyecto'),
    (TIPO_ENVIO_INFORMACION, 'Envio de informacion'),
    (TIPO_CITA_VISITA, 'Cita / visita'),
    (TIPO_RESPUESTA_FORMAL, 'Respuesta formal'),
    (TIPO_GESTION_INTERNA, 'Gestion interna'),
    (TIPO_OTRO, 'Otro'),
)

TIPO_LABELS = dict(TIPO_CHOICES)

ITEMS_ENVIO = (
    ('brochure', 'Brochure'),
    ('licencias', 'Licencias'),
    ('certificados', 'Certificados'),
    ('planos', 'Planos'),
    ('estado_cuenta', 'Estado de cuenta'),
    ('paz_salvo', 'Paz y salvo'),
    ('otro', 'Otro'),
)

CANALES_ENVIO = (
    ('correo', 'Correo'),
    ('whatsapp', 'WhatsApp'),
    ('presencial', 'Presencial'),
)

LUGARES_CITA = (
    ('obra', 'Obra'),
    ('sala_ventas', 'Sala de ventas'),
    ('notaria', 'Notaria'),
    ('otro', 'Otro'),
)

CANALES_RESPUESTA = (
    ('carta', 'Carta'),
    ('correo', 'Correo'),
    ('pqrs', 'PQRS'),
)

AREAS_GESTION = (
    ('juridica', 'Juridica'),
    ('cartera', 'Cartera'),
    ('operaciones', 'Operaciones'),
    ('contabilidad', 'Contabilidad'),
    ('otra', 'Otra'),
)

_ITEM_LABELS = dict(ITEMS_ENVIO)
_CANAL_ENVIO_LABELS = dict(CANALES_ENVIO)
_LUGAR_LABELS = dict(LUGARES_CITA)
_CANAL_RTA_LABELS = dict(CANALES_RESPUESTA)
_AREA_LABELS = dict(AREAS_GESTION)


def tipo_label(tipo):
    return TIPO_LABELS.get(tipo or TIPO_OTRO, TIPO_LABELS[TIPO_OTRO])


def titulo_por_tipo(tipo, detalle=None, titulo_libre=''):
    detalle = detalle or {}
    if tipo == TIPO_OTRO:
        return (titulo_libre or 'Compromiso').strip() or 'Compromiso'
    if tipo == TIPO_CAMBIO_PROYECTO:
        destino = (detalle.get('proyecto_destino') or '').strip()
        return f'Cambio a {destino}' if destino else 'Cambio a otro proyecto'
    if tipo == TIPO_ENVIO_INFORMACION:
        items = detalle.get('items') or []
        labels = [_ITEM_LABELS.get(i, i) for i in items if i]
        if labels:
            return 'Enviar ' + ', '.join(labels[:3])
        return 'Envio de informacion'
    if tipo == TIPO_CITA_VISITA:
        lugar = _LUGAR_LABELS.get(detalle.get('lugar_tipo'), '')
        return f'Cita {lugar.lower()}' if lugar else 'Cita / visita'
    if tipo == TIPO_RESPUESTA_FORMAL:
        canal = _CANAL_RTA_LABELS.get(detalle.get('canal'), '')
        return f'Respuesta formal ({canal})' if canal else 'Respuesta formal'
    if tipo == TIPO_GESTION_INTERNA:
        area = _AREA_LABELS.get(detalle.get('area'), '')
        return f'Gestion {area.lower()}' if area else 'Gestion interna'
    return tipo_label(tipo)


def resumen_linea(tipo, detalle=None, titulo=''):
    detalle = detalle or {}
    partes = []
    if tipo == TIPO_CAMBIO_PROYECTO:
        destino = (detalle.get('proyecto_destino') or '').strip()
        lotes = (detalle.get('lotes_prospecto') or '').strip()
        fecha = detalle.get('fecha_estimada_entrega') or ''
        espera = (detalle.get('expectativa_cliente') or '').strip()
        if destino:
            partes.append(destino)
        if lotes:
            partes.append(lotes)
        if fecha:
            partes.append(f'entrega {fecha}')
        if espera:
            partes.append(f'espera: {espera}')
    elif tipo == TIPO_ENVIO_INFORMACION:
        items = detalle.get('items') or []
        labels = [_ITEM_LABELS.get(i, i) for i in items if i]
        extra = (detalle.get('items_otro') or '').strip()
        if extra:
            labels.append(extra)
        canal = _CANAL_ENVIO_LABELS.get(detalle.get('canal'), '')
        if labels:
            partes.append(', '.join(labels))
        if canal:
            partes.append(canal)
    elif tipo == TIPO_CITA_VISITA:
        lugar_tipo = _LUGAR_LABELS.get(detalle.get('lugar_tipo'), '')
        lugar = (detalle.get('lugar') or '').strip()
        hora = (detalle.get('hora') or '').strip()
        if lugar_tipo:
            partes.append(lugar_tipo)
        if lugar:
            partes.append(lugar)
        if hora:
            partes.append(hora)
    elif tipo == TIPO_RESPUESTA_FORMAL:
        canal = _CANAL_RTA_LABELS.get(detalle.get('canal'), '')
        radicado = (detalle.get('id_pqrs') or '').strip()
        if canal:
            partes.append(canal)
        if radicado:
            partes.append(f'radicado {radicado}')
    elif tipo == TIPO_GESTION_INTERNA:
        area = _AREA_LABELS.get(detalle.get('area'), '')
        pedido = (detalle.get('que_se_pide') or '').strip()
        if area:
            partes.append(area)
        if pedido:
            partes.append(pedido)
    else:
        if titulo:
            return titulo
    if not partes:
        return titulo or tipo_label(tipo)
    return ' — '.join(partes)


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    text = str(value).strip()
    return [text] if text else []


def normalizar_detalle(tipo, raw):
    raw = raw or {}
    tipo = tipo or TIPO_OTRO
    if tipo == TIPO_CAMBIO_PROYECTO:
        return {
            'proyecto_destino': str(raw.get('proyecto_destino') or '').strip(),
            'lotes_prospecto': str(raw.get('lotes_prospecto') or '').strip(),
            'fecha_estimada_entrega': str(raw.get('fecha_estimada_entrega') or '').strip(),
            'observaciones': str(raw.get('observaciones') or '').strip(),
            'expectativa_cliente': str(raw.get('expectativa_cliente') or '').strip(),
        }
    if tipo == TIPO_ENVIO_INFORMACION:
        items = [i for i in _as_list(raw.get('items')) if i in _ITEM_LABELS]
        return {
            'items': items,
            'items_otro': str(raw.get('items_otro') or '').strip(),
            'canal': str(raw.get('canal') or '').strip(),
        }
    if tipo == TIPO_CITA_VISITA:
        return {
            'lugar_tipo': str(raw.get('lugar_tipo') or '').strip(),
            'lugar': str(raw.get('lugar') or '').strip(),
            'hora': str(raw.get('hora') or '').strip(),
        }
    if tipo == TIPO_RESPUESTA_FORMAL:
        return {
            'canal': str(raw.get('canal') or '').strip(),
            'id_pqrs': str(raw.get('id_pqrs') or '').strip(),
        }
    if tipo == TIPO_GESTION_INTERNA:
        return {
            'area': str(raw.get('area') or '').strip(),
            'que_se_pide': str(raw.get('que_se_pide') or '').strip(),
        }
    return {}


def errores_detalle(tipo, detalle):
    detalle = detalle or {}
    errores = {}
    if tipo == TIPO_CAMBIO_PROYECTO:
        if not detalle.get('proyecto_destino'):
            errores['proyecto_destino'] = 'Indique el proyecto destino.'
        if not detalle.get('expectativa_cliente'):
            errores['expectativa_cliente'] = 'Indique que espera el cliente.'
    elif tipo == TIPO_ENVIO_INFORMACION:
        if not detalle.get('items'):
            errores['items'] = 'Seleccione que se envia.'
        if 'otro' in (detalle.get('items') or []) and not detalle.get('items_otro'):
            errores['items_otro'] = 'Describa el otro documento.'
        if not detalle.get('canal'):
            errores['canal'] = 'Indique el canal de envio.'
    elif tipo == TIPO_CITA_VISITA:
        if not detalle.get('lugar_tipo'):
            errores['lugar_tipo'] = 'Indique el tipo de cita.'
        if not detalle.get('lugar'):
            errores['lugar'] = 'Indique el lugar.'
    elif tipo == TIPO_RESPUESTA_FORMAL:
        if not detalle.get('canal'):
            errores['canal'] = 'Indique el canal de respuesta.'
    elif tipo == TIPO_GESTION_INTERNA:
        if not detalle.get('area'):
            errores['area'] = 'Indique el area.'
        if not detalle.get('que_se_pide'):
            errores['que_se_pide'] = 'Indique que se pide.'
    return errores
