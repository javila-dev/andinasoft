"""Qué se puede llamar desde una conversación y cómo se cierra cada llamada.

Frontera de seguridad: el usuario de Andinasoft con el permiso `telefonia.llamar`.
La conversación se confirma con la API de Chatwoot (token del servidor) y el número
siempre sale de Chatwoot o de `clientes`: el navegador solo elige de qué campo.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from andinasoft.models import clientes
from chatwoot_panel.chatwoot_api import nota_privada, obtener_conversacion
from telefonia import numeros
from telefonia.models import LineaSaliente, Llamada

logger = logging.getLogger(__name__)

PERMISO = 'telefonia.llamar'
FUENTE_CHATWOOT = 'chatwoot'
LINEA_AUTO = 'auto'
LINEA_DEFECTO = 'defecto'  # TELEFONIA_CALLER_ID, si no hay líneas en el admin

# CallStatus de Twilio (tramo hacia el cliente) → estado final.
ESTADO_TWILIO = {
    'completed': Llamada.COMPLETADA,
    'busy': Llamada.OCUPADO,
    'no-answer': Llamada.SIN_RESPUESTA,
    'canceled': Llamada.CANCELADA,
    'failed': Llamada.FALLIDA,
}
TEXTO_ESTADO = {
    Llamada.COMPLETADA: 'contestada',
    Llamada.OCUPADO: 'ocupado',
    Llamada.SIN_RESPUESTA: 'no contestó',
    Llamada.CANCELADA: 'cancelada antes de contestar',
    Llamada.FALLIDA: 'no se pudo conectar',
}


class NoPermitido(Exception):
    """Mensaje para el agente; la vista lo devuelve como 400/403."""

    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.status = status


def puede_llamar(user):
    return bool(user and user.is_active and user.has_perm(PERMISO))


def max_llamadas_hora():
    return int(getattr(settings, 'TELEFONIA_MAX_LLAMADAS_HORA', 40) or 40)


def nombre_usuario(user):
    return user.get_full_name() or user.get_username()


def verificar_conversacion(account_id, conversation_id, contact_id=''):
    """Confirma con Chatwoot la conversación y devuelve su contacto: {'id', 'nombre', 'telefono'}."""
    if not str(account_id).isdigit() or not str(conversation_id).isdigit():
        raise NoPermitido('Abre la conversación del cliente en Chatwoot.')
    data = obtener_conversacion(account_id, conversation_id)
    if data is None:
        raise NoPermitido('No se pudo confirmar la conversación con Chatwoot.', status=502)
    sender = (data.get('meta') or {}).get('sender') or {}
    if str(data.get('id')) != str(conversation_id) or not sender.get('id'):
        raise NoPermitido('No se pudo confirmar la conversación con Chatwoot.', status=502)
    if contact_id and str(sender['id']) != str(contact_id):
        raise NoPermitido('El contacto no corresponde a esa conversación. Recarga el panel.')
    return {
        'id': str(sender['id']),
        'nombre': (sender.get('name') or '').strip(),
        'telefono': sender.get('phone_number') or '',
    }


def destinos(contacto, cedula=''):
    """Números para llamar: [{'id', 'etiqueta', 'numero' (10 dígitos)}], sin repetir números."""
    lista = []
    vistos = set()

    def agregar(id_, etiqueta, diez):
        if diez in vistos:
            return
        vistos.add(diez)
        lista.append({'id': id_, 'etiqueta': etiqueta, 'numero': diez})

    for diez in numeros.numeros_en(contacto.get('telefono')):
        agregar(FUENTE_CHATWOOT, 'Número de la conversación', diez)

    cedula = str(cedula or '').strip()
    if cedula:
        fila = clientes.objects.filter(pk=cedula).values(*numeros.CAMPOS).first()
        for campo in numeros.CAMPOS if fila else ():
            encontrados = numeros.numeros_en(fila.get(campo))
            for i, diez in enumerate(encontrados):
                varios = len(encontrados) > 1
                agregar(f'{campo}.{i + 1}' if varios else campo,
                        numeros.ETIQUETAS[campo] + (f' ({i + 1})' if varios else ''), diez)
    return lista


def resolver_destino(contacto, cedula, destino_id):
    for d in destinos(contacto, cedula):
        if d['id'] == destino_id:
            return d
    raise NoPermitido('Ese número ya no está disponible. Vuelve a cargar los números.')


def _linea_defecto():
    numero = (getattr(settings, 'TELEFONIA_CALLER_ID', '') or '').strip()
    return {'id': LINEA_DEFECTO, 'nombre': 'Línea principal', 'numero': numero} if numero else None


def lineas():
    """Líneas para «Llamar desde»: las activas del admin o, si no hay, TELEFONIA_CALLER_ID."""
    activas = [{'id': str(l.pk), 'nombre': l.nombre, 'numero': l.numero}
               for l in LineaSaliente.objects.filter(activa=True)]
    if activas:
        return activas
    defecto = _linea_defecto()
    return [defecto] if defecto else []


def elegir_linea(linea_id):
    """La línea pedida o, en automático, la activa que lleva más tiempo sin usarse. Marca el uso."""
    linea_id = str(linea_id or LINEA_AUTO)
    with transaction.atomic():
        activas = LineaSaliente.objects.select_for_update().filter(activa=True)
        if linea_id == LINEA_AUTO:
            linea = activas.order_by(F('ultimo_uso').asc(nulls_first=True), 'orden', 'pk').first()
        else:
            linea = activas.filter(pk=linea_id).first() if linea_id.isdigit() else None
        if linea is not None:
            LineaSaliente.objects.filter(pk=linea.pk).update(ultimo_uso=timezone.now())
            return {'id': str(linea.pk), 'nombre': linea.nombre, 'numero': linea.numero}

    defecto = _linea_defecto()
    if defecto and linea_id in (LINEA_AUTO, LINEA_DEFECTO) and not LineaSaliente.objects.filter(activa=True).exists():
        return defecto
    if linea_id != LINEA_AUTO:
        raise NoPermitido('Esa línea ya no está disponible. Elige otra.')
    raise NoPermitido('No hay líneas para llamar. Avisa a sistemas.', status=503)


def iniciar(user, *, account_id, conversation_id, contact_id, cedula, destino_id, linea_id='', ip=''):
    """Valida todo y deja la llamada lista para marcar. Devuelve (Llamada, destino)."""
    if not puede_llamar(user):
        raise NoPermitido('Tu usuario no tiene permiso para hacer llamadas.', status=403)
    desde = timezone.now() - timedelta(hours=1)
    if Llamada.objects.filter(user=user, created_at__gte=desde).count() >= max_llamadas_hora():
        raise NoPermitido('Llegaste al límite de llamadas por hora. Espera un momento.', status=429)

    contacto = verificar_conversacion(account_id, conversation_id, contact_id)
    destino = resolver_destino(contacto, cedula, destino_id)
    linea = elegir_linea(linea_id)
    llamada = Llamada.objects.create(
        user=user,
        numero=numeros.e164(destino['numero']),
        fuente=destino['id'][:20],
        caller_id=linea['numero'],
        linea_nombre=linea['nombre'][:60],
        cliente_id=str(cedula or '')[:255],
        chatwoot_account_id=str(account_id),
        chatwoot_conversation_id=str(conversation_id),
        chatwoot_contact_id=contacto['id'],
        ip=ip[:64],
    )
    return llamada, destino


def _duracion(segundos):
    m, s = divmod(int(segundos or 0), 60)
    return f'{m}:{s:02d}'


def texto_nota(llamada):
    numero = numeros.enmascarar(llamada.numero[-10:])
    fuente = (numeros.ETIQUETAS.get(llamada.fuente.split('.')[0])
              or ('número de la conversación' if llamada.fuente == FUENTE_CHATWOOT else llamada.fuente))
    desde = f' desde {llamada.linea_nombre}' if llamada.linea_nombre else ''
    linea = f'📞 Llamada saliente a {numero} ({fuente}){desde} por {nombre_usuario(llamada.user)}: '
    linea += TEXTO_ESTADO.get(llamada.estado, llamada.estado)
    if llamada.estado == Llamada.COMPLETADA:
        linea += f' · {_duracion(llamada.duracion)}'
    if llamada.grabada:
        linea += ' · grabada'
    return linea


def finalizar(llamada, estado, duracion=0, detalle=''):
    """Cierra la llamada una sola vez (los webhooks pueden repetirse) y la anota en Chatwoot."""
    cambios = {'estado': estado, 'finalizada_at': timezone.now(), 'duracion': int(duracion or 0)}
    if detalle:
        cambios['detalle'] = detalle[:255]
    abiertas = (Llamada.INICIANDO, Llamada.EN_CURSO)
    if not Llamada.objects.filter(pk=llamada.pk, estado__in=abiertas).update(**cambios):
        return False
    for campo, valor in cambios.items():
        setattr(llamada, campo, valor)
    anotar(llamada)
    return True


def anotar(llamada):
    """Nota privada en la conversación; la marca primero para no anotarla dos veces."""
    if not Llamada.objects.filter(pk=llamada.pk, nota_privada=False).update(nota_privada=True):
        return False
    if nota_privada(llamada.chatwoot_account_id, llamada.chatwoot_conversation_id, texto_nota(llamada)):
        llamada.nota_privada = True
        return True
    Llamada.objects.filter(pk=llamada.pk).update(nota_privada=False)
    return False
