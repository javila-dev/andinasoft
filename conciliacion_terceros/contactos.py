"""
Enlace manual de un tercero con su contacto en Alegra, desde la conciliación.

Es el mismo enlace de la integración de Alegra («Enlazar tercero»): un mapeo de contacto por empresa más el índice de
contactos, así lo usan también caja, egresos y facturación. Se enlaza como cliente si el tercero está en clientes de
Andinasoft; si no, como «tercero egreso» (idtercero/NIT), que también resuelve.
"""
import re

from andinasoft.models import clientes, empresas
from alegra_integration.models import AlegraMapping


class EnlaceError(Exception):
    pass


def _solo_digitos(v):
    return re.sub(r'\D', '', str(v or ''))


def _empresa(empresa_id):
    emp = empresas.objects.filter(pk=empresa_id).first()
    if not emp:
        raise EnlaceError('La empresa no existe.')
    if not getattr(emp, 'alegra_enabled', False):
        raise EnlaceError(f'{emp.nombre} no tiene integración con Alegra.')
    return emp


def _local(identificacion):
    c = clientes.objects.filter(pk=identificacion).first()
    if c:
        return 'andinasoft.clientes', c.nombrecompleto or ''
    return 'andinasoft.terceros_raw', ''


def _conflicto(empresa_id, alegra_id, local_model, identificacion):
    return AlegraMapping.objects.filter(
        empresa_id=empresa_id, proyecto__isnull=True, mapping_type=AlegraMapping.CONTACT, alegra_id=alegra_id, active=True,
    ).exclude(local_model=local_model, local_pk=identificacion).exclude(
        local_model__in=('andinasoft.clientes', 'andinasoft.terceros_raw'), local_pk=identificacion,
    ).first()


def validar(empresa_id, identificacion, alegra_id, client=None):
    """Consulta el contacto en Alegra. Devuelve {id, nombre, identificacion, coincide} o lanza EnlaceError."""
    from alegra_integration.client import AlegraMCPClient

    emp = _empresa(empresa_id)
    alegra_id = str(alegra_id or '').strip()
    if not alegra_id.isdigit():
        raise EnlaceError('El ID de Alegra es un número (lo ves en la URL del contacto).')
    local_model, _ = _local(identificacion)
    otro = _conflicto(emp.pk, alegra_id, local_model, identificacion)
    if otro:
        raise EnlaceError(f'El contacto {alegra_id} de Alegra ya está enlazado a otro tercero ({otro.local_pk}).')
    try:
        c = (client or AlegraMCPClient(emp, timeout=60)).rest('GET', f'/contacts/{alegra_id}')
    except Exception as exc:
        raise EnlaceError(f'No se encontró el contacto {alegra_id} en Alegra ({exc}).')
    if not isinstance(c, dict) or not c.get('id'):
        raise EnlaceError(f'No se encontró el contacto {alegra_id} en Alegra.')
    ident = c.get('identification') or ''
    if isinstance(ident, dict):
        ident = ident.get('number') or ''
    a, b = _solo_digitos(ident), _solo_digitos(identificacion)
    # Con dígito de verificación el NIT de Alegra puede traer un dígito de más.
    coincide = bool(a and b and (a == b or a[:-1] == b or b[:-1] == a))
    return {'id': str(c.get('id')), 'nombre': c.get('name') or c.get('businessName') or '',
            'identificacion': str(ident), 'coincide': coincide}


def enlazar(empresa_id, identificacion, alegra_id, nombre=''):
    """Guarda el enlace (mismo efecto que «Enlazar tercero» de la integración). Devuelve el local_model usado."""
    from alegra_integration.services import (
        _contact_index_ident, _local_third_party_info, _mirror_tercero_raw_contact_mapping, _upsert_contact_index_for_mapping,
    )

    emp = _empresa(empresa_id)
    alegra_id = str(alegra_id or '').strip()
    local_model, nombre_local = _local(identificacion)
    otro = _conflicto(emp.pk, alegra_id, local_model, identificacion)
    if otro:
        raise EnlaceError(f'El contacto {alegra_id} de Alegra ya está enlazado a otro tercero ({otro.local_pk}).')
    AlegraMapping.objects.update_or_create(
        empresa_id=emp.pk, proyecto=None, mapping_type=AlegraMapping.CONTACT, local_model=local_model,
        local_pk=identificacion, local_code='',
        defaults={'alegra_id': alegra_id, 'description': (nombre or nombre_local)[:255], 'active': True},
    )
    if local_model != 'andinasoft.terceros_raw':
        _mirror_tercero_raw_contact_mapping(emp.pk, local_pk=identificacion, alegra_id=alegra_id, name=nombre or nombre_local)
    resolved, ident, nombre_resuelto, tipos = _local_third_party_info(local_model, identificacion)
    _upsert_contact_index_for_mapping(emp, ident=_contact_index_ident(resolved, ident or identificacion), alegra_id=alegra_id,
                                      name=(nombre or nombre_resuelto or nombre_local)[:255], contact_types=tipos)
    return local_model
