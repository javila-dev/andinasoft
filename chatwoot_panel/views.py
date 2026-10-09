import datetime
import json
import logging
import re
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from andinasoft.estado_cuenta_service import build_estado_cuenta_context
from andinasoft.handlers_functions import abrir_documento_contrato
from andinasoft.promesas_service import resumen_promesa
from andinasoft.servicio_cliente_service import url_ficha
from andinasoft.shared_models import documentos_contratos
from chatwoot_panel import seguimientos_service
from chatwoot_panel.auth import auditar, emitir_token, panel_api, puede_usar_panel, revocar
from chatwoot_panel.chatwoot_api import borrar_cedula_de_contacto, guardar_cedula_en_contacto, nota_privada
from chatwoot_panel.identificacion import (
    buscar_manual, enmascarar, puede_ver_proyecto, resolver_cliente, resolver_contexto,
)
from chatwoot_panel.models import ChatwootContactLink
from client_portal.services.documents import build_account_statement_response

logger = logging.getLogger(__name__)


def chatwoot_origin():
    return (getattr(settings, 'CHATWOOT_ORIGIN', '') or '').strip().rstrip('/')


def _csp(frame_ancestors):
    return (
        "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-src blob:; object-src 'none'; base-uri 'none'; "
        f"form-action 'self'; frame-ancestors {frame_ancestors}"
    )


def _nombre(user):
    return user.get_full_name() or user.get_username()


@require_GET
@xframe_options_exempt
def panel(request):
    """Página que Chatwoot carga en el iframe. No lleva datos: todo llega por la API."""
    origin = chatwoot_origin()
    response = render(request, 'chatwoot_panel/panel.html', {
        'chatwoot_origin': origin,
        'debug': settings.DEBUG,
    })
    response['Content-Security-Policy'] = _csp(origin or "'none'")
    response['Referrer-Policy'] = 'no-referrer'
    return response


@login_required
@require_http_methods(['GET', 'POST'])
def conectar(request):
    """Ventana aparte (primer nivel): con la sesión normal autoriza el panel."""
    context = {'nombre': _nombre(request.user), 'permitido': puede_usar_panel(request.user)}
    template = 'chatwoot_panel/conectar.html'
    if request.method == 'POST' and context['permitido']:
        token, raw = emitir_token(request.user, request)
        auditar(request, 'conectar', token=token)
        context['token'] = raw
        template = 'chatwoot_panel/conectado.html'

    response = render(request, template, context)
    response['Content-Security-Policy'] = _csp("'none'")
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@require_GET
@panel_api
def api_yo(request):
    user = request.user
    return JsonResponse({
        'usuario': user.get_username(),
        'nombre': _nombre(user),
        'email': user.email or '',
        'vence': request.panel_token.expires_at.isoformat(),
    })


@require_POST
@panel_api
def api_desconectar(request):
    revocar(request.panel_token)
    auditar(request, 'desconectar')
    return JsonResponse({'ok': True})


# ---------- Etapa 2: cliente, negocios y cartera ----------

def _json_body(request):
    try:
        data = json.loads(request.body or b'{}')
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def _texto(valor, largo=255):
    return str(valor or '').strip()[:largo]


def _dinero(valor):
    return str(Decimal(str(valor or 0)).quantize(Decimal('1')))


def _fecha(valor):
    return valor.isoformat() if valor else None


def _negocio_json(n):
    return {
        'proyecto': n['proyecto'],
        'adj': n['adj'],
        'inmueble': n['inmueble'],
        'estado': n['estado'],
        'valor': _dinero(n['valor']),
        'titulares': [t['nombre'] for t in n['titulares']],
    }


def _contexto_json(resultado, chatwoot_sync=None):
    data = dict(resultado)
    data['negocios'] = [_negocio_json(n) for n in resultado['negocios']]
    if data.get('cliente'):
        data['cliente'] = dict(data['cliente'], cedula_mask=enmascarar(data['cliente']['cedula']))
    if chatwoot_sync is not None:
        data['chatwoot_sync'] = chatwoot_sync
    return data


