"""Cierre diario de las cuentas de efectivo desde la planilla diaria."""
import datetime
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import JsonResponse
from django.utils import timezone

from andina.decorators import check_perms
from andinasoft.models import cuentas_pagos
from accounting.models import CierreCaja
from accounting.saldo_caja import (CONCEPTOS, cuadre_del_dia, es_caja_planilla,
                                   libro_caja, neto, ultimo_cierre, _fecha)


PERM_PLANILLA = 'accounting.view_planilla_movimiento'
PERM_APROBAR = 'accounting.aprobar_ajuste_cierrecaja'


def _respuesta(msj, ok=False, title=None, **extra):
    data = {
        'ok': ok,
        'title': title or ('Listo!' if ok else 'Oh Oh!'),
        'msj': msj,
        'class': 'alert-success' if ok else 'alert-danger',
    }
    data.update(extra)
    return JsonResponse(data)


def _movimientos_lista(movimientos):
    return [
        {'clave': clave, 'concepto': etiqueta, 'valor': float(movimientos.get(clave, 0) or 0)}
        for clave, etiqueta, _ in CONCEPTOS
    ]


def _num(valor):
    return None if valor is None else float(valor)


def _libro_dict(libro):
    base = libro['cierre_base']
    return {
        'desde': libro['desde'].strftime('%Y-%m-%d'),
        'base_fecha': base.fecha.strftime('%Y-%m-%d') if base else None,
        'saldo_inicial': _num(libro['saldo_inicial']),
        'filas': [{
            'fecha': f['fecha'].strftime('%Y-%m-%d'),
            'concepto': f['concepto'],
            'documento': f['documento'],
            'detalle': f['detalle'],
            'entrada': float(f['entrada']),
            'salida': float(f['salida']),
            'saldo': _num(f['saldo']),
        } for f in libro['filas']],
        'total_entradas': float(libro['total_entradas']),
        'total_salidas': float(libro['total_salidas']),
        'saldo_final': _num(libro['saldo_final']),
    }


def _cierre_dict(cierre):
    return {
        'pk': cierre.pk,
        'fecha': cierre.fecha.strftime('%Y-%m-%d'),
        'es_apertura': cierre.es_apertura,
        'saldo_inicial': float(cierre.saldo_inicial),
        'saldo_teorico': float(cierre.saldo_teorico),
        'saldo_fisico': float(cierre.saldo_fisico),
        'diferencia': float(cierre.diferencia),
        'motivo': cierre.motivo_diferencia,
        'estado_ajuste': cierre.estado_ajuste,
        'usuario': cierre.usuario.username,
        'registrado': timezone.localtime(cierre.fecha_registro).strftime('%d/%m/%Y %H:%M'),
        'revisado_por': cierre.ajuste_revisado_por.username if cierre.ajuste_revisado_por else '',
    }


def _bloqueo_cierre(cuenta, fecha):
    """Motivo por el que no se puede cerrar la cuenta en `fecha`, o None."""
    if fecha > datetime.date.today():
        return 'No se puede cerrar una fecha futura.'
    if CierreCaja.objects.filter(cuenta=cuenta, fecha=fecha).exists():
        return 'Esta fecha ya está cerrada.'
    previo = ultimo_cierre(cuenta.pk)
    if previo is not None and previo.fecha > fecha:
        return (f'La caja ya está cerrada hasta el {previo.fecha:%d/%m/%Y}; '
                'solo se pueden cerrar fechas posteriores.')
    if previo is not None and previo.estado_ajuste == CierreCaja.AJUSTE_PENDIENTE:
        return (f'El cierre del {previo.fecha:%d/%m/%Y} tiene una diferencia pendiente de aprobar. '
                'Debe aprobarse el ajuste o reabrirse ese cierre antes de cerrar otro día.')
    return None


@login_required
def ajax_cierre_caja(request):
    if not check_perms(request, (PERM_PLANILLA,), raise_exception=False):
        return _respuesta('No tienes permiso para registrar cierres de caja.')
    if request.method == 'GET':
        return _consultar(request)
    accion = request.POST.get('accion')
    if accion == 'cerrar':
        return _cerrar(request)
    if accion == 'aprobar':
        return _aprobar(request)
    if accion == 'reabrir':
        return _reabrir(request)
    return _respuesta('Acción no válida.')


def _cuenta_y_fecha(params):
    cuenta = cuentas_pagos.objects.filter(pk=params.get('cuenta')).first()
    if cuenta is None:
        return None, None, 'Selecciona una cuenta.'
    if not es_caja_planilla(cuenta):
        msj = ('Las cajas con responsable se arquean en el módulo de cajas.'
               if cuenta.usuario_responsable_id else
               'El cierre de caja solo aplica a cuentas de efectivo.')
        return None, None, msj
    try:
        fecha = _fecha(params.get('fecha'))
    except (TypeError, ValueError):
        return None, None, 'Selecciona una fecha válida.'
    return cuenta, fecha, None


