"""
Tools MCP para Adjudicaciones

Proporciona herramientas para consultar el estado de cuenta y los documentos
cargados de una adjudicación en un proyecto específico.

La búsqueda acepta tanto el ID de adjudicación como el nombre o cédula del cliente.
"""
import datetime
import logging
import os
from urllib.parse import quote

from django.conf import settings
from django.core.files.storage import default_storage
from django.db.models import Q

from mcp_server.tools.utils import resolve_proyecto

logger = logging.getLogger(__name__)


# Mapeo de proyecto a empresa recaudadora (igual que en andinasoft/views.py:8471)
_RECAUDADOR = {
    'Tesoro Escondido': 'STATUS COMERCIALIZADORA S.A.S. NIT: 901018375-4',
    'Vegas de Venecia': 'STATUS COMERCIALIZADORA S.A.S. NIT: 901018375-4',
    'Perla del Mar': 'ANDINA CONCEPTOS INMOBILIARIOS S.A.S. NIT: 900993044-9',
    'Sandville Beach': 'ANDINA CONCEPTOS INMOBILIARIOS S.A.S. NIT: 900993044-9',
    'Carmelo Reservado': 'ANDINA CONCEPTOS INMOBILIARIOS S.A.S. NIT: 900993044-9',
}


def _doc_url(proyecto: str, adj: str, descripcion_doc: str) -> str:
    """Construye la URL del storage para un documento de contrato (local o S3/MinIO)."""
    storage_key = f"docs_andinasoft/doc_contratos/{proyecto}/{adj}/{descripcion_doc}.pdf"
    try:
        return default_storage.url(storage_key)
    except Exception:
        encoded = '/'.join(quote(seg) for seg in storage_key.split('/'))
        return settings.MEDIA_URL + encoded


def _find_clientes_por_nombre(valor: str) -> list:
    """
    Busca clientes en la base de datos compartida por nombre o apellido.
    Retorna lista de idTercero (cédulas).

    Estrategias:
      1. nombrecompleto icontains valor
      2. nombres icontains valor OR apellidos icontains valor
      3. Cada palabra del valor en nombrecompleto (AND)
      4. Fuzzy por palabras (Levenshtein ≥ 0.82) — maneja typos como "anderson" → "andersson"
    """
    from andinasoft.models import clientes
    from mcp_server.tools.bank_movements import _normalize_text_for_search, _fuzzy_match

    valor = valor.strip()
    if not valor:
        return []

    # Intento 1: nombre completo como cadena
    qs = clientes.objects.filter(nombrecompleto__icontains=valor)
    logger.info("[DEBUG _find_clientes] intento1 nombrecompleto icontains=%r count=%d", valor, qs.count())
    if qs.exists():
        return list(qs.values_list('idTercero', flat=True))

    # Intento 2: nombres OR apellidos por separado
    qs = clientes.objects.filter(
        Q(nombres__icontains=valor) | Q(apellidos__icontains=valor)
    )
    logger.info("[DEBUG _find_clientes] intento2 nombres/apellidos icontains=%r count=%d", valor, qs.count())
    if qs.exists():
        return list(qs.values_list('idTercero', flat=True))

    # Intento 3: cada palabra del valor en nombrecompleto (AND)
    palabras = valor.split()
    if len(palabras) > 1:
        filtro = Q()
        for p in palabras:
            filtro &= Q(nombrecompleto__icontains=p)
        qs = clientes.objects.filter(filtro)
        logger.info("[DEBUG _find_clientes] intento3 word-by-word count=%d", qs.count())
        if qs.exists():
            return list(qs.values_list('idTercero', flat=True))

    # Intento 4: fuzzy matching por palabras (Levenshtein) para tolerar typos
    # Pre-filtro en DB por los primeros 3 chars de cada palabra para reducir candidatos
    busqueda_norm = _normalize_text_for_search(valor)
    palabras_norm = busqueda_norm.split()

    prefijo_q = Q()
    for p in palabras_norm:
        if len(p) >= 3:
            prefijo_q |= Q(nombrecompleto__icontains=p[:3])

    if not prefijo_q:
        return []

    candidatos = list(
        clientes.objects.filter(prefijo_q).values('idTercero', 'nombrecompleto')
    )
    logger.info("[DEBUG _find_clientes] intento4 fuzzy pre-filtro=%d candidatos", len(candidatos))

    resultados_fuzzy = []
    for c in candidatos:
        nombre_norm = _normalize_text_for_search(c['nombrecompleto'] or '')
        palabras_nombre = nombre_norm.split()
        # Cada palabra buscada debe matchear al menos una palabra del nombre del cliente
        all_match = all(
            any(_fuzzy_match(p_busq, p_nom, threshold=0.82) for p_nom in palabras_nombre)
            for p_busq in palabras_norm
        )
        if all_match:
            resultados_fuzzy.append(c['idTercero'])

    logger.info("[DEBUG _find_clientes] intento4 fuzzy results=%d", len(resultados_fuzzy))
    return resultados_fuzzy


