"""
Lectores por formato de archivo. Todos devuelven un `BalanceTercero` (cuentas → terceros → saldo),
así el motor no depende de si la empresa lleva la contabilidad en Alegra o en SIIGO.
"""
from conciliacion_terceros.models import FuenteConciliacion
from conciliacion_terceros.parser import BalanceParseError, parse_balance, parse_siigo_terceros_cuenta

LECTORES = {
    FuenteConciliacion.FORMATO_ALEGRA: parse_balance,
    FuenteConciliacion.FORMATO_SIIGO: parse_siigo_terceros_cuenta,
}


def leer_fuente(formato, path):
    lector = LECTORES.get(formato)
    if lector is None:
        raise BalanceParseError(f'Formato de archivo no soportado: {formato}')
    return lector(path)