def _consultar(request):
    cuenta, fecha, error = _cuenta_y_fecha(request.GET)
    if error:
        return _respuesta(error)
    cierre = CierreCaja.objects.filter(cuenta=cuenta, fecha=fecha).first()
    historial = [_cierre_dict(c) for c in
                 CierreCaja.objects.filter(cuenta=cuenta).select_related(
                     'usuario', 'ajuste_revisado_por').order_by('-fecha')[:90]]
    ultimo = ultimo_cierre(cuenta.pk)
    data = {
        'ok': True,
        'cuenta': cuenta.cuentabanco,
        'fecha': fecha.strftime('%Y-%m-%d'),
        'puede_aprobar': check_perms(request, (PERM_APROBAR,), raise_exception=False),
        'ultimo_cierre_pk': ultimo.pk if ultimo else None,
        'historial': historial,
        'libro': _libro_dict(libro_caja(cuenta.pk, fecha)),
    }
    if cierre is not None:
        data.update({
            'cierre': _cierre_dict(cierre),
            'movimientos': _movimientos_lista(cierre.movimientos),
        })
        return JsonResponse(data)

    cuadre = cuadre_del_dia(cuenta.pk, fecha)
    es_apertura = ultimo is None
    data.update({
        'cierre': None,
        'es_apertura': es_apertura,
        'bloqueo': _bloqueo_cierre(cuenta, fecha),
        'saldo_inicial': None if cuadre['saldo_inicial'] is None else float(cuadre['saldo_inicial']),
        'saldo_inicial_desde': cuadre['cierre_base'].fecha.strftime('%Y-%m-%d') if cuadre['cierre_base'] else None,
        'movimientos': _movimientos_lista(cuadre['movimientos']),
        'saldo_teorico': None if cuadre['saldo_final'] is None else float(cuadre['saldo_final']),
    })
    return JsonResponse(data)


def _cerrar(request):
    cuenta, fecha, error = _cuenta_y_fecha(request.POST)
    if error:
        return _respuesta(error)
    bloqueo = _bloqueo_cierre(cuenta, fecha)
    if bloqueo:
        return _respuesta(bloqueo)
    try:
        saldo_fisico = Decimal(str(request.POST.get('saldo_fisico', '')).replace(',', ''))
    except InvalidOperation:
        return _respuesta('Registra el valor contado en caja.')
    forma = request.POST.get('forma') or '{}'
    try:
        json.loads(forma)
    except ValueError:
        return _respuesta('El detalle de billetes y monedas no es válido.')
    motivo = (request.POST.get('motivo') or '').strip()

    cuadre = cuadre_del_dia(cuenta.pk, fecha)
    es_apertura = ultimo_cierre(cuenta.pk) is None
    if es_apertura:
        # Sin cierre previo no hay saldo de partida: el conteo físico se toma como saldo de apertura.
        saldo_teorico = saldo_fisico
        saldo_inicial = saldo_fisico - neto(cuadre['movimientos'])
    else:
        saldo_teorico = cuadre['saldo_final']
        saldo_inicial = cuadre['saldo_inicial']
    diferencia = saldo_fisico - saldo_teorico
    if diferencia and not motivo:
        return _respuesta('Hay una diferencia entre el arqueo y el saldo teórico: escribe el motivo.')

    try:
        cierre = CierreCaja.objects.create(
            cuenta=cuenta,
            fecha=fecha,
            es_apertura=es_apertura,
            saldo_inicial=saldo_inicial,
            movimientos={k: float(v) for k, v in cuadre['movimientos'].items()},
            saldo_teorico=saldo_teorico,
            saldo_fisico=saldo_fisico,
            forma=forma,
            diferencia=diferencia,
            motivo_diferencia=motivo,
            estado_ajuste=(CierreCaja.AJUSTE_PENDIENTE if diferencia
                           else CierreCaja.AJUSTE_SIN_DIFERENCIA),
            usuario=request.user,
        )
    except IntegrityError:
        return _respuesta('Esta fecha ya está cerrada.')

    if diferencia:
        msj = (f'Caja cerrada con una diferencia de ${diferencia:,.0f}. '
               'Queda pendiente de aprobación del ajuste.')
    elif es_apertura:
        msj = f'Se registró el saldo de apertura de ${saldo_fisico:,.0f}.'
    else:
        msj = 'Caja cerrada y cuadrada.'
    return _respuesta(msj, ok=True, cierre=_cierre_dict(cierre))


def _cierre_para_revision(request):
    if not check_perms(request, (PERM_APROBAR,), raise_exception=False):
        return None, _respuesta('No tienes permiso para aprobar ajustes ni reabrir cierres de caja.')
    cierre = CierreCaja.objects.filter(pk=request.POST.get('cierre')).select_related('cuenta').first()
    if cierre is None:
        return None, _respuesta('El cierre no existe.')
    return cierre, None


def _aprobar(request):
    cierre, error = _cierre_para_revision(request)
    if error:
        return error
    if cierre.estado_ajuste != CierreCaja.AJUSTE_PENDIENTE:
        return _respuesta('Este cierre no tiene un ajuste pendiente.')
    if cierre.usuario_id == request.user.pk:
        return _respuesta('El ajuste debe aprobarlo una persona distinta a quien registró el cierre.')
    cierre.estado_ajuste = CierreCaja.AJUSTE_APROBADO
    cierre.ajuste_revisado_por = request.user
    cierre.ajuste_revisado_en = timezone.now()
    cierre.save(update_fields=['estado_ajuste', 'ajuste_revisado_por', 'ajuste_revisado_en'])
    return _respuesta(f'Ajuste de ${cierre.diferencia:,.0f} aprobado. '
                      'El saldo teórico continúa desde el arqueo físico.', ok=True)


def _reabrir(request):
    cierre, error = _cierre_para_revision(request)
    if error:
        return error
    ultimo = ultimo_cierre(cierre.cuenta_id)
    if ultimo.pk != cierre.pk:
        return _respuesta(f'Solo se puede reabrir el último cierre ({ultimo.fecha:%d/%m/%Y}).')
    fecha = cierre.fecha
    cierre.delete()
    return _respuesta(f'Se reabrió la caja del {fecha:%d/%m/%Y}. Corrige los movimientos y vuelve a cerrarla.',
                      ok=True)