def _find_adjudicacion(proyecto: str, valor: str):
    """
    Resuelve el ID de adjudicación a partir de:
      1. ID exacto de adjudicación (ej. "CV-2025-001")
      2. Nombre parcial del cliente → busca cédulas en clientes (default DB)
         → cruza con Adjudicacion.idtercero1-4
      3. Cédula exacta del cliente → cruza con Adjudicacion.idtercero1-4

    Returns:
        (idadjudicacion: str | None, error: dict | None, multiples: list | None)
        - Exactamente uno encontrado: (id, None, None)
        - Múltiples encontrados: (None, None, [lista resumen])
        - Ninguno encontrado: (None, {'error': ...}, None)
    """
    from andinasoft.shared_models import Adjudicacion
    from andinasoft.models import clientes

    valor = valor.strip()

    # Intento 1: ID exacto de adjudicación
    try:
        Adjudicacion.objects.using(proyecto).get(pk=valor)
        logger.info("[DEBUG _find_adjudicacion] encontrado por ID exacto: %s", valor)
        return (valor, None, None)
    except Adjudicacion.DoesNotExist:
        pass

    # Intento 2: Buscar cédulas por nombre en clientes (default DB)
    cedulas = _find_clientes_por_nombre(valor)
    logger.info("[DEBUG _find_adjudicacion] busqueda por nombre=%r cedulas_encontradas=%d", valor, len(cedulas))

    # Intento 3: Si no encontró por nombre, probar como cédula exacta
    if not cedulas:
        cedulas = [valor]
        logger.info("[DEBUG _find_adjudicacion] intentando como cedula directa: %r", valor)

    # Cruzar cédulas con idtercero1-4 en Adjudicacion
    filtro = Q()
    for c in cedulas:
        filtro |= (
            Q(idtercero1=c) | Q(idtercero2=c) |
            Q(idtercero3=c) | Q(idtercero4=c)
        )
    qs_adj = Adjudicacion.objects.using(proyecto).filter(filtro)
    count = qs_adj.count()
    logger.info("[DEBUG _find_adjudicacion] adjudicaciones encontradas por cedulas=%d", count)

    if count == 0:
        return (
            None,
            {'error': f'No se encontró ninguna adjudicación para "{valor}" en "{proyecto}". '
                      'Verifica el ID de adjudicación, nombre o cédula del cliente.'},
            None
        )

    if count == 1:
        return (qs_adj.first().pk, None, None)

    # Múltiples resultados: enriquecer con nombre del titular para presentar al usuario
    cedulas_set = set(cedulas)
    nombres_map = {
        c.idTercero: f'{c.nombres} {c.apellidos}'.strip()
        for c in clientes.objects.filter(idTercero__in=cedulas_set)
    }
    multiples = []
    for a in qs_adj[:10]:
        nombre_titular = (
            nombres_map.get(a.idtercero1) or
            nombres_map.get(a.idtercero2) or
            nombres_map.get(a.idtercero3) or
            nombres_map.get(a.idtercero4) or
            ''
        )
        multiples.append({
            'idadjudicacion': a.pk,
            'nombre_titular': nombre_titular,
            'inmueble': str(a.idinmueble) if a.idinmueble else None,
            'estado': a.estado,
        })
    return (None, None, multiples)


