"""Números a los que se puede llamar, en E.164 (`+573505810975`, `+13055551234`).

Colombia: celular (3XX) o fijo (60X), con o sin +57. Otros países: solo si el
número trae su indicativo (`+1 305…`, `0034 6…`); qué países salen lo decide
Twilio (Geo Permissions), no Andinasoft.

Los teléfonos de `clientes` son texto libre (`350 581 09 75`, `+57 350…`,
`3001234567 ELLA`, dos números en un campo, `NO TIENE`…). De cada campo se sacan
los números válidos; el resto se ignora.
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
# Otro país: + o 00, indicativo distinto de 57 y de 8 a 15 dígitos en total (E.164).
_EXTRANJERO = re.compile(r'(?<![\d+])(?:\+|00)[\s.-]?((?!57)[1-9](?:[\s.-]?\d){7,14})(?!\d)')


def es_destino_valido(diez_digitos):
    return bool(diez_digitos and _VALIDO.match(diez_digitos))


def e164(diez_digitos):
    return f'+57{diez_digitos}'


def numeros_en(valor):
    """Números válidos (E.164) dentro de un campo de texto libre, sin repetir."""
    texto = str(valor or '')
    encontrados = []

    def agregar(numero):
        if numero not in encontrados:
            encontrados.append(numero)

    for crudo in _EXTRANJERO.findall(texto):
        d = solo_digitos(crudo)
        if len(set(d)) > 2:
            agregar(f'+{d}')

    resto = _EXTRANJERO.sub(' ', texto)
    llave = llave_colombia(resto)
    if llave:
        if es_destino_valido(llave):
            agregar(e164(llave))
        return encontrados
    for crudo in _EN_TEXTO.findall(resto):
        d = solo_digitos(crudo)
        if es_destino_valido(d):
            agregar(e164(d))
    return encontrados


def enmascarar(numero):
    """'+573505810975' → '350 ••• 0975'; '+13055551234' → '+130 ••• 1234'."""
    n = str(numero or '')
    if n.startswith('+57') and len(n) == 13:
        return f'{n[3:6]} ••• {n[-4:]}'
    if n.startswith('+') and len(n) >= 9:
        return f'{n[:4]} ••• {n[-4:]}'
    return '•••'
