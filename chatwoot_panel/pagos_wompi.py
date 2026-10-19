"""Links de pago de Wompi desde el panel de Chatwoot.

Cada proyecto se cobra con un comercio Wompi (ComercioWompi/ProyectoWompi en el admin);
la llave privada de cada comercio va en WOMPI_LLAVES_PRIVADAS (`alias=prv_...;alias2=prv_...`).
El link es de un solo pago, con valor fijo y vencimiento. El valor lo propone el panel
y el servidor lo limita a lo que el cliente debe hoy. Ver docs/telefonia.md (links de pago).
"""
import logging
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from andinasoft.estado_cuenta_service import build_estado_cuenta_context
from chatwoot_panel.auth import PERMISO as PERMISO_PANEL
from chatwoot_panel.chatwoot_api import enviar_mensaje, nombre_para_contacto, obtener_conversacion
from chatwoot_panel.identificacion import puede_ver_proyecto
from chatwoot_panel.models import LinkPagoWompi, ProyectoWompi

logger = logging.getLogger(__name__)

PERMISO = PERMISO_PANEL  # sin permisos aparte: quien usa el panel puede enviar links
API_PRODUCCION = 'https://production.wompi.co/v1'
API_SANDBOX = 'https://sandbox.wompi.co/v1'
CHECKOUT = 'https://checkout.wompi.co/l/'
TIMEOUT = 15


class LinkError(Exception):
    """Mensaje para el agente."""

    def __init__(self, mensaje, status=400):
        super().__init__(mensaje)
        self.status = status


class ImagenRechazada(LinkError):
    """Wompi rechazó image_url (p. ej. 'Image url no permitida'): se reintenta sin logo."""


def puede_enviar(user):
    return bool(user and user.is_active and user.has_perm(PERMISO))


def llaves_privadas():
    """'andina=prv_prod_x;VENECIA:prv_prod_y' → {'andina': 'prv_prod_x', 'venecia': 'prv_prod_y'}.

    Alias y llave se separan con '=' o ':'; el alias no distingue mayúsculas.
    """
    crudo = (getattr(settings, 'WOMPI_LLAVES_PRIVADAS', '') or '').strip().strip('"').strip("'")
    llaves = {}
    for parte in crudo.split(';'):
        sep = '=' if '=' in parte else ':'
        alias, _, llave = parte.partition(sep)
        if alias.strip() and llave.strip():
            llaves[alias.strip().lower()] = llave.strip()
    return llaves


def llave_de(comercio):
    return llaves_privadas().get((comercio.alias or '').strip().lower()) if comercio else None


def vigencia():
    return timedelta(hours=int(getattr(settings, 'WOMPI_LINK_VIGENCIA_HORAS', 72) or 72))


def valor_minimo():
    return int(getattr(settings, 'WOMPI_LINK_VALOR_MINIMO', 1500) or 1500)


def _asignacion(proyecto):
    return ProyectoWompi.objects.select_related('comercio').filter(proyecto=proyecto, comercio__activo=True).first()


def comercio_de(proyecto):
    asignacion = _asignacion(proyecto)
    return asignacion.comercio if asignacion else None


def bucket_publico_configurado():
    """Con S3, el logo tiene que ir al bucket público (sin firma). Si AWS_PUBLIC_BUCKET_NAME falta,
    PublicMediaStorage cae al bucket privado y Wompi recibiría una URL que responde 403."""
    if not getattr(settings, 'USE_S3_MEDIA', False):
        return True
    publico = getattr(settings, 'AWS_PUBLIC_BUCKET_NAME', '') or ''
    return bool(publico) and publico != (getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '') or '')


def logo_visible(url):
    """True si la URL se ve sin credenciales (lo que hace Wompi)."""
    try:
        response = requests.get(url, timeout=5, stream=True)
        response.close()
    except requests.RequestException:
        return False
    return response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/')


