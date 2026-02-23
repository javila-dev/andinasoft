"""
Vistas para el servidor MCP (Model Context Protocol)

Soporta dos transportes:
1. Streamable HTTP (recomendado): POST único a /mcp/
2. SSE legacy (deprecated): GET /mcp/sse + POST /mcp/messages

Referencias:
- https://modelcontextprotocol.io/specification/2025-03-26/basic/transports
"""
import json
import logging
import time
import uuid

from django.http import JsonResponse, StreamingHttpResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from api_auth.decorators import api_token_auth

logger = logging.getLogger(__name__)


# Importar tools y sus schemas
from mcp_server.tools.lotes import (
    lotes_list, lotes_change_status, LOTES_TOOLS
)
from mcp_server.tools.bank_movements import (
    bank_movements_list, bank_movements_create,
    bank_movements_mark_used, bank_movements_for_receipt,
    BANK_MOVEMENTS_TOOLS
)


# Combinar todos los tools disponibles
ALL_TOOLS = LOTES_TOOLS + BANK_MOVEMENTS_TOOLS

# Almacén simple de sesiones (en producción usar Redis/DB)
_sessions = {}


# ============================================================================
# STREAMABLE HTTP TRANSPORT (Recomendado - MCP 2025)
# ============================================================================

@csrf_exempt
@api_token_auth
def mcp_streamable_endpoint(request):
    """
    Endpoint principal Streamable HTTP para MCP.

    Soporta:
    - POST: Recibe mensajes JSON-RPC, responde con JSON o SSE
    - GET: Stream SSE para notificaciones servidor→cliente

    Headers requeridos:
    - Authorization: Token <api-key>
    - Accept: application/json, text/event-stream (para POST)
    - Accept: text/event-stream (para GET)

    URL: https://tu-dominio.com/mcp/
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Token inválido o no autenticado'}, status=401)

    if request.method == 'POST':
        return _handle_streamable_post(request)
    elif request.method == 'GET':
        return _handle_streamable_get(request)
    elif request.method == 'DELETE':
        return _handle_session_delete(request)
    else:
        return JsonResponse({'error': 'Method not allowed'}, status=405)


def _handle_streamable_post(request):
    """Maneja POST en Streamable HTTP."""
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            'jsonrpc': '2.0',
            'error': {'code': -32700, 'message': 'Parse error'},
            'id': None
        }, status=400)

    # Verificar si es batch o mensaje único
    is_batch = isinstance(payload, list)
    messages = payload if is_batch else [payload]

    # Verificar header Accept para decidir formato de respuesta
    accept = request.META.get('HTTP_ACCEPT', '')
    wants_sse = 'text/event-stream' in accept

    # Procesar mensajes
    responses = []
    session_id = request.META.get('HTTP_MCP_SESSION_ID')

    for msg in messages:
        method = msg.get('method', '')
        params = msg.get('params', {})
        msg_id = msg.get('id')

        # Si es notificación (sin id), no requiere respuesta
        if msg_id is None and method.startswith('notifications/'):
            continue

        result = _process_jsonrpc_message(method, params, request.user, session_id)

        if 'error' in result:
            responses.append({
                'jsonrpc': '2.0',
                'error': result['error'],
                'id': msg_id
            })
        else:
            response_obj = {
                'jsonrpc': '2.0',
                'result': result.get('result', result),
                'id': msg_id
            }
            # Agregar session_id en initialize
            if method == 'initialize' and 'session_id' in result:
                session_id = result['session_id']
            responses.append(response_obj)

    # Si no hay respuestas (solo notificaciones), devolver 202
    if not responses:
        return HttpResponse(status=202)

    # Decidir formato de respuesta
    if wants_sse and len(responses) > 1:
        # Responder con SSE stream
        return _create_sse_response(responses, session_id)
    else:
        # Responder con JSON
        response_data = responses if is_batch else responses[0]
        response = JsonResponse(response_data, safe=False)
        if session_id:
            response['Mcp-Session-Id'] = session_id
        return response


def _handle_streamable_get(request):
    """Maneja GET en Streamable HTTP (stream de notificaciones)."""
    accept = request.META.get('HTTP_ACCEPT', '')
    if 'text/event-stream' not in accept:
        return JsonResponse({'error': 'Accept header must include text/event-stream'}, status=406)

    def event_stream():
        """Generador de eventos SSE."""
        # En una implementación completa, aquí se enviarían notificaciones
        # Por ahora solo keepalive
        while True:
            try:
                yield ": keepalive\n\n"
                time.sleep(30)
            except GeneratorExit:
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


def _handle_session_delete(request):
    """Maneja DELETE para terminar sesión."""
    session_id = request.META.get('HTTP_MCP_SESSION_ID')
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    return HttpResponse(status=204)


def _create_sse_response(responses, session_id=None):
    """Crea una respuesta SSE con múltiples mensajes."""
    def event_stream():
        for resp in responses:
            event_id = str(uuid.uuid4())
            data = json.dumps(resp, ensure_ascii=False)
            yield f"event: message\nid: {event_id}\ndata: {data}\n\n"

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    if session_id:
        response['Mcp-Session-Id'] = session_id
    return response


# ============================================================================
# SSE LEGACY TRANSPORT (Deprecated - para compatibilidad)
# ============================================================================

@csrf_exempt
@api_token_auth
@require_http_methods(["GET"])
def mcp_sse_endpoint(request):
    """
    Endpoint SSE legacy para el servidor MCP.
    DEPRECATED: Usar Streamable HTTP (/mcp/) en su lugar.

    Los clientes MCP legacy se conectan aquí para recibir el endpoint de mensajes.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Token inválido o no autenticado'}, status=401)

    def event_stream():
        """Generador de eventos SSE."""
        # Enviar evento con la URL del endpoint de mensajes (protocolo legacy)
        yield f"event: endpoint\ndata: /mcp/messages\n\n"

        # Mantener la conexión abierta con keepalives
        while True:
            try:
                yield ": keepalive\n\n"
                time.sleep(30)
            except GeneratorExit:
                break

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
@api_token_auth
@require_http_methods(["POST"])
def mcp_messages_endpoint(request):
    """
    Endpoint para mensajes JSON-RPC (SSE legacy).
    DEPRECATED: Usar Streamable HTTP (/mcp/) en su lugar.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Token inválido o no autenticado'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({
            'jsonrpc': '2.0',
            'error': {'code': -32700, 'message': 'Parse error'},
            'id': None
        }, status=400)

    method = payload.get('method', '')
    params = payload.get('params', {})
    msg_id = payload.get('id')

    result = _process_jsonrpc_message(method, params, request.user, None)

    if 'error' in result:
        return JsonResponse({
            'jsonrpc': '2.0',
            'error': result['error'],
            'id': msg_id
        })

    return JsonResponse({
        'jsonrpc': '2.0',
        'result': result.get('result', result),
        'id': msg_id
    })


# ============================================================================
# LÓGICA COMPARTIDA
# ============================================================================

def _process_jsonrpc_message(method: str, params: dict, user, session_id: str = None) -> dict:
    """Procesa un mensaje JSON-RPC y retorna el resultado."""
    try:
        if method == 'initialize':
            return _handle_initialize(params)
        elif method == 'tools/list':
            return _handle_list_tools()
        elif method == 'tools/call':
            return _handle_call_tool(params, user)
        elif method == 'ping':
            return {'result': {}}
        elif method.startswith('notifications/'):
            # Notificaciones no requieren respuesta
            return {'result': {}}
        else:
            return {'error': {'code': -32601, 'message': f'Method not found: {method}'}}
    except Exception as e:
        logger.exception(f"Error procesando mensaje MCP: {method}")
        return {'error': {'code': -32603, 'message': str(e)}}


def _handle_initialize(params: dict) -> dict:
    """Maneja la inicialización del cliente MCP."""
    # Generar session ID
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        'created': time.time(),
        'client_info': params.get('clientInfo', {})
    }

    return {
        'result': {
            'protocolVersion': '2024-11-05',
            'capabilities': {
                'tools': {}
            },
            'serverInfo': {
                'name': 'andinasoft-mcp',
                'version': '1.0.0'
            }
        },
        'session_id': session_id
    }


def _handle_list_tools() -> dict:
    """Retorna la lista de tools disponibles."""
    return {'result': {'tools': ALL_TOOLS}}


def _handle_call_tool(params: dict, user) -> dict:
    """Ejecuta un tool y retorna el resultado."""
    tool_name = params.get('name', '')
    arguments = params.get('arguments', {})

    # Mapeo de tools a funciones
    tool_functions = {
        'lotes_list': lambda args: lotes_list(
            proyecto=args.get('proyecto'),
            estado=args.get('estado'),
            manzana=args.get('manzana'),
            idinmueble=args.get('idinmueble'),
            user=user
        ),
        'lotes_change_status': lambda args: lotes_change_status(
            proyecto=args.get('proyecto'),
            idinmueble=args.get('idinmueble'),
            estado=args.get('estado'),
            motivo_bloqueo=args.get('motivo_bloqueo'),
            user=user
        ),
        'bank_movements_list': lambda args: bank_movements_list(
            fecha_desde=args.get('fecha_desde'),
            fecha_hasta=args.get('fecha_hasta'),
            cuenta=args.get('cuenta'),
            cuenta_numero=args.get('cuenta_numero'),
            empresa=args.get('empresa'),
            estado=args.get('estado'),
            usado_agente=args.get('usado_agente'),
            valor_positivo=args.get('valor_positivo'),
            descripcion=args.get('descripcion'),
            page=args.get('page', 1),
            page_size=args.get('page_size', 100)
        ),
        'bank_movements_create': lambda args: bank_movements_create(
            movimientos=args.get('movimientos', []),
            cuenta=args.get('cuenta'),
            cuenta_numero=args.get('cuenta_numero'),
            empresa=args.get('empresa')
        ),
        'bank_movements_mark_used': lambda args: bank_movements_mark_used(
            movement_id=args.get('movement_id'),
            usado_agente=args.get('usado_agente'),
            recibo_asociado_agente=args.get('recibo_asociado_agente'),
            proyecto_asociado_agente=args.get('proyecto_asociado_agente')
        ),
        'bank_movements_for_receipt': lambda args: bank_movements_for_receipt(
            proyecto=args.get('proyecto'),
            fecha_pago=args.get('fecha_pago'),
            recibo_asociado=args.get('recibo_asociado')
        ),
    }

    if tool_name not in tool_functions:
        return {
            'result': {
                'content': [{'type': 'text', 'text': json.dumps({'error': f"Tool '{tool_name}' no encontrada"})}],
                'isError': True
            }
        }

    try:
        result = tool_functions[tool_name](arguments)
        return {
            'result': {
                'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False, default=str)}],
                'isError': 'error' in result
            }
        }
    except Exception as e:
        logger.exception(f"Error ejecutando tool {tool_name}")
        return {
            'result': {
                'content': [{'type': 'text', 'text': json.dumps({'error': str(e)})}],
                'isError': True
            }
        }


# ============================================================================
# HEALTH CHECK
# ============================================================================

@csrf_exempt
@require_http_methods(["GET"])
def mcp_health(request):
    """Endpoint de health check para el servidor MCP."""
    return JsonResponse({
        'status': 'ok',
        'server': 'andinasoft-mcp',
        'version': '1.0.0',
        'transports': {
            'streamable_http': '/mcp/',
            'sse_legacy': '/mcp/sse'
        },
        'tools_count': len(ALL_TOOLS),
        'tools': [t['name'] for t in ALL_TOOLS]
    })
