"""Flujo de aprobación de gastos con origen Alegra."""
import json
import re

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounting.models import Facturas, GastoAprobador, history_facturas
from alegra_integration.bill_mapping import ALEGRA_DOC_JOURNAL
from accounting.journal_cxp import persist_journal_cxp_mappings, serializar_detalle_journal_pago
from andina.decorators import check_groups
from andinasoft.models import empresas


def usuario_es_aprobador_gasto(user, empresa_id=None):
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    qs = GastoAprobador.objects.filter(user=user, activo=True)
    if empresa_id:
        qs = qs.filter(Q(empresa_id=empresa_id) | Q(empresa__isnull=True))
    return qs.exists()


def aprobadores_para_empresa(empresa_id):
    qs = GastoAprobador.objects.filter(activo=True).filter(
        Q(empresa_id=empresa_id) | Q(empresa__isnull=True)
    ).select_related('user', 'empresa').order_by('user__username')
    return qs


def _valor_factura_entero(valor):
    if isinstance(valor, int):
        return valor
    if hasattr(valor, '__int__'):
        return int(valor)
    return parse_valor_entero(valor)


def empresa_config_sin_aprobador(empresa):
    """
    Configuración por empresa para registro sin aprobador.
    alegra_gasto_max_sin_aprobador: None o <=0 → no permite; >0 → tope COP.
    """
    if empresa is None:
        return {
            'permite_sin_aprobador': False,
            'max_sin_aprobador': None,
            'mensaje_requiere_aprobador': 'Empresa no encontrada.',
        }
    if not isinstance(empresa, empresas):
        empresa = empresas.objects.filter(pk=str(empresa).strip()).first()
    if not empresa:
        return {
            'permite_sin_aprobador': False,
            'max_sin_aprobador': None,
            'mensaje_requiere_aprobador': 'Empresa no encontrada.',
        }
    raw = getattr(empresa, 'alegra_gasto_max_sin_aprobador', None)
    if raw is None:
        max_cop = 0
    else:
        try:
            max_cop = int(raw)
        except (TypeError, ValueError):
            max_cop = 0
    if max_cop <= 0:
        return {
            'permite_sin_aprobador': False,
            'max_sin_aprobador': None,
            'mensaje_requiere_aprobador': (
                f'La empresa {empresa.nombre} no permite gastos Alegra sin aprobador. '
                'Configure un tope en Admin (empresas) o asigne un aprobador.'
            ),
        }
    return {
        'permite_sin_aprobador': True,
        'max_sin_aprobador': max_cop,
        'mensaje_requiere_aprobador': '',
    }


def validar_gasto_sin_aprobador(empresa, valor):
    """Lanza ValueError si no puede registrarse sin aprobador."""
    cfg = empresa_config_sin_aprobador(empresa)
    if not cfg['permite_sin_aprobador']:
        raise ValueError(cfg['mensaje_requiere_aprobador'])
    v = _valor_factura_entero(valor)
    max_cop = cfg['max_sin_aprobador']
    if v > max_cop:
        emp = empresa if isinstance(empresa, empresas) else empresas.objects.filter(pk=str(empresa).strip()).first()
        nombre = getattr(emp, 'nombre', empresa) if emp else empresa
        raise ValueError(
            f'El valor ${v:,} supera el máximo sin aprobador (${max_cop:,}) para {nombre}. '
            'Asigne un aprobador.'
        )


def parse_aprobador_user_id_opcional(aprobador_user_id):
    """None = sin aprobador; al asignar oficina el gasto queda aprobado de inmediato."""
    if aprobador_user_id is None:
        return None
    if isinstance(aprobador_user_id, str):
        raw = aprobador_user_id.strip()
        if not raw:
            return None
        aprobador_user_id = raw
    try:
        uid = int(aprobador_user_id)
    except (TypeError, ValueError):
        return None
    return uid if uid > 0 else None


def alegra_sin_aprobacion_q():
    """Radicados Alegra que aún no pueden operarse en causación/tesorería."""
    return Q(origen='Alegra', gasto_aprobado=False)


