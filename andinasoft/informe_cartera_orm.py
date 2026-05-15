"""
Réplica en Django ORM del procedimiento MySQL `informe_cartera`.

Misma fuente de datos y reglas que el SP (subconsultas sobre presupuesto_cartera,
recaudos_general, filtros sobre adjudicacion, etc.). Los CASE complejos del SELECT
se evalúan en Python sobre valores ya anotados para coincidir con el SP.
"""
import calendar
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import (
    CharField,
    DecimalField,
    F,
    Max,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce

from andinasoft.shared_models import (
    Adjudicacion,
    InfoCartera,
    PresupuestoCartera,
    Recaudos_general,
    Vista_Adjudicacion,
)

_DEC = DecimalField(max_digits=20, decimal_places=2)
_ZERO = Value(Decimal('0'), output_field=_DEC)


def _dec(x) -> Decimal:
    if x is None:
        return Decimal('0')
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x))


def _recaudo_mes(recaudo, ppto_vencido, ppto_mes, presupuesto) -> Decimal:
    r, v, pm, p = map(_dec, (recaudo, ppto_vencido, ppto_mes, presupuesto))
    if r >= v and r <= p:
        return r - v
    if r > p:
        return pm
    if r < v:
        return Decimal('0')
    return Decimal('0')


def _recaudo_vencido(recaudo, ppto_vencido) -> Decimal:
    r, v = map(_dec, (recaudo, ppto_vencido))
    if r <= v:
        return r
    if r > v:
        return v
    return Decimal('0')


def _recaudo_pptado(recaudo, presupuesto) -> Decimal:
    r, p = map(_dec, (recaudo, presupuesto))
    return p if r > p else r


def _recaudo_nopptado(recaudo, presupuesto) -> Decimal:
    r, p = map(_dec, (recaudo, presupuesto))
    return (r - p) if r > p else Decimal('0')


