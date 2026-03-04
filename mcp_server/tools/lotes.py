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
    """Normaliza el estado del lote a uno de los valores válidos."""
    if value is None:
        return None
    normalized = ' '.join(str(value).strip().lower().split())
    estados = {
        'libre': 'Libre',
        'bloqueado': 'Bloqueado',
        'sin liberar': 'Sin Liberar',
        'adjudicado': 'Adjudicado',
        'reservado': 'Reservado'
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
    idinmueble: str = None,
    user=None
) -> dict:
    """
    Consulta lotes por estado, con filtro opcional por manzanas o ID de inmueble.

    Args:
        proyecto: Nombre exacto del proyecto (requerido en práctica)
        estado: Estado del lote (Libre|Bloqueado|Sin Liberar). Default: Libre
        manzana: Lista de manzanas separadas por comas
        idinmueble: ID exacto del lote (si se envía, ignora estado y manzana)
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

    manzanas = _parse_list_param(manzana)
    idinmueble = (idinmueble or '').strip()

    estados = []
    if estado:
        for item in estado.split(','):
            normalized = _normalize_lote_estado(item)
            if normalized:
                estados.append(normalized)

    if estado and not estados and not idinmueble:
        return {
            'error': 'El estado enviado no es válido.',
            'estado_permitido': ['Libre', 'Bloqueado', 'Sin Liberar'],
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
            else:
                inventario = inventario.filter(estado__iexact='Libre')

            if manzanas:
                inventario = inventario.filter(manzananumero__in=manzanas)

        data = []
        for lote in inventario:
            relacion = None
            estado_lote = (lote.estado or '').strip().lower()
            if estado_lote == 'adjudicado':
                adj = Adjudicacion.objects.using(proyecto).filter(idinmueble=lote.idinmueble).first()
                if adj:
                    cliente_nombre = _get_cliente_nombre(adj.idtercero1)
                    relacion = {
                        'tipo': 'adjudicacion',
                        'referencia': adj.idadjudicacion,
                        'cliente': cliente_nombre
                    }
            elif estado_lote == 'reservado':
                venta = (ventas_nuevas.objects.using(proyecto)
                         .filter(inmueble=lote.idinmueble)
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
                'idinmueble': lote.idinmueble,
                'estado': lote.estado,
                'manzana': lote.manzananumero,
                'lote': lote.lotenumero,
                'area_privada': float(lote.areaprivada) if lote.areaprivada else None,
                'precio_m2': float(lote.vrmetrocuadrado) if lote.vrmetrocuadrado else None,
                'valor_lote': _calculate_lote_valor(lote),
                'motivo_bloqueo': lote.obsbloqueo,
                'usuario_bloqueo': lote.usuariobloquea,
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

    if estado_actual in ('Adjudicado', 'Reservado'):
        return {
            'error': f'No se puede modificar el estado de un lote {estado_actual}. Esta acción requiere gestión directa en el sistema.',
            'estado_actual': estado_actual
        }

    estado_nuevo_norm = _normalize_lote_estado(estado)

    if not estado_nuevo_norm:
        return {
            'error': 'El estado enviado no es válido.',
            'estado_permitido': ['Libre', 'Bloqueado', 'Sin Liberar']
        }

    if estado_nuevo_norm == 'Bloqueado' and not (motivo_bloqueo or '').strip():
        return {'error': 'Debes enviar "motivo_bloqueo" para bloquear un lote.'}

    if estado_actual == estado_nuevo_norm:
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
        'description': 'Consulta lotes/inmuebles. Requiere proyecto explícito (preguntar si no lo menciona).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'proyecto': {'type': 'string'},
                'estado': {
                    'type': 'string', 
                    'enum': ['Libre', 'Bloqueado', 'Sin Liberar', 'Adjudicado', 'Reservado']
                },
                'manzana': {'type': 'string', 'description': 'Separadas por comas (ej: 1,2,3)'},
                'idinmueble': {'type': 'string'}
            },
            'required': ['proyecto']
        }
    },
    {
        'name': 'lotes_change_status',
        'description': 'Cambia el estado de un lote.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'proyecto': {'type': 'string'},
                'idinmueble': {'type': 'string'},
                'estado': {
                    'type': 'string', 
                    'enum': ['Libre', 'Bloqueado', 'Sin Liberar']
                },
                'motivo_bloqueo': {'type': 'string', 'description': 'Requerido si estado=Bloqueado'}
            },
            'required': ['proyecto', 'idinmueble', 'estado']
        }
    }
]