def alegra_id_para_tabla(alegra_bill_id):
    """Id visible en UI: bill numérico (28) o journal:11."""
    raw = (alegra_bill_id or '').strip()
    if not raw:
        return ''
    if ':journal:' in raw:
        return 'journal:' + raw.rsplit(':journal:', 1)[-1]
    if ':' in raw:
        return raw.split(':', 1)[-1]
    return raw


def factura_a_dict(fac):
    alegra_bill = fac.alegra_bill_id or ''
    valor = int(fac.valor or 0)
    pago_neto = int(fac.pago_neto if fac.pago_neto is not None else valor)
    return {
        'pk': fac.pk,
        'nrofactura': fac.nrofactura,
        'nombretercero': fac.nombretercero,
        'fechafactura': fac.fechafactura.isoformat() if fac.fechafactura else '',
        'fechavenc': fac.fechavenc.isoformat() if fac.fechavenc else '',
        'fecharadicado': fac.fecharadicado.isoformat() if fac.fecharadicado else '',
        'valor': valor,
        'pago_neto': pago_neto,
        'total': valor,
        'empresa': fac.empresa_id,
        'empresa_nombre': getattr(fac.empresa, 'nombre', '') or str(fac.empresa_id),
        'descripcion': fac.descripcion,
        'alegra_bill_id': alegra_bill,
        'alegra_document_type': getattr(fac, 'alegra_document_type', '') or '',
        'alegra_id': alegra_id_para_tabla(alegra_bill),
        'oficina': fac.oficina or '',
        'gasto_aprobacion_estado': fac.gasto_aprobacion_estado,
        'gasto_aprobacion_comentario_contable': fac.gasto_aprobacion_comentario_contable or '',
        'gasto_aprobador_asignado': (
            fac.gasto_aprobador_asignado.get_full_name() or fac.gasto_aprobador_asignado.username
        ) if fac.gasto_aprobador_asignado_id else '',
        'idtercero': fac.idtercero or '',
    }


HISTORICO_ASIGNACION_LIMIT = 5


def _qs_historico_asignacion_alegra(empresa_id, id_tercero, *, exclude_pk=None):
    empresa_id = str(empresa_id or '').strip()
    id_tercero = str(id_tercero or '').strip()
    if not empresa_id or not id_tercero:
        return Facturas.objects.none()
    qs = (
        Facturas.objects.filter(
            origen='Alegra',
            empresa_id=empresa_id,
            idtercero=id_tercero,
            oficina__in=('MONTERIA', 'MEDELLIN'),
        )
        .exclude(gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION)
        .select_related('gasto_aprobador_asignado')
        .order_by('-gasto_asignado_en', '-pk')
    )
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs


def _historial_item_dict(fac):
    aprobador = fac.gasto_aprobador_asignado
    return {
        'pk': fac.pk,
        'nombretercero': fac.nombretercero or '',
        'oficina': fac.oficina or '',
        'valor': fac.valor,
        'descripcion': (fac.descripcion or '').strip(),
        'aprobador_id': fac.gasto_aprobador_asignado_id,
        'aprobador_label': (
            (aprobador.get_full_name() or aprobador.username) if aprobador else ''
        ),
        'sin_aprobador': not fac.gasto_aprobador_asignado_id,
        'fecharadicado': fac.fecharadicado.isoformat() if fac.fecharadicado else '',
    }


def sugerencias_asignacion_gasto_alegra(empresa_id, id_tercero, *, exclude_pk=None):
    """
    Historial reciente del mismo tercero/empresa (ya asignados) y sugerencia de oficina/aprobador.
    Oficina: la del radicado más reciente. Aprobador: el del más reciente que tuvo aprobador asignado.
    """
    qs = _qs_historico_asignacion_alegra(empresa_id, id_tercero, exclude_pk=exclude_pk)
    facturas = list(qs[:HISTORICO_ASIGNACION_LIMIT])
    historial = [_historial_item_dict(f) for f in facturas]
    sugerencia = {'oficina': '', 'aprobador_id': None}
    if facturas:
        sugerencia['oficina'] = facturas[0].oficina or ''
        for fac in facturas:
            if fac.gasto_aprobador_asignado_id:
                sugerencia['aprobador_id'] = fac.gasto_aprobador_asignado_id
                break
    return {'historial': historial, 'sugerencia': sugerencia}


