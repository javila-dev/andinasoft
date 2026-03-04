"""
Tools MCP para Comisiones

Proporciona herramientas para consultar comisiones por asesor, proyecto y rango de fechas.
"""
import logging
from collections import defaultdict
from django.db.models import Q
from django.utils.dateparse import parse_date

logger = logging.getLogger(__name__)


def _find_asesor(valor: str):
    """
    Busca un asesor por cédula exacta o nombre parcial.
    Retorna lista de (cedula, nombre_completo).
    """
    from django.db.models import Q as DjQ
    from andinasoft.models import asesores

    valor = (valor or '').strip()
    logger.info("[DEBUG _find_asesor] buscando valor=%r", valor)
    if not valor:
        return []

    # Intento 1: cédula exacta
    try:
        a = asesores.objects.get(cedula=valor)
        logger.info("[DEBUG _find_asesor] encontrado por cedula exacta: %s / %s", a.cedula, a.nombre)
        return [(a.cedula, a.nombre or '')]
    except asesores.DoesNotExist:
        logger.info("[DEBUG _find_asesor] no encontrado por cedula exacta")

    # Intento 2: nombre como cadena completa (icontains)
    qs = asesores.objects.filter(nombre__icontains=valor)
    logger.info("[DEBUG _find_asesor] intento2 icontains nombre=%r count=%d", valor, qs.count())
    if qs.exists():
        resultados = [(a.cedula, a.nombre or '') for a in qs]
        logger.info("[DEBUG _find_asesor] encontrados intento2: %s", resultados)
        return resultados

    # Intento 3: cada palabra del nombre por separado (AND) — maneja acentos y orden distinto
    palabras = valor.split()
    if len(palabras) > 1:
        filtro = DjQ()
        for p in palabras:
            filtro &= DjQ(nombre__icontains=p)
        qs = asesores.objects.filter(filtro)
        logger.info("[DEBUG _find_asesor] intento3 word-by-word count=%d", qs.count())
        if qs.exists():
            resultados = [(a.cedula, a.nombre or '') for a in qs]
            logger.info("[DEBUG _find_asesor] encontrados intento3: %s", resultados)
            return resultados

    # Log muestra de asesores para comparar
    muestra = list(asesores.objects.values_list('cedula', 'nombre')[:10])
    logger.info("[DEBUG _find_asesor] no encontrado. Muestra de asesores en DB: %s", muestra)
    return []