def _resolver_busqueda(proyecto, idadjudicacion, cliente):
    """
    Centraliza la resolución del ID de adjudicación para los tools.
    Acepta idadjudicacion (ID directo) o cliente (nombre/cédula).

    Returns:
        (adj_id: str | None, respuesta_error: dict | None)
    """
    # Determinar el valor de búsqueda
    valor = (idadjudicacion or '').strip() or (cliente or '').strip()
    if not valor:
        return None, {
            'error': 'Debes proporcionar "idadjudicacion" (ej: "CV-2025-001") '
                     'o "cliente" (nombre o cédula del cliente).'
        }

    adj_id, err, multiples = _find_adjudicacion(proyecto, valor)

    if err:
        return None, err

    if multiples:
        return None, {
            'accion_requerida': (
                f'Se encontraron {len(multiples)} adjudicaciones que coinciden con "{valor}". '
                'PREGUNTA al usuario cuál es la correcta antes de continuar.'
            ),
            'adjudicaciones_encontradas': multiples,
        }

    return adj_id, None


def adjudicacion_estado_cuenta(
    proyecto: str = None,
    idadjudicacion: str = None,
    cliente: str = None,
    user=None
) -> dict:
    """
    Genera el PDF de estado de cuenta para una adjudicación y retorna
    su URL pública junto con un resumen financiero.

    Acepta el ID de adjudicación o el nombre/cédula del cliente para buscarla.

    Args:
        proyecto: Nombre del proyecto.
        idadjudicacion: ID de la adjudicación (ej. "CV-2025-001").
        cliente: Nombre parcial o cédula del cliente titular.
        user: Usuario Django autenticado.

    Returns:
        dict con pdf_url y resumen financiero (titulares, saldos, mora, cuotas próximas).
    """
    from andinasoft.shared_models import Adjudicacion, PlanPagos
    from andinasoft.utilities import pdf_gen

    logger.info(
        "[DEBUG adjudicacion_estado_cuenta] proyecto=%r idadjudicacion=%r cliente=%r user=%r",
        proyecto, idadjudicacion, cliente, str(user) if user else None
    )

    if not (proyecto or '').strip():
        return {
            'accion_requerida': (
                'El usuario no especificó el proyecto. '
                'PREGUNTA: "¿En qué proyecto está la adjudicación?" '
                'y espera su respuesta antes de llamar este tool.'
            )
        }

    proyecto_nombre, err = resolve_proyecto(proyecto)
    if err:
        return err
    proyecto = proyecto_nombre

    adj, err = _resolver_busqueda(proyecto, idadjudicacion, cliente)
    if err:
        return err

    try:
        obj_adj = Adjudicacion.objects.using(proyecto).get(pk=adj)
    except Exception as exc:
        logger.exception("Error buscando adjudicacion")
        return {'error': 'Error consultando la adjudicación.', 'detail': str(exc)}

    try:
        from andinasoft.shared_models import PlanPagos

        today = datetime.date.today()
        next_30_days = today + datetime.timedelta(days=30)

        # Misma lógica que ajax_print_estado_cuenta en andinasoft/views.py:8458
        cuotas_a_la_fecha = PlanPagos.objects.using(proyecto).filter(
            adj=adj, fecha__lte=today
        ).order_by('fecha')

        cuotas_futuras = PlanPagos.objects.using(proyecto).filter(
            adj=adj, fecha__gt=today, fecha__lte=next_30_days
        ).order_by('fecha')

        cuotas_vencidas = []
        total_cuotas_vencidas = {'valor': 0, 'intereses_mora': 0, 'total': 0}

        for q in cuotas_a_la_fecha:
            pendiente = q.pendiente()
            if pendiente.get('total', 0) > 0:
                mora = q.mora()
                cuotas_vencidas.append({
                    'fecha': q.fecha,
                    'idcta': q.pk.split('ADJ')[0],
                    'pendiente': pendiente,
                    'mora': mora,
                })
                total_cuotas_vencidas['valor'] += pendiente.get('total')
                total_cuotas_vencidas['intereses_mora'] += mora.get('valor')
                total_cuotas_vencidas['total'] += pendiente.get('total') + mora.get('valor')

        total_proximo_30dias = sum(
            float(q.cuota or 0) for q in cuotas_futuras
        )

        context = {
            'adj': obj_adj,
            'cuotas_a_la_fecha': cuotas_vencidas,
            'cuotas_futuras': cuotas_futuras,
            'user': user,
            'now': datetime.datetime.now(),
            'totals': total_cuotas_vencidas,
            'recaudador': _RECAUDADOR.get(proyecto),
        }

        filename = f'Estado_de_cuenta_{adj}_{proyecto}.pdf'
        logger.info("[DEBUG adjudicacion_estado_cuenta] generando PDF: %s", filename)
        pdf = pdf_gen('pdf/statement_of_account.html', context, filename)

        if not isinstance(pdf, dict):
            logger.error("[DEBUG adjudicacion_estado_cuenta] pdf_gen fallo (pisa error)")
            return {'error': 'Error generando el PDF del estado de cuenta.'}

        # Verificar que el archivo fue creado
        ruta_archivo = pdf.get('root', '')
        if not os.path.exists(ruta_archivo):
            logger.error("[DEBUG adjudicacion_estado_cuenta] PDF no encontrado en disco: %s", ruta_archivo)
            return {'error': f'El PDF fue procesado pero no se encontró en disco: {ruta_archivo}'}

        logger.info("[DEBUG adjudicacion_estado_cuenta] PDF generado OK: %s (%d bytes)",
                    ruta_archivo, os.path.getsize(ruta_archivo))

        # URL absoluta con filename URL-encoded (espacios → %20)
        pdf_url = settings.DIR_DOWNLOADS + quote(filename)

        # Construir resumen para el agente
        titulares_obj = obj_adj.titulares()
        titulares_nombres = []
        for t in titulares_obj.values():
            if t:
                nombres = getattr(t, 'nombres', '') or ''
                apellidos = getattr(t, 'apellidos', '') or ''
                full = f'{nombres} {apellidos}'.strip()
                if full:
                    titulares_nombres.append(full)

        return {
            'idadjudicacion': adj,
            'proyecto': proyecto,
            'pdf_url': pdf_url,
            'resumen': {
                'titulares': titulares_nombres,
                'inmueble': str(obj_adj.idinmueble) if obj_adj.idinmueble else None,
                'valor_contrato': float(obj_adj.valor or 0),
                'cuotas_vencidas_count': len(cuotas_vencidas),
                'total_capital_vencido': float(total_cuotas_vencidas['valor'] or 0),
                'total_mora': float(total_cuotas_vencidas['intereses_mora'] or 0),
                'total_a_pagar': float(total_cuotas_vencidas['total'] or 0),
                'cuotas_proximas_count': cuotas_futuras.count(),
                'total_proximo_30dias': round(total_proximo_30dias, 2),
            }
        }

    except Exception as exc:
        logger.exception("Error generando estado de cuenta")
        return {'error': 'Error generando el estado de cuenta.', 'detail': str(exc)}


