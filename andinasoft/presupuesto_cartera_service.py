"""
Carga / ensure de presupuesto_cartera por periodo (YYYYMM).

Reutiliza CALL ver_presupuesto; idempotente si el periodo ya existe.
"""
from __future__ import annotations

import calendar
import datetime
import logging

from django.db import connections

from andinasoft.models import Usuarios_Proyectos, proyectos as Proyectos
from andinasoft.shared_models import PresupuestoCartera, saldos_adj

logger = logging.getLogger(__name__)


def periodo_actual(today=None) -> str:
    today = today or datetime.date.today()
    return f'{today.year}{today.month:02d}'


def fecha_hasta_periodo(periodo: str) -> datetime.datetime:
    año = int(periodo[:4])
    mes = int(periodo[-2:])
    dia = calendar.monthrange(año, mes)[1]
    return datetime.datetime(año, mes, dia)


def usuario_label(user) -> str:
    if user is None:
        return 'sistema'
    return str(getattr(user, 'username', None) or user)


def proyectos_accesibles(user) -> list:
    """Proyectos activos con DB configurada y acceso del usuario."""
    excluidos = {'sotavento'}
    nombres = []
    qs = Proyectos.objects.exclude(proyecto='default').order_by('proyecto')
    try:
        qs = qs.filter(activo=True)
    except Exception:
        pass

    allowed = None
    if not getattr(user, 'is_superuser', False):
        rel = Usuarios_Proyectos.objects.filter(usuario=user).first()
        if rel is None:
            return []
        allowed = {p.proyecto for p in rel.proyecto.all()}

    for item in qs:
        name = item.proyecto
        if name.lower() in excluidos:
            continue
        if name not in connections.databases:
            continue
        if allowed is not None and name not in allowed:
            continue
        nombres.append(name)
    return nombres


def periodo_existe(proyecto: str, periodo: str) -> bool:
    return PresupuestoCartera.objects.using(proyecto).filter(periodo=periodo).exists()


def cargar_presupuesto(proyecto: str, periodo: str, user, *, adj: str = '') -> dict:
    """
    Inserta filas de presupuesto para el periodo.

    Si el periodo ya tiene datos, no pisa (skipped=True).
    adj vacio = todo el proyecto (mismo SP que la UI manual).
    """
    if periodo_existe(proyecto, periodo):
        return {'ok': True, 'skipped': True, 'count': 0, 'error': None}

    fecha_hasta = fecha_hasta_periodo(periodo)
    adj_arg = adj or ''
    stmt = f'CALL ver_presupuesto("{fecha_hasta}","{adj_arg}")'
    try:
        filas = list(saldos_adj.objects.using(proyecto).raw(stmt))
    except Exception as exc:
        logger.exception('ver_presupuesto SP failed proyecto=%s periodo=%s', proyecto, periodo)
        return {'ok': False, 'skipped': False, 'count': 0, 'error': str(exc)}

    created = 0
    user_str = usuario_label(user)
    hoy = datetime.date.today()
    manager = PresupuestoCartera.objects.using(proyecto)
    for cuota in filas:
        try:
            manager.create(
                id_ppto=cuota.id,
                periodo=periodo,
                idadjudicacion=cuota.adj,
                cliente=getattr(cuota, 'cliente', None),
                tipocta=cuota.tipocta,
                ncta=cuota.nrocta,
                idcta=cuota.idcta,
                tipocartera=getattr(cuota, 'tipocartera', None),
                fecha=getattr(cuota, 'fechacta', None),
                capital=cuota.saldocapital,
                interes=cuota.saldointcte,
                cuota=cuota.saldocuota,
                diasmora=cuota.diasmora,
                mora=cuota.saldomora,
                asesor=getattr(cuota, 'asesor', None),
                usuario=user_str,
                fechaoperacion=hoy,
                edad=getattr(cuota, 'edad', None),
            )
            created += 1
        except Exception:
            logger.exception(
                'presupuesto insert failed proyecto=%s periodo=%s idcta=%s',
                proyecto,
                periodo,
                getattr(cuota, 'idcta', None),
            )
    return {'ok': True, 'skipped': False, 'count': created, 'error': None}


def ensure_presupuesto(proyecto: str, periodo: str, user) -> dict:
    """Ensure silencioso: crea si falta; errores solo en log."""
    try:
        return cargar_presupuesto(proyecto, periodo, user)
    except Exception as exc:
        logger.exception('ensure_presupuesto failed proyecto=%s periodo=%s', proyecto, periodo)
        return {'ok': False, 'skipped': False, 'count': 0, 'error': str(exc)}


def ensure_presupuestos(proyectos_list, periodo: str, user) -> list:
    """Solo genera donde falta el periodo (exists es barato; SP solo si hace falta)."""
    results = []
    for proyecto in proyectos_list:
        if periodo_existe(proyecto, periodo):
            results.append((proyecto, {'ok': True, 'skipped': True, 'count': 0, 'error': None}))
            continue
        results.append((proyecto, ensure_presupuesto(proyecto, periodo, user)))
    return results
