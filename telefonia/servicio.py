"""Qué se puede llamar desde una conversación y cómo se cierra cada llamada.

Frontera de seguridad: el usuario de Andinasoft con el permiso del panel de Chatwoot
(un solo permiso para todo el panel: cartera, llamadas y links de pago).
La conversación se confirma con la API de Chatwoot (token del servidor) y el número
siempre sale de Chatwoot o de `clientes`: el navegador solo elige de qué campo.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from andinasoft.models import clientes
from chatwoot_panel import seguimientos_service
from chatwoot_panel.auth import PERMISO as PERMISO_PANEL
from chatwoot_panel.chatwoot_api import nota_privada, obtener_conversacion
from chatwoot_panel.identificacion import negocios_de, puede_ver_proyecto
from telefonia import numeros
from telefonia.models import LineaSaliente, Llamada, NumeroDescartado

logger = logging.getLogger(__name__)

PERMISO = PERMISO_PANEL  # sin permisos aparte: quien usa el panel puede llamar
FUENTE_CHATWOOT = 'chatwoot'
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
        raise NoPermitido('Abre la conversación del cliente en Lyvio.')
    data = obtener_conversacion(account_id, conversation_id)
    if data is None:
        raise NoPermitido('No se pudo confirmar la conversación con Lyvio.', status=502)
    sender = (data.get('meta') or {}).get('sender') or {}
    if str(data.get('id')) != str(conversation_id) or not sender.get('id'):
        raise NoPermitido('No se pudo confirmar la conversación con Lyvio.', status=502)
    if contact_id and str(sender['id']) != str(contact_id):
        raise NoPermitido('El contacto no corresponde a esa conversación. Recarga el panel.')
    return {
        'id': str(sender['id']),
        'nombre': (sender.get('name') or '').strip(),
        'telefono': sender.get('phone_number') or '',
    }


def descartados(contacto, cedula=''):
    """Números (10 dígitos) marcados como equivocados para este cliente o este contacto."""
    filtro = Q(chatwoot_contact_id=contacto.get('id')) if contacto.get('id') else Q(pk__in=[])
    if cedula:
        filtro |= Q(cliente_id=cedula)
    return {n[-10:] for n in NumeroDescartado.objects.filter(filtro).values_list('numero', flat=True)}


def destinos(contacto, cedula=''):
    """Números para llamar: [{'id', 'etiqueta', 'numero' (10 dígitos)}], sin repetir ni equivocados."""
    lista = []
    cedula = str(cedula or '').strip()
    vistos = descartados(contacto, cedula)

    def agregar(id_, etiqueta, diez):
        if diez in vistos:
            return
        vistos.add(diez)
        lista.append({'id': id_, 'etiqueta': etiqueta, 'numero': diez})

    for diez in numeros.numeros_en(contacto.get('telefono')):
        agregar(FUENTE_CHATWOOT, 'Número de la conversación', diez)

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


def elegir_linea():
    """Rotación automática: la línea activa que lleva más tiempo sin usarse. Marca el uso.

    El agente no elige la línea. Sin líneas activas en el admin se usa TELEFONIA_CALLER_ID.
    """
    with transaction.atomic():
        linea = (LineaSaliente.objects.select_for_update().filter(activa=True)
                 .order_by(F('ultimo_uso').asc(nulls_first=True), 'orden', 'pk').first())
        if linea is not None:
            LineaSaliente.objects.filter(pk=linea.pk).update(ultimo_uso=timezone.now())
            return {'id': str(linea.pk), 'nombre': linea.nombre, 'numero': linea.numero}
    defecto = _linea_defecto()
    if defecto:
        return defecto
    raise NoPermitido('No hay líneas para llamar. Avisa a sistemas.', status=503)


def iniciar(user, *, account_id, conversation_id, contact_id, cedula, destino_id, ip=''):
    """Valida todo y deja la llamada lista para marcar. Devuelve (Llamada, destino)."""
    if not puede_llamar(user):
        raise NoPermitido('Tu usuario no tiene permiso para hacer llamadas.', status=403)
    desde = timezone.now() - timedelta(hours=1)
    if Llamada.objects.filter(user=user, created_at__gte=desde).count() >= max_llamadas_hora():
        raise NoPermitido('Llegaste al límite de llamadas por hora. Espera un momento.', status=429)

    contacto = verificar_conversacion(account_id, conversation_id, contact_id)
    destino = resolver_destino(contacto, cedula, destino_id)
    linea = elegir_linea()
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


# ---------- resultado de la llamada (un clic al colgar) ----------

ETIQUETA_RESULTADO = dict(Llamada.RESULTADOS)
TIPO_POR_RESULTADO = {Llamada.R_NUMERO_EQUIVOCADO: 'Anotacion'}  # el resto: 'Cobro'


def _forma_llamada():
    """Valor de forma_contacto para llamadas (en form_seguimiento es 'LLamada')."""
    return next((f for f in seguimientos_service.FORMAS if f.lower() == 'llamada'), seguimientos_service.FORMAS[0])


def comentario_resultado(llamada, resultado, comentario=''):
    partes = [f'Llamada ({_duracion(llamada.duracion)})' if llamada.estado == Llamada.COMPLETADA else 'Llamada',
              ETIQUETA_RESULTADO[resultado]]
    texto = ': '.join(partes) + '.'
    comentario = ' '.join(str(comentario or '').split())
    if comentario:
        texto += ' ' + comentario
    return texto[:seguimientos_service.MAX_COMENTARIO]


def _negocio_del_cliente(user, llamada, proyecto, adj):
    """El negocio tiene que ser del cliente de la llamada y de un proyecto del usuario."""
    if not proyecto or not adj:
        return False
    if not llamada.cliente_id:
        raise NoPermitido('La llamada no tiene un cliente identificado: registra el seguimiento desde el panel.')
    if not puede_ver_proyecto(user, proyecto):
        raise NoPermitido('No tienes acceso a ese proyecto en Andinasoft.', status=403)
    if not any(n['adj'] == adj for n in negocios_de([llamada.cliente_id], [proyecto])):
        raise NoPermitido('Ese negocio no es del cliente de la llamada.')
    return True


def registrar_resultado(user, llamada, *, resultado, comentario='', compromiso=None, proyecto='', adj=''):
    """Guarda el resultado, el seguimiento del negocio (si hay) y la nota en Chatwoot. Una sola vez.

    compromiso: {'fecha': 'AAAA-MM-DD', 'valor': '150000'} cuando resultado es compromiso de pago.
    Devuelve {'seguimiento': bool, 'nota_privada': bool, 'descartado': bool}.
    """
    if llamada.user_id != user.pk:
        raise NoPermitido('Esa llamada no es tuya.', status=403)
    if resultado not in ETIQUETA_RESULTADO:
        raise NoPermitido('Elige el resultado de la llamada.')
    if llamada.estado == Llamada.INICIANDO:
        raise NoPermitido('La llamada no llegó a salir.')
    if llamada.resultado:
        raise NoPermitido('Ya registraste el resultado de esta llamada.', status=409)

    proyecto, adj = str(proyecto or '').strip()[:60], str(adj or '').strip()[:30]
    con_negocio = _negocio_del_cliente(user, llamada, proyecto, adj)
    compromiso = compromiso or {}
    es_compromiso = resultado == Llamada.R_COMPROMISO
    datos = seguimientos_service.validar({
        'tipo': TIPO_POR_RESULTADO.get(resultado, 'Cobro'),
        'forma': _forma_llamada(),
        'comentario': comentario_resultado(llamada, resultado, comentario),
        'compromiso': es_compromiso,
        'fecha_compromiso': compromiso.get('fecha') if es_compromiso else '',
        'valor_compromiso': compromiso.get('valor') if es_compromiso else '',
        'idempotency_key': f'telefonia-llamada-{llamada.pk}',
    })

    # Reserva el resultado primero: si dos clics llegan juntos, solo uno sigue.
    if not Llamada.objects.filter(pk=llamada.pk, resultado='').update(
            resultado=resultado, resultado_comentario=datos['comentario'], proyecto=proyecto, adj=adj):
        raise NoPermitido('Ya registraste el resultado de esta llamada.', status=409)
    llamada.resultado, llamada.proyecto, llamada.adj = resultado, proyecto, adj

    seguimiento = False
    if con_negocio:
        try:
            ref, _ = seguimientos_service.registrar(
                proyecto, adj, datos, user,
                account_id=llamada.chatwoot_account_id, conversation_id=llamada.chatwoot_conversation_id,
            )
        except seguimientos_service.NoDisponible:
            ref = None
        if ref is not None:
            seguimiento = True
            Llamada.objects.filter(pk=llamada.pk).update(seguimiento_id=ref.seguimiento_id)

    descartado = False
    if resultado == Llamada.R_NUMERO_EQUIVOCADO:
        desde_chatwoot = llamada.fuente == FUENTE_CHATWOOT
        NumeroDescartado.objects.create(
            numero=llamada.numero, llamada=llamada, user=user,
            cliente_id='' if desde_chatwoot else llamada.cliente_id,
            chatwoot_contact_id=llamada.chatwoot_contact_id if desde_chatwoot else '',
        )
        descartado = True

    texto = f'📌 Resultado de la llamada por {nombre_usuario(user)}: {datos["comentario"]}'
    if datos['compromiso']:
        texto += (f"\nCompromiso de pago: ${datos['valor_compromiso']:,} para el "
                  f"{datos['fecha_compromiso']:%d/%m/%Y}").replace(',', '.')
    if con_negocio:
        texto += f'\nSeguimiento en {proyecto} · {adj}' + ('' if seguimiento else ' (no se pudo registrar)')
    if descartado:
        texto += '\nEl número quedó descartado para este cliente.'
    nota = nota_privada(llamada.chatwoot_account_id, llamada.chatwoot_conversation_id, texto)
    return {'seguimiento': seguimiento, 'nota_privada': nota, 'descartado': descartado}
