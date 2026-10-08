"""Recibos de pago y seguimientos de un negocio, desde el panel de Chatwoot.

`seguimientos` y `recaudos_general` viven en la BD de cada proyecto (Alttum no las
tiene). `seguimientos` es MyISAM: no hay transacción que proteja un doble envío, así
que la llave de idempotencia se reserva primero en ChatwootSeguimientoRef (InnoDB).
"""
import datetime
import logging

from django.db import IntegrityError, transaction

from andinasoft.forms import form_seguimiento
from andinasoft.shared_models import Recaudos_general, seguimientos
from chatwoot_panel.models import ChatwootSeguimientoRef

logger = logging.getLogger(__name__)

TIPOS = [valor for valor, _ in form_seguimiento.tipos_seguimientos]
FORMAS = [valor for valor, _ in form_seguimiento.formas_contacto]
FORMA_POR_DEFECTO = 'Whatsapp'
MAX_COMENTARIO = 500


class NoDisponible(Exception):
    """El proyecto no tiene la tabla (p. ej. Alttum)."""


class DatosInvalidos(ValueError):
    pass


def recibos(proyecto, adj, limite=100):
    try:
        filas = list(
            Recaudos_general.objects.using(proyecto).filter(idadjudicacion=adj)
            .order_by('-fecha', '-idrecaudo')
            .values('numrecibo', 'fecha', 'fecha_pago', 'valor', 'formapago', 'concepto', 'operacion')[:limite]
        )
    except Exception as exc:
        logger.warning('chatwoot_panel: recibos no disponibles en %s: %s', proyecto, exc)
        raise NoDisponible(proyecto) from exc
    return filas


def listar(proyecto, adj, limite=50):
    try:
        filas = list(
            seguimientos.objects.using(proyecto).filter(adj=adj)
            .order_by('-fecha', '-id_seg')
            .values('id_seg', 'fecha', 'tipo_seguimiento', 'forma_contacto', 'respuesta_cliente',
                    'valor_compromiso', 'fecha_compromiso', 'usuario')[:limite]
        )
    except Exception as exc:
        logger.warning('chatwoot_panel: seguimientos no disponibles en %s: %s', proyecto, exc)
        raise NoDisponible(proyecto) from exc
    desde_chatwoot = set(
        ChatwootSeguimientoRef.objects.filter(proyecto=proyecto, adj=adj, seguimiento_id__isnull=False)
        .values_list('seguimiento_id', flat=True)
    )
    for fila in filas:
        fila['desde_chatwoot'] = fila['id_seg'] in desde_chatwoot
    return filas


def validar(datos, hoy=None):
    """Normaliza el formulario del panel. Lanza DatosInvalidos con un mensaje para el agente."""
    hoy = hoy or datetime.date.today()
    tipo = str(datos.get('tipo') or '').strip()
    forma = str(datos.get('forma') or FORMA_POR_DEFECTO).strip()
    comentario = ' '.join(str(datos.get('comentario') or '').split())
    if tipo not in TIPOS:
        raise DatosInvalidos('Elige el tipo de seguimiento.')
    if forma not in FORMAS:
        raise DatosInvalidos('Elige la forma de contacto.')
    if not comentario:
        raise DatosInvalidos('Escribe qué respondió el cliente.')
    if len(comentario) > MAX_COMENTARIO:
        raise DatosInvalidos(f'El comentario no puede pasar de {MAX_COMENTARIO} caracteres.')

    compromiso = bool(datos.get('compromiso'))
    fecha = None
    valor = 0
    if compromiso:
        try:
            fecha = datetime.date.fromisoformat(str(datos.get('fecha_compromiso') or ''))
        except ValueError:
            raise DatosInvalidos('Indica la fecha del compromiso de pago.')
        if fecha < hoy:
            raise DatosInvalidos('La fecha del compromiso no puede ser anterior a hoy.')
        try:
            valor = int(str(datos.get('valor_compromiso') or '').replace('.', '').replace(',', '').strip())
        except ValueError:
            raise DatosInvalidos('Indica el valor del compromiso.')
        if valor <= 0:
            raise DatosInvalidos('El valor del compromiso debe ser mayor que cero.')

    key = str(datos.get('idempotency_key') or '').strip()
    if not 8 <= len(key) <= 64:
        raise DatosInvalidos('Falta la llave del envío; recarga el panel.')
    return {
        'tipo': tipo, 'forma': forma, 'comentario': comentario,
        'compromiso': compromiso, 'fecha_compromiso': fecha, 'valor_compromiso': valor,
        'idempotency_key': key,
    }


def registrar(proyecto, adj, datos, user, *, account_id='', conversation_id='', hoy=None):
    """Crea el seguimiento una sola vez por llave. Devuelve (ref, creado)."""
    hoy = hoy or datetime.date.today()
    try:
        with transaction.atomic():
            ref = ChatwootSeguimientoRef.objects.create(
                idempotency_key=datos['idempotency_key'], proyecto=proyecto, adj=adj,
                chatwoot_account_id=str(account_id or '')[:20],
                chatwoot_conversation_id=str(conversation_id or '')[:20],
                created_by=user,
            )
    except IntegrityError:
        ref = ChatwootSeguimientoRef.objects.get(idempotency_key=datos['idempotency_key'])
        if ref.proyecto != proyecto or ref.adj != adj:
            raise DatosInvalidos('Ese envío ya se registró en otro negocio.')
        return ref, False

    usuario = user.get_username()
    try:
        seguimientos.objects.using(proyecto).create(
            adj=adj,
            fecha=hoy,
            tipo_seguimiento=datos['tipo'],
            forma_contacto=datos['forma'],
            respuesta_cliente=datos['comentario'],
            valor_compromiso=datos['valor_compromiso'],
            fecha_compromiso=datos['fecha_compromiso'],
            usuario=usuario,
        )
        # El pk de `seguimientos` no es AutoField en el modelo: se recupera el id recién creado.
        seguimiento_id = (
            seguimientos.objects.using(proyecto)
            .filter(adj=adj, fecha=hoy, usuario=usuario, tipo_seguimiento=datos['tipo'],
                    respuesta_cliente=datos['comentario'])
            .order_by('-id_seg').values_list('id_seg', flat=True).first()
        )
    except Exception as exc:
        ref.delete()
        logger.exception('chatwoot_panel: no se pudo crear el seguimiento en %s %s', proyecto, adj)
        raise NoDisponible(proyecto) from exc

    ref.seguimiento_id = seguimiento_id
    ref.save(update_fields=['seguimiento_id'])
    return ref, True
