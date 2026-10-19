"""Softphone (ventana aparte, sesión normal de Andinasoft) y webhooks de Twilio.

El iframe de Chatwoot no tiene permiso de micrófono, por eso el softphone es una
ventana de primer nivel que abre el panel. Ver docs/telefonia.md.
"""
import json
import logging
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from chatwoot_panel.auth import client_ip
from telefonia import numeros, servicio, twilio_service
from telefonia.models import Llamada

logger = logging.getLogger(__name__)

SDK_URL_DEFECTO = 'https://cdn.jsdelivr.net/npm/@twilio/voice-sdk@2.18.5/dist/twilio.min.js'
VENCE_INICIO = timedelta(minutes=2)  # entre pedir el token y que Twilio pida el TwiML


def sdk_url():
    return getattr(settings, 'TWILIO_VOICE_SDK_URL', '') or SDK_URL_DEFECTO


def _origen(url):
    p = urlparse(url)
    return f'{p.scheme}://{p.netloc}' if p.scheme and p.netloc else ''


def _csp():
    sdk = _origen(sdk_url())
    return (
        f"default-src 'self'; script-src 'self' {sdk}; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self' https://*.twilio.com wss://*.twilio.com; "
        "media-src 'self' blob: https://*.twilio.com; worker-src 'self' blob:; "
        "object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
    )


def _json_body(request):
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _texto(valor, largo=40):
    return str(valor or '').strip()[:largo]


def _ids(body):
    return {
        'account_id': _texto(body.get('account_id'), 20),
        'conversation_id': _texto(body.get('conversation_id'), 20),
        'contact_id': _texto(body.get('contact_id'), 20),
        'cedula': _texto(body.get('cedula'), 255),
    }


def _error(exc):
    return JsonResponse({'detail': str(exc)}, status=exc.status)


# ---------- softphone ----------

@require_GET
@login_required
def softphone(request):
    context = {
        'permitido': servicio.puede_llamar(request.user),
        'configurado': twilio_service.configurado(),
        'nombre': servicio.nombre_usuario(request.user),
        'sdk_url': sdk_url(),
    }
    response = render(request, 'telefonia/softphone.html', context)
    response['Content-Security-Policy'] = _csp()
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