def _validar_fechas_radicado(fecha_factura, fecha_vencimiento):
    if fecha_vencimiento < fecha_factura:
        raise ValueError('La fecha de vencimiento no puede ser anterior a la fecha de la factura.')


def parse_valor_entero(valor):
    """
    Entero COP sin decimales. Acepta lo que envía el front (solo dígitos) o valores
    con máscara miles ($, comas, puntos), igual que tesorería/causación.
    """
    if isinstance(valor, int):
        n = valor
    else:
        digits = re.sub(r'\D', '', str(valor or ''))
        if not digits:
            raise ValueError('Valor inválido.')
        n = int(digits)
    if n < 0:
        raise ValueError('El valor no puede ser negativo.')
    if n == 0:
        raise ValueError('El valor debe ser mayor que cero.')
    return n


def _validar_soporte_pdf(soporte):
    if not soporte:
        raise ValueError('El soporte PDF es obligatorio.')
    name = (getattr(soporte, 'name', '') or '').lower()
    if not name.endswith('.pdf'):
        raise ValueError('El soporte debe ser un archivo PDF.')


def normalizar_id_tercero(id_tercero):
    """NIT/CC del proveedor: solo dígitos."""
    ref = (id_tercero or '').strip()
    if not ref:
        raise ValueError('NIT/CC es obligatorio.')
    if not re.fullmatch(r'\d+', ref):
        raise ValueError('NIT/CC solo puede contener números (sin puntos, guiones ni letras).')
    return ref[:255]


def normalizar_alegra_bill_id(empresa_id, referencia_alegra, *, es_radicado_manual=False):
    """
    El usuario solo ingresa el id numérico en Alegra; el sistema arma alegra_bill_id.
    Webhook bills: {NIT}:{id}. Radicado manual (journal sin webhook): {NIT}:journal:{id}.
    """
    ref = (referencia_alegra or '').strip()
    if not ref:
        raise ValueError('El id en Alegra es obligatorio.')
    if not re.fullmatch(r'\d+', ref):
        raise ValueError('Ingrese solo el número id en Alegra (sin NIT, journal: ni otros prefijos).')
    nit = str(empresa_id).strip()
    if es_radicado_manual:
        alegra_id = f'{nit}:journal:{ref}'
    else:
        alegra_id = f'{nit}:{ref}'
    if len(alegra_id) > 64:
        raise ValueError('El id en Alegra es demasiado largo para esta empresa.')
    return alegra_id


