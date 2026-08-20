"""
Tools MCP para Inventario de Lotes

Proporciona herramientas para consultar y gestionar el inventario de lotes/inmuebles.
"""
import logging
from decimal import Decimal
from typing import Any, Optional
from django.db.models import Q

logger = logging.getLogger(__name__)


def _normalize_lote_estado(value: str) -> Optional[str]:
    """Normaliza el estado del lote a su forma canónica (case-insensitive)."""
    if value is None:
        return None
    # Colapsa espacios y unifica separadores (_, -) para aceptar variantes de casing/formato.
    normalized = ' '.join(str(value).strip().lower().replace('_', ' ').replace('-', ' ').split())
    estados = {
        'libre': 'Libre',
        'bloqueado': 'Bloqueado',
        'sin liberar': 'Sin Liberar',
        'sinliberar': 'Sin Liberar',
        'adjudicado': 'Adjudicado',
        'reservado': 'Reservado',
    }
    return estados.get(normalized)


def _calculate_lote_valor(lote) -> int:
    """Calcula el valor del lote considerando factores de incremento."""
    from andinasoft.utilities import Utilidades

    area = lote.areaprivada or Decimal('0')
    vr_m2 = lote.vrmetrocuadrado or Decimal('0')
    fac_via = lote.fac_valor_via_principal or Decimal('1')
    fac_area = lote.fac_valor_area_social or Decimal('1')
    fac_esq = lote.fac_valor_esquinero or Decimal('1')
    incrementos = fac_via * fac_area * fac_esq
    valor_lote = area * vr_m2 * incrementos
    return Utilidades().redondear_numero(numero=valor_lote, multiplo=1000000, redondeo='>')


def _parse_list_param(value: str) -> list:
    """Parsea un parámetro de lista separado por comas."""
    if not value:
        return []
    parts = [item.strip() for item in str(value).split(',')]
    return [item for item in parts if item]


def _expand_manzana_variants(manzanas: list) -> list:
    """
    Expande variantes de manzana para tolerar padding numérico (6 vs 06).
    Conserva el valor original y agrega forma sin ceros a la izquierda y con zfill(2).
    """
    expanded = []
    seen = set()
    for raw in manzanas:
        candidates = [raw]
        stripped = str(raw).strip()
        if stripped.isdigit():
            as_int = str(int(stripped))  # '06' -> '6', '6' -> '6'
            candidates.append(as_int)
            candidates.append(as_int.zfill(2))  # '6' -> '06'
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                expanded.append(candidate)
    return expanded


def _get_cliente_nombre(cliente_id: str) -> Optional[str]:
    """Obtiene el nombre del cliente por su ID."""
    if not cliente_id:
        return None
    try:
        from andinasoft.models import clientes
        cliente = clientes.objects.get(idcliente=cliente_id)
        return f"{cliente.nombre1 or ''} {cliente.nombre2 or ''} {cliente.apellido1 or ''} {cliente.apellido2 or ''}".strip()
    except Exception:
        return None


def _check_user_project_access(user, proyecto: str) -> bool:
    """Verifica si el usuario tiene acceso al proyecto."""
    if user.is_superuser:
        return True
    from andinasoft.models import Usuarios_Proyectos
    user_projects = Usuarios_Proyectos.objects.filter(usuario=user.pk)
    if user_projects.exists():
        user_projects = user_projects[0].proyecto.all()
        for p in user_projects:
            if p.proyecto == proyecto:
                return True
    return False


