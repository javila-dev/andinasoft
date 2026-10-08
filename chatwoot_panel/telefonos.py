"""Búsqueda de clientes por teléfono con los formatos libres que hay en `clientes`.

Los teléfonos se guardaron a mano: `3505810975`, `350 581 09 75`, `+57 350…`,
`573505810975`, `3001234567 ELLA`, dos números en un campo, `NO TIENE`…
Chatwoot envía E.164 (`+573505810975`). Ver docs/plan_integracion_chatwoot.md §4.1–4.2.
"""
import re

from django.db.models import F, Func, Q, Value

from andinasoft.models import asesores, clientes

CAMPOS_TITULAR = ('celular1', 'celular2', 'telefono1', 'telefono2')
CAMPO_CONYUGE = 'celular_cony'


def solo_digitos(valor):
    return re.sub(r'\D', '', str(valor or ''))


def _es_basura(digitos):
    return len(set(digitos)) <= 2


def llave_colombia(valor):
    """10 dígitos de un número colombiano (celular o fijo 60X), o None."""
    d = solo_digitos(valor)
    if d.startswith('0057'):
        d = d[4:]
    elif d.startswith('57') and len(d) == 12:
        d = d[2:]
    if len(d) != 10 or _es_basura(d):
        return None
    return d


def llaves_chatwoot(phone):
    """Qué buscar a partir del teléfono de Chatwoot.

    Devuelve {'contiene': [...], 'exacto': [...]} o None si no se puede buscar.
    - Colombia (+57 o 10 dígitos): la llave de 10 dígitos, contenida en el campo.
    - Otro país: todos los dígitos contenidos (`13055551234`) y, como "posible",
      el número nacional igual exacto (indicativo de 1 a 3 dígitos).
    """
    raw = str(phone or '').strip()
    d = solo_digitos(raw)
    if not d or _es_basura(d):
        return None
    es_internacional = raw.startswith('+') or raw.startswith('00')
    if d.startswith('00'):
        d = d[2:]
    if not es_internacional or d.startswith('57'):
        llave = llave_colombia(d)
        return {'contiene': [llave], 'exacto': []} if llave else None
    if len(d) < 8:
        return None
    nacionales = [d[n:] for n in (1, 2, 3) if len(d[n:]) >= 7]
    return {'contiene': [d], 'exacto': nacionales}


def _limpio(campo):
    return Func(F(campo), Value('[^0-9]'), Value(''), function='REGEXP_REPLACE')


def _anotar(qs, campos):
    return qs.annotate(**{f'_{c}': _limpio(c) for c in campos})


def _filtro(campos, llaves):
    q = Q()
    for c in campos:
        for llave in llaves['contiene']:
            q |= Q(**{f'_{c}__contains': llave})
        for nacional in llaves['exacto']:
            q |= Q(**{f'_{c}': nacional})
    return q


def _es_coincidencia_posible(fila, campos, llaves):
    """True si solo coincidió por número nacional exacto (indicativo extranjero)."""
    for c in campos:
        valor = fila.get(f'_{c}') or ''
        if any(llave in valor for llave in llaves['contiene']):
            return False
    return True


def _choca_con_celular_colombiano(fila, campos, llaves):
    """Un nacional extranjero de 10 dígitos que empieza por 3 es un celular colombiano."""
    for c in campos:
        valor = fila.get(f'_{c}') or ''
        if valor in llaves['exacto'] and not (len(valor) == 10 and valor.startswith('3')):
            return False
    return True


def buscar_clientes(phone, limite=20):
    """Clientes cuyo teléfono coincide.

    Devuelve (titulares, conyuges, es_asesor):
      titulares: [{'cedula', 'nombre', 'posible'}] por celular1/2 o telefono1/2
      conyuges:  [{'cedula', 'nombre', 'posible'}] por celular_cony
      es_asesor: el número pertenece a un asesor
    """
    llaves = llaves_chatwoot(phone)
    if not llaves:
        return [], [], False

    def consulta(campos):
        qs = _anotar(clientes.objects.all(), campos).filter(_filtro(campos, llaves))
        filas = qs.values('idTercero', 'nombrecompleto', *[f'_{c}' for c in campos])[:limite]
        resultado = []
        for fila in filas:
            posible = bool(llaves['exacto']) and _es_coincidencia_posible(fila, campos, llaves)
            if posible and _choca_con_celular_colombiano(fila, campos, llaves):
                continue
            resultado.append({
                'cedula': fila['idTercero'],
                'nombre': (fila['nombrecompleto'] or '').strip(),
                'posible': posible,
            })
        return resultado

    titulares = consulta(CAMPOS_TITULAR)
    ya = {c['cedula'] for c in titulares}
    conyuges = [c for c in consulta((CAMPO_CONYUGE,)) if c['cedula'] not in ya]
    es_asesor = (
        _anotar(asesores.objects.all(), ('telefono',)).filter(_filtro(('telefono',), llaves)).exists()
    )
    return titulares, conyuges, es_asesor