@require_POST
@panel_api
def api_contexto(request):
    """Identifica al cliente del contacto abierto en Chatwoot."""
    body = _json_body(request)
    account_id = _texto(body.get('account_id'), 20)
    contact_id = _texto(body.get('contact_id'), 20)
    resultado = resolver_contexto(
        request.user,
        account_id=account_id,
        contact_id=contact_id,
        telefono=_texto(body.get('telefono'), 40),
        cedula_atributo=_texto(body.get('cedula_atributo')),
        cedula=_texto(body.get('cedula')),
    )
    auditar(
        request, 'contexto', chatwoot_account_id=account_id, chatwoot_contact_id=contact_id,
        chatwoot_conversation_id=_texto(body.get('conversation_id'), 20),
        detalle=f"{resultado['estado']} {resultado['via']} {(resultado.get('cliente') or {}).get('cedula', '')}".strip(),
    )
    return JsonResponse(_contexto_json(resultado))


@require_POST
@panel_api
def api_buscar(request):
    texto = _texto(_json_body(request).get('q'), 80)
    candidatos = buscar_manual(request.user, texto)
    auditar(request, 'buscar', detalle=texto)
    return JsonResponse({'candidatos': candidatos})


@require_http_methods(['POST', 'DELETE'])
@panel_api
def api_vincular(request):
    """Confirma (POST) o quita (DELETE) el vínculo contacto de Chatwoot ↔ cliente."""
    body = _json_body(request)
    account_id = _texto(body.get('account_id'), 20)
    contact_id = _texto(body.get('contact_id'), 20)
    if not account_id or not contact_id:
        return JsonResponse({'detail': 'Falta el contacto de Chatwoot.'}, status=400)

    if request.method == 'DELETE':
        ChatwootContactLink.objects.filter(chatwoot_account_id=account_id, chatwoot_contact_id=contact_id).delete()
        sync = borrar_cedula_de_contacto(account_id, contact_id)
        auditar(request, 'desvincular', chatwoot_account_id=account_id, chatwoot_contact_id=contact_id)
        return JsonResponse({'ok': True, 'chatwoot_sync': sync})

    cedula = _texto(body.get('cedula'))
    r = resolver_cliente(request.user, cedula)
    if r is None:
        return JsonResponse({'detail': 'El cliente no existe.'}, status=404)
    ChatwootContactLink.objects.update_or_create(
        chatwoot_account_id=account_id, chatwoot_contact_id=contact_id,
        defaults={'cliente_id': r[0]['cedula'], 'created_by': request.user},
    )
    # En Lyvio el contacto queda con la cédula y el nombre del cliente en Andinasoft.
    sync = guardar_cedula_en_contacto(account_id, contact_id, r[0]['cedula'], r[0]['nombre'])
    auditar(request, 'vincular', chatwoot_account_id=account_id, chatwoot_contact_id=contact_id,
            chatwoot_conversation_id=_texto(body.get('conversation_id'), 20), detalle=r[0]['cedula'])
    resultado = resolver_contexto(request.user, cedula=r[0]['cedula'])
    resultado.update(estado='identificado', via='vinculo')
    return JsonResponse(_contexto_json(resultado, chatwoot_sync=sync))


def _sin_permiso_proyecto():
    return JsonResponse({'detail': 'No tienes acceso a este proyecto en Andinasoft.', 'code': 'proyecto'}, status=403)