def comisiones_list(
    proyecto: str = None,
    fecha_desde: str = None,
    fecha_hasta: str = None,
    asesor: str = None,
    user=None
) -> dict:
    """
    Consulta comisiones por proyecto, rango de fechas y/o asesor.
    Devuelve el detalle y totales agrupados por fecha.

    Args:
        proyecto: Nombre del proyecto (opcional en schema, pero requerido en práctica)
        fecha_desde: Fecha inicio YYYY-MM-DD (default: primer día del mes actual)
        fecha_hasta: Fecha fin YYYY-MM-DD (default: hoy)
        asesor: Nombre o cédula del asesor (opcional)
        user: Usuario Django

    Returns:
        dict con asesor_encontrado, resumen_por_fecha, totales y detalle
    """
    from andinasoft.shared_models import Pagocomision
    from django.utils import timezone
    from mcp_server.tools.utils import resolve_proyecto

    logger.info(
        "[DEBUG comisiones_list] ENTRADA: proyecto=%r asesor=%r fecha_desde=%r fecha_hasta=%r "
        "user=%r (pk=%s)",
        proyecto, asesor, fecha_desde, fecha_hasta,
        str(user) if user else None,
        getattr(user, 'pk', None)
    )

    # Si no se especificó proyecto, devolver instrucción para preguntar al usuario
    if not (proyecto or '').strip():
        from andinasoft.models import proyectos as ProyectosModel
        available = sorted([p.proyecto for p in ProyectosModel.objects.all()])
        return {
            'accion_requerida': (
                'El usuario no especificó el proyecto. '
                'PREGUNTA: "¿En qué proyecto quieres consultar las comisiones?" '
                'y espera su respuesta antes de llamar este tool.'
            ),
            'proyectos_disponibles': available
        }

    proyecto_nombre, err = resolve_proyecto(proyecto)
    if err:
        return err
    proyecto = proyecto_nombre

    # Fechas por defecto: mes actual
    hoy = timezone.now().date()
    if not fecha_desde:
        fecha_desde = hoy.replace(day=1).isoformat()
    if not fecha_hasta:
        fecha_hasta = hoy.isoformat()

    fecha_desde_dt = parse_date(fecha_desde)
    fecha_hasta_dt = parse_date(fecha_hasta)

    if not fecha_desde_dt or not fecha_hasta_dt:
        return {'error': 'Formato de fecha inválido, usa YYYY-MM-DD'}

    if fecha_desde_dt > fecha_hasta_dt:
        return {'error': '"fecha_desde" no puede ser mayor que "fecha_hasta"'}

    # Buscar asesor
    cedulas = []
    asesor_info = []

    if asesor:
        # Se especificó asesor explícitamente: buscar por nombre o cédula
        resultados = _find_asesor(asesor)
        if not resultados:
            return {
                'error': f'No encontramos ningún asesor con el nombre o cédula "{asesor}".',
                'sugerencia': 'Pregunta al usuario su número de cédula de asesor para buscarlo directamente.'
            }
        if len(resultados) > 3:
            nombres = ', '.join([r[1] for r in resultados[:5]])
            return {
                'error': f'El nombre "{asesor}" es ambiguo, encontramos {len(resultados)} asesores: {nombres}... Sé más específico.',
                'count': len(resultados),
                'sugerencia': 'Pide al usuario que especifique mejor el nombre del asesor o que dé su cédula.'
            }
        cedulas = [r[0] for r in resultados]
        asesor_info = resultados

    elif user:
        # Sin asesor explícito: auto-detectar desde el perfil del usuario autenticado
        try:
            from andinasoft.models import Profiles
            profile = Profiles.objects.get(user=user)
            logger.info("[DEBUG comisiones_list] profile encontrado: identificacion=%r", profile.identificacion)
            if profile.identificacion:
                resultados = _find_asesor(profile.identificacion)
                logger.info("[DEBUG comisiones_list] _find_asesor por profile.identificacion=%r -> %s", profile.identificacion, resultados)
                if resultados:
                    cedulas = [r[0] for r in resultados]
                    asesor_info = resultados
        except Exception as e:
            logger.info("[DEBUG comisiones_list] error buscando profile: %s", e)

        # Si no se pudo auto-detectar el asesor (sin perfil, sin identificacion,
        # o identificacion no coincide con ningún asesor), pedir al usuario.
        # Nunca devolver todo el proyecto por defecto.
        if not cedulas:
            return {
                'accion_requerida': (
                    'No se pudo detectar automáticamente el asesor. '
                    'PREGUNTA al usuario su nombre completo o cédula y vuelve a llamar '
                    'con ese valor en el parámetro "asesor".'
                )
            }

    try:
        logger.info("comisiones_list: proyecto=%s asesor=%s fechas=%s/%s cedulas=%s",
                    proyecto, asesor, fecha_desde, fecha_hasta, cedulas)
        queryset = Pagocomision.objects.using(proyecto).filter(
            fecha__range=(fecha_desde_dt, fecha_hasta_dt)
        ).order_by('fecha')

        if cedulas:
            filtro = Q()
            for c in cedulas:
                filtro |= Q(idgestor=c)
            queryset = queryset.filter(filtro)

        # Cargar nombres de asesores para el detalle
        from andinasoft.models import asesores as AsesoresModel
        cedulas_en_resultado = set(p.idgestor for p in queryset if p.idgestor)
        nombres_map = {}
        for a in AsesoresModel.objects.filter(cedula__in=cedulas_en_resultado):
            nombres_map[a.cedula] = a.nombre or ''

        # Construir detalle y agrupar por fecha
        detalle = []
        por_fecha = defaultdict(lambda: {
            'comision': 0.0,
            'retefuente': 0.0,
            'pagoneto': 0.0,
            'registros': 0
        })
        total_comision = 0.0
        total_retefuente = 0.0
        total_pagoneto = 0.0

        for p in queryset:
            fecha_str = p.fecha.isoformat() if p.fecha else None
            comision = float(p.comision or 0)
            retefuente = float(p.retefuente or 0)
            pagoneto = float(p.pagoneto or 0)
            nombre_asesor = nombres_map.get(p.idgestor, p.idgestor)

            detalle.append({
                'id_pago': p.id_pago,
                'fecha': fecha_str,
                'asesor': nombre_asesor,
                'cedula': p.idgestor,
                'idadjudicacion': p.idadjudicacion,
                'comision': comision,
                'retefuente': retefuente,
                'pagoneto': pagoneto,
            })

            if fecha_str:
                por_fecha[fecha_str]['comision'] += comision
                por_fecha[fecha_str]['retefuente'] += retefuente
                por_fecha[fecha_str]['pagoneto'] += pagoneto
                por_fecha[fecha_str]['registros'] += 1

            total_comision += comision
            total_retefuente += retefuente
            total_pagoneto += pagoneto

        resumen_por_fecha = [
            {
                'fecha': fecha,
                'comision': round(vals['comision'], 2),
                'retefuente': round(vals['retefuente'], 2),
                'pagoneto': round(vals['pagoneto'], 2),
                'registros': vals['registros']
            }
            for fecha, vals in sorted(por_fecha.items())
        ]

        resultado = {
            'proyecto': proyecto,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'asesor_buscado': asesor,
            'asesores_encontrados': [{'cedula': c, 'nombre': n} for c, n in asesor_info] if asesor_info else None,
            'total_registros': len(detalle),
            'resumen_por_fecha': resumen_por_fecha,
            'totales': {
                'comision': round(total_comision, 2),
                'retefuente': round(total_retefuente, 2),
                'pagoneto': round(total_pagoneto, 2),
            },
            'detalle': detalle
        }

        if len(detalle) == 0:
            resultado['agente'] = 'Sin resultados. DETENTE: no repitas esta llamada para otros proyectos. Informa al usuario que no se encontraron comisiones en este proyecto y pregunta si desea consultar otro.'

        return resultado

    except Exception as exc:
        logger.exception("Error al consultar comisiones")
        return {'error': 'Error al consultar comisiones.', 'detail': str(exc)}