def adjudicacion_documentos(
    proyecto: str = None,
    idadjudicacion: str = None,
    cliente: str = None,
    user=None
) -> dict:
    """
    Lista los documentos cargados para una adjudicación, con metadata y
    URL pública de cada archivo.

    Acepta el ID de adjudicación o el nombre/cédula del cliente para buscarla.

    Args:
        proyecto: Nombre del proyecto.
        idadjudicacion: ID de la adjudicación.
        cliente: Nombre parcial o cédula del cliente titular.
        user: Usuario Django autenticado.

    Returns:
        dict con lista de documentos (descripcion, fecha_carga, usuario_carga, url).
    """
    from andinasoft.shared_models import documentos_contratos

    logger.info(
        "[DEBUG adjudicacion_documentos] proyecto=%r idadjudicacion=%r cliente=%r",
        proyecto, idadjudicacion, cliente
    )

    if not (proyecto or '').strip():
        return {
            'accion_requerida': (
                'El usuario no especificó el proyecto. '
                'PREGUNTA: "¿En qué proyecto está la adjudicación?" '
                'y espera su respuesta antes de llamar este tool.'
            )
        }

    proyecto_nombre, err = resolve_proyecto(proyecto)
    if err:
        return err
    proyecto = proyecto_nombre

    adj, err = _resolver_busqueda(proyecto, idadjudicacion, cliente)
    if err:
        return err

    try:
        docs_qs = documentos_contratos.objects.using(proyecto).filter(adj=adj).order_by('fecha_carga')

        documentos = []
        for doc in docs_qs:
            documentos.append({
                'descripcion': doc.descripcion_doc,
                'fecha_carga': str(doc.fecha_carga) if doc.fecha_carga else None,
                'usuario_carga': doc.usuario_carga,
                'url': _doc_url(proyecto, adj, doc.descripcion_doc),
            })

        resultado = {
            'idadjudicacion': adj,
            'proyecto': proyecto,
            'total_documentos': len(documentos),
            'documentos': documentos,
        }

        if not documentos:
            resultado['nota'] = f'No hay documentos cargados para la adjudicación "{adj}" en "{proyecto}".'

        return resultado

    except Exception as exc:
        logger.exception("Error listando documentos de adjudicacion")
        return {'error': 'Error consultando los documentos.', 'detail': str(exc)}