def lotes_list(
    proyecto: str = None,
    estado: str = None,
    manzana: str = None,
    lote: str = None,
    idinmueble: str = None,
    user=None
) -> dict:
    """
    Consulta lotes por estado, con filtro opcional por manzanas, lotes o ID de inmueble.

    Args:
        proyecto: Nombre exacto del proyecto (requerido en práctica)
        estado: Estado del lote (Libre|Bloqueado|Sin Liberar|...).
                Sin estado: default Libre (inventario disponible / libres en manzana).
                Si se envía lote sin estado: no filtra por estado (útil para liberar lotes concretos).
        manzana: Lista de manzanas separadas por comas (tolera 6 y 06)
        lote: Lista de números de lote separados por comas (ej: 1A,1B)
        idinmueble: ID exacto del lote (si se envía, ignora estado, manzana y lote)
        user: Usuario Django para verificar permisos

    Returns:
        dict con count y data (lista de lotes)
    """
    from andinasoft.shared_models import Inmuebles, Adjudicacion, ventas_nuevas
    from mcp_server.tools.utils import resolve_proyecto

    # Si no se especificó proyecto, devolver instrucción para preguntar al usuario
    if not (proyecto or '').strip():
        from andinasoft.models import proyectos as ProyectosModel
        available = sorted([p.proyecto for p in ProyectosModel.objects.all()])
        return {
            'accion_requerida': (
                'El usuario no especificó el proyecto. '
                'PREGUNTA: "¿En qué proyecto quieres consultar el inventario?" '
                'y espera su respuesta antes de llamar este tool.'
            ),
            'proyectos_disponibles': available,
            'count': 0,
            'data': []
        }

    proyecto_nombre, err = resolve_proyecto(proyecto)
    if err:
        return {**err, 'count': 0, 'data': []}
    proyecto = proyecto_nombre

    if user and not _check_user_project_access(user, proyecto):
        return {'error': f'No tienes acceso al proyecto "{proyecto}".', 'count': 0, 'data': []}

    manzanas = _expand_manzana_variants(_parse_list_param(manzana))
    lotes = _parse_list_param(lote)
    idinmueble = (idinmueble or '').strip()

    estados = []
    if estado:
        for item in estado.split(','):
            normalized = _normalize_lote_estado(item)
            if normalized:
                estados.append(normalized)

    estados_consulta = ['Libre', 'Bloqueado', 'Sin Liberar', 'Adjudicado', 'Reservado']
    if estado and not estados and not idinmueble:
        return {
            'error': 'El estado enviado no es válido.',
            'estado_permitido': estados_consulta,
            'count': 0,
            'data': []
        }

    try:
        inventario = Inmuebles.objects.using(proyecto).all()

        if idinmueble:
            inventario = inventario.filter(pk=idinmueble)
        else:
            if estados:
                estado_filter = Q()
                for est in estados:
                    estado_filter |= Q(estado__iexact=est)
                inventario = inventario.filter(estado_filter)
            elif not lotes:
                # Default Libre: "¿qué lotes libres hay?" / libres en manzana X.
                # Si el agente pide lotes concretos (1A,1B) sin estado, no forzar Libre
                # para poder encontrarlos y liberarlos/bloquearlos.
                inventario = inventario.filter(estado__iexact='Libre')

            if manzanas:
                inventario = inventario.filter(manzananumero__in=manzanas)

            if lotes:
                lote_filter = Q()
                for lot_num in lotes:
                    lote_filter |= Q(lotenumero__iexact=lot_num)
                inventario = inventario.filter(lote_filter)

        data = []
        for lote_obj in inventario:
            relacion = None
            estado_lote_norm = _normalize_lote_estado(lote_obj.estado)
            if estado_lote_norm == 'Adjudicado':
                adj = Adjudicacion.objects.using(proyecto).filter(idinmueble=lote_obj.idinmueble).first()
                if adj:
                    cliente_nombre = _get_cliente_nombre(adj.idtercero1)
                    relacion = {
                        'tipo': 'adjudicacion',
                        'referencia': adj.idadjudicacion,
                        'cliente': cliente_nombre
                    }
            elif estado_lote_norm == 'Reservado':
                venta = (ventas_nuevas.objects.using(proyecto)
                         .filter(inmueble=lote_obj.idinmueble)
                         .order_by('-fecha_contrato', '-id_venta')
                         .first())
                if venta:
                    cliente_nombre = _get_cliente_nombre(venta.id_t1)
                    relacion = {
                        'tipo': 'reserva',
                        'referencia': venta.id_venta,
                        'cliente': cliente_nombre
                    }

            data.append({
                'idinmueble': lote_obj.idinmueble,
                'estado': estado_lote_norm or lote_obj.estado,
                'manzana': lote_obj.manzananumero,
                'lote': lote_obj.lotenumero,
                'area_privada': float(lote_obj.areaprivada) if lote_obj.areaprivada else None,
                'precio_m2': float(lote_obj.vrmetrocuadrado) if lote_obj.vrmetrocuadrado else None,
                'valor_lote': _calculate_lote_valor(lote_obj),
                'motivo_bloqueo': lote_obj.obsbloqueo,
                'usuario_bloqueo': lote_obj.usuariobloquea,
                'relacion': relacion
            })

        return {'count': len(data), 'data': data}

    except Exception as exc:
        logger.exception("Error al consultar lotes")
        return {'error': 'Error al consultar lotes.', 'detail': str(exc), 'count': 0, 'data': []}


