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
- No inventes ids. Si no reconoces el impuesto, deja impuesto_id en null y pon el valor en valor_impuesto.
- Las retenciones (retefuente, reteica, reteiva) van en retenciones, no en lineas.
- Montos en pesos, numeros sin separador de miles.
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
            )
        else:
            data, _cfg = extract_json_from_pdf(
                system=SYSTEM_PROMPT,
                user=user + '\n\nEl PDF viene escaneado. Lee las paginas adjuntas.',
                pdf_bytes=pdf_bytes,
                config=config,
            )
    except (LlmConfigurationError, LlmRequestError) as exc:
        raise FacturaLecturaError(str(exc)) from exc
    payload = normalize_factura_payload(data)
    payload['tercero_id'] = _tercero_id(payload.get('nit') or '')
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
    from accounting.models import impuestos_legalizacion
    return [
        {'id': row.pk, 'descripcion': row.descripcion}
        for row in impuestos_legalizacion.objects.filter(activo=True).order_by('descripcion')
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


def _tercero_id(nit: str):
    if not nit:
        return ''
    from accounting.models import Partners
    partner = Partners.objects.filter(pk=nit).first()
    if partner is None and len(nit) > 6:
        partner = Partners.objects.filter(pk=nit[:-1]).first()
    return partner.pk if partner else ''


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
    elif text.count('.') > 1 or ('.' in text and text.split('.')[-1].isdigit() and len(text.split('.')[-1]) == 3):
        parts = text.split('.')
        if all(part.isdigit() for part in parts):
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
