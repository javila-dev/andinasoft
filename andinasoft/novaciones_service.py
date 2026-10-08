"""Novaciones: traslado de un cliente de una adjudicacion a una venta nueva de otro lote/proyecto.

Flujo:
1. ``crear_solicitud``: registra la novacion En documentacion. La ADJ de origen queda
   bloqueada para recaudos y la venta destino (Pendiente/Aprobado, lote Reservado)
   no se puede adjudicar por el flujo comercial. Ya se puede imprimir su promesa.
2. Documentacion (quien la creo, su jefe o un superusuario): ``registrar_nota`` y
   ``cargar_documento`` (firmados, en los documentos de la venta nueva). Con el
   ``checklist`` completo, ``enviar_a_aprobacion`` la pasa a Por aprobar y avisa solo al
   aprobador que se eligio al registrarla (``cambiar_aprobador`` mientras se documenta).
3. ``aprobar``: en una sola operacion atomica (default + BD origen + BD destino)
   adjudica la venta destino sin comisiones, aplica lo trasladado a la cuota inicial,
   desiste la ADJ de origen con una nota negativa por lo trasladado y libera su lote.
   ``devolver`` la regresa a documentacion; ``rechazar`` la cierra y desbloquea el origen.
"""
import datetime
import logging
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from andinasoft.adjudicacion_service import crear_plan_pagos, total_cuota_inicial
from andinasoft.handlers_functions import aplicar_pago
from andinasoft.handlers_functions import (
    eliminar_documento_contrato,
    guardar_documento_contrato,
    url_documento_contrato,
)
from andinasoft.models import Novacion, NovacionEvento, Usuarios_Proyectos
from andinasoft.saldo_favor import exclude_sf_recaudos_filter
from andinasoft.shared_models import (
    Adjudicacion,
    InfoCartera,
    Inmuebles,
    PlanPagos,
    PresupuestoCartera,
    Promesas,
    Recaudos,
    Recaudos_general,
    RecaudosNoradicados,
    consecutivos,
    documentos_contratos,
    saldos_adj,
    timeline,
    titulares_por_adj,
    usuario_corto,
    ventas_nuevas,
)

# Los informes ya excluyen del recaudo efectivo la forma de pago 'NOVACION…'.
FORMA_PAGO_NOVACION = 'NOVACION'
CONCEPTO_NOVACION = 'Novacion'  # recaudos_general.concepto admite 12 caracteres
ESTADOS_VENTA_DESTINO = ('Pendiente', 'Aprobado')
MAX_NRO_NOTA = 12  # recaudos_general.numrecibo / recaudos.recibo
MAX_ACCION_TIMELINE = 255
SUFIJO_RECIBO_ORIGEN = '-D'  # nota negativa del origen cuando origen y destino son el mismo proyecto
TIPO_CONTRATO = 'Promesa'  # la venta nueva de una novacion siempre se adjudica como promesa

logger = logging.getLogger(__name__)

# Documentos firmados que se cargan en la venta nueva: (tipo, etiqueta, obligatorio).
# El tipo es el prefijo del nombre en documentos_contratos ("<tipo>_<fecha>").
DOCUMENTOS = (
    ('Novacion', 'Novación firmada', True),
    ('Promesa', 'Promesa firmada', True),
    ('Pagare', 'Pagaré', False),
    ('Otrosi', 'Otrosí', False),
)
TIPOS_DOCUMENTO = {tipo: etiqueta for tipo, etiqueta, _ in DOCUMENTOS}

COMPONENTES = (
    ('capital', 'Capital'),
    ('interes_cte', 'Interés corriente'),
    ('interes_mora', 'Interés de mora'),
)


class NovacionError(Exception):
    """Regla de negocio que impide registrar o aprobar la novacion."""


def _money(valor):
    return f'${Decimal(valor or 0):,.0f}'


def _hoy():
    return datetime.date.today()


def _registrar_timeline(proyecto, adj, usuario, accion):
    timeline.objects.using(proyecto).create(
        adj=adj, fecha=_hoy(), usuario=usuario, accion=accion[:MAX_ACCION_TIMELINE],
    )


# ─── Consultas ────────────────────────────────────────────────────────────────

def novacion_pendiente_origen(proyecto, adj):
    """Novacion abierta (en documentacion o por aprobar) que bloquea la ADJ ``adj`` (o None)."""
    if not proyecto or not adj:
        return None
    return Novacion.objects.filter(
        estado__in=Novacion.ESTADOS_ABIERTOS, proyecto_origen_id=proyecto, adj_origen=adj,
    ).first()


def novacion_pendiente_venta(proyecto, venta_id):
    """Novacion abierta que tiene reservada la venta ``venta_id`` de ``proyecto`` (o None)."""
    try:
        venta_id = int(venta_id)
    except (TypeError, ValueError):
        return None
    return Novacion.objects.filter(
        estado__in=Novacion.ESTADOS_ABIERTOS, proyecto_destino_id=proyecto, venta_destino=venta_id,
    ).first()