@require_GET
@panel_api
def api_cartera(request, proyecto, adj):
    if not puede_ver_proyecto(request.user, proyecto):
        return _sin_permiso_proyecto()
    context, error = build_estado_cuenta_context(proyecto, adj, request.user)
    if error:
        return JsonResponse({'detail': error}, status=404)

    a = context['adj']
    totales = context['totals']
    vencidas = context['cuotas_a_la_fecha']
    saldos = a.saldos_por_cartera
    titulares = [t.nombrecompleto for t in a.titulares.values() if getattr(t, 'nombrecompleto', '')]
    try:
        ultimo = seguimientos_service.recibos(proyecto, adj, limite=1)
    except seguimientos_service.NoDisponible:
        ultimo = []
    auditar(request, 'cartera', proyecto=proyecto, adj=adj)
    return JsonResponse({
        'proyecto': proyecto,
        'adj': adj,
        'inmueble': a.idinmueble or '',
        'estado': getattr(a.extra_info, 'Estado', '') or '',
        'titulares': titulares,
        'fecha_corte': _fecha(datetime.date.today()),
        'valor': _dinero(a.valor),
        # Igual que el PDF: abonado y saldo de capital por tipo de cuota (vista saldos_cuotas).
        'pagado': _dinero(saldos.abonado_ci + saldos.abonado_fn),
        'saldo': _dinero(saldos.saldo_ci + saldos.saldo_fn),
        'vencido': _dinero(totales['valor']),
        'mora': _dinero(totales['intereses_mora']),
        'total_vencido': _dinero(totales['total']),
        'cuotas_vencidas': len(vencidas),
        'dias_mora': max((q.mora.get('dias_totales', 0) for q in vencidas), default=0),
        # El PDF suma la mora al total para cancelar hoy.
        'pago_total_hoy': _dinero(Decimal(str(saldos.pago_hoy.total_pago_hoy)) + Decimal(str(totales['intereses_mora']))),
        'vencidas': [
            {
                'cuota': q.idcta,
                'fecha': _fecha(q.fecha),
                'pendiente': _dinero(q.pendiente['total']),
                'mora': _dinero(q.mora.get('valor', 0)),
                'dias': q.mora.get('dias_totales', 0),
            }
            for q in vencidas
        ],
        'proximas': [
            {'fecha': _fecha(q.fecha), 'valor': _dinero(q.pendiente['total'])}
            for q in context['cuotas_futuras'] if q.is_pending
        ],
        'ultimo_pago': {
            'recibo': ultimo[0]['numrecibo'],
            'fecha': _fecha(ultimo[0]['fecha_pago'] or ultimo[0]['fecha']),
            'valor': _dinero(ultimo[0]['valor']),
            'forma_pago': ultimo[0]['formapago'] or '',
        } if ultimo else None,
    })


@require_GET
@panel_api
def api_estado_cuenta(request, proyecto, adj):
    """PDF del estado de cuenta: mismo generador y plantillas que el portal de clientes."""
    if not puede_ver_proyecto(request.user, proyecto):
        return _sin_permiso_proyecto()
    try:
        response = build_account_statement_response(proyecto, adj, actor_label=request.user)
    except Exception:
        logger.exception('chatwoot_panel: no se pudo generar el estado de cuenta %s %s', proyecto, adj)
        response = None
    if response is None:
        return JsonResponse({'detail': 'No se pudo generar el estado de cuenta.'}, status=502)
    auditar(request, 'estado_cuenta', proyecto=proyecto, adj=adj)
    return response


# ---------- Seguimientos, escrituración y entrega ----------

def _no_disponible(que):
    return JsonResponse({'detail': f'Este proyecto no maneja {que} en Andinasoft.', 'code': 'no_disponible'}, status=409)


def _seguimiento_json(f):
    return {
        'id': f['id_seg'],
        'fecha': _fecha(f['fecha']),
        'tipo': f['tipo_seguimiento'] or '',
        'forma': f['forma_contacto'] or '',
        'comentario': f['respuesta_cliente'] or '',
        'valor_compromiso': _dinero(f['valor_compromiso']) if f['valor_compromiso'] else None,
        'fecha_compromiso': _fecha(f['fecha_compromiso']),
        'usuario': f['usuario'] or '',
        'desde_chatwoot': f['desde_chatwoot'],
    }