COMISIONES_TOOLS = [
    {
        'name': 'comisiones_list',
        'description': (
            'Consulta comisiones liquidadas por proyecto, fechas y asesor. '
            'Requiere proyecto explícito (preguntar si no lo menciona). '
            'SIEMPRE pasa "asesor" con el nombre del usuario cuando diga "mis comisiones" — '
            'usa el nombre que conoces del usuario en la conversación (ej: "Jorge"). '
            'Solo omite "asesor" si el usuario pide ver las comisiones de TODOS.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'proyecto': {
                    'type': 'string',
                    'description': 'Nombre del proyecto'
                },
                'fecha_desde': {
                    'type': 'string',
                    'description': 'YYYY-MM-DD (Default: inicio mes actual)'
                },
                'fecha_hasta': {
                    'type': 'string',
                    'description': 'YYYY-MM-DD (Default: hoy)'
                },
                'asesor': {
                    'type': 'string',
                    'description': (
                        'Nombre o cédula del asesor. '
                        'Pasar SIEMPRE cuando el usuario diga "mis comisiones" o hable en primera persona — '
                        'usa el nombre del usuario que conoces del contexto de la conversación. '
                        'Omitir solo si el usuario pide ver las comisiones de todos.'
                    )
                }
            },
            'required': ['proyecto']
        }
    }
]
