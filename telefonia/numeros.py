"""Números a los que se puede llamar: solo Colombia, celular (3XX) o fijo (60X).

Los teléfonos de `clientes` son texto libre (`350 581 09 75`, `+57 350…`,
`3001234567 ELLA`, dos números en un campo, `NO TIENE`…). De cada campo se sacan
los números colombianos válidos; el resto se ignora.
"""
import re

from chatwoot_panel.telefonos import CAMPO_CONYUGE, CAMPOS_TITULAR, llave_colombia, solo_digitos

ETIQUETAS = {
    'celular1': 'Celular 1',
    'celular2': 'Celular 2',
    'telefono1': 'Teléfono 1',
    'telefono2': 'Teléfono 2',
    CAMPO_CONYUGE: 'Celular del cónyuge',
}
CAMPOS = CAMPOS_TITULAR + (CAMPO_CONYUGE,)

# Celular: 3 + 9 dígitos. Fijo (desde 2021): 60 + indicativo + 7 dígitos.
_VALIDO = re.compile(r'^(3\d{9}|60[1-8]\d{7})$')
_EN_TEXTO = re.compile(r'(?<![\d+])(?:\+?57[\s.-]?)?((?:3\d{2}|60[1-8])(?:[\s.-]?\d){7})(?!\d)')
# Un indicativo de otro país (+1 305…, 0044…) no se puede confundir con un celular colombiano.
_EXTRANJERO = re.compile(r'(?:^|[^\d])(?:\+|00)(?!57)\d')


def es_destino_valido(diez_digitos):
    return bool(diez_digitos and _VALIDO.match(diez_digitos))


def e164(diez_digitos):
    return f'+57{diez_digitos}'


def numeros_en(valor):
    """Números colombianos válidos (10 dígitos) dentro de un campo de texto libre, sin repetir."""
    if _EXTRANJERO.search(str(valor or '')):
        return []
    llave = llave_colombia(valor)
    if llave:
        return [llave] if es_destino_valido(llave) else []
    encontrados = []
    for crudo in _EN_TEXTO.findall(str(valor or '')):
        d = solo_digitos(crudo)
        if es_destino_valido(d) and d not in encontrados:
            encontrados.append(d)
    return encontrados


def enmascarar(diez_digitos):
    """'3505810975' → '350 ••• 0975'."""
    d = str(diez_digitos or '')
    return f'{d[:3]} ••• {d[-4:]}' if len(d) == 10 else '•••'