def _texto_nota(user, proyecto, adj, datos):
    partes = [f'📌 Seguimiento en Andinasoft ({proyecto} · {adj}) por {_nombre(user)}',
              f"{datos['tipo']} · {datos['forma']}: {datos['comentario']}"]
    if datos['compromiso']:
        partes.append(f"Compromiso de pago: ${datos['valor_compromiso']:,} para el {datos['fecha_compromiso']:%d/%m/%Y}"
                      .replace(',', '.'))
    return '\n'.join(partes)


@require_http_methods(['GET', 'POST'])
@panel_api
def api_seguimientos(request, proyecto, adj):
    if not puede_ver_proyecto(request.user, proyecto):
        return _sin_permiso_proyecto()

    if request.method == 'POST':
        body = _json_body(request)
        try:
            datos = seguimientos_service.validar(body)
            ref, creado = seguimientos_service.registrar(
                proyecto, adj, datos, request.user,
                account_id=_texto(body.get('account_id'), 20),
                conversation_id=_texto(body.get('conversation_id'), 20),
            )
        except seguimientos_service.DatosInvalidos as exc:
            return JsonResponse({'detail': str(exc)}, status=400)
        except seguimientos_service.NoDisponible:
            return _no_disponible('seguimientos')

        nota = ref.nota_privada
        if creado:
            auditar(request, 'seguimiento', proyecto=proyecto, adj=adj,
                    chatwoot_account_id=ref.chatwoot_account_id,
                    chatwoot_conversation_id=ref.chatwoot_conversation_id,
                    detalle=f"{datos['tipo']} #{ref.seguimiento_id}")
            nota = nota_privada(ref.chatwoot_account_id, ref.chatwoot_conversation_id,
                                _texto_nota(request.user, proyecto, adj, datos))
            if nota:
                ref.nota_privada = True
                ref.save(update_fields=['nota_privada'])
        try:
            historial = seguimientos_service.listar(proyecto, adj)
        except seguimientos_service.NoDisponible:
            historial = []
        return JsonResponse({
            'creado': creado,
            'nota_privada': nota,
            'seguimientos': [_seguimiento_json(f) for f in historial],
        }, status=201 if creado else 200)

    try:
        historial = seguimientos_service.listar(proyecto, adj)
    except seguimientos_service.NoDisponible:
        return _no_disponible('seguimientos')
    auditar(request, 'seguimientos', proyecto=proyecto, adj=adj)
    return JsonResponse({
        'tipos': seguimientos_service.TIPOS,
        'formas': seguimientos_service.FORMAS,
        'forma_por_defecto': seguimientos_service.FORMA_POR_DEFECTO,
        'seguimientos': [_seguimiento_json(f) for f in historial],
    })


def _fecha_pareja(anterior, nueva):
    if not anterior and not nueva:
        return None
    return {'anterior': _fecha(anterior), 'nueva': _fecha(nueva)}


