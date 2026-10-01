"""Lee un PDF de factura y devuelve datos para prellenar el gasto de caja. No guarda nada."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from andinasoft.llm_client import (
    PURPOSE_EXTRACCION_FACTURA_CAJA,
    LlmConfigurationError,
    LlmRequestError,
    LlmResolvedConfig,
    extract_json,
    extract_json_from_pdf,
    resolve_purpose_config,
)
from andinasoft.models import IntegrationCredential

MIN_TEXT_CHARS = 40
MAX_PDF_BYTES = 18 * 1024 * 1024

SYSTEM_PROMPT = """Eres un auxiliar contable. Lees facturas de compra colombianas y devuelves SOLO un JSON con esta forma:
{
  "fecha": "YYYY-MM-DD",
  "nit": "solo digitos del vendedor",
  "nombre": "razon social del vendedor",
  "descripcion": "resumen corto de la compra",
  "total": 0,
  "lineas": [
    {"descripcion": "texto", "base": 0, "impuesto_id": null, "valor_impuesto": 0}
  ],
  "retenciones": [
    {"impuesto_id": null, "valor": 0, "asumida": false}
  ]
}
Reglas:
- base es el valor sin impuestos de esa linea.
- Una linea tiene un solo impuesto. Si hay varias tarifas (19, 5, exento), son lineas distintas.
- impuesto_id debe ser uno de los ids del catalogo que te paso, o null si la linea no tiene impuesto.
- Si la linea trae IVA 19%, IVA 5%, ICO 8% o ICUI 20%, impuesto_id es el id de ese nombre en el catalogo. No lo dejes vacio.
- Si no es ninguna de esas tarifas, impuesto_id queda null y valor_impuesto queda 0. El monto de esa linea va en base.
- Las retenciones (retefuente, reteica, reteiva) van en retenciones, no en lineas.
- Montos en pesos, numeros sin separador de miles.
- Un punto seguido de exactamente dos digitos es decimal. 2000.00 es 2000 y 12000.00 es 12000. No borres ese punto: 2000.00 no es 200000.
- El separador de miles es un punto seguido de tres digitos: 200.000 es 200000. No lo confundas con 2000.00.
- "total" es el monto del renglón rotulado Total, Total a pagar o Valor total. En una tirilla es el de "TOTAL", no el precio de un producto.
- No uses el efectivo, el dinero recibido, el valor entregado, el cambio ni las vueltas. Esos montos no son el total de la factura.
- "fecha" es la fecha de la compra o de emisión. Ignora la resolución DIAN, la vigencia, la habilitación y la numeración: un año como 2022 al lado de "resolución" no es la fecha de la factura.
- A veces una tirilla marca cada producto con una letra y mas abajo explica esa letra, por ejemplo "(B) ventas al 19%" o "(E) exentas". Solo en ese caso la letra es el impuesto de la linea.
- Si el documento no trae esa leyenda, no inventes letras ni tasas.
- Toda linea tiene subtotal: base es mayor que 0. Nunca dejes base en 0.
- valor_impuesto no se digita. Solo va si impuesto_id es un id del catalogo, y entonces es el calculo redondeado de base por el porcentaje de ese id. Con tarifa 19, valor_impuesto es round(base * 19 / 100). Si la linea no tiene esa tarifa, valor_impuesto es 0.
- Un renglón que es el impuesto mismo (impuesto al consumo, licores, ICUI, ICO) no se llena como impuesto suelto. Si es un cargo aparte, base es ese monto, impuesto_id queda null y valor_impuesto es 0. Si es el impuesto de un producto que ya tiene subtotal, no crees otra linea: pon el id en el producto y calcula valor_impuesto.
- No pongas IVA 19% por defecto. Si esa linea no muestra su tarifa, deja impuesto_id en null y valor_impuesto en 0.
- Si el precio ya incluye el impuesto (precios visualizados o IVA incluido), no lo sumes otra vez: base es el valor sin impuesto y valor_impuesto es la parte de impuesto que ya iba dentro del precio.
- El nit y el nombre son del emisor de la factura (quien vende), no del comprador.
- Si un dato no esta, usa cadena vacia, 0 o null. No agregues llaves distintas a las pedidas.
"""


class FacturaLecturaError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def leer_factura_pdf(pdf_bytes: bytes) -> dict:
    if not pdf_bytes:
        raise FacturaLecturaError('El PDF está vacío.')
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise FacturaLecturaError('El PDF es demasiado grande para leerlo.')
    catalogo = _catalogo_impuestos()
    user = (
        'Catalogo de impuestos locales (usa estos id):\n'
        + json.dumps(catalogo, ensure_ascii=False)
    )
    config = _config_factura()
    text = _text_from_pdf_bytes(pdf_bytes)
    try:
        if len(text) >= MIN_TEXT_CHARS:
            data, _cfg = extract_json(
                system=SYSTEM_PROMPT,
                user=user + '\n\nTexto del PDF:\n' + text[:20000],
                config=config,
                thinking_budget=512,
            )
        else:
            data, _cfg = extract_json_from_pdf(
                system=SYSTEM_PROMPT,
                user=user + '\n\nEl PDF viene escaneado. Lee las paginas adjuntas.',
                pdf_bytes=pdf_bytes,
                config=config,
                thinking_budget=512,
            )
    except (LlmConfigurationError, LlmRequestError) as exc:
        raise FacturaLecturaError(str(exc)) from exc
    payload = normalize_factura_payload(data)
    _corregir_punto_decimal(payload, text)
    total_rotulado = _total_desde_texto(text)
    if total_rotulado:
        payload['total'] = total_rotulado
    fecha_rotulada = _fecha_desde_texto(text)
    if fecha_rotulada:
        payload['fecha'] = fecha_rotulada
    elif _fecha_modelo_es_resolucion(text, payload.get('fecha')):
        payload['fecha'] = ''
    lineas_pos = _lineas_tirilla_pos(text, catalogo)
    if lineas_pos:
        payload['lineas'] = lineas_pos
        payload['aviso'] = ''
    _corregir_iva_lineas(payload, text, catalogo)
    _asegurar_lineas_calculadas(payload, catalogo)
    payload['precio_incluye_iva'] = bool(re.search(
        r'precios\s+visualizados|iva\s+incluido|impuestos?\s+incluidos',
        text or '',
        re.IGNORECASE,
    ))
    if payload['precio_incluye_iva']:
        for row in payload.get('lineas') or []:
            bruto = (row.get('base') or 0) + (row.get('valor_impuesto') or 0)
            row['bruto'] = float(int(round(bruto)))
    tercero_id, tercero_nombre = _buscar_tercero(payload.get('nit') or '')
    payload['tercero_id'] = tercero_id
    payload['tercero_nombre'] = tercero_nombre
    return payload


def normalize_factura_payload(data) -> dict:
    """Tolera una respuesta incompleta. No persiste el gasto."""
    if not isinstance(data, dict):
        data = {}
    lineas_raw = data.get('lineas') or data.get('lines') or []
    rets_raw = data.get('retenciones') or data.get('retentions') or []
    if not isinstance(lineas_raw, list):
        lineas_raw = []
    if not isinstance(rets_raw, list):
        rets_raw = []

    lineas = []
    for row in lineas_raw:
        if not isinstance(row, dict):
            continue
        lineas.append({
            'descripcion': str(row.get('descripcion') or '')[:255],
            'base': _num(row.get('base')),
            'impuesto_id': _optional_int(row.get('impuesto_id')),
            'valor_impuesto': _num(row.get('valor_impuesto')),
        })
    retenciones = []
    for row in rets_raw:
        if not isinstance(row, dict):
            continue
        valor = _num(row.get('valor'))
        if valor <= 0:
            continue
        retenciones.append({
            'impuesto_id': _optional_int(row.get('impuesto_id')),
            'valor': valor,
            'asumida': bool(row.get('asumida')),
        })

    aviso = ''
    if not lineas:
        aviso = 'No se leyeron líneas de la factura. Complétalas a mano.'
    return {
        'ok': True,
        'fecha': _fecha(data.get('fecha')),
        'nit': re.sub(r'\D', '', str(data.get('nit') or '')),
        'nombre': str(data.get('nombre') or '')[:255],
        'descripcion': str(data.get('descripcion') or '')[:255],
        'total': _num(data.get('total')),
        'lineas': lineas,
        'retenciones': retenciones,
        'aviso': aviso,
    }


def _config_factura() -> LlmResolvedConfig:
    try:
        return resolve_purpose_config(PURPOSE_EXTRACCION_FACTURA_CAJA)
    except LlmConfigurationError:
        cred = (
            IntegrationCredential.objects.filter(
                provider=IntegrationCredential.PROVIDER_OPENAI,
                activo=True,
            )
            .exclude(api_key='')
            .order_by('id')
            .first()
        )
        if not cred:
            raise FacturaLecturaError(
                'No hay credencial OpenAI activa para leer la factura. '
                'Configúrala en Integraciones LLM.'
            )
        from andinasoft.llm_models_catalog import DEFAULT_MODELS
        model = (cred.default_model or '').strip() or DEFAULT_MODELS.get('openai', 'gpt-4o-mini')
        return LlmResolvedConfig(
            provider=cred.provider,
            api_key=cred.api_key.strip(),
            model=model,
            credential_id=cred.pk,
            purpose=PURPOSE_EXTRACCION_FACTURA_CAJA,
        )


def _catalogo_impuestos():
    from accounting.caja_gasto_detalle import catalogo_impuestos_formulario
    catalogo = catalogo_impuestos_formulario()
    return [
        {'id': row['id'], 'descripcion': row['descripcion']}
        for row in catalogo['taxes'] + catalogo['retentions']
    ]


def _text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise FacturaLecturaError('Falta la dependencia pypdf.') from exc
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
    except Exception:
        return ''
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or '')
        except Exception:
            continue
    text = re.sub(r'[ \t]+', ' ', '\n'.join(parts))
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _nit_candidatos(nit: str) -> list:
    """NIT solo digitos, y el mismo sin el digito de verificacion."""
    digits = re.sub(r'\D', '', nit or '')
    if not digits:
        return []
    found = [digits]
    if len(digits) > 6:
        sin_dv = digits[:-1]
        if sin_dv not in found:
            found.append(sin_dv)
    return found


def _buscar_tercero(nit: str):
    """Devuelve (id, nombre) si el emisor ya esta en proveedores. Si no, ('', '')."""
    candidatos = _nit_candidatos(nit)
    if not candidatos:
        return '', ''
    from django.db.models import Value
    from django.db.models.functions import Replace

    from accounting.models import Partners
    nit_limpio = Replace(
        Replace(
            Replace('pk', Value('.'), Value('')),
            Value('-'),
            Value(''),
        ),
        Value(' '),
        Value(''),
    )
    partner = (
        Partners.objects.annotate(nit_limpio=nit_limpio)
        .filter(nit_limpio__in=candidatos)
        .exclude(pk='0')
        .first()
    )
    if partner is None:
        return '', ''
    return partner.pk, partner.nombre_completo()


_CASH_LABEL = re.compile(
    r'efectivo|recibid|entregad|cambio|vuelt|devuelt|propina',
    re.IGNORECASE,
)
_NOT_GRAND_TOTAL = re.compile(
    r'sub\s*total|total\s+(?:iva|bruto|descuento|rete|retenc|impuesto|base)',
    re.IGNORECASE,
)
_TOTAL_LABEL = re.compile(
    r'(?:valor\s+total|vlr\.?\s+total|vr\.?\s+total|total\s+a\s+pagar|'
    r'total\s+(?:de\s+la\s+)?factura|total\s+neto|(?<![A-Za-z])total)\b',
    re.IGNORECASE,
)
_MONEY = re.compile(
    r'\$?\s*('
    r'\d{1,3}(?:\.\d{3})+\.\d{2}'
    r'|\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?'
    r'|\d+\.\d{2}(?!\d)'
    r'|\d+(?:,\d{1,2})?'
    r')'
)


def _total_desde_texto(text: str):
    """Monto del renglón Total. Si el efectivo va en la misma línea, no lo usa."""
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    found = None
    for index, line in enumerate(lines):
        if _NOT_GRAND_TOTAL.search(line):
            continue
        match = _TOTAL_LABEL.search(line)
        if not match:
            continue
        after = line[match.end():]
        cash = _CASH_LABEL.search(after)
        if cash:
            after = after[:cash.start()]
        amount = _first_money(after)
        if amount is None and index + 1 < len(lines):
            nxt = lines[index + 1]
            if not _CASH_LABEL.search(nxt) and not _TOTAL_LABEL.search(nxt) and len(nxt.split()) <= 3:
                amount = _first_money(nxt)
        if amount:
            found = amount
    return found


_SKIP_FECHA = re.compile(
    r'resoluc|vigenc|autoriz|habilita|expedici|certific|numeraci|rango',
    re.IGNORECASE,
)
_FECHA_ISO = re.compile(r'\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b')
_FECHA_DMY = re.compile(r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b')


def _fecha_desde_texto(text: str):
    """Fecha de la compra. Ignora resolución, vigencia y numeración."""
    if not text:
        return None
    best = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or _SKIP_FECHA.search(line):
            continue
        fechas = _fechas_en_linea(line)
        if not fechas:
            continue
        peso = 0
        if re.search(r'\bfecha\b', line, re.IGNORECASE):
            peso += 2
        if re.search(r'\d{1,2}:\d{2}', line):
            peso += 1
        for fecha in fechas:
            if best is None or (peso, fecha) >= best:
                best = (peso, fecha)
    return best[1] if best else None


def _fecha_modelo_es_resolucion(text: str, fecha: str) -> bool:
    """True si ese año solo aparece en la resolución y no hay otra fecha de compra."""
    anio = str(fecha or '')[:4]
    if len(anio) != 4 or not anio.isdigit() or not text:
        return False
    en_resolucion = False
    en_otra = False
    for raw in text.splitlines():
        line = raw.strip()
        if anio not in line:
            continue
        if _SKIP_FECHA.search(line):
            en_resolucion = True
        else:
            en_otra = True
    return en_resolucion and not en_otra


def _fechas_en_linea(line: str):
    found = []
    for match in _FECHA_ISO.finditer(line):
        iso = _fecha_iso(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        if iso:
            found.append(iso)
    for match in _FECHA_DMY.finditer(line):
        iso = _fecha_iso(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        if iso:
            found.append(iso)
    return found


def _fecha_iso(year: int, month: int, day: int):
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


_POS_PRICE = re.compile(r'(\d[\d.]*)\s*([A-Za-z])\s*$')
_POS_LEGEND = re.compile(
    r'^\(([A-Za-z])\)\s+(.*?)\s+(?:COP\s*)?(\d[\d.,]*)\s*$',
    re.IGNORECASE,
)
_POS_QTY = re.compile(r'^\d+\s*@\s*', re.IGNORECASE)
_POS_NOISE = re.compile(
    r'^(total|sub\s*total|efectivo|cambio|copia|precios\s+visualizados|nit|nombre cliente)\b',
    re.IGNORECASE,
)


def _lineas_tirilla_pos(text: str, catalogo) -> list:
    """Solo si el PDF trae letra en el producto y la leyenda de esa letra. Si no, no aplica."""
    if not text or not re.search(r'\([A-Za-z]\)', text):
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    tasas = {}
    for line in lines:
        match = _POS_LEGEND.match(line)
        if not match:
            continue
        letra = match.group(1).upper()
        detalle = match.group(2)
        tasa = _tasa_leyenda(detalle)
        if tasa is None:
            continue
        tasas[letra] = tasa
    if not tasas:
        return []

    desc = ''
    items = []
    for line in lines:
        if _POS_QTY.match(line) or _POS_LEGEND.match(line) or _POS_NOISE.match(line):
            continue
        match = _POS_PRICE.search(line)
        if match and match.group(2).upper() in tasas:
            bruto = _num(match.group(1))
            if bruto <= 0:
                continue
            letra = match.group(2).upper()
            nombre = desc or _texto_antes_de_precio(line, match)
            items.append((nombre, bruto, letra))
            desc = ''
            continue
        if re.search(r'[A-Za-zÁÉÍÓÚáéíóúñ]{3,}', line):
            desc = re.sub(r'^\d+\s+', '', line).strip()

    if not items:
        return []

    incluido = bool(re.search(r'precios\s+visualizados|iva\s+incluido', text, re.IGNORECASE))
    if not incluido:
        incluido = _precios_traen_impuesto(items, tasas, lines)

    lineas = []
    for nombre, bruto, letra in items:
        tasa = tasas[letra]
        if incluido and tasa > 0:
            impuesto = int(round(bruto * tasa / (100.0 + tasa)))
            base = int(round(bruto)) - impuesto
        elif tasa > 0:
            base = int(round(bruto))
            impuesto = int(round(base * tasa / 100.0))
        else:
            base = int(round(bruto))
            impuesto = 0
        lineas.append({
            'descripcion': (nombre or 'Producto')[:255],
            'base': float(base),
            'impuesto_id': _id_por_tasa(catalogo, tasa),
            'valor_impuesto': float(impuesto),
        })
    return lineas


def _tasa_leyenda(detalle: str):
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', detalle or '')
    if match:
        return float(match.group(1).replace(',', '.'))
    if re.search(r'exent', detalle or '', re.IGNORECASE):
        return 0.0
    return None


def _precios_traen_impuesto(items, tasas, lines) -> bool:
    por_letra = {}
    for _nombre, bruto, letra in items:
        por_letra[letra] = por_letra.get(letra, 0.0) + bruto
    for line in lines:
        match = _POS_LEGEND.match(line)
        if not match:
            continue
        letra = match.group(1).upper()
        tasa = tasas.get(letra) or 0
        bruto = por_letra.get(letra) or 0
        if tasa <= 0 or bruto <= 0:
            continue
        impuesto_leyenda = _num(match.group(3))
        incluido = round(bruto * tasa / (100.0 + tasa))
        if abs(impuesto_leyenda - incluido) <= 2:
            return True
    return False


def _texto_antes_de_precio(line: str, match) -> str:
    resto = line[:match.start()].strip()
    resto = re.sub(r'\d{6,}', '', resto).strip()
    return re.sub(r'^\d+\s+', '', resto).strip()


def _asegurar_lineas_calculadas(payload, catalogo):
    """Toda línea lleva subtotal. El valor del impuesto solo sale de la tarifa."""
    lineas = []
    for row in payload.get('lineas') or []:
        base = float(row.get('base') or 0)
        valor = float(row.get('valor_impuesto') or 0)
        if base <= 0 and valor > 0:
            row['base'] = float(int(round(valor)))
            row['impuesto_id'] = None
            row['valor_impuesto'] = 0.0
            lineas.append(row)
            continue
        if base <= 0:
            continue
        tasa = _tasa_de_id(catalogo, row.get('impuesto_id'))
        if not tasa or tasa <= 0:
            inferido = _inferir_impuesto(catalogo, base, valor)
            if inferido is None:
                row['impuesto_id'] = None
                row['valor_impuesto'] = 0.0
                lineas.append(row)
                continue
            impuesto_id, tasa, incluido = inferido
            if incluido:
                neto = int(round(base)) - int(round(valor))
                if neto <= 0:
                    row['impuesto_id'] = None
                    row['valor_impuesto'] = 0.0
                    lineas.append(row)
                    continue
                row['base'] = float(neto)
                base = float(neto)
            row['impuesto_id'] = impuesto_id
        row['valor_impuesto'] = float(int(round(base * tasa / 100.0)))
        lineas.append(row)
    payload['lineas'] = lineas


def _corregir_iva_lineas(payload, text, catalogo):
    """Quita un IVA que el documento no respalda y no lo suma sobre un precio que ya lo trae."""
    lineas = payload.get('lineas') or []
    if not text or not lineas:
        return
    incluido = bool(re.search(
        r'precios\s+visualizados|iva\s+incluido|impuestos?\s+incluidos',
        text,
        re.IGNORECASE,
    ))
    resumen = _resumen_tarifas(text)
    positivas = sorted(
        tasa for tasa, monto in resumen.items()
        if tasa > 0 and (monto is None or monto > 1)
    )
    hay_exentas = (resumen.get(0) or 0) > 1
    varias = len(positivas) > 1 or (len(positivas) == 1 and hay_exentas)
    montos = _montos_en_texto(text)
    quito_tarifa = False
    for row in lineas:
        base = float(row.get('base') or 0)
        valor = float(row.get('valor_impuesto') or 0)
        if base <= 0:
            continue
        tasa_actual = _tasa_de_id(catalogo, row.get('impuesto_id'))
        if len(positivas) == 1 and not varias:
            tasa = positivas[0]
        elif tasa_actual in positivas or (tasa_actual == 0 and hay_exentas):
            tasa = tasa_actual
        elif positivas:
            tasa = None
        else:
            tasa = tasa_actual
        impreso = _monto_en_texto(base, montos) and (
            valor <= 1 or not _monto_en_texto(base + valor, montos)
        )
        if incluido and impreso and varias:
            if row.get('impuesto_id') is not None or valor > 1:
                row['impuesto_id'] = None
                row['valor_impuesto'] = 0
                quito_tarifa = True
            continue
        if incluido and tasa and tasa > 0 and impreso:
            bruto = int(round(base))
            impuesto = int(round(bruto * tasa / (100.0 + tasa)))
            row['base'] = float(bruto - impuesto)
            row['valor_impuesto'] = float(impuesto)
            row['impuesto_id'] = _id_por_tasa(catalogo, tasa)
            continue
        if tasa is not None and _cuadra_exclusivo(base, valor, tasa):
            row['impuesto_id'] = _id_por_tasa(catalogo, tasa) if tasa else row.get('impuesto_id')
            continue
        if tasa is not None and _cuadra_incluido(base, valor, tasa):
            row['base'] = float(int(round(base)) - int(round(valor)))
            row['impuesto_id'] = _id_por_tasa(catalogo, tasa)
            continue
        if tasa is not None and not incluido and _iva_impreso_cuadra_con_base(
            resumen, tasa, base, len(lineas) == 1
        ):
            esperado = int(round(base * tasa / 100.0)) if tasa else 0
            row['valor_impuesto'] = float(esperado)
            row['impuesto_id'] = _id_por_tasa(catalogo, tasa)
            continue
        if row.get('impuesto_id') is not None or valor > 1:
            inferido = _inferir_impuesto(catalogo, base, valor)
            if inferido:
                impuesto_id, _, incluido = inferido
                if incluido:
                    neto = int(round(base)) - int(round(valor))
                    if neto > 0:
                        row['base'] = float(neto)
                row['impuesto_id'] = impuesto_id
                continue
        if row.get('impuesto_id') is not None:
            row['impuesto_id'] = None
            row['valor_impuesto'] = 0
            quito_tarifa = True
    if quito_tarifa:
        payload['aviso'] = (
            'Hay más de una tarifa y el documento no marca cuál va en cada producto. Revisa el IVA.'
        )


def _resumen_tarifas(text):
    """Tarifa -> monto impreso en el resumen. Ignora retenciones."""
    tasas = {}
    for line in (text or '').splitlines():
        if re.search(r'rete|rte|retenc', line, re.IGNORECASE):
            continue
        if not re.search(
            r'iva|impuesto|venta|exent|gravad|\binc\b|consumo|\([A-Za-z]\)',
            line,
            re.IGNORECASE,
        ):
            continue
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', line)
        if match:
            tasa = float(match.group(1).replace(',', '.'))
            resto = line[match.end():]
        elif re.search(r'exent', line, re.IGNORECASE):
            tasa = 0.0
            resto = line
        else:
            continue
        monies = [_num(raw) for raw in _MONEY.findall(resto)]
        monto = monies[-1] if monies else None
        previo = tasas.get(tasa)
        if previo is None:
            tasas[tasa] = monto
        elif monto:
            tasas[tasa] = (previo or 0) + monto
    return tasas


def _inferir_impuesto(catalogo, base, valor):
    """Si el monto cuadra con una tarifa del catalogo, devuelve (id, tasa, incluido)."""
    if base <= 0 or valor <= 1:
        return None
    candidatos = []
    for row in catalogo or []:
        desc = str(row.get('descripcion') or '')
        if re.search(r'rete|rte', desc, re.IGNORECASE):
            continue
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        if match is None:
            continue
        tasa = float(match.group(1).replace(',', '.'))
        if tasa <= 0:
            continue
        exclusivo = round(base * tasa / 100.0)
        incluido = round(base * tasa / (100.0 + tasa))
        if abs(valor - exclusivo) <= 1:
            candidatos.append((0, row, tasa, False))
        elif abs(valor - incluido) <= 1:
            candidatos.append((1, row, tasa, True))
    if not candidatos:
        return None
    candidatos.sort(key=lambda item: (
        item[0],
        0 if 'iva' in str(item[1].get('descripcion') or '').lower() else 1,
        item[1].get('id') or 0,
    ))
    _, row, tasa, incluido = candidatos[0]
    return row.get('id'), tasa, incluido


def _tasa_de_id(catalogo, impuesto_id):
    if impuesto_id is None:
        return None
    for row in catalogo or []:
        if row.get('id') != impuesto_id and str(row.get('id')) != str(impuesto_id):
            continue
        desc = str(row.get('descripcion') or '')
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        if match:
            return float(match.group(1).replace(',', '.'))
        if re.search(r'exent', desc, re.IGNORECASE):
            return 0.0
    return None


def _montos_en_texto(text):
    return [_num(raw) for raw in _MONEY.findall(text or '')]


def _monto_en_texto(amount, montos) -> bool:
    target = round(float(amount or 0))
    if target <= 0:
        return False
    return any(abs(round(value) - target) <= 1 for value in montos)


def _cuadra_exclusivo(base, valor, tasa) -> bool:
    if tasa is None or tasa <= 0:
        return abs(valor) <= 1
    return abs(valor - round(base * tasa / 100.0)) <= 1


def _iva_impreso_cuadra_con_base(resumen, tasa, base, una_sola_linea) -> bool:
    if not una_sola_linea or not tasa:
        return False
    monto = resumen.get(tasa)
    if not monto:
        return False
    return abs(monto - round(base * tasa / 100.0)) <= 1


def _cuadra_incluido(base, valor, tasa) -> bool:
    if tasa is None or tasa <= 0 or valor <= 0:
        return False
    return abs(valor - round(base * tasa / (100.0 + tasa))) <= 1


def _id_por_tasa(catalogo, tasa):
    if tasa is None:
        return None
    candidatos = []
    for row in catalogo or []:
        desc = str(row.get('descripcion') or '')
        pct = re.search(r'(\d+(?:[.,]\d+)?)\s*%', desc)
        if pct is None:
            if tasa == 0 and re.search(r'exent', desc, re.IGNORECASE):
                candidatos.append(row)
            continue
        if abs(float(pct.group(1).replace(',', '.')) - tasa) < 0.05:
            candidatos.append(row)
    if not candidatos:
        return None
    candidatos.sort(key=lambda row: (0 if 'iva' in str(row.get('descripcion')).lower() else 1, row.get('id') or 0))
    return candidatos[0].get('id')


def _first_money(line: str):
    matches = list(_MONEY.finditer(line or ''))
    if not matches:
        return None
    value = _num(matches[0].group(1))
    return value or None


def _last_money(line: str):
    matches = list(_MONEY.finditer(line))
    if not matches:
        return None
    value = _num(matches[-1].group(1))
    return value or None


_MONTO_ESCRITO = re.compile(
    r'(?<!\d)('
    r'\d{1,3}(?:\.\d{3})+\.\d{2}'
    r'|\d+\.\d{2}'
    r'|\d{1,3}(?:\.\d{3})+'
    r')(?!\d)'
)


def _montos_escritos(text: str):
    """Separa 2000.00 (decimal) de 200.000 (miles)."""
    decimales = set()
    miles = set()
    for match in _MONTO_ESCRITO.finditer(text or ''):
        token = match.group(1)
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+\.\d{2}', token):
            entero, cents = token.rsplit('.', 1)
            decimales.add(int(round(float(entero.replace('.', '') + '.' + cents))))
        elif re.fullmatch(r'\d+\.\d{2}', token):
            decimales.add(int(round(float(token))))
        else:
            miles.add(int(token.replace('.', '')))
    return decimales, miles


def _corregir_punto_decimal(payload, text: str):
    """2000.00 es 2000. Si el modelo lo devolvio como 200000, lo baja."""
    decimales, miles = _montos_escritos(text)
    if not decimales:
        return

    def ajustar(valor, forzar=False):
        if not valor:
            return valor
        actual = int(round(float(valor)))
        if actual in decimales or actual in miles:
            return float(actual)
        if actual % 100 == 0:
            reducido = actual // 100
            if reducido in decimales and actual not in miles:
                return float(reducido)
        if forzar and actual % 100 == 0 and actual not in miles:
            return float(actual // 100)
        return float(valor)

    if payload.get('total'):
        payload['total'] = ajustar(payload['total'])
    for row in payload.get('lineas') or []:
        base = float(row.get('base') or 0)
        nueva = ajustar(base)
        if nueva != base and base and nueva == base / 100:
            row['valor_impuesto'] = ajustar(row.get('valor_impuesto'), forzar=True)
        row['base'] = nueva
    for row in payload.get('retenciones') or []:
        row['valor'] = ajustar(row.get('valor'))


def _num(raw) -> float:
    if raw is None or raw == '':
        return 0.0
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).replace('$', '').replace(' ', '')
    if ',' in text and '.' in text:
        if text.rfind(',') > text.rfind('.'):
            text = text.replace('.', '').replace(',', '.')
        else:
            text = text.replace(',', '')
    elif ',' in text:
        parts = text.split(',')
        if len(parts) > 1 and len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            text = ''.join(parts)
        else:
            text = text.replace(',', '.')
    elif '.' in text:
        parts = text.split('.')
        if parts and all(part.isdigit() for part in parts):
            if len(parts[-1]) == 2:
                # 2000.00 y 2.000.00 son dos mil. Los dos decimales no se pegan al entero.
                text = ''.join(parts[:-1]) + '.' + parts[-1]
            elif len(parts[-1]) == 3 and all(len(part) == 3 for part in parts[1:]):
                text = ''.join(parts)
    try:
        return float(Decimal(text))
    except (InvalidOperation, ValueError):
        return 0.0


def _optional_int(raw):
    if raw is None or str(raw).strip() in ('', 'null', 'None'):
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _fecha(raw) -> str:
    text = str(raw or '').strip()[:10]
    if not text:
        return ''
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return ''