def pagado_por_componente(proyecto, adj):
    """Lo recaudado en la ADJ separado en capital, interes corriente y mora (sin saldo a favor)."""
    agg = Recaudos.objects.using(proyecto).filter(
        exclude_sf_recaudos_filter(), idadjudicacion=adj,
    ).aggregate(
        capital=Sum('capital'),
        interes_cte=Sum('interescte'),
        interes_mora=Sum('interesmora'),
    )
    return {key: Decimal(agg.get(key) or 0) for key, _ in COMPONENTES}


def ventas_destino_disponibles(proyecto):
    """Ventas de lote Pendientes/Aprobadas de ``proyecto`` que no estan reservadas por otra novacion."""
    reservadas = Novacion.objects.filter(
        estado__in=Novacion.ESTADOS_ABIERTOS, proyecto_destino_id=proyecto,
    ).values_list('venta_destino', flat=True)
    return ventas_nuevas.objects.using(proyecto).filter(
        estado__in=ESTADOS_VENTA_DESTINO,
    ).exclude(tipo_venta='Fractal').exclude(id_venta__in=list(reservadas)).order_by('-id_venta')


def _titulares_venta(venta):
    return {t for t in (venta.id_t1, venta.id_t2, venta.id_t3, venta.id_t4) if t}


def _nota_usada(proyecto, nro_nota):
    return (
        Recaudos_general.objects.using(proyecto).filter(numrecibo=nro_nota).exists()
        or Recaudos.objects.using(proyecto).filter(recibo=nro_nota).exists()
    )


# ─── Validacion ───────────────────────────────────────────────────────────────

def recibo_origen(nro_nota, proyecto_origen, proyecto_destino):
    """Numero del recibo negativo en el origen. Si origen y destino son el mismo proyecto, ambos
    recibos van a la misma recaudos_general (NumRecibo unico), asi que el del origen lleva sufijo."""
    if proyecto_origen == proyecto_destino:
        return f'{nro_nota}{SUFIJO_RECIBO_ORIGEN}'
    return nro_nota


def validar_nota(nro_nota, proyecto_origen, proyecto_destino, novacion_actual=None):
    """El numero de nota se usa como recibo en origen y destino: no puede repetirse."""
    nro_nota = (nro_nota or '').strip()
    if not nro_nota:
        raise NovacionError('Indica el número de la nota contable.')
    mismo_proyecto = proyecto_origen == proyecto_destino
    maximo = MAX_NRO_NOTA - (len(SUFIJO_RECIBO_ORIGEN) if mismo_proyecto else 0)
    if len(nro_nota) > maximo:
        detalle = ' cuando la novación es dentro del mismo proyecto' if mismo_proyecto else ''
        raise NovacionError(f'El número de nota admite máximo {maximo} caracteres{detalle}.')
    recibos = {(proyecto_destino, nro_nota), (proyecto_origen, recibo_origen(nro_nota, proyecto_origen, proyecto_destino))}
    for proyecto, recibo in recibos:
        if _nota_usada(proyecto, recibo):
            raise NovacionError(f'El número {recibo} ya existe como recibo en {proyecto}.')
    nota_repetida = Novacion.objects.filter(nro_nota=nro_nota).exclude(estado=Novacion.ESTADO_RECHAZADA)
    if novacion_actual:
        nota_repetida = nota_repetida.exclude(pk=novacion_actual.pk)
    if nota_repetida.exists():
        raise NovacionError(f'La nota {nro_nota} ya está registrada en otra novación.')
    return nro_nota