def _api(view_func):
    """APIs del softphone: sesión normal + CSRF (es una ventana de primer nivel) y permiso de llamar."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({'detail': 'Tu sesión de Andinasoft venció. Recarga esta ventana.'}, status=401)
        if not servicio.puede_llamar(request.user):
            return JsonResponse({'detail': 'Tu usuario no tiene permiso para hacer llamadas.'}, status=403)
        response = view_func(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response

    return _wrapped


@require_POST
@_api
def api_destinos(request):
    ids = _ids(_json_body(request))
    try:
        contacto = servicio.verificar_conversacion(ids['account_id'], ids['conversation_id'], ids['contact_id'])
        lista = servicio.destinos(contacto, ids['cedula'])
    except servicio.NoPermitido as exc:
        return _error(exc)
    return JsonResponse({
        'contacto': contacto['nombre'],
        'destinos': [{'id': d['id'], 'etiqueta': d['etiqueta'], 'numero': numeros.enmascarar(d['numero'])}
                     for d in lista],
        'grabar': twilio_service.grabar(),
    })


@require_POST
@_api
def api_llamar(request):
    if not twilio_service.configurado():
        logger.error('telefonia: faltan ajustes %s', ', '.join(twilio_service.faltantes()))
        return JsonResponse({'detail': 'La telefonía no está configurada. Avisa a sistemas.'}, status=503)
    body = _json_body(request)
    try:
        # La línea de salida la elige el servidor (rotación automática), nunca el navegador.
        llamada, destino = servicio.iniciar(
            request.user, destino_id=_texto(body.get('destino'), 30), ip=client_ip(request), **_ids(body),
        )
    except servicio.NoPermitido as exc:
        return _error(exc)
    return JsonResponse({
        'llamada': llamada.pk,
        'token': twilio_service.token_de_acceso(request.user),
        'numero': numeros.enmascarar(destino['numero']),
        'etiqueta': destino['etiqueta'],
        'linea': llamada.linea_nombre,
    }, status=201)


@require_GET
@_api
def api_llamada(request, pk):
    llamada = Llamada.objects.filter(pk=pk, user=request.user).first()
    if llamada is None:
        return JsonResponse({'detail': 'Llamada no encontrada.'}, status=404)
    return JsonResponse({
        'llamada': llamada.pk,
        'estado': llamada.estado,
        'estado_texto': llamada.get_estado_display(),
        'finalizada': llamada.finalizada,
        'duracion': llamada.duracion,
        'nota_privada': llamada.nota_privada,
        'resultado': llamada.resultado,
    })


@require_POST
@_api
def api_resultado(request, pk):
    """Resultado de la llamada en un clic: seguimiento del negocio y nota en Chatwoot."""
    llamada = Llamada.objects.select_related('user').filter(pk=pk, user=request.user).first()
    if llamada is None:
        return JsonResponse({'detail': 'Llamada no encontrada.'}, status=404)
    body = _json_body(request)
    compromiso = body.get('compromiso') if isinstance(body.get('compromiso'), dict) else {}
    try:
        resultado = servicio.registrar_resultado(
            request.user, llamada,
            resultado=_texto(body.get('resultado'), 20),
            comentario=_texto(body.get('comentario'), 400),
            compromiso={'fecha': _texto(compromiso.get('fecha'), 10), 'valor': _texto(compromiso.get('valor'), 15)},
            proyecto=_texto(body.get('proyecto'), 60),
            adj=_texto(body.get('adj'), 30),
        )
    except servicio.NoPermitido as exc:
        return _error(exc)
    except servicio.seguimientos_service.DatosInvalidos as exc:
        return JsonResponse({'detail': str(exc)}, status=400)
    return JsonResponse(resultado, status=201)


# ---------- webhooks de Twilio ----------

def _twiml(xml):
    return HttpResponse(xml, content_type='text/xml')


def _twilio(view_func):
    """Solo peticiones firmadas por Twilio (X-Twilio-Signature)."""

    @csrf_exempt
    @require_POST
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not twilio_service.firma_valida(request):
            logger.warning('telefonia: webhook sin firma válida en %s desde %s', request.path, client_ip(request))
            return HttpResponseForbidden('firma inválida')
        return view_func(request, *args, **kwargs)

    return _wrapped


def _llamada_de(request):
    pk = request.GET.get('l') or ''
    return Llamada.objects.select_related('user').filter(pk=pk).first() if pk.isdigit() else None


@_twilio
def twilio_voz(request):
    """TwiML App → el navegador pidió marcar. Solo marca la llamada que creó api_llamar."""
    pk = request.POST.get('llamada', '')
    llamada = Llamada.objects.select_related('user').filter(pk=pk).first() if pk.isdigit() else None
    user_id = twilio_service.user_id_de(request.POST.get('From'))
    valida = (
        llamada is not None and user_id == llamada.user_id and llamada.estado == Llamada.INICIANDO
        and not llamada.call_sid and timezone.now() - llamada.created_at <= VENCE_INICIO
        and servicio.puede_llamar(llamada.user)
    )
    if not valida:
        logger.warning('telefonia: TwiML rechazado (llamada=%s, from=%s)', pk, request.POST.get('From'))
        if llamada is not None and llamada.estado == Llamada.INICIANDO:
            servicio.finalizar(llamada, Llamada.FALLIDA, detalle='Solicitud de marcado inválida o vencida.')
        return _twiml(twilio_service.twiml_rechazo())

    llamada.call_sid = request.POST.get('CallSid', '')[:64]
    llamada.estado = Llamada.EN_CURSO
    llamada.grabada = twilio_service.grabar()
    Llamada.objects.filter(pk=llamada.pk).update(
        call_sid=llamada.call_sid, estado=llamada.estado, grabada=llamada.grabada)
    return _twiml(twilio_service.twiml_marcar(llamada, request))


@_twilio
def twilio_estado(request):
    """Estado del tramo hacia el cliente (?l=) o, desde la TwiML App, del tramo del navegador."""
    llamada = _llamada_de(request)
    status = request.POST.get('CallStatus', '')
    if llamada is not None:
        if status == 'initiated':
            Llamada.objects.filter(pk=llamada.pk, dial_sid='').update(dial_sid=request.POST.get('CallSid', '')[:64])
        elif status == 'in-progress':
            Llamada.objects.filter(pk=llamada.pk, contestada_at__isnull=True).update(
                contestada_at=timezone.now(), dial_sid=request.POST.get('CallSid', '')[:64])
        elif status in servicio.ESTADO_TWILIO:
            Llamada.objects.filter(pk=llamada.pk, dial_sid='').update(dial_sid=request.POST.get('CallSid', '')[:64])
            servicio.finalizar(llamada, servicio.ESTADO_TWILIO[status], request.POST.get('CallDuration') or 0)
        return _twiml(twilio_service.twiml_vacio())

    # Tramo del navegador: solo cierra si nunca se llegó a marcar al cliente (si no, cierra el otro tramo).
    sid = request.POST.get('CallSid', '')
    if status in servicio.ESTADO_TWILIO and sid:
        llamada = Llamada.objects.select_related('user').filter(call_sid=sid, dial_sid='').first()
        if llamada is not None and llamada.contestada_at is None:
            servicio.finalizar(llamada, Llamada.CANCELADA if status == 'completed' else servicio.ESTADO_TWILIO[status])
    return _twiml(twilio_service.twiml_vacio())


@_twilio
def twilio_grabacion(request):
    llamada = _llamada_de(request)
    if llamada is not None and request.POST.get('RecordingStatus') == 'completed':
        Llamada.objects.filter(pk=llamada.pk).update(
            grabada=True, grabacion_sid=request.POST.get('RecordingSid', '')[:64])
    return _twiml(twilio_service.twiml_vacio())


@_twilio
def twilio_aviso(request):
    return _twiml(twilio_service.twiml_aviso_grabacion())
