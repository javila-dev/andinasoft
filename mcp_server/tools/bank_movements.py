"""
Tools MCP para Movimientos Bancarios

Proporciona herramientas para consultar, crear y gestionar movimientos bancarios (egresos_banco).
"""
import re
import logging
import unicodedata
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from typing import Optional

from django.db import transaction
from django.db.models import Count
from django.core.paginator import Paginator, EmptyPage
from django.utils.dateparse import parse_date

logger = logging.getLogger(__name__)


def _normalize_account(value: str) -> Optional[str]:
    """Normaliza el número de cuenta removiendo caracteres especiales."""
    if not value:
        return None
    return re.sub(r'[^A-Za-z0-9]', '', str(value)).lower() or None


def _get_account_by_number(account_number: str):
    """Busca una cuenta bancaria por su número normalizado."""
    from andinasoft.models import cuentas_pagos

    normalized = _normalize_account(account_number)
    if not normalized:
        return None
    for cuenta in cuentas_pagos.objects.all():
        normalized_current = _normalize_account(cuenta.cuentabanco)
        if normalized_current == normalized:
            return cuenta
    return None


def _normalize_text_for_search(text: str) -> str:
    """Normaliza texto removiendo diacríticas y convirtiendo a minúsculas."""
    if not text:
        return ''
    normalized = unicodedata.normalize('NFD', str(text))
    without_accents = ''.join(char for char in normalized if unicodedata.category(char) != 'Mn')
    return without_accents.lower()


def _fuzzy_match(word1: str, word2: str, threshold: float = 0.7) -> bool:
    """
    Calcula si dos palabras son similares usando distancia de Levenshtein.
    Retorna True si la similitud es >= threshold (default 70%).
    """
    if not word1 or not word2:
        return False

    if word1 == word2:
        return True

    if word1 in word2 or word2 in word1:
        min_len = min(len(word1), len(word2))
        max_len = max(len(word1), len(word2))
        similarity = min_len / max_len
        return similarity >= threshold

    len1, len2 = len(word1), len(word2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if word1[i-1] == word2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = 1 + min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1])

    max_len = max(len1, len2)
    distance = dp[len1][len2]
    similarity = 1 - (distance / max_len)

    return similarity >= threshold