def validar(
    *, proyecto_origen, adj_origen, proyecto_destino, venta_id,
    capital, interes_cte, interes_mora, nro_nota=None, novacion_actual=None,
):
    """Valida la novacion y devuelve ``(adjudicacion_origen, venta_destino, pagado)``.

    ``nro_nota`` solo se valida si se pasa (al registrar la novacion aun no hay nota).
    ``novacion_actual`` evita chocar con su propio bloqueo al revalidar.
    """
    try:
        obj_adj = Adjudicacion.objects.using(proyecto_origen).get(idadjudicacion=adj_origen)
    except Adjudicacion.DoesNotExist:
        raise NovacionError(f'La adjudicación {adj_origen} no existe en {proyecto_origen}.')
    if (obj_adj.estado or '').startswith('Desistido'):
        raise NovacionError(f'La adjudicación {adj_origen} ya está desistida.')

    otra = novacion_pendiente_origen(proyecto_origen, adj_origen)
    if otra and otra != novacion_actual:
        raise NovacionError(f'{adj_origen} ya tiene una novación pendiente (#{otra.pk}).')

    try:
        venta = ventas_nuevas.objects.using(proyecto_destino).get(pk=venta_id)
    except (ventas_nuevas.DoesNotExist, ValueError, TypeError):
        raise NovacionError(f'La venta {venta_id} no existe en {proyecto_destino}.')
    if venta.estado not in ESTADOS_VENTA_DESTINO:
        raise NovacionError(f'La venta {venta.pk} está {venta.estado}; debe estar Pendiente o Aprobada.')
    if venta.tipo_venta == 'Fractal':
        raise NovacionError('Las ventas de fracciones no se pueden usar como destino de novación.')
    reserva = novacion_pendiente_venta(proyecto_destino, venta.pk)
    if reserva and reserva != novacion_actual:
        raise NovacionError(f'La venta {venta.pk} ya está asignada a la novación #{reserva.pk}.')
    if proyecto_origen == proyecto_destino and venta.inmueble == obj_adj.idinmueble:
        raise NovacionError('El lote destino es el mismo lote de origen.')
    if obj_adj.idtercero1 not in _titulares_venta(venta):
        raise NovacionError(
            f'El titular {obj_adj.idtercero1} de {adj_origen} no es titular de la venta {venta.pk}.'
        )

    pagado = pagado_por_componente(proyecto_origen, adj_origen)
    trasladado = {
        'capital': Decimal(capital or 0),
        'interes_cte': Decimal(interes_cte or 0),
        'interes_mora': Decimal(interes_mora or 0),
    }
    for key, label in COMPONENTES:
        if trasladado[key] < 0:
            raise NovacionError(f'{label}: el valor a trasladar no puede ser negativo.')
        if trasladado[key] > pagado[key]:
            raise NovacionError(
                f'{label}: se quiere trasladar {_money(trasladado[key])} y solo hay pagado {_money(pagado[key])}.'
            )
    total = sum(trasladado.values())
    if total <= 0:
        raise NovacionError('Selecciona al menos un valor a trasladar.')
    tope_ci = Decimal(total_cuota_inicial(venta))
    if total > tope_ci:
        raise NovacionError(
            f'Lo trasladado ({_money(total)}) supera la cuota inicial de la venta destino ({_money(tope_ci)}).'
        )

    if nro_nota is not None:
        validar_nota(nro_nota, proyecto_origen, proyecto_destino, novacion_actual)

    return obj_adj, venta, pagado


# ─── Solicitud ────────────────────────────────────────────────────────────────

# ─── Aprobador ────────────────────────────────────────────────────────────────

def _tiene_proyecto(user, proyecto):
    asignacion = Usuarios_Proyectos.objects.filter(usuario=user).first()
    return bool(asignacion and asignacion.proyecto.filter(pk=proyecto).exists())


def candidatos_aprobador(proyecto_origen):
    """Usuarios que se pueden elegir como aprobador: superusuarios activos y quienes tengan el
    permiso aprobar_novacion (directo o por grupo) con acceso al proyecto de origen."""
    perm = Permission.objects.filter(content_type__app_label='andinasoft', codename='aprobar_novacion').first()
    filtro = Q(is_superuser=True)
    if perm:
        filtro |= Q(user_permissions=perm) | Q(groups__permissions=perm)
    usuarios = User.objects.filter(filtro, is_active=True).distinct().order_by('first_name', 'last_name', 'username')
    return [u for u in usuarios if u.is_superuser or _tiene_proyecto(u, proyecto_origen)]


def _validar_aprobador(aprobador, proyecto_origen):
    if aprobador is None:
        raise NovacionError('Elige quién revisa y aprueba la novación.')
    if aprobador.pk not in {u.pk for u in candidatos_aprobador(proyecto_origen)}:
        raise NovacionError(f'{aprobador.username} no puede aprobar novaciones de {proyecto_origen}.')


def puede_resolver(user, novacion):
    """Aprobar, devolver o rechazar: el aprobador designado o un superusuario."""
    return user.is_superuser or (novacion.aprobador_id is not None and novacion.aprobador_id == user.pk)


def _exigir_resolver(user, novacion):
    if not puede_resolver(user, novacion):
        raise NovacionError('Solo el aprobador designado o un superusuario pueden resolver esta novación.')


def _nombre_usuario(user):
    return (user.get_full_name() or '').strip() or user.username


def _evento(novacion, usuario, accion, detalle=''):
    NovacionEvento.objects.create(novacion=novacion, usuario=usuario, accion=accion, detalle=detalle)


def _notificar(novacion, evento, comentario=''):
    """Avisa (correo + n8n) cuando la transaccion confirma; un fallo del aviso no tumba el flujo."""
    from andinasoft.novaciones_notify import notificar

    novacion_id = novacion.pk
    transaction.on_commit(lambda: notificar(novacion_id, evento, comentario), using='default')