_SCHEMA_BUSQUEDA = {
    'proyecto': {
        'type': 'string',
        'description': 'Nombre exacto del proyecto (Ej: Casas de Verano).'
    },
    'idadjudicacion': {
        'type': 'string',
        'description': 'ID de adjudicación (Ej: ADJ1). Usar SOLO si el usuario lo provee explícitamente.'
    },
    'cliente': {
        'type': 'string',
        'description': 'Nombre o cédula del titular (Ej: Juan Camilo Castaño, 1037588511). Priorizar este campo si el usuario da un nombre. NO pedir ID extra, la búsqueda es automática.'
    },
}

ADJUDICACIONES_TOOLS = [
    {
        'name': 'adjudicacion_estado_cuenta',
        'description': (
            'Genera PDF de estado de cuenta, URL pública y resumen financiero (saldos, mora, cuotas). '
            'Ejecutar sin preguntar al consultar deudas o saldos, pasando "cliente" o "idadjudicacion". '
            'Auto-resuelve múltiples coincidencias.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': _SCHEMA_BUSQUEDA,
            'required': ['proyecto']
        }
    },
    {
        'name': 'adjudicacion_documentos',
        'description': (
            'Lista documentos cargados (cédulas, contratos, soportes) con fechas, autor y URLs. '
            'Ejecutar sin preguntar al consultar documentos, pasando "cliente" o "idadjudicacion". '
            'Auto-resuelve múltiples coincidencias.'
        ),
        'inputSchema': {
            'type': 'object',
            'properties': _SCHEMA_BUSQUEDA,
            'required': ['proyecto']
        }
    },
]