@transaction.atomic
def crear_radicado_gasto_alegra(
    request,
    *,
    empresa_id,
    nro_factura,
    fecha_factura,
    fecha_vencimiento,
    id_tercero,
    nombre_tercero,
    valor,
    descripcion,
    soporte,
    oficina,
    aprobador_user_id=None,
    comentario_contable='',
    referencia_alegra,
    alegra_journal_detalle=None,
):
    """
    Radicado manual (p. ej. journal en Alegra sin webhook): origen Alegra + asignación en un paso.
    alegra_journal_detalle: JSON o lista con CxP por tercero (id_tercero, valor, account_code PUC).
    """
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        raise PermissionError('Solo Contabilidad puede crear radicados Alegra.')
    try:
        empresa = empresas.objects.get(pk=str(empresa_id).strip())
    except empresas.DoesNotExist:
        raise ValueError('Empresa no encontrada.')
    if not getattr(empresa, 'alegra_enabled', False):
        raise ValueError('La empresa no tiene Alegra habilitado.')

    nro_factura = (nro_factura or '').strip()[:255]
    id_tercero = normalizar_id_tercero(id_tercero)
    nombre_tercero = (nombre_tercero or '').strip()[:255]
    descripcion = (descripcion or '').strip()[:255]
    if not nro_factura or not nombre_tercero:
        raise ValueError('Nº factura y proveedor son obligatorios.')
    valor = parse_valor_entero(valor)

    _validar_fechas_radicado(fecha_factura, fecha_vencimiento)
    _validar_soporte_pdf(soporte)

    if Facturas.objects.filter(idtercero=id_tercero, nrofactura=nro_factura).exists():
        raise ValueError(f'Ya existe un radicado con factura {nro_factura} para el tercero {id_tercero}.')

    alegra_bill_id = normalizar_alegra_bill_id(empresa.pk, referencia_alegra, es_radicado_manual=True)
    if Facturas.objects.filter(alegra_bill_id=alegra_bill_id).exists():
        raise ValueError(f'Ya existe un radicado con referencia Alegra {alegra_bill_id}.')

    detalle_json = None
    if alegra_journal_detalle is not None:
        if isinstance(alegra_journal_detalle, str):
            raw = alegra_journal_detalle.strip()
            if raw:
                try:
                    rows = json.loads(raw)
                    if isinstance(rows, list):
                        rows = persist_journal_cxp_mappings(empresa, rows)
                        detalle_json = json.dumps(rows, ensure_ascii=False)
                    else:
                        detalle_json = raw
                except (TypeError, ValueError):
                    detalle_json = raw
        else:
            rows = serializar_detalle_journal_pago(alegra_journal_detalle)
            rows = persist_journal_cxp_mappings(empresa, rows)
            detalle_json = json.dumps(rows, ensure_ascii=False)

    fac = Facturas.objects.create(
        empresa=empresa,
        nrofactura=nro_factura,
        fechafactura=fecha_factura,
        fechavenc=fecha_vencimiento,
        idtercero=id_tercero,
        nombretercero=nombre_tercero,
        descripcion=descripcion or f'Gasto Alegra manual {nro_factura}',
        valor=valor,
        pago_neto=valor,
        nrocausa=nro_factura,
        fechacausa=fecha_factura,
        origen='Alegra',
        alegra_bill_id=alegra_bill_id,
        alegra_document_type=ALEGRA_DOC_JOURNAL,
        alegra_journal_detalle=detalle_json,
        soporte_radicado=soporte,
        gasto_aprobacion_estado=Facturas.GASTO_APROB_PENDIENTE_ASIGNACION,
        gasto_aprobacion_comentario_contable='',
        gasto_aprobado=False,
    )
    history_facturas.objects.create(
        factura=fac,
        usuario=request.user,
        accion=f'Radicó manualmente gasto Alegra ({alegra_bill_id})',
        ubicacion='Contabilidad',
    )
    asignar_gasto_alegra(
        request,
        factura=fac,
        oficina=oficina,
        aprobador_user_id=aprobador_user_id,
        comentario_contable=comentario_contable,
    )
    return fac