def bank_movements_list(
    fecha_desde: str,
    fecha_hasta: str,
    cuenta: int = None,
    cuenta_numero: str = None,
    empresa: str = None,
    estado: str = None,
    usado_agente: bool = None,
    valor_positivo: bool = None,
    descripcion: str = None,
    page: int = 1,
    page_size: int = 100
) -> dict:
    """
    Consulta movimientos bancarios por cuenta y/o empresa en un rango de fechas.

    Args:
        fecha_desde: Fecha inicio (YYYY-MM-DD) - requerido
        fecha_hasta: Fecha fin (YYYY-MM-DD) - requerido
        cuenta: ID de la cuenta bancaria
        cuenta_numero: Número de la cuenta bancaria (alternativo a cuenta)
        empresa: NIT o nombre de la empresa
        estado: CONCILIADO o SIN CONCILIAR
        usado_agente: Filtrar por si fue usado por agente (true/false)
        valor_positivo: Filtrar solo valores positivos (ingresos)
        descripcion: Búsqueda difusa en descripción (~70% similitud)
        page: Número de página (default 1)
        page_size: Tamaño de página (max 500, default 100)

    Returns:
        dict con filters, pagination y movimientos
    """
    from andinasoft.models import cuentas_pagos, empresas
    from accounting.models import egresos_banco

    empty_response = {
        'filters': {},
        'pagination': {'page': 1, 'page_size': 0, 'total_pages': 0, 'total_records': 0},
        'movimientos': []
    }

    if not any([cuenta, cuenta_numero, empresa]):
        return {**empty_response, 'detail': 'Debes enviar al menos "cuenta", "cuenta_numero" o "empresa"'}

    if not fecha_desde or not fecha_hasta:
        return {**empty_response, 'detail': 'Debes enviar "fecha_desde" y "fecha_hasta" (YYYY-MM-DD)'}

    fecha_desde_dt = parse_date(fecha_desde)
    fecha_hasta_dt = parse_date(fecha_hasta)

    if not fecha_desde_dt or not fecha_hasta_dt:
        return {**empty_response, 'detail': 'Formato de fecha inválido, usa YYYY-MM-DD'}

    if fecha_desde_dt > fecha_hasta_dt:
        return {**empty_response, 'detail': '"fecha_desde" no puede ser mayor que "fecha_hasta"'}

    cuenta_obj = None
    if cuenta:
        try:
            cuenta_obj = cuentas_pagos.objects.get(pk=int(cuenta))
        except ValueError:
            return {**empty_response, 'detail': f'El ID de cuenta "{cuenta}" no es válido.', 'cuenta_enviada': str(cuenta)}
        except cuentas_pagos.DoesNotExist:
            return {**empty_response, 'detail': f'No se encontró cuenta con ID {cuenta}.', 'cuenta_enviada': str(cuenta)}
    elif cuenta_numero:
        cuenta_obj = _get_account_by_number(cuenta_numero)
        if not cuenta_obj:
            return {**empty_response, 'detail': f'No se encontró cuenta con número "{cuenta_numero}".', 'cuenta_enviada': cuenta_numero}

    empresa_obj = None
    if empresa:
        try:
            empresa_obj = empresas.objects.get(pk=empresa)
        except empresas.DoesNotExist:
            try:
                empresa_obj = empresas.objects.get(nombre__iexact=empresa)
            except empresas.DoesNotExist:
                return {**empty_response, 'detail': f'No se encontró empresa con NIT o nombre "{empresa}".', 'empresa_enviada': empresa}

        if cuenta_obj and cuenta_obj.nit_empresa_id and cuenta_obj.nit_empresa_id != empresa_obj.pk:
            return {
                **empty_response,
                'detail': f'La cuenta {cuenta_obj.cuentabanco} no pertenece a la empresa {empresa_obj.nombre}.'
            }

    queryset = egresos_banco.objects.filter(
        fecha__range=(fecha_desde_dt, fecha_hasta_dt)
    ).select_related('empresa', 'cuenta').order_by('fecha', 'pk')

    if cuenta_obj:
        queryset = queryset.filter(cuenta=cuenta_obj)
    if empresa_obj:
        queryset = queryset.filter(empresa=empresa_obj)
    if estado:
        estado_upper = estado.upper()
        if estado_upper not in ('CONCILIADO', 'SIN CONCILIAR'):
            return {'error': 'El estado debe ser CONCILIADO o SIN CONCILIAR'}
        queryset = queryset.filter(estado=estado_upper)
    if usado_agente is not None:
        queryset = queryset.filter(usado_agente=usado_agente)
    if valor_positivo:
        queryset = queryset.filter(valor__gt=0)

    # Filtro por descripción con búsqueda difusa
    if descripcion:
        search_term_normalized = _normalize_text_for_search(descripcion)
        search_words = search_term_normalized.split()

        matching_ids = []
        for mvto in queryset:
            if mvto.descripcion:
                desc_normalized = _normalize_text_for_search(mvto.descripcion)
                desc_words = desc_normalized.split()

                all_words_match = True
                for search_word in search_words:
                    word_found = any(_fuzzy_match(search_word, desc_word, threshold=0.7)
                                   for desc_word in desc_words)
                    if not word_found:
                        all_words_match = False
                        break

                if all_words_match:
                    matching_ids.append(mvto.id_mvto)

        queryset = queryset.filter(id_mvto__in=matching_ids)

    try:
        page = int(page)
        page_size = min(max(int(page_size), 1), 500)
    except (ValueError, TypeError):
        page = 1
        page_size = 100

    paginator = Paginator(queryset, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        return {**empty_response, 'detail': 'La página solicitada no existe'}

    movimientos = []
    for mvto in page_obj.object_list:
        mvto_data = {
            'id_mvto': mvto.id_mvto,
            'empresa': mvto.empresa.pk,
            'cuenta': mvto.cuenta.pk,
            'cuenta_verbose': mvto.cuenta.cuentabanco,
            'fecha': mvto.fecha.isoformat(),
            'descripcion': mvto.descripcion,
            'referencia': mvto.referencia,
            'valor': float(mvto.valor),
            'estado': mvto.estado,
            'conciliacion_id': mvto.conciliacion_id,
            'pago_id': mvto.pago_asociado_id,
            'anticipo_id': mvto.anticipo_asociado_id,
            'transferencia_id': mvto.transferencia_asociada_id,
            'usado_agente': mvto.usado_agente,
            'fecha_uso_agente': mvto.fecha_uso_agente.isoformat() if mvto.fecha_uso_agente else None,
            'recibo_asociado_agente': mvto.recibo_asociado_agente,
            'proyecto_asociado_agente': mvto.proyecto_asociado_agente
        }
        movimientos.append(mvto_data)

    return {
        'filters': {
            'empresa': empresa_obj.pk if empresa_obj else None,
            'cuenta': cuenta_obj.pk if cuenta_obj else None,
            'fecha_desde': fecha_desde,
            'fecha_hasta': fecha_hasta,
            'estado': estado,
            'usado_agente': usado_agente,
            'valor_positivo': valor_positivo,
            'descripcion': descripcion
        },
        'pagination': {
            'page': page,
            'page_size': page_size,
            'total_pages': paginator.num_pages,
            'total_records': paginator.count
        },
        'movimientos': movimientos
    }


def bank_movements_create(
    movimientos: list,
    cuenta: int = None,
    cuenta_numero: str = None,
    empresa: int = None
) -> dict:
    """
    Carga movimientos bancarios en lote.

    Args:
        movimientos: Lista de movimientos. Cada uno con: fecha, descripcion, valor, referencia (opcional),
                     estado (opcional), pago_id, anticipo_id, transferencia_id, external_id (opcionales)
        cuenta: ID de la cuenta bancaria
        cuenta_numero: Número de la cuenta (alternativo a cuenta)
        empresa: ID de la empresa (opcional si la cuenta tiene empresa asociada)

    Returns:
        dict con empresa, cuenta, total_movimientos y lista de movimientos creados
    """
    from andinasoft.models import cuentas_pagos, empresas
    from accounting.models import egresos_banco, Pagos, Anticipos, transferencias_companias

    if not movimientos or not isinstance(movimientos, list):
        return {'error': 'El campo "movimientos" debe ser una lista con al menos un elemento'}

    cuenta_obj = None
    if cuenta:
        try:
            cuenta_obj = cuentas_pagos.objects.get(pk=cuenta)
        except cuentas_pagos.DoesNotExist:
            return {'error': 'Cuenta no encontrada'}
    elif cuenta_numero:
        cuenta_obj = _get_account_by_number(cuenta_numero)
        if not cuenta_obj:
            return {'error': 'Cuenta no encontrada'}
    else:
        return {'error': 'Debes enviar "cuenta" o "cuenta_numero"'}

    empresa_obj = None
    if empresa:
        try:
            empresa_obj = empresas.objects.get(pk=empresa)
        except empresas.DoesNotExist:
            return {'error': 'Empresa no encontrada'}
        if cuenta_obj.nit_empresa_id and cuenta_obj.nit_empresa_id != empresa_obj.pk:
            return {'error': 'La cuenta no pertenece a la empresa indicada'}
    else:
        if cuenta_obj.nit_empresa_id:
            try:
                empresa_obj = empresas.objects.get(pk=cuenta_obj.nit_empresa_id)
            except empresas.DoesNotExist:
                return {'error': 'La empresa asociada a la cuenta no existe'}
        else:
            return {'error': 'No se pudo determinar la empresa. Envía "empresa" o relaciona la cuenta a una empresa.'}

    movimientos_limpios = []
    for index, movimiento in enumerate(movimientos, start=1):
        if not isinstance(movimiento, dict):
            return {'error': f'El movimiento #{index} no es un objeto válido'}

        fecha = parse_date(str(movimiento.get('fecha', '')))
        if fecha is None:
            return {'error': f'La fecha del movimiento #{index} es inválida (YYYY-MM-DD)'}

        descripcion = (movimiento.get('descripcion') or '').strip()
        if not descripcion:
            return {'error': f'La descripción del movimiento #{index} es obligatoria'}

        try:
            valor = Decimal(str(movimiento.get('valor')))
        except (InvalidOperation, TypeError):
            return {'error': f'El valor del movimiento #{index} es inválido'}
        if valor == 0:
            return {'error': f'El valor del movimiento #{index} no puede ser cero'}

        estado = (movimiento.get('estado') or 'SIN CONCILIAR').upper()
        if estado not in ('CONCILIADO', 'SIN CONCILIAR'):
            return {'error': f'El estado del movimiento #{index} no es válido'}

        pago_obj = anticipo_obj = transferencia_obj = None

        if movimiento.get('pago_id'):
            try:
                pago_obj = Pagos.objects.get(pk=movimiento['pago_id'])
            except Pagos.DoesNotExist:
                return {'error': f'El pago asociado del movimiento #{index} no existe'}

        if movimiento.get('anticipo_id'):
            try:
                anticipo_obj = Anticipos.objects.get(pk=movimiento['anticipo_id'])
            except Anticipos.DoesNotExist:
                return {'error': f'El anticipo asociado del movimiento #{index} no existe'}

        if movimiento.get('transferencia_id'):
            try:
                transferencia_obj = transferencias_companias.objects.get(pk=movimiento['transferencia_id'])
            except transferencias_companias.DoesNotExist:
                return {'error': f'La transferencia asociada del movimiento #{index} no existe'}

        movimientos_limpios.append({
            'fecha': fecha,
            'descripcion': descripcion,
            'referencia': movimiento.get('referencia'),
            'valor': valor,
            'estado': estado,
            'pago': pago_obj,
            'anticipo': anticipo_obj,
            'transferencia': transferencia_obj,
            'external_id': movimiento.get('external_id')
        })

    registros = []
    with transaction.atomic():
        for item in movimientos_limpios:
            registro = egresos_banco.objects.create(
                empresa=empresa_obj,
                cuenta=cuenta_obj,
                fecha=item['fecha'],
                descripcion=item['descripcion'],
                referencia=item['referencia'],
                valor=item['valor'],
                estado=item['estado'],
                pago_asociado=item['pago'],
                anticipo_asociado=item['anticipo'],
                transferencia_asociada=item['transferencia']
            )
            registros.append({
                'id_mvto': registro.id_mvto,
                'external_id': item['external_id']
            })

    return {
        'empresa': empresa_obj.pk,
        'cuenta': cuenta_obj.pk,
        'total_movimientos': len(registros),
        'movimientos': registros
    }


def bank_movements_mark_used(
    movement_id: int,
    usado_agente: bool,
    recibo_asociado_agente: str = None,
    proyecto_asociado_agente: str = None
) -> dict:
    """
    Marca o desmarca un movimiento bancario como usado por el agente.

    Args:
        movement_id: ID del movimiento bancario
        usado_agente: True para marcar como usado, False para desmarcar
        recibo_asociado_agente: Número de recibo asociado (opcional)
        proyecto_asociado_agente: Nombre del proyecto asociado (opcional)

    Returns:
        dict con el estado actualizado del movimiento
    """
    from django.utils import timezone
    from accounting.models import egresos_banco

    try:
        movement = egresos_banco.objects.get(pk=movement_id)
    except egresos_banco.DoesNotExist:
        return {'error': 'Movimiento no encontrado', 'error_code': 'NOT_FOUND'}

    movement.usado_agente = bool(usado_agente)
    if movement.usado_agente:
        movement.fecha_uso_agente = timezone.now()
        movement.recibo_asociado_agente = recibo_asociado_agente or None
        movement.proyecto_asociado_agente = proyecto_asociado_agente or None
    else:
        movement.fecha_uso_agente = None
        movement.recibo_asociado_agente = None
        movement.proyecto_asociado_agente = None

    movement.save()

    return {
        'id_mvto': movement.pk,
        'usado_agente': movement.usado_agente,
        'fecha_uso_agente': movement.fecha_uso_agente.isoformat(sep=' ') if movement.fecha_uso_agente else None,
        'recibo_asociado_agente': movement.recibo_asociado_agente,
        'proyecto_asociado_agente': movement.proyecto_asociado_agente,
        'mensaje': 'Movimiento marcado como usado' if movement.usado_agente else 'Movimiento desmarcado'
    }


def bank_movements_for_receipt(
    proyecto: str,
    fecha_pago: str,
    recibo_asociado: str = None
) -> dict:
    """
    Obtiene movimientos bancarios relacionados con una solicitud de recibo.

    Args:
        proyecto: Nombre del proyecto (requerido)
        fecha_pago: Fecha de pago (YYYY-MM-DD) (requerido)
        recibo_asociado: Número de recibo para buscar movimiento existente (opcional)

    Returns:
        dict con cuenta, movimiento_asociado_id, fechas y lista de movimientos
    """
    from andinasoft.models import cuentas_pagos
    from accounting.models import egresos_banco

    if not proyecto or not fecha_pago:
        return {'error': 'Debes enviar "proyecto" y "fecha_pago" (YYYY-MM-DD)'}

    fecha_pago_dt = parse_date(fecha_pago)
    if not fecha_pago_dt:
        return {'error': 'Formato de fecha inválido, usa YYYY-MM-DD'}

    fecha_desde = fecha_pago_dt - timedelta(days=1)
    fecha_hasta = fecha_pago_dt + timedelta(days=1)

    cuenta_obj = None
    movimiento_asociado_id = None

    # Si tiene recibo asociado, buscar el movimiento
    if recibo_asociado and recibo_asociado.strip():
        try:
            movimiento = egresos_banco.objects.filter(
                recibo_asociado_agente=recibo_asociado,
                proyecto_asociado_agente=proyecto
            ).first()

            if not movimiento:
                movimiento = egresos_banco.objects.filter(
                    recibo_asociado_agente=recibo_asociado
                ).first()

            if movimiento:
                cuenta_obj = movimiento.cuenta
                movimiento_asociado_id = movimiento.id_mvto
        except Exception:
            pass

    # Si no se encontró cuenta, buscar la más común del proyecto
    if not cuenta_obj:
        movimientos_proyecto = egresos_banco.objects.filter(
            proyecto_asociado_agente=proyecto
        ).values('cuenta').annotate(
            count=Count('cuenta')
        ).order_by('-count').first()

        if movimientos_proyecto:
            try:
                cuenta_obj = cuentas_pagos.objects.get(pk=movimientos_proyecto['cuenta'])
            except cuentas_pagos.DoesNotExist:
                pass

    if not cuenta_obj:
        return {
            'detail': 'No se encontró una cuenta bancaria asociada al proyecto',
            'movimientos': [],
            'cuenta': None,
            'movimiento_asociado_id': None
        }

    # Buscar movimientos en la cuenta con valor positivo
    queryset = egresos_banco.objects.filter(
        cuenta=cuenta_obj,
        fecha__range=(fecha_desde, fecha_hasta),
        valor__gt=0
    ).select_related('empresa', 'cuenta').order_by('fecha', 'pk')

    movimientos = []
    for mvto in queryset:
        movimientos.append({
            'id_mvto': mvto.id_mvto,
            'empresa': mvto.empresa.pk,
            'cuenta': mvto.cuenta.pk,
            'fecha': mvto.fecha.isoformat(),
            'descripcion': mvto.descripcion,
            'referencia': mvto.referencia,
            'valor': float(mvto.valor),
            'estado': mvto.estado,
            'conciliacion_id': mvto.conciliacion_id,
            'pago_id': mvto.pago_asociado_id,
            'anticipo_id': mvto.anticipo_asociado_id,
            'transferencia_id': mvto.transferencia_asociada_id,
            'usado_agente': mvto.usado_agente,
            'fecha_uso_agente': mvto.fecha_uso_agente.isoformat() if mvto.fecha_uso_agente else None,
            'recibo_asociado_agente': mvto.recibo_asociado_agente,
            'proyecto_asociado_agente': mvto.proyecto_asociado_agente
        })

    return {
        'cuenta': cuenta_obj.pk,
        'cuenta_numero': cuenta_obj.cuentabanco,
        'movimiento_asociado_id': movimiento_asociado_id,
        'fecha_desde': fecha_desde.isoformat(),
        'fecha_hasta': fecha_hasta.isoformat(),
        'total_movimientos': len(movimientos),
        'movimientos': movimientos
    }


# Definición de schemas para el MCP
BANK_MOVEMENTS_TOOLS = [
    {
        'name': 'bank_movements_list',
        'description': 'Consulta movimientos bancarios por cuenta y/o empresa en un rango de fechas. Soporta búsqueda difusa por descripción (~70% similitud).',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'fecha_desde': {'type': 'string', 'description': 'Fecha inicio YYYY-MM-DD (requerido)'},
                'fecha_hasta': {'type': 'string', 'description': 'Fecha fin YYYY-MM-DD (requerido)'},
                'cuenta': {'type': 'integer', 'description': 'ID de la cuenta bancaria'},
                'cuenta_numero': {'type': 'string', 'description': 'Número de la cuenta bancaria'},
                'empresa': {'type': 'string', 'description': 'NIT o nombre de la empresa'},
                'estado': {'type': 'string', 'enum': ['CONCILIADO', 'SIN CONCILIAR'], 'description': 'Filtrar por estado'},
                'usado_agente': {'type': 'boolean', 'description': 'Filtrar por si fue usado por agente'},
                'valor_positivo': {'type': 'boolean', 'description': 'Solo valores positivos (ingresos)'},
                'descripcion': {'type': 'string', 'description': 'Búsqueda difusa en descripción'},
                'page': {'type': 'integer', 'description': 'Número de página (default 1)'},
                'page_size': {'type': 'integer', 'description': 'Tamaño de página (max 500)'}
            },
            'required': ['fecha_desde', 'fecha_hasta']
        }
    },
    {
        'name': 'bank_movements_create',
        'description': 'Carga movimientos bancarios en lote.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'cuenta': {'type': 'integer', 'description': 'ID de la cuenta bancaria'},
                'cuenta_numero': {'type': 'string', 'description': 'Número de la cuenta'},
                'empresa': {'type': 'integer', 'description': 'ID de la empresa'},
                'movimientos': {
                    'type': 'array',
                    'description': 'Lista de movimientos a crear',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'fecha': {'type': 'string', 'description': 'Fecha YYYY-MM-DD'},
                            'descripcion': {'type': 'string', 'description': 'Descripción'},
                            'valor': {'type': 'number', 'description': 'Valor'},
                            'referencia': {'type': 'string'},
                            'estado': {'type': 'string', 'enum': ['CONCILIADO', 'SIN CONCILIAR']},
                            'pago_id': {'type': 'integer'},
                            'anticipo_id': {'type': 'integer'},
                            'transferencia_id': {'type': 'integer'},
                            'external_id': {'type': 'string'}
                        },
                        'required': ['fecha', 'descripcion', 'valor']
                    }
                }
            },
            'required': ['movimientos']
        }
    },
    {
        'name': 'bank_movements_mark_used',
        'description': 'Marca o desmarca un movimiento como usado por el agente de conciliación.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'movement_id': {'type': 'integer', 'description': 'ID del movimiento (requerido)'},
                'usado_agente': {'type': 'boolean', 'description': 'True=marcar, False=desmarcar (requerido)'},
                'recibo_asociado_agente': {'type': 'string', 'description': 'Número de recibo'},
                'proyecto_asociado_agente': {'type': 'string', 'description': 'Nombre del proyecto'}
            },
            'required': ['movement_id', 'usado_agente']
        }
    },
    {
        'name': 'bank_movements_for_receipt',
        'description': 'Obtiene movimientos bancarios para una solicitud de recibo. Busca en ±1 día de la fecha de pago.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'proyecto': {'type': 'string', 'description': 'Nombre del proyecto (requerido)'},
                'fecha_pago': {'type': 'string', 'description': 'Fecha de pago YYYY-MM-DD (requerido)'},
                'recibo_asociado': {'type': 'string', 'description': 'Número de recibo (opcional)'}
            },
            'required': ['proyecto', 'fecha_pago']
        }
    }
]
