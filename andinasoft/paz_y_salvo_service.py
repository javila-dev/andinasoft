"""
Contexto para el certificado de paz y salvo de cartera de una adjudicacion.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from andinasoft.cartera_gestor_service import CARTA_LOGO_STATIC
from andinasoft.certificado_tributario_service import (
    MESES_ES,
    _datos_adj_certificado,
    _tipo_documento_label,
    _titulares_seguros,
)
from andinasoft.models import empresas
from andinasoft.shared_models import Adjudicacion
from andinasoft.utilities import Utilidades

LOGOS_PROYECTO_EXTRA = {
    'Fractal': 'img/fractal-logo.jpg',
    'Oasis': 'img/logo_oasis.png',
}

LOGO_ANDINA = 'img/Andina-Conceptos.png'

# Colores tomados de la paleta del logo de cada proyecto (no se muestrean en runtime).
# (principal, acento)
PALETA_DEFAULT = ('#1A4A4A', '#c9a227')
PALETA_PROYECTO = {
    'Oasis': ('#1A4A4A', '#D4572A'),
    'Carmelo Reservado': ('#1F4A3C', '#C8963E'),
    'Casas de Verano': ('#1A4A4A', '#E06020'),
    'Tesoro Escondido': ('#1A4A4A', '#2A90A0'),
    'Vegas de Venecia': ('#5C2A22', '#904030'),
    'Sandville Beach': ('#1A4A4A', '#1A9A9A'),
    'Perla del Mar': ('#1A4A4A', '#C47850'),
    'Fractal': ('#1A4A4A', '#c9a227'),
}


def logos_proyecto(proyecto: str) -> list[str]:
    """Un solo logo de proyecto para el encabezado."""
    nombre = (proyecto or '').strip()
    principal = CARTA_LOGO_STATIC.get(nombre) or LOGOS_PROYECTO_EXTRA.get(nombre) or LOGO_ANDINA
    return [principal]


def paleta_proyecto(proyecto: str) -> dict[str, str]:
    principal, acento = PALETA_PROYECTO.get((proyecto or '').strip(), PALETA_DEFAULT)
    return {'principal': principal, 'acento': acento}


def format_nit(nit: str | None) -> str:
    raw = (nit or '').strip().replace('.', '').replace(' ', '')
    if not raw:
        return ''
    if '-' in raw:
        num, dv = raw.split('-', 1)
        if num.isdigit():
            return f'{_miles(num)}-{dv}'
        return raw
    digits = ''.join(c for c in raw if c.isdigit())
    if len(digits) == 10:
        return f'{_miles(digits[:-1])}-{digits[-1]}'
    if digits:
        return _miles(digits)
    return raw


def _miles(num: str) -> str:
    return f'{int(num):,}'.replace(',', '.')


def fecha_expedicion_texto(fecha: datetime.date | None = None) -> str:
    hoy = fecha or datetime.date.today()
    return f'{hoy.day} de {MESES_ES[hoy.month]} de {hoy.year}'


def titulares_certificado(titulares: list) -> list[dict[str, str]]:
    filas = []
    for titular in titulares:
        filas.append(
            {
                'nombre': (getattr(titular, 'nombrecompleto', None) or '').strip().upper(),
                'tipo': _tipo_documento_label(getattr(titular, 'tipo_doc', None)),
                'numero': str(getattr(titular, 'pk', '') or ''),
            }
        )
    return filas


def frase_titulares(titulares: list) -> str:
    partes = []
    for titular in titulares:
        tipo = _tipo_documento_label(getattr(titular, 'tipo_doc', None))
        nombre = (getattr(titular, 'nombrecompleto', None) or '').strip().upper()
        numero = getattr(titular, 'pk', '') or ''
        partes.append(f'{nombre}, identificado(a) con {tipo} No. {numero}')
    if not partes:
        return ''
    if len(partes) == 1:
        return partes[0]
    if len(partes) == 2:
        return f'{partes[0]} y {partes[1]}'
    return f'{", ".join(partes[:-1])} y {partes[-1]}'


def valor_en_letras(valor) -> str:
    monto = Decimal('0') if valor is None else Decimal(str(valor))
    entero = int(monto.quantize(Decimal('1')))
    texto = Utilidades().numeros_letras(entero, formato='Numero') or ''
    return ' '.join(texto.split())


def build_paz_y_salvo_context(
    proyecto: str,
    adj_id: str,
    empresa_nit: str,
    nombre_responsable: str,
    cargo_responsable: str,
    user=None,
    titular_ids: list[str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    nombre_responsable = (nombre_responsable or '').strip()
    cargo_responsable = (cargo_responsable or '').strip()
    empresa_nit = (empresa_nit or '').strip()

    if not empresa_nit:
        return None, 'Debe seleccionar la empresa que expide el certificado.'
    if not nombre_responsable:
        return None, 'Debe indicar el nombre de quien firma el certificado.'
    if not cargo_responsable:
        return None, 'Debe indicar el cargo de quien firma el certificado.'

    try:
        adj = Adjudicacion.objects.using(proyecto).get(pk=adj_id)
    except Adjudicacion.DoesNotExist:
        return None, 'Adjudicacion no encontrada.'

    try:
        empresa = empresas.objects.get(pk=empresa_nit)
    except empresas.DoesNotExist:
        return None, 'Empresa no encontrada.'

    titulares = _titulares_seguros(adj)
    if not titulares:
        return None, 'La adjudicacion no tiene titulares registrados.'

    ids_validos = {str(t.pk) for t in titulares}
    seleccion = [str(tid).strip() for tid in (titular_ids or []) if str(tid).strip()]
    if not seleccion:
        return None, 'Debe seleccionar al menos un titular.'
    if any(tid not in ids_validos for tid in seleccion):
        return None, 'El titular seleccionado no pertenece a esta adjudicacion.'

    orden = {tid: idx for idx, tid in enumerate(seleccion)}
    titulares = [t for t in titulares if str(t.pk) in orden]
    titulares.sort(key=lambda t: orden.get(str(t.pk), 99))

    inmueble, _fecha_contrato = _datos_adj_certificado(proyecto, adj_id, adj)
    valor_contrato = adj.valor or Decimal('0')
    numero_contrato = (adj.contrato or '').strip() or adj_id
    hoy = datetime.date.today()

    context = {
        'user': user,
        'now': hoy.strftime('%d/%m/%Y'),
        'fecha_expedicion': fecha_expedicion_texto(hoy),
        'proyecto': proyecto,
        'adj': adj_id,
        'empresa': empresa,
        'empresa_nombre': (empresa.nombre or '').strip().upper(),
        'empresa_nit': format_nit(empresa.Nit),
        'titulares': titulares_certificado(titulares),
        'frase_cliente': frase_titulares(titulares),
        'numero_contrato': numero_contrato,
        'valor_contrato': valor_contrato,
        'valor_contrato_letras': valor_en_letras(valor_contrato),
        'inmueble': (inmueble or '').strip(),
        'logos': logos_proyecto(proyecto),
        'paleta': paleta_proyecto(proyecto),
        'nombre_responsable': nombre_responsable.upper(),
        'cargo_responsable': cargo_responsable,
    }
    return context, None