def asignar_gasto_alegra(request, *, factura, oficina, aprobador_user_id=None, comentario_contable=''):
    if not check_groups(request, ('Contabilidad',), raise_exception=False) and not request.user.is_superuser:
        raise PermissionError('Solo Contabilidad puede asignar aprobador y oficina.')
    if factura.origen != 'Alegra':
        raise ValueError('Solo aplica a radicados con origen Alegra.')
    if factura.gasto_aprobacion_estado != Facturas.GASTO_APROB_PENDIENTE_ASIGNACION:
        raise ValueError('El radicado no está pendiente de asignación.')
    if oficina not in ('MONTERIA', 'MEDELLIN'):
        raise ValueError('Oficina inválida.')
    from django.contrib.auth import get_user_model
    User = get_user_model()
    aprobador_uid = parse_aprobador_user_id_opcional(aprobador_user_id)

    factura.oficina = oficina
    factura.gasto_asignado_por = request.user
    factura.gasto_asignado_en = timezone.now()
    factura.gasto_aprobacion_comentario_contable = (comentario_contable or '').strip()[:2000]

    if aprobador_uid:
        aprobador = User.objects.filter(pk=aprobador_uid).first()
        if not aprobador or not usuario_es_aprobador_gasto(aprobador, factura.empresa_id):
            raise ValueError('El aprobador seleccionado no está autorizado para esta empresa.')
        factura.gasto_aprobador_asignado = aprobador
        factura.gasto_aprobacion_estado = Facturas.GASTO_APROB_PENDIENTE_APROBACION
        factura.gasto_aprobado = False
        factura.gasto_aprobado_por = None
        factura.gasto_aprobado_en = None
        update_fields = [
            'oficina',
            'gasto_aprobador_asignado',
            'gasto_asignado_por',
            'gasto_asignado_en',
            'gasto_aprobacion_comentario_contable',
            'gasto_aprobacion_estado',
            'gasto_aprobado',
            'gasto_aprobado_por',
            'gasto_aprobado_en',
        ]
        accion = (
            f'Asignó oficina {oficina} y aprobador {aprobador.get_full_name() or aprobador.username}'
            + (f'. Nota: {factura.gasto_aprobacion_comentario_contable[:200]}' if factura.gasto_aprobacion_comentario_contable else '')
        )
    else:
        validar_gasto_sin_aprobador(factura.empresa, factura.valor)
        factura.gasto_aprobador_asignado = None
        factura.gasto_aprobacion_estado = Facturas.GASTO_APROB_APROBADO
        factura.gasto_aprobado = True
        factura.gasto_aprobado_por = request.user
        factura.gasto_aprobado_en = timezone.now()
        update_fields = [
            'oficina',
            'gasto_aprobador_asignado',
            'gasto_asignado_por',
            'gasto_asignado_en',
            'gasto_aprobacion_comentario_contable',
            'gasto_aprobacion_estado',
            'gasto_aprobado',
            'gasto_aprobado_por',
            'gasto_aprobado_en',
        ]
        accion = (
            f'Asignó oficina {oficina} sin aprobador (aprobación automática)'
            + (f'. Nota: {factura.gasto_aprobacion_comentario_contable[:200]}' if factura.gasto_aprobacion_comentario_contable else '')
        )

    factura.save(update_fields=update_fields)
    history_facturas.objects.create(
        factura=factura,
        usuario=request.user,
        accion=accion[:255],
        ubicacion='Contabilidad',
    )
    if aprobador_uid:
        from accounting.gasto_n8n_notify import notify_gasto_pendiente_aprobacion

        notify_gasto_pendiente_aprobacion(
            factura.pk,
            assigned_by_user_id=request.user.pk,
        )
    return factura


def aprobar_gasto_alegra_para_usuario(factura, user, *, canal=''):
    """
    Aprueba un gasto Alegra (misma regla que la UI).
    `canal` se anota en historial (p. ej. WhatsApp/n8n).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        raise PermissionError('Usuario no válido.')
    if factura.origen != 'Alegra':
        raise ValueError('Solo aplica a radicados con origen Alegra.')
    if factura.gasto_aprobacion_estado != Facturas.GASTO_APROB_PENDIENTE_APROBACION:
        raise ValueError('El radicado no está pendiente de aprobación.')
    if factura.gasto_aprobador_asignado_id != user.pk and not getattr(user, 'is_superuser', False):
        raise PermissionError('Solo el aprobador asignado puede aprobar este gasto.')
    if not usuario_es_aprobador_gasto(user, factura.empresa_id):
        raise PermissionError('No está autorizado como aprobador de gastos.')

    factura.gasto_aprobado = True
    factura.gasto_aprobado_por = user
    factura.gasto_aprobado_en = timezone.now()
    factura.gasto_aprobacion_estado = Facturas.GASTO_APROB_APROBADO
    factura.save(
        update_fields=[
            'gasto_aprobado',
            'gasto_aprobado_por',
            'gasto_aprobado_en',
            'gasto_aprobacion_estado',
        ]
    )
    nota_canal = f' ({canal})' if (canal or '').strip() else ''
    history_facturas.objects.create(
        factura=factura,
        usuario=user,
        accion=f'Gasto aprobado para pago (oficina {factura.oficina}){nota_canal}'[:255],
        ubicacion='Contabilidad',
    )
    return factura


def aprobar_gasto_alegra(request, *, factura):
    return aprobar_gasto_alegra_para_usuario(factura, request.user)