def crear_solicitud(
    *, usuario, proyecto_origen, adj_origen, proyecto_destino, venta_id,
    capital, interes_cte, interes_mora, aprobador, observaciones='',
):
    _validar_aprobador(aprobador, proyecto_origen)
    obj_adj, venta, pagado = validar(
        proyecto_origen=proyecto_origen, adj_origen=adj_origen,
        proyecto_destino=proyecto_destino, venta_id=venta_id,
        capital=capital, interes_cte=interes_cte, interes_mora=interes_mora,
    )
    with transaction.atomic(using='default'):
        novacion = Novacion.objects.create(
            proyecto_origen_id=proyecto_origen,
            adj_origen=adj_origen,
            inmueble_origen=obj_adj.idinmueble or '',
            titular=obj_adj.idtercero1 or '',
            proyecto_destino_id=proyecto_destino,
            venta_destino=venta.pk,
            inmueble_destino=venta.inmueble,
            pagado_capital=pagado['capital'],
            pagado_interes_cte=pagado['interes_cte'],
            pagado_interes_mora=pagado['interes_mora'],
            capital_trasladado=Decimal(capital or 0),
            interes_cte_trasladado=Decimal(interes_cte or 0),
            interes_mora_trasladado=Decimal(interes_mora or 0),
            observaciones=observaciones or '',
            usuario_solicita=usuario,
            aprobador=aprobador,
        )
        _evento(
            novacion, usuario, 'Registro',
            f'{adj_origen} ({proyecto_origen}) a venta {venta.pk} de {proyecto_destino}, lote {venta.inmueble}. '
            f'Trasladado: {_detalle_traslado(novacion)}. Aprobador: {_nombre_usuario(aprobador)}.',
        )
    _registrar_timeline(
        proyecto_origen, adj_origen, usuario.username,
        f'Solicitó novación #{novacion.pk} a {proyecto_destino} lote {venta.inmueble} '
        f'(venta {venta.pk}) por {_money(novacion.total_trasladado)}. Recaudos bloqueados hasta resolverla.',
    )
    return novacion


# ─── Documentacion ────────────────────────────────────────────────────────────

def puede_gestionar(user, novacion):
    """Cargar nota/documentos y enviar a aprobacion: quien la creo, su jefe o un superusuario."""
    return (
        user.is_superuser
        or novacion.usuario_solicita_id == user.pk
        or user.has_perm('andinasoft.change_novacion')
    )


def _exigir_documentacion(user, novacion):
    if not puede_gestionar(user, novacion):
        raise NovacionError('Solo quien registró la novación, su jefe o un superusuario pueden documentarla.')
    if novacion.estado != Novacion.ESTADO_DOCUMENTACION:
        raise NovacionError(f'La novación #{novacion.pk} está {novacion.get_estado_display()}; ya no se puede modificar.')


def _adj_documentos(novacion):
    """Los documentos viven en la venta nueva y, al aprobar, pasan a su ADJ."""
    return novacion.adj_destino or str(novacion.venta_destino)


def documentos_cargados(novacion):
    """Documentos de la venta nueva (o de su ADJ si ya se aprobo), con tipo y URL."""
    proyecto = novacion.proyecto_destino_id
    adj = _adj_documentos(novacion)
    filas = documentos_contratos.objects.using(proyecto).filter(adj=adj).order_by('descripcion_doc')
    docs = []
    for fila in filas:
        tipo = fila.descripcion_doc.split('_', 1)[0]
        docs.append({
            'descripcion': fila.descripcion_doc,
            'tipo': tipo,
            'etiqueta': TIPOS_DOCUMENTO.get(tipo, tipo),
            'de_novacion': tipo in TIPOS_DOCUMENTO,
            'fecha_carga': fila.fecha_carga,
            'usuario_carga': fila.usuario_carga,
            'url': url_documento_contrato(proyecto, adj, fila.descripcion_doc),
        })
    return docs


def checklist(novacion, docs=None):
    """Requisitos para enviar a aprobacion (y para aprobar): nota completa y firmados obligatorios."""
    docs = documentos_cargados(novacion) if docs is None else docs
    tipos = {d['tipo'] for d in docs}
    nota_ok = bool(novacion.nro_nota and novacion.fecha_nota and novacion.empresa_nota_id and novacion.soporte)
    items = [{
        'clave': 'nota',
        'etiqueta': 'Nota contable',
        'detalle': 'Número, fecha, empresa y PDF de la nota',
        'obligatorio': True,
        'ok': nota_ok,
    }, {
        'clave': 'fechas_promesa',
        'etiqueta': 'Fechas de la promesa',
        'detalle': 'Entrega y escritura pactadas en la promesa nueva',
        'obligatorio': True,
        'ok': bool(novacion.fecha_entrega and novacion.fecha_escritura),
    }]
    for tipo, etiqueta, obligatorio in DOCUMENTOS:
        items.append({'clave': tipo, 'etiqueta': etiqueta, 'obligatorio': obligatorio, 'ok': tipo in tipos})
    completo = all(item['ok'] for item in items if item['obligatorio'])
    return items, completo