@require_GET
@panel_api
def api_promesa(request, proyecto, adj):
    """Entrega, escritura y otrosíes del negocio (módulo de promesas)."""
    if not puede_ver_proyecto(request.user, proyecto):
        return _sin_permiso_proyecto()
    r = resumen_promesa(proyecto, adj)
    if r is None:
        return JsonResponse({'detail': 'Negocio no encontrado.'}, status=404)
    auditar(request, 'promesa', proyecto=proyecto, adj=adj)
    entrega, escritura = r['entrega'], r['escritura']
    return JsonResponse({
        # Ficha de servicio al cliente: ahí se gestionan entrega, escritura y otrosíes.
        'ficha_url': url_ficha(r['cliente_id'], proyecto, adj),
        'tiene_promesa': r['tiene_promesa'],
        'nropromesa': r['nropromesa'],
        'fecha_promesa': _fecha(r['fechapromesa']),
        'entrega': {
            'pactada': _fecha(entrega['pactada']),
            'real': _fecha(entrega['real']),
            'entregado': entrega['entregado'],
            'estado': entrega['estado'],
            'estado_label': entrega['estado_label'],
        },
        'escritura': {
            'pactada': _fecha(escritura['pactada']),
            'real': _fecha(escritura['real']),
            'completa': escritura['completa'],
            'estado': escritura['estado'],
            'estado_label': escritura['estado_label'],
            'paso_label': escritura['paso_label'],
            'siguiente_label': escritura['siguiente_label'],
            'alerta_firma_empresa': escritura['alerta_firma_empresa'],
            'dias_firma_cliente': escritura['dias_firma_cliente'],
            'pasos': [
                {'label': paso['label'], 'hecho': paso['estado'] == 'done', 'fecha': _fecha(paso['fecha'])}
                for paso in escritura['pasos']
            ],
        },
        'otrosi': [
            {
                'tipo': o['tipo_label'],
                'fecha': _fecha(o['fecha_registro'].date() if o['fecha_registro'] else None),
                'promesa': _fecha_pareja(o['fecha_promesa_anterior'], o['fecha_promesa_nueva']),
                'entrega': _fecha_pareja(o['fecha_entrega_anterior'], o['fecha_entrega_nueva']),
                'escritura': _fecha_pareja(o['fecha_escritura_anterior'], o['fecha_escritura_nueva']),
                'observaciones': o['observaciones'],
            }
            for o in r['otrosi']
        ],
        'observaciones': r['observaciones'],
    })


# ---------- Documentos del contrato ----------

_SELLO_CARGA = re.compile(r'\s*\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$')


def _nombre_documento(descripcion):
    """'Otros_2022-11-16 15:50:08.627873' → 'Otros' (la fecha de carga se muestra aparte)."""
    nombre = (descripcion or '').replace('_', ' ').strip()
    return _SELLO_CARGA.sub('', nombre).strip() or nombre


def _documentos(proyecto, adj):
    return documentos_contratos.objects.using(proyecto).filter(adj=adj)


@require_GET
@panel_api
def api_documentos(request, proyecto, adj):
    if not puede_ver_proyecto(request.user, proyecto):
        return _sin_permiso_proyecto()
    try:
        filas = list(_documentos(proyecto, adj).order_by('-id_model').values(
            'id_model', 'descripcion_doc', 'fecha_carga', 'usuario_carga'))
    except Exception:
        logger.exception('chatwoot_panel: documentos no disponibles en %s', proyecto)
        return _no_disponible('documentos')
    auditar(request, 'documentos', proyecto=proyecto, adj=adj)
    return JsonResponse({'documentos': [
        {
            'id': f['id_model'],
            'nombre': _nombre_documento(f['descripcion_doc']),
            # El modelo la declara texto, pero en algunas BD la columna es DATE.
            'fecha': str(f['fecha_carga'] or '')[:10],
            'usuario': f['usuario_carga'] or '',
        }
        for f in filas
    ]})


@require_GET
@panel_api
def api_documento(request, proyecto, adj, doc_id):
    """Sirve el PDF a través de Andinasoft: el storage es privado y el panel solo tiene el token."""
    if not puede_ver_proyecto(request.user, proyecto):
        return _sin_permiso_proyecto()
    doc = _documentos(proyecto, adj).filter(id_model=doc_id).values('descripcion_doc').first()
    if doc is None:
        return JsonResponse({'detail': 'Documento no encontrado.'}, status=404)
    try:
        archivo = abrir_documento_contrato(proyecto, adj, doc['descripcion_doc'])
    except Exception:
        logger.exception('chatwoot_panel: no se pudo abrir el documento %s %s %s', proyecto, adj, doc_id)
        return JsonResponse({'detail': 'El archivo no está en el almacenamiento.'}, status=404)
    auditar(request, 'documento', proyecto=proyecto, adj=adj, detalle=doc['descripcion_doc'])
    return FileResponse(archivo, content_type='application/pdf', filename=f"{doc['descripcion_doc']}.pdf")