def lotes_change_status(
    proyecto: str,
    idinmueble: str,
    estado: str,
    motivo_bloqueo: str = None,
    user=None
) -> dict:
    """
    Cambia el estado de un lote entre Libre, Bloqueado y Sin Liberar.

    Solo se pueden modificar lotes cuyo estado actual sea Libre, Bloqueado o Sin Liberar.
    Adjudicado y Reservado no se pueden cambiar por MCP.

    Args:
        proyecto: Nombre del proyecto (requerido)
        idinmueble: ID del lote (requerido)
        estado: Nuevo estado (Libre|Bloqueado|Sin Liberar) (requerido)
        motivo_bloqueo: Requerido si estado=Bloqueado
        user: Usuario Django para verificar permisos y registrar quién bloquea

    Returns:
        dict con idinmueble, estado_anterior y estado_actual
    """
    import datetime
    from andinasoft.shared_models import Inmuebles
    from mcp_server.tools.utils import resolve_proyecto

    idinmueble = (idinmueble or '').strip()
    estado = (estado or '').strip()

    if not idinmueble:
        return {'error': 'Debes enviar "idinmueble".'}
    if not estado:
        return {'error': 'Debes enviar "estado".'}

    proyecto_nombre, err = resolve_proyecto(proyecto)
    if err:
        return err
    proyecto = proyecto_nombre

    if user and not _check_user_project_access(user, proyecto):
        return {'error': f'No tienes acceso al proyecto "{proyecto}".'}

    try:
        lote = Inmuebles.objects.using(proyecto).get(pk=idinmueble)
    except Inmuebles.DoesNotExist:
        return {'error': f'El lote "{idinmueble}" no existe.'}
    except Exception as exc:
        return {'error': 'Error al buscar el lote.', 'detail': str(exc)}

    estado_actual = (lote.estado or '').strip()
    estado_actual_norm = _normalize_lote_estado(estado_actual) or estado_actual
    estados_modificables = ('Libre', 'Bloqueado', 'Sin Liberar')

    if estado_actual_norm not in estados_modificables:
        return {
            'error': (
                f'No se puede modificar el estado de un lote {estado_actual or "sin estado"}. '
                f'Por MCP solo se pueden cambiar lotes en estado Libre, Bloqueado o Sin Liberar '
                f'(no Adjudicado ni Reservado).'
            ),
            'estado_actual': estado_actual,
            'estados_modificables': list(estados_modificables),
        }

    estado_nuevo_norm = _normalize_lote_estado(estado)

    if not estado_nuevo_norm or estado_nuevo_norm not in estados_modificables:
        return {
            'error': 'El estado enviado no es válido.',
            'estado_permitido': list(estados_modificables)
        }

    if estado_nuevo_norm == 'Bloqueado' and not (motivo_bloqueo or '').strip():
        return {'error': 'Debes enviar "motivo_bloqueo" para bloquear un lote.'}

    if estado_actual_norm == estado_nuevo_norm:
        return {
            'error': 'El lote ya se encuentra en el estado solicitado.',
            'estado_actual': estado_actual
        }

    try:
        lote.estado = estado_nuevo_norm
        if estado_nuevo_norm == 'Bloqueado':
            lote.obsbloqueo = motivo_bloqueo
            lote.usuariobloquea = str(user) if user else 'MCP'
            lote.fechadesbloque = datetime.datetime.today()
        else:
            lote.usuariobloquea = ''
            lote.obsbloqueo = ''
            lote.fechadesbloque = None

        lote.save(using=proyecto)

        return {
            'idinmueble': lote.idinmueble,
            'estado_anterior': estado_actual,
            'estado_actual': lote.estado
        }

    except Exception as exc:
        logger.exception("Error al cambiar estado del lote")
        return {'error': 'Error al cambiar el estado del lote.', 'detail': str(exc)}


