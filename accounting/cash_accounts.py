"""Helpers para cuentas de caja / efectivo en tesoreria."""
from andinasoft.models import cuentas_pagos


def texto_es_caja_efectivo(texto):
    t = (texto or '').strip().lower()
    return ('efectivo' in t) or ('caja' in t)


def cuenta_es_caja_efectivo(cuenta=None, *, pk=None, descripcion=None):
    """
    Determina si una cuenta no debe exigir asociacion de movimientos bancarios.
    Prioridad: instancia/PK (usa es_caja + descripcion) o solo texto.
    """
    if cuenta is not None:
        if hasattr(cuenta, 'es_cuenta_caja_efectivo'):
            return cuenta.es_cuenta_caja_efectivo()
        if getattr(cuenta, 'es_caja', False):
            return True
        return texto_es_caja_efectivo(getattr(cuenta, 'cuentabanco', None))

    if pk is not None and str(pk).strip() != '':
        obj = cuentas_pagos.objects.filter(pk=pk).first()
        if obj is None:
            return texto_es_caja_efectivo(descripcion)
        return obj.es_cuenta_caja_efectivo()

    return texto_es_caja_efectivo(descripcion)