def cambiar_aprobador(usuario, novacion, aprobador):
    _exigir_documentacion(usuario, novacion)
    _validar_aprobador(aprobador, novacion.proyecto_origen_id)
    if aprobador.pk == novacion.aprobador_id:
        return novacion
    with transaction.atomic(using='default'):
        novacion.aprobador = aprobador
        novacion.save()
        _evento(novacion, usuario, 'Aprobador', f'Ahora revisa y aprueba {_nombre_usuario(aprobador)}.')
    return novacion


def registrar_fechas_promesa(usuario, novacion, *, fecha_entrega, fecha_escritura):
    """Fechas pactadas de la promesa nueva; con ellas se registra la promesa al aprobar."""
    _exigir_documentacion(usuario, novacion)
    if not (fecha_entrega and fecha_escritura):
        raise NovacionError('Indica la fecha de entrega y la de escritura.')
    with transaction.atomic(using='default'):
        novacion.fecha_entrega = fecha_entrega
        novacion.fecha_escritura = fecha_escritura
        novacion.save()
        _evento(novacion, usuario, 'Promesa', f'Entrega {fecha_entrega}, escritura {fecha_escritura}.')
    return novacion


def registrar_nota(usuario, novacion, *, nro_nota, fecha_nota, empresa_nota, soporte=None):
    _exigir_documentacion(usuario, novacion)
    nro_nota = validar_nota(nro_nota, novacion.proyecto_origen_id, novacion.proyecto_destino_id, novacion)
    with transaction.atomic(using='default'):
        novacion.nro_nota = nro_nota
        novacion.fecha_nota = fecha_nota
        novacion.empresa_nota = empresa_nota
        if soporte:
            novacion.soporte = soporte
        novacion.save()
        _evento(novacion, usuario, 'Nota', f'Nota {nro_nota} del {fecha_nota} de {empresa_nota.nombre}.')
    return novacion


def cargar_documento(usuario, novacion, tipo, archivo):
    _exigir_documentacion(usuario, novacion)
    if tipo not in TIPOS_DOCUMENTO:
        raise NovacionError('Tipo de documento no válido.')
    if any(d['tipo'] == tipo for d in documentos_cargados(novacion)):
        raise NovacionError(f'Ya hay {TIPOS_DOCUMENTO[tipo]} cargado; elimínalo si necesitas reemplazarlo.')
    descripcion = f'{tipo}_{_hoy()}'
    resultado = guardar_documento_contrato(
        novacion.proyecto_destino_id, str(novacion.venta_destino), descripcion, archivo, usuario,
    )
    _evento(
        novacion, usuario, 'Documento',
        f'{"Reemplazó" if resultado == "reemplazado" else "Cargó"} {TIPOS_DOCUMENTO[tipo]} ({descripcion}).',
    )
    return descripcion


def eliminar_documento(usuario, novacion, descripcion):
    _exigir_documentacion(usuario, novacion)
    if descripcion.split('_', 1)[0] not in TIPOS_DOCUMENTO:
        raise NovacionError('Desde aquí solo se eliminan los documentos de la novación.')
    eliminar_documento_contrato(novacion.proyecto_destino_id, str(novacion.venta_destino), descripcion)
    _evento(novacion, usuario, 'Documento', f'Eliminó {descripcion}.')


def enviar_a_aprobacion(usuario, novacion_id):
    with transaction.atomic(using='default'):
        novacion = Novacion.objects.select_for_update().get(pk=novacion_id)
        _exigir_documentacion(usuario, novacion)
        _, completo = checklist(novacion)
        if not completo:
            raise NovacionError('Falta la nota, las fechas de la promesa o algún documento firmado obligatorio.')
        _validar_aprobador(novacion.aprobador, novacion.proyecto_origen_id)
        # Revalida montos, venta y nota antes de pasarla al aprobador.
        validar(
            proyecto_origen=novacion.proyecto_origen_id, adj_origen=novacion.adj_origen,
            proyecto_destino=novacion.proyecto_destino_id, venta_id=novacion.venta_destino,
            capital=novacion.capital_trasladado, interes_cte=novacion.interes_cte_trasladado,
            interes_mora=novacion.interes_mora_trasladado, nro_nota=novacion.nro_nota,
            novacion_actual=novacion,
        )
        novacion.estado = Novacion.ESTADO_POR_APROBAR
        novacion.usuario_envia = usuario
        novacion.fecha_envio = timezone.now()
        novacion.save()
        _evento(novacion, usuario, 'Enviada a aprobación', f'Se avisó a {_nombre_usuario(novacion.aprobador)}.')
        _notificar(novacion, 'por_aprobar')
    return novacion


