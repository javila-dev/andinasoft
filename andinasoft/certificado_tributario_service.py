"""
Construcción del contexto para el certificado tributario (abono en cuenta).

Divide capital e intereses por titular en partes iguales, agrupados por año,
con base en los recaudos aplicados de la adjudicación.
"""
from __future__ import annotations

import datetime
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db.models import Min, Sum

from andinasoft.models import clientes, empresas
from andinasoft.shared_models import Adjudicacion, Recaudos, Recaudos_general, Vista_Adjudicacion
from andinasoft.utilities import Utilidades

MESES_ES = (
    '',
    'enero',
    'febrero',
    'marzo',
    'abril',
    'mayo',
    'junio',
    'julio',
    'agosto',
    'septiembre',
    'octubre',
    'noviembre',
    'diciembre',
)


def _d(value) -> Decimal:
    if value is None:
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _divide_titular(valor: Decimal, cantidad: int) -> Decimal:
    if cantidad <= 0:
        return Decimal('0')
    return (valor / Decimal(cantidad)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _tipo_documento_label(tipo_doc: str | None) -> str:
    labels = dict(clientes.dc_types)
    if not tipo_doc:
        return 'documento de identidad'
    return labels.get(tipo_doc, 'documento de identidad').lower()


def anios_disponibles_certificado(proyecto: str, adj_id: str) -> list[int]:
    hoy = datetime.date.today()
    agg = Recaudos_general.objects.using(proyecto).filter(
        idadjudicacion=adj_id,
    ).aggregate(min_fecha=Min('fecha'))
    min_fecha = agg.get('min_fecha')
    if min_fecha:
        anio_inicio = min_fecha.year
    else:
        try:
            adj = Adjudicacion.objects.using(proyecto).get(pk=adj_id)
            anio_inicio = adj.fechacontrato.year if adj.fechacontrato else hoy.year
        except Adjudicacion.DoesNotExist:
            anio_inicio = hoy.year
    return list(range(hoy.year, anio_inicio - 1, -1))


def _pagos_agrupados_por_anio(proyecto: str, adj_id: str, anio_hasta: int) -> dict[int, dict[str, Decimal]]:
    fin_anio = datetime.date(anio_hasta, 12, 31)
    recibos = Recaudos_general.objects.using(proyecto).filter(
        idadjudicacion=adj_id,
        fecha__lte=fin_anio,
    ).values_list('numrecibo', flat=True)

    recaudos = Recaudos.objects.using(proyecto).filter(
        idadjudicacion=adj_id,
        recibo__in=recibos,
        fecha__lte=fin_anio,
    )

    por_anio: dict[int, dict[str, Decimal]] = defaultdict(
        lambda: {
            'capital': Decimal('0'),
            'interescte': Decimal('0'),
            'interesmora': Decimal('0'),
        }
    )
    for rec in recaudos:
        if not rec.fecha:
            continue
        cap = _d(rec.capital)
        intcte = _d(rec.interescte)
        intmora = _d(rec.interesmora)
        por_anio[rec.fecha.year]['capital'] += cap
        por_anio[rec.fecha.year]['interescte'] += intcte
        por_anio[rec.fecha.year]['interesmora'] += intmora
    return por_anio


def build_certificado_tributario_context(
    proyecto: str,
    adj_id: str,
    titular_id: str,
    empresa_nit: str,
    anio_hasta: int,
    user,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        adj = Adjudicacion.objects.using(proyecto).get(pk=adj_id)
    except Adjudicacion.DoesNotExist:
        return None, 'Adjudicacion no encontrada.'

    titulares = adj.titulares2()
    if not titulares:
        return None, 'La adjudicacion no tiene titulares registrados.'

    titular_ids = {t.pk for t in titulares}
    if titular_id not in titular_ids:
        return None, 'El titular seleccionado no pertenece a esta adjudicacion.'

    try:
        titular = clientes.objects.get(pk=titular_id)
    except clientes.DoesNotExist:
        return None, 'Titular no encontrado.'

    try:
        empresa = empresas.objects.get(pk=empresa_nit)
    except empresas.DoesNotExist:
        return None, 'Empresa no encontrada.'

    hoy = datetime.date.today()
    if anio_hasta < 1900 or anio_hasta > hoy.year:
        return None, f'El año debe estar entre 1900 y {hoy.year}.'

    cantidad_titulares = len(titulares)
    pagos_por_anio = _pagos_agrupados_por_anio(proyecto, adj_id, anio_hasta)

    filas = []
    total_capital = Decimal('0')
    total_interescte = Decimal('0')
    total_interesmora = Decimal('0')
    for anio in sorted(pagos_por_anio.keys()):
        datos = pagos_por_anio[anio]
        capital = _divide_titular(datos['capital'], cantidad_titulares)
        interescte = _divide_titular(datos['interescte'], cantidad_titulares)
        interesmora = _divide_titular(datos['interesmora'], cantidad_titulares)
        cuota = capital + interescte + interesmora
        filas.append(
            {
                'anio': anio,
                'capital': capital,
                'interescte': interescte,
                'interesmora': interesmora,
                'cuota': cuota,
            }
        )
        total_capital += capital
        total_interescte += interescte
        total_interesmora += interesmora

    if not filas:
        return None, 'No hay pagos aplicados para generar el certificado en el periodo seleccionado.'

    total_general = total_capital + total_interescte + total_interesmora
    total_general_letras = Utilidades().numeros_letras(int(total_general))

    try:
        vista_adj = Vista_Adjudicacion.objects.using(proyecto).get(IdAdjudicacion=adj_id)
        inmueble = vista_adj.IdInmueble
        fecha_contrato = vista_adj.FechaContrato
    except Vista_Adjudicacion.DoesNotExist:
        inmueble = adj.idinmueble
        fecha_contrato = adj.fechacontrato

    total_recaudado_general = Recaudos_general.objects.using(proyecto).filter(
        idadjudicacion=adj_id,
        fecha__lte=datetime.date(anio_hasta, 12, 31),
    ).aggregate(total=Sum('valor')).get('total') or Decimal('0')
    total_recaudado_titular = _divide_titular(_d(total_recaudado_general), cantidad_titulares)

    context = {
        'user': user,
        'now': hoy.strftime('%d/%m/%Y'),
        'dia_expedicion': hoy.day,
        'mes_expedicion': MESES_ES[hoy.month],
        'anio_expedicion': hoy.year,
        'fecha_texto': f'{hoy.day} de {MESES_ES[hoy.month]} de {hoy.year}',
        'proyecto': proyecto,
        'adj': adj_id,
        'anio_hasta': anio_hasta,
        'empresa': empresa,
        'titular': titular,
        'tipo_documento': _tipo_documento_label(titular.tipo_doc),
        'inmueble': inmueble,
        'fecha_contrato': fecha_contrato,
        'valor_contrato': adj.valor,
        'cantidad_titulares': cantidad_titulares,
        'total_recaudado_titular': total_recaudado_titular,
        'filas': filas,
        'total_capital': total_capital,
        'total_interescte': total_interescte,
        'total_interesmora': total_interesmora,
        'total_general': total_general,
        'total_general_letras': total_general_letras,
    }
    return context, None