# Definición de schemas para el MCP
LOTES_TOOLS = [
    {
        'name': 'lotes_list',
        'description': (
            'Consulta inventario de lotes/inmuebles de un proyecto. '
            'Cuándo usarla: listar libres, ubicar lotes concretos antes de liberar/bloquear, '
            'o ver estado de un idinmueble. '
            'Cómo elegir filtros: '
            '(1) "libres / inventario disponible / libres en manzana X" → proyecto + manzana opcional; '
            'si omites estado, filtra solo Libre. '
            '(2) "liberar/bloquear lotes 1A,1B de manzana 6" → proyecto + manzana + lote="1A,1B" '
            'SIN estado=Libre (con lote y sin estado no fuerza Libre; también puedes pasar '
            'estado="Sin Liberar,Bloqueado"). Usa el idinmueble devuelto para lotes_change_status. '
            '(3) Si conoces el ID exacto → idinmueble (ignora estado/manzana/lote). '
            'Si count=0 con idinmueble, reintenta con manzana+lote. '
            'Requiere proyecto; si el usuario no lo dijo, pregunta antes de llamar.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'proyecto': {
                    'type': 'string',
                    'description': (
                        'Nombre del proyecto (ej: Oasis, Fractal, Casas de Verano). '
                        'Obligatorio. No inventes; si falta, pregunta al usuario.'
                    ),
                },
                'estado': {
                    'type': 'string',
                    'description': (
                        'Filtro de estado (case-insensitive), varios separados por coma: '
                        'Libre, Bloqueado, Sin Liberar, Adjudicado, Reservado. '
                        'Default si omites: Libre — excepto si envías lote (entonces no filtra por estado, '
                        'para poder encontrar lotes a liberar/bloquear). '
                        'Para liberar: no uses estado=Libre; omite estado con lote, o usa '
                        '"Sin Liberar,Bloqueado".'
                    ),
                },
                'manzana': {
                    'type': 'string',
                    'description': (
                        'Número(s) de manzana separados por coma (ej: "6", "06", "1,2,3"). '
                        'Tolera padding 6↔06. Úsalo para inventario por manzana o junto con lote.'
                    ),
                },
                'lote': {
                    'type': 'string',
                    'description': (
                        'Número(s) de lote (campo lotenumero), separados por coma '
                        '(ej: "1A,1B", "3", "12A"). Case-insensitive. '
                        'Para pedidos concretos ("liberar 1A y 1B"): pásalos aquí + manzana. '
                        'Con lote y sin estado no se aplica el default Libre.'
                    ),
                },
                'idinmueble': {
                    'type': 'string',
                    'description': (
                        'ID exacto del inmueble en BD (ej: M06L01A o el que devuelva este tool). '
                        'Si se envía, ignora estado, manzana y lote. '
                        'No inventes el ID si no estás seguro: mejor busca por manzana+lote '
                        'y usa el idinmueble de la respuesta.'
                    ),
                },
            },
            'required': ['proyecto'],
        },
    },
    {
        'name': 'lotes_change_status',
        'description': (
            'Cambia el estado de UN lote a Libre, Bloqueado o Sin Liberar. '
            'Antes: confirma con el usuario (ID, proyecto, estado actual→nuevo, motivo si bloquea). '
            'Obtén idinmueble con lotes_list si no lo tienes. '
            'Solo modifica lotes hoy en Libre, Bloqueado o Sin Liberar. '
            'NUNCA Adjudicado ni Reservado. Un lote por llamada.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'proyecto': {
                    'type': 'string',
                    'description': 'Nombre del proyecto del lote (mismo que en lotes_list).',
                },
                'idinmueble': {
                    'type': 'string',
                    'description': (
                        'ID exacto del inmueble (el campo idinmueble de lotes_list). '
                        'No uses solo "1A" o "manzana 6"; debe ser el ID canónico de BD.'
                    ),
                },
                'estado': {
                    'type': 'string',
                    'description': (
                        'Nuevo estado (case-insensitive): Libre, Bloqueado o Sin Liberar. '
                        'Liberar = Libre. Bloquear = Bloqueado (+ motivo_bloqueo).'
                    ),
                },
                'motivo_bloqueo': {
                    'type': 'string',
                    'description': (
                        'Obligatorio si estado=Bloqueado. Pregunta el motivo al usuario '
                        'antes de llamar este tool.'
                    ),
                },
            },
            'required': ['proyecto', 'idinmueble', 'estado'],
        },
    },
]