def devolver(usuario, novacion_id, comentario):
    comentario = (comentario or '').strip()
    if not comentario:
        raise NovacionError('Indica qué hay que corregir.')
    with transaction.atomic(using='default'):
        novacion = Novacion.objects.select_for_update().get(pk=novacion_id)
        _exigir_resolver(usuario, novacion)
        if novacion.estado != Novacion.ESTADO_POR_APROBAR:
            raise NovacionError(f'Solo se devuelve una novación Por aprobar; esta está {novacion.get_estado_display()}.')
        novacion.estado = Novacion.ESTADO_DOCUMENTACION
        novacion.save()
        _evento(novacion, usuario, 'Devuelta', comentario)
        _notificar(novacion, 'devuelta', comentario)
    return novacion


# ─── Aprobacion ───────────────────────────────────────────────────────────────

def _detalle_traslado(novacion):
    return (
        f'capital {_money(novacion.capital_trasladado)}, '
        f'int. cte {_money(novacion.interes_cte_trasladado)}, '
        f'mora {_money(novacion.interes_mora_trasladado)}'
    )


class _Deshacer:
    """Como revertir lo escrito en tablas MyISAM (plan_pagos, consecutivos, timeline_adj,
    info_cartera, recaudos_noradicados...), que no entran en la transaccion de la BD."""

    def __init__(self):
        self._pasos = []

    def registrar(self, paso):
        self._pasos.append(paso)

    def descartar(self):
        """Lo escrito ya quedo confirmado junto con la transaccion: no hay nada que deshacer."""
        self._pasos = []

    def ejecutar(self):
        for paso in reversed(self._pasos):
            try:
                paso()
            except Exception:
                logger.exception('No se pudo revertir un paso de la novacion')