def logo_url(proyecto):
    """URL pública (https) del logo del proyecto para el link, o None.

    En S3 la URL ya es absoluta; con almacenamiento local (/media/…) se completa con
    ANDINA_PUBLIC_BASE_URL, y sin ella no se manda imagen (Wompi no podría verla).
    """
    asignacion = _asignacion(proyecto)
    if asignacion is None or not asignacion.logo:
        return None
    if not bucket_publico_configurado():
        logger.error('chatwoot_panel: AWS_PUBLIC_BUCKET_NAME no está configurado (o es el privado): '
                     'el link de %s sale sin logo', proyecto)
        return None
    try:
        url = asignacion.logo.url
    except Exception:
        logger.warning('chatwoot_panel: no se pudo obtener la URL del logo de %s', proyecto)
        return None
    if url.startswith('/'):
        # Almacenamiento local (desarrollo): la base pública puede ser otro servidor que no tiene el
        # archivo, así que solo se manda si de verdad se ve desde fuera.
        base = (getattr(settings, 'ANDINA_PUBLIC_BASE_URL', '') or '').rstrip('/')
        url = base + url if base.startswith('https://') else ''
        return url if url and logo_visible(url) else None
    return url if url.startswith('https://') else None


def disponible(proyecto):
    """True si el proyecto tiene comercio activo con llave configurada (para mostrar el botón)."""
    return bool(llave_de(comercio_de(proyecto)))


def cifras(proyecto, adj, user):
    """{'total_vencido', 'pago_total_hoy', 'inmueble', 'estado', 'titular'} con las cifras del estado de cuenta."""
    context, error = build_estado_cuenta_context(proyecto, adj, user)
    if error:
        raise LinkError(error, status=404)
    a = context['adj']
    totales = context['totals']
    saldos = a.saldos_por_cartera
    titulares = [t.nombrecompleto for t in a.titulares.values() if getattr(t, 'nombrecompleto', '')]
    return {
        'total_vencido': int(Decimal(str(totales['total']))),
        'pago_total_hoy': int(Decimal(str(saldos.pago_hoy.total_pago_hoy)) + Decimal(str(totales['intereses_mora']))),
        'inmueble': a.idinmueble or '',
        'estado': getattr(a.extra_info, 'Estado', '') or '',
        'titular': titulares[0] if titulares else '',
    }


def _host(llave):
    return API_SANDBOX if llave.startswith('prv_test_') else API_PRODUCCION


def _crear_en_wompi(llave, *, nombre, descripcion, valor, vence, sku, imagen=None):
    response = requests.post(
        f'{_host(llave)}/payment_links',
        headers={'Authorization': f'Bearer {llave}', 'Content-Type': 'application/json'},
        json={
            'name': nombre[:100],
            'description': descripcion[:255],
            'single_use': True,
            'collect_shipping': False,
            'currency': 'COP',
            'amount_in_cents': valor * 100,
            'expires_at': vence.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            'sku': sku[:36],
            'redirect_url': getattr(settings, 'WOMPI_LINK_REDIRECT_URL', '') or None,
            'image_url': imagen or None,
        },
        timeout=TIMEOUT,
    )
    if response.status_code >= 400:
        logger.error('chatwoot_panel: Wompi rechazó el link (%s): %s', response.status_code, response.text[:500])
        if imagen and 'image' in response.text.lower():
            raise ImagenRechazada('Wompi no aceptó la imagen del link.', status=502)
        raise LinkError('Wompi no pudo crear el link. Intenta de nuevo o avisa a sistemas.', status=502)
    link_id = ((response.json() or {}).get('data') or {}).get('id') or ''
    if not link_id:
        raise LinkError('Wompi no devolvió el link.', status=502)
    return link_id


def texto_mensaje(link, nombre_cliente, inmueble):
    nombre = nombre_para_contacto(nombre_cliente).split(' ')[0] if nombre_cliente else ''
    valor = f'${link.valor:,}'.replace(',', '.')
    vence = timezone.localtime(link.vence)
    lugar = f'{link.proyecto} ({inmueble})' if inmueble else link.proyecto
    return (f'Hola{" " + nombre if nombre else ""}, este es tu link de pago de {lugar} por {valor}:\n'
            f'{link.url}\n'
            f'Es de un solo uso y vence el {vence:%d/%m/%Y a las %I:%M %p}.')