def informe_cartera_rows(proyecto: str, periodo: str, gestor_param):
    """
    Devuelve (lista de SimpleNamespace compatibles con ver_ppto.html, mensaje_error).

    gestor_param: None o '' = sin filtro por gestor. En MySQL el SP con NULL en el
    segundo parámetro hace que LIKE CONCAT('%',NULL,'%') no devuelva filas; aquí
    omitimos el filtro para equivaler al uso en la aplicación (admin / NULL).
    """
    err = ''
    periodo = str(periodo).strip()
    try:
        y = int(periodo[:4])
        m = int(periodo[4:6])
    except (ValueError, TypeError):
        return [], 'Periodo inválido (use YYYYMM).'

    fecha_corte = date(y, m, 1)
    fecha_final = date(y, m, calendar.monthrange(y, m)[1])

    def _ppto_sum_cuota(extra_q):
        return (
            PresupuestoCartera.objects.using(proyecto)
            .filter(periodo=periodo, idadjudicacion=OuterRef('pk'))
            .filter(extra_q)
            .values('idadjudicacion')
            .annotate(t=Coalesce(Sum('cuota'), _ZERO))
            .values('t')[:1]
        )

    cuota_info = Subquery(
        PresupuestoCartera.objects.using(proyecto)
        .filter(periodo=periodo, idadjudicacion=OuterRef('pk'))
        .values('idadjudicacion')
        .annotate(t=Coalesce(Sum('cuota'), _ZERO))
        .values('t')[:1],
        output_field=_DEC,
    )
    cuota_cta_mes = Subquery(
        _ppto_sum_cuota(Q(fecha__date__gte=fecha_corte)),
        output_field=_DEC,
    )
    cuota_cta_vencida = Subquery(
        _ppto_sum_cuota(Q(fecha__date__lt=fecha_corte)),
        output_field=_DEC,
    )
    edad_ppto = Subquery(
        PresupuestoCartera.objects.using(proyecto)
        .filter(periodo=periodo, idadjudicacion=OuterRef('pk'))
        .values('idadjudicacion')
        .annotate(t=Max('edad'))
        .values('t')[:1],
        output_field=CharField(max_length=50),
    )
    tipo_ppto = Subquery(
        PresupuestoCartera.objects.using(proyecto)
        .filter(periodo=periodo, idadjudicacion=OuterRef('pk'))
        .values('idadjudicacion')
        .annotate(t=Max('tipocartera'))
        .values('t')[:1],
        output_field=CharField(max_length=30),
    )
    asesor_ppto = Subquery(
        PresupuestoCartera.objects.using(proyecto)
        .filter(periodo=periodo, idadjudicacion=OuterRef('pk'))
        .values('idadjudicacion')
        .annotate(t=Max('asesor'))
        .values('t')[:1],
        output_field=CharField(max_length=120),
    )

    recaudo_mes = Subquery(
        Recaudos_general.objects.using(proyecto)
        .filter(
            idadjudicacion=OuterRef('pk'),
            fecha__gte=fecha_corte,
            fecha__lte=fecha_final,
        )
        .exclude(numrecibo__startswith='N')
        .exclude(numrecibo__startswith='A')
        .values('idadjudicacion')
        .annotate(t=Coalesce(Sum('valor'), _ZERO))
        .values('t')[:1],
        output_field=_DEC,
    )

    nombre_adj = Subquery(
        Vista_Adjudicacion.objects.using(proyecto)
        .filter(IdAdjudicacion=OuterRef('pk'))
        .values('Nombre')[:1],
        output_field=CharField(max_length=255),
    )
    tipo_vista = Subquery(
        Vista_Adjudicacion.objects.using(proyecto)
        .filter(IdAdjudicacion=OuterRef('pk'))
        .values('tipo_cartera')[:1],
        output_field=CharField(max_length=255),
    )
    gestor_info = Subquery(
        InfoCartera.objects.using(proyecto)
        .filter(idadjudicacion=OuterRef('pk'))
        .values('gestorasignado')[:1],
        output_field=CharField(max_length=255),
    )

    qs = (
        Adjudicacion.objects.using(proyecto)
        .exclude(origenventa='Canje')
        .filter(Q(estado__isnull=True) | ~Q(estado__startswith='Des'))
        .annotate(
            _cliente=nombre_adj,
            _recaudo=Coalesce(recaudo_mes, _ZERO),
            _cuota_info=Coalesce(cuota_info, _ZERO),
            _cuota_mes=Coalesce(cuota_cta_mes, _ZERO),
            _cuota_venc=Coalesce(cuota_cta_vencida, _ZERO),
            _edad_ppto=edad_ppto,
            _tipo_ppto=tipo_ppto,
            _asesor_ppto=asesor_ppto,
            _tipo_vista=tipo_vista,
            _gestor_info=gestor_info,
        )
        .filter(Q(_recaudo__gt=0) | Q(_cuota_info__gt=0))
    )

    gestor_param = (gestor_param or '').strip()
    if gestor_param:
        qs = qs.annotate(
            _asesor_final=Coalesce(
                F('_asesor_ppto'),
                F('_gestor_info'),
                Value(''),
                output_field=CharField(),
            ),
        ).filter(_asesor_final__icontains=gestor_param)
    # Sin filtro gestor: no aplicar LIKE (ver comentario del docstring).

    qs = qs.order_by('_cliente')

    out = []
    try:
        for adj in qs:
            cliente = adj._cliente or ''
            recaudo = adj._recaudo
            ppto_mes = adj._cuota_mes
            ppto_vencido = adj._cuota_venc
            presupuesto = adj._cuota_info or Decimal('0')
            tipocartera = adj._tipo_ppto or adj._tipo_vista or ''
            edad = adj._edad_ppto or '-30-30'
            asesor = adj._asesor_ppto or adj._gestor_info or ''

            venta_mes = 'Si' if (adj.fechacontrato and adj.fechacontrato >= fecha_corte) else 'No'

            r_mes = _recaudo_mes(recaudo, ppto_vencido, ppto_mes, presupuesto)
            r_venc = _recaudo_vencido(recaudo, ppto_vencido)
            r_ppt = _recaudo_pptado(recaudo, presupuesto)
            r_noppt = _recaudo_nopptado(recaudo, presupuesto)

            out.append(
                SimpleNamespace(
                    pk=adj.pk,
                    cliente=cliente,
                    estado=adj.estado,
                    asesor=asesor,
                    origen=adj.origenventa,
                    venta_mes=venta_mes,
                    tipocartera=tipocartera,
                    edad=edad,
                    ppto_mes=ppto_mes,
                    recaudo_mes=r_mes,
                    ppto_vencido=ppto_vencido,
                    recaudo_vencido=r_venc,
                    presupuesto=presupuesto,
                    recaudo_pptado=r_ppt,
                    recaudo_nopptado=r_noppt,
                    recaudo_total=recaudo,
                )
            )
    except Exception as exc:
        return [], str(exc)

    return out, err