def _adjudicar_destino(request, novacion, venta, deshacer, *, oficina, gestor_cartera):
    """Crea la ADJ de la venta destino (sin comisiones) y le aplica lo trasladado a la cuota inicial."""
    from andinasoft.views import _radicar_recibos_noradicados

    destino = novacion.proyecto_destino_id
    usuario = request.user.username
    hoy = _hoy()

    consecutivo = consecutivos.objects.using(destino).select_for_update().get(documento='ADJ')
    numero = consecutivo.consecutivo
    adj = f'ADJ{numero}'
    obj_adj = Adjudicacion.objects.using(destino).create(
        fecha=hoy,
        idadjudicacion=adj,
        tipocontrato=TIPO_CONTRATO,
        contrato=venta.pk,
        idinmueble=venta.inmueble,
        idtercero1=venta.id_t1,
        idtercero2=venta.id_t2,
        idtercero3=venta.id_t3,
        idtercero4=venta.id_t4,
        valor=venta.valor_venta,
        formapago=venta.forma_pago,
        cuotainicial=venta.cuota_inicial,
        financiacion=venta.saldo,
        plazofnc=venta.nro_cuotas_fn,
        cuotafnc=venta.valor_ctas_fn,
        iniciofnc=venta.inicio_fn,
        plazoextra=venta.nro_cuotas_ce,
        inicioextra=venta.inicio_ce,
        cuotaextra=venta.valor_ctas_ce,
        fechacontrato=venta.fecha_contrato,
        estado='Aprobado',
        origenventa='Novacion',
        basecomision=0,
        oficina=oficina,
        usuario=usuario_corto(usuario),
        p_enmendadura=0,
        p_doccompleta=0,
        p_valincorrectos=0,
        p_obs=f'Novación #{novacion.pk}',
        tasafnc=venta.tasa,
    )
    venta.estado = 'Adjudicado'
    venta.adj = obj_adj
    venta.save()
    lote = Inmuebles.objects.using(destino).get(idinmueble=venta.inmueble)
    lote.estado = 'Adjudicado'
    lote.save()

    consecutivo.consecutivo = numero + 1
    consecutivo.save()
    deshacer.registrar(
        lambda: consecutivos.objects.using(destino).filter(
            documento='ADJ', consecutivo=numero + 1,
        ).update(consecutivo=numero)
    )

    # La ADJ es nueva: todo lo que quede en plan_pagos / info_cartera / timeline con su id es de aqui.
    deshacer.registrar(lambda: PlanPagos.objects.using(destino).filter(adj=adj).delete())
    crear_plan_pagos(destino, venta, adj)

    # Lo trasladado entra como un recibo con el numero de la nota, solo a cuotas CI y sin mora.
    cuotas_ci = list(
        saldos_adj.objects.using(destino).filter(adj=adj, tipocta='CI', saldocuota__gt=0).order_by('nrocta')
    )
    if not cuotas_ci:
        raise NovacionError('La venta destino no genera cuotas de cuota inicial para aplicar lo trasladado.')
    total = novacion.total_trasladado
    aplicar_pago(
        request=request, adj=adj, fecha=novacion.fecha_nota, forma_pago=FORMA_PAGO_NOVACION,
        valor_pagado=total, concepto=CONCEPTO_NOVACION, valor_recibo=total,
        porcentaje_condonado=100, saldo_cuotas=cuotas_ci, consecutivo=novacion.nro_nota,
        Recaudos=Recaudos, Recaudos_general=Recaudos_general,
        titulares=titulares_por_adj.objects.using(destino).get(adj=adj),
        proyecto=destino, cobrar_mora=False,
    )
    # Abonos que el cliente haya hecho directamente a la venta nueva (se borran de la cola al aplicarlos).
    pendientes = list(RecaudosNoradicados.objects.using(destino).filter(contrato=venta.pk).values())

    def _restaurar_noradicados():
        for fila in pendientes:
            if not RecaudosNoradicados.objects.using(destino).filter(recibo=fila['recibo']).exists():
                RecaudosNoradicados.objects.using(destino).create(**fila)

    deshacer.registrar(_restaurar_noradicados)
    _radicar_recibos_noradicados(request, destino, venta.pk, adj)

    deshacer.registrar(lambda: InfoCartera.objects.using(destino).filter(idadjudicacion=adj).delete())
    InfoCartera.objects.using(destino).create(idadjudicacion=adj, gestorasignado=gestor_cartera)

    # La promesa queda registrada con las fechas pactadas (cambios posteriores van por otrosi).
    deshacer.registrar(lambda: Promesas.objects.using(destino).filter(idadjudicacion=adj).delete())
    Promesas.objects.using(destino).create(
        idadjudicacion=adj,
        nropromesa=str(venta.pk),
        fechapromesa=venta.fecha_contrato or hoy,
        fechaentrega=novacion.fecha_entrega,
        fechaescritura=novacion.fecha_escritura,
        formapago=venta.forma_pago or '',
        estado='Aprobado',
        ciudad=oficina,
        usuariocrea=usuario,
        usuarioaprueba=usuario,
        fechaaprueba=hoy,
        entregado=False,
        escriturado=False,
        observaciones=f'Novación #{novacion.pk}',
    )

    deshacer.registrar(lambda: timeline.objects.using(destino).filter(adj=adj).delete())
    timeline.objects.using(destino).create(
        adj=adj, fecha=venta.fecha_contrato or hoy, usuario=venta.usuario or usuario,
        accion='Creó el Contrato',
    )
    _registrar_timeline(
        destino, adj, usuario,
        f'Adjudicó por novación #{novacion.pk} desde {novacion.proyecto_origen_id} '
        f'{novacion.adj_origen} (lote {novacion.inmueble_origen}). Nota {novacion.nro_nota} '
        f'de {novacion.empresa_nota.nombre}: {_detalle_traslado(novacion)}.',
    )
    _registrar_timeline(
        destino, adj, usuario,
        f'Registró la promesa: entrega {novacion.fecha_entrega}, escritura {novacion.fecha_escritura}.',
    )
    return adj


def _desistir_origen(request, novacion, obj_adj, adj_destino, deshacer):
    """Desiste la ADJ de origen con una nota negativa por lo trasladado y libera su lote."""
    origen = novacion.proyecto_origen_id
    adj = novacion.adj_origen
    usuario = request.user.username
    hoy = _hoy()
    recibo = recibo_origen(novacion.nro_nota, origen, novacion.proyecto_destino_id)

    obj_adj.estado = 'Desistido'
    obj_adj.fechadesistimiento = hoy
    obj_adj.save()

    Recaudos_general.objects.using(origen).create(
        idadjudicacion=adj, fecha=novacion.fecha_nota, numrecibo=recibo,
        idtercero=obj_adj.idtercero1, operacion='Desistimiento',
        valor=-novacion.total_trasladado, formapago=FORMA_PAGO_NOVACION,
        concepto=CONCEPTO_NOVACION, usuario=usuario,
    )
    Recaudos.objects.using(origen).create(
        recibo=recibo, fecha=novacion.fecha_nota, idcta=adj, idadjudicacion=adj,
        capital=-novacion.capital_trasladado,
        interescte=-novacion.interes_cte_trasladado,
        interesmora=-novacion.interes_mora_trasladado,
        moralqd=0, fechaoperacion=hoy, usuario=usuario_corto(usuario), estado='Aprobado',
    )

    if obj_adj.idinmueble:
        Inmuebles.objects.using(origen).filter(idinmueble=obj_adj.idinmueble).update(estado='Libre')

    periodo = f'{hoy.year}{hoy.month:02d}'
    PresupuestoCartera.objects.using(origen).filter(idadjudicacion=adj, periodo=periodo).delete()

    accion = (
        f'Desistió por novación #{novacion.pk}: se novó a {novacion.proyecto_destino_id} '
        f'lote {novacion.inmueble_destino} ({adj_destino}). Nota {novacion.nro_nota} (recibo {recibo}) de '
        f'{novacion.empresa_nota.nombre}. Trasladado: {_detalle_traslado(novacion)}.'
    )[:MAX_ACCION_TIMELINE]
    _registrar_timeline(origen, adj, usuario, accion)
    deshacer.registrar(lambda: timeline.objects.using(origen).filter(adj=adj, accion=accion).delete())