def crear_link(user, proyecto, adj, *, valor, account_id, conversation_id, idempotency_key, enviar=True):
    """Crea (una vez por llave) el link y, si `enviar`, lo manda a la conversación. Devuelve (link, mensaje, enviado)."""
    if not puede_enviar(user):
        raise LinkError('Tu usuario no tiene permiso para enviar links de pago.', status=403)
    if not puede_ver_proyecto(user, proyecto):
        raise LinkError('No tienes acceso a este proyecto en Andinasoft.', status=403)
    key = str(idempotency_key or '').strip()
    if not 8 <= len(key) <= 64:
        raise LinkError('Falta la llave del envío; recarga el panel.')

    existente = LinkPagoWompi.objects.filter(idempotency_key=key).first()
    if existente is not None:
        if existente.proyecto != proyecto or existente.adj != adj:
            raise LinkError('Ese envío ya se usó en otro negocio.')
        if not existente.link_id:
            raise LinkError('Ese link se está creando. Espera un momento.', status=409)
        return existente, '', existente.enviado

    comercio = comercio_de(proyecto)
    llave = llave_de(comercio)
    if not llave:
        raise LinkError('Este proyecto no tiene un comercio Wompi configurado. Avisa a sistemas.', status=503)
    if not str(account_id).isdigit() or not str(conversation_id).isdigit() \
            or obtener_conversacion(account_id, conversation_id) is None:
        raise LinkError('No se pudo confirmar la conversación con Chatwoot.', status=502)

    try:
        valor = int(str(valor or '').replace('.', '').replace(',', '').strip())
    except ValueError:
        raise LinkError('Indica el valor del link.')
    c = cifras(proyecto, adj, user)
    if c['estado'].lower().startswith('desistido'):
        raise LinkError('El negocio está desistido: no se envían links de pago.')
    if valor < valor_minimo():
        raise LinkError(f'El valor mínimo es ${valor_minimo():,}.'.replace(',', '.'))
    if valor > c['pago_total_hoy']:
        raise LinkError(f"El valor no puede pasar de lo que cancela el negocio hoy (${c['pago_total_hoy']:,})."
                        .replace(',', '.'))

    vence = timezone.now() + vigencia()
    try:
        with transaction.atomic():
            link = LinkPagoWompi.objects.create(
                idempotency_key=key, comercio=comercio, proyecto=proyecto, adj=adj, valor=valor, vence=vence,
                chatwoot_account_id=str(account_id), chatwoot_conversation_id=str(conversation_id), created_by=user,
            )
    except IntegrityError:
        raise LinkError('Ese link se está creando. Espera un momento.', status=409)

    datos_link = dict(nombre=f'{proyecto} · {adj}', descripcion=f'Pago {c["inmueble"] or adj} · {adj}',
                      valor=valor, vence=vence, sku=adj)
    imagen = logo_url(proyecto)
    sin_logo = False
    try:
        try:
            link_id = _crear_en_wompi(llave, imagen=imagen, **datos_link)
        except ImagenRechazada:
            # El logo nunca debe impedir cobrar: se crea igual, sin imagen.
            logger.warning('chatwoot_panel: Wompi rechazó el logo de %s (%s); se crea sin logo', proyecto, imagen)
            link_id = _crear_en_wompi(llave, imagen=None, **datos_link)
            sin_logo = True
    except LinkError:
        link.delete()
        raise
    except requests.RequestException:
        link.delete()
        logger.exception('chatwoot_panel: Wompi no respondió al crear el link de %s %s', proyecto, adj)
        raise LinkError('Wompi no respondió. Intenta de nuevo.', status=502)

    link.link_id = link_id
    link.url = CHECKOUT + link_id
    link.save(update_fields=['link_id', 'url'])
    link.sin_logo = sin_logo  # solo para avisar en el panel

    mensaje = texto_mensaje(link, c['titular'], c['inmueble'])
    enviado = False
    if enviar:
        enviado = enviar_mensaje(account_id, conversation_id, mensaje)
        if enviado:
            link.enviado = True
            link.save(update_fields=['enviado'])
    return link, mensaje, enviado
