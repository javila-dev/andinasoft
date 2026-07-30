"""
Alcance contable por usuario (empresas + oficinas) para el flujo radicación → pago.

Reglas:
- Sin fila UsuarioAccountingAlcance (o activo=False): sin acceso.
- Fila con M2M vacíos: acceso total (comodín).
- M2M poblado en una dimensión: restringe esa dimensión; vacío = comodín en esa dimensión.
- Superuser: bypass.
"""
from __future__ import annotations

from typing import Optional

from django.db.models import Q
from django.http import JsonResponse

from accounting.models import GastoNotificacionOficina, UsuarioAccountingAlcance
from andinasoft.models import empresas as EmpresasModel


ALCANCE_DENY_DETAIL = 'Sin alcance contable configurado.'


def get_alcance(user) -> Optional[dict]:
    """
    Retorna None si no hay acceso.
    Retorna dict con:
      - empresa_ids: list|None  (None = todas)
      - oficinas: list[str]|None  (None = todas)
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    if getattr(user, 'is_superuser', False):
        return {'empresa_ids': None, 'oficinas': None}

    entry = (
        UsuarioAccountingAlcance.objects.filter(user=user, activo=True)
        .prefetch_related('empresas', 'oficinas')
        .first()
    )
    if not entry:
        return None

    empresa_ids = list(entry.empresas.values_list('pk', flat=True))
    oficinas = list(entry.oficinas.values_list('codigo', flat=True))
    return {
        'empresa_ids': empresa_ids or None,
        'oficinas': oficinas or None,
    }


def user_can_access(user, *, empresa_id=None, oficina=None) -> bool:
    alcance = get_alcance(user)
    if alcance is None:
        return False

    if empresa_id is not None and alcance['empresa_ids'] is not None:
        if str(empresa_id) not in {str(x) for x in alcance['empresa_ids']}:
            return False

    if oficina is not None and str(oficina).strip() != '' and alcance['oficinas'] is not None:
        oficina_norm = str(oficina).strip().upper()
        allowed = {str(x).strip().upper() for x in alcance['oficinas']}
        if oficina_norm not in allowed:
            return False

    return True


def _apply_empresa_oficina(qs, alcance, *, empresa_field='empresa_id', oficina_field='oficina'):
    if alcance is None:
        return qs.none()
    if alcance['empresa_ids'] is not None:
        qs = qs.filter(**{f'{empresa_field}__in': alcance['empresa_ids']})
    if alcance['oficinas'] is not None:
        qs = qs.filter(**{f'{oficina_field}__in': alcance['oficinas']})
    return qs


def filter_facturas_qs(qs, user):
    return _apply_empresa_oficina(qs, get_alcance(user), empresa_field='empresa_id', oficina_field='oficina')


def filter_pagos_qs(qs, user):
    return _apply_empresa_oficina(
        qs,
        get_alcance(user),
        empresa_field='empresa_id',
        oficina_field='nroradicado__oficina',
    )


def filter_anticipos_qs(qs, user):
    return _apply_empresa_oficina(qs, get_alcance(user), empresa_field='empresa_id', oficina_field='oficina')


def filter_transf_qs(qs, user):
    alcance = get_alcance(user)
    if alcance is None:
        return qs.none()
    if alcance['oficinas'] is not None:
        qs = qs.filter(oficina__in=alcance['oficinas'])
    if alcance['empresa_ids'] is not None:
        ids = alcance['empresa_ids']
        qs = qs.filter(Q(empresa_sale_id__in=ids) | Q(empresa_entra_id__in=ids))
    return qs


def filter_otros_ingresos_qs(qs, user):
    return _apply_empresa_oficina(qs, get_alcance(user), empresa_field='empresa_id', oficina_field='oficina')


def filter_info_facturas_qs(qs, user):
    """Vista info_facturas: empresa es texto; se acota vía PKs de Facturas en alcance."""
    from accounting.models import Facturas

    alcance = get_alcance(user)
    if alcance is None:
        return qs.none()
    if alcance['empresa_ids'] is None and alcance['oficinas'] is None:
        return qs
    allowed = filter_facturas_qs(Facturas.objects.all(), user).values_list('pk', flat=True)
    return qs.filter(radicado__in=allowed)


def empresas_queryset_for(user):
    alcance = get_alcance(user)
    if alcance is None:
        return EmpresasModel.objects.none()
    qs = EmpresasModel.objects.all()
    if alcance['empresa_ids'] is not None:
        qs = qs.filter(pk__in=alcance['empresa_ids'])
    return qs


def oficinas_choices_for(user, *, include_todas=False):
    """Lista de tuplas (codigo, etiqueta) para selects de oficina."""
    alcance = get_alcance(user)
    if alcance is None:
        return []

    if alcance['oficinas'] is None:
        oficinas = list(GastoNotificacionOficina.objects.order_by('codigo'))
        if oficinas:
            choices = [(o.codigo, o.etiqueta or o.codigo) for o in oficinas]
        else:
            choices = [('MEDELLIN', 'MEDELLIN'), ('MONTERIA', 'MONTERIA')]
    else:
        allowed = {c.upper() for c in alcance['oficinas']}
        oficinas = list(
            GastoNotificacionOficina.objects.filter(codigo__in=allowed).order_by('codigo')
        )
        if oficinas:
            choices = [(o.codigo, o.etiqueta or o.codigo) for o in oficinas]
        else:
            choices = [(c, c) for c in sorted(allowed)]

    if include_todas and choices:
        return [('TODAS', 'TODAS')] + choices
    return choices


def bind_form_alcance(form, user, *, empresa_fields=None, oficina_fields=None, include_todas=False):
    """Restringe querysets/choices de empresa y oficina en un form ya instanciado."""
    empresa_fields = empresa_fields or []
    oficina_fields = oficina_fields or []
    emp_qs = empresas_queryset_for(user)
    ofi_choices = oficinas_choices_for(user, include_todas=include_todas)
    for name in empresa_fields:
        field = form.fields.get(name)
        if field is not None and hasattr(field, 'queryset'):
            field.queryset = emp_qs
    for name in oficina_fields:
        field = form.fields.get(name)
        if field is not None and hasattr(field, 'choices'):
            # Mantener blank/empty si existía
            existing = list(field.choices)
            blank = [c for c in existing if c[0] in ('', None)]
            field.choices = blank + list(ofi_choices)
    return form


def resolve_oficina_filter(user, oficina_param: str):
    """
    Interpreta el param de UI (incl. TODAS) contra el alcance.
    Retorna (ok, codigo) donde codigo puede ser 'TODAS' o un código concreto.
    """
    alcance = get_alcance(user)
    if alcance is None:
        return False, None

    raw = (oficina_param or '').strip()
    if not raw or raw.upper() == 'TODAS':
        return True, 'TODAS'

    codigo = raw.upper()
    if alcance['oficinas'] is not None:
        allowed = {str(x).strip().upper() for x in alcance['oficinas']}
        if codigo not in allowed:
            return False, None
    return True, codigo


def deny_alcance_json(status=403):
    return JsonResponse({'detail': ALCANCE_DENY_DETAIL, 'passed': False}, status=status)


def context_alcance(user, *, include_todas=False):
    """Context helpers para templates del flujo."""
    alcance = get_alcance(user)
    return {
        'accounting_alcance_ok': alcance is not None,
        'empresas': empresas_queryset_for(user),
        'oficinas_permitidas': oficinas_choices_for(user, include_todas=include_todas),
        'oficinas_choices': oficinas_choices_for(user, include_todas=False),
    }