def aprobar(request, novacion_id, *, oficina, gestor_cartera):
    """Aprueba la novacion. Todo o nada: si algo falla no queda nada escrito en ninguna BD.

    Las tablas InnoDB se revierten con la transaccion; lo escrito en tablas MyISAM se
    deshace a mano con ``_Deshacer`` una vez la transaccion ya se revirtio (tras un error de
    BD, MySQL no deja ejecutar mas consultas dentro del bloque atomic).
    """
    from andinasoft.views import _mover_documentos_venta_a_adj

    deshacer = _Deshacer()
    try:
        novacion = _aprobar_en_transaccion(
            request, novacion_id, deshacer, oficina=oficina, gestor_cartera=gestor_cartera,
        )
    except Exception:
        deshacer.ejecutar()
        raise
    # Al final y sin tumbar la aprobacion: si falla, los documentos se reasignan a mano.
    try:
        _mover_documentos_venta_a_adj(novacion.proyecto_destino_id, novacion.venta_destino, novacion.adj_destino)
    except Exception:
        logger.exception('Novacion %s: no se movieron los documentos de la venta %s', novacion.pk, novacion.venta_destino)
    return novacion


def _aprobar_en_transaccion(request, novacion_id, deshacer, *, oficina, gestor_cartera):
    with transaction.atomic(using='default'):
        novacion = Novacion.objects.select_for_update().select_related('empresa_nota').get(pk=novacion_id)
        _exigir_resolver(request.user, novacion)
        if novacion.estado != Novacion.ESTADO_POR_APROBAR:
            raise NovacionError(f'La novación #{novacion.pk} está {novacion.get_estado_display()}; no se puede aprobar.')
        _, completo = checklist(novacion)
        if not completo:
            raise NovacionError('Falta la nota, las fechas de la promesa o algún documento firmado obligatorio.')
        origen = novacion.proyecto_origen_id
        destino = novacion.proyecto_destino_id

        with transaction.atomic(using=destino), transaction.atomic(using=origen):
            # Se revalida: entre la solicitud y la aprobacion pudo cambiar algo.
            obj_adj, venta, _ = validar(
                proyecto_origen=origen, adj_origen=novacion.adj_origen,
                proyecto_destino=destino, venta_id=novacion.venta_destino,
                capital=novacion.capital_trasladado,
                interes_cte=novacion.interes_cte_trasladado,
                interes_mora=novacion.interes_mora_trasladado,
                nro_nota=novacion.nro_nota, novacion_actual=novacion,
            )
            adj_destino = _adjudicar_destino(
                request, novacion, venta, deshacer, oficina=oficina, gestor_cartera=gestor_cartera,
            )
            _desistir_origen(request, novacion, obj_adj, adj_destino, deshacer)
            novacion.estado = Novacion.ESTADO_APROBADA
            novacion.adj_destino = adj_destino
            novacion.usuario_resuelve = request.user
            novacion.fecha_resuelve = timezone.now()
            novacion.save()
            _evento(novacion, request.user, 'Aprobada', f'{adj_destino} adjudicada en {destino}.')
        # Origen y destino ya confirmaron: lo MyISAM escrito corresponde a datos validos.
        deshacer.descartar()
        _notificar(novacion, 'aprobada')
    return novacion


def rechazar(usuario, novacion_id, motivo):
    motivo = (motivo or '').strip()
    if not motivo:
        raise NovacionError('Indica el motivo del rechazo.')
    with transaction.atomic(using='default'):
        novacion = Novacion.objects.select_for_update().get(pk=novacion_id)
        _exigir_resolver(usuario, novacion)
        if not novacion.abierta:
            raise NovacionError(f'La novación #{novacion.pk} ya está {novacion.get_estado_display()}.')
        novacion.estado = Novacion.ESTADO_RECHAZADA
        novacion.motivo_rechazo = motivo
        novacion.usuario_resuelve = usuario
        novacion.fecha_resuelve = timezone.now()
        novacion.save()
        _evento(novacion, usuario, 'Rechazada', motivo)
        _notificar(novacion, 'rechazada', motivo)
    _registrar_timeline(
        novacion.proyecto_origen_id, novacion.adj_origen, usuario.username,
        f'Novación #{novacion.pk} rechazada: {motivo}. Se desbloquean los recaudos.',
    )
    return novacion
