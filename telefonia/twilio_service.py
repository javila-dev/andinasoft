"""Twilio: token del softphone, firma de los webhooks y TwiML para marcar."""
from django.conf import settings
from django.urls import reverse
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Dial, VoiceResponse

TOKEN_TTL = 600  # el token solo sirve para empezar la llamada; la llamada sigue aunque venza
LIMITE_TIMBRE = 40
# El caller ID sale de las líneas del admin (o TELEFONIA_CALLER_ID): ver servicio.lineas().
AJUSTES = ('TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_API_KEY_SID', 'TWILIO_API_KEY_SECRET',
           'TWILIO_TWIML_APP_SID')


def _ajuste(nombre):
    return (getattr(settings, nombre, '') or '').strip()


def faltantes():
    return [n for n in AJUSTES if not _ajuste(n)]


def configurado():
    return not faltantes()


def grabar():
    return bool(getattr(settings, 'TELEFONIA_GRABAR', False))


def duracion_maxima():
    return int(getattr(settings, 'TELEFONIA_DURACION_MAXIMA', 3600) or 3600)


def identidad(user):
    return f'andina-{user.pk}'


def user_id_de(from_twilio):
    """'client:andina-7' → 7, o None."""
    valor = str(from_twilio or '')
    prefijo = 'client:andina-'
    if not valor.startswith(prefijo) or not valor[len(prefijo):].isdigit():
        return None
    return int(valor[len(prefijo):])


def token_de_acceso(user):
    token = AccessToken(
        _ajuste('TWILIO_ACCOUNT_SID'), _ajuste('TWILIO_API_KEY_SID'), _ajuste('TWILIO_API_KEY_SECRET'),
        identity=identidad(user), ttl=TOKEN_TTL,
    )
    token.add_grant(VoiceGrant(outgoing_application_sid=_ajuste('TWILIO_TWIML_APP_SID'), incoming_allow=False))
    jwt = token.to_jwt()
    return jwt.decode() if isinstance(jwt, bytes) else jwt


def base_publica():
    return (getattr(settings, 'TELEFONIA_PUBLIC_BASE_URL', '') or getattr(settings, 'ANDINA_PUBLIC_BASE_URL', '')
            or '').rstrip('/')


def url_publica(nombre_ruta, request=None, query=''):
    """URL absoluta tal como la ve Twilio (detrás del proxy, request.build_absolute_uri no sirve)."""
    ruta = reverse(nombre_ruta) + (f'?{query}' if query else '')
    base = base_publica()
    if base:
        return base + ruta
    return request.build_absolute_uri(ruta) if request is not None else ruta


def firma_valida(request):
    firma = request.META.get('HTTP_X_TWILIO_SIGNATURE', '')
    if not firma or not _ajuste('TWILIO_AUTH_TOKEN'):
        return False
    base = base_publica()
    url = base + request.get_full_path() if base else request.build_absolute_uri()
    return RequestValidator(_ajuste('TWILIO_AUTH_TOKEN')).validate(url, request.POST.dict(), firma)


def twiml_marcar(llamada, request=None):
    estado = url_publica('telefonia:twilio_estado', request, f'l={llamada.pk}')
    respuesta = VoiceResponse()
    opciones = {
        'caller_id': llamada.caller_id or _ajuste('TELEFONIA_CALLER_ID'),
        'answer_on_bridge': True,
        'timeout': LIMITE_TIMBRE,
        'time_limit': duracion_maxima(),
    }
    if grabar():
        opciones.update(record='record-from-answer-dual',
                        recording_status_callback=url_publica('telefonia:twilio_grabacion', request,
                                                              f'l={llamada.pk}'),
                        recording_status_callback_event='completed')
    dial = Dial(**opciones)
    numero = {'status_callback': estado, 'status_callback_event': 'initiated answered completed',
              'status_callback_method': 'POST'}
    if grabar():
        # Lo oye el cliente al contestar, antes de conectar con el agente (Ley 1581).
        numero['url'] = url_publica('telefonia:twilio_aviso', request)
    dial.number(llamada.numero, **numero)
    respuesta.append(dial)
    return str(respuesta)


def twiml_rechazo(mensaje='No se pudo hacer la llamada.'):
    respuesta = VoiceResponse()
    respuesta.say(mensaje, language='es-MX')
    respuesta.hangup()
    return str(respuesta)


def twiml_aviso_grabacion():
    respuesta = VoiceResponse()
    respuesta.say('Esta llamada puede ser grabada.', language='es-MX')
    return str(respuesta)


def twiml_vacio():
    return str(VoiceResponse())
