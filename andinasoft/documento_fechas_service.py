"""
Extraccion de fechas certeras desde PDFs de venta (promesa / otrosi / otros).
"""
from __future__ import annotations

import calendar
import datetime
import io
import json
import logging
import re
from typing import Iterable, Optional

from andinasoft.llm_client import (
    PURPOSE_EXTRACCION_FECHAS,
    PURPOSE_EXTRACCION_FECHAS_ESCANEADO,
    LlmConfigurationError,
    LlmRequestError,
    LlmResolvedConfig,
    extract_json,
    extract_json_from_pdf,
    resolve_credential_config,
)
from andinasoft.llm_models_catalog import DEFAULT_MODELS
from andinasoft.models import AdjFechaDocumentoExtraccion, clientes
from andinasoft.shared_models import Adjudicacion, Promesas, documentos_contratos

logger = logging.getLogger(__name__)

DOCS_DESDE_DEFAULT = datetime.date(2021, 1, 1)
TIPOS_PRIORIDAD = ('Promesa', 'Otrosi', 'Otros', 'Escritura')
MIN_TEXT_CHARS = 80
MAX_TEXT_CHARS = 28000
# PDFs tipo formulario/DocuSign a veces dejan "texto" de campos sin etiquetas
# (pypdf: Impossible to decode XFormObject). Sin estos marcadores el LLM de texto falla.
TEXT_CONTRACT_MARKERS = (
    'escritura',
    'entrega',
    'promesa',
    'compraventa',
    'otorgamiento',
    'inmueble',
    'otrosi',
    'clausula',
    'cláusula',
)

SYSTEM_PROMPT = (
    'Eres un asistente que analiza contratos inmobiliarios colombianos (promesa de '
    'compraventa, contrato, otrosi). Respondes SOLO JSON valido sin markdown.'
)

FECHAS_RULES = """Clasifica el documento y extrae fechas pactadas si aparecen.

Reglas generales:
- fecha_contrato: fecha de firma/celebracion del contrato o promesa (no la de carga del archivo).
- fecha_escritura: fecha pactada o comprometida de escritura publica (calendario), si aparece.
- fecha_entrega: fecha pactada o comprometida de entrega del inmueble (calendario), si aparece.
- Si un otrosi MODIFICA fechas, usa las fechas NUEVAS del otrosi.
- Si una fecha no aparece con claridad, usa null.
- doc_tipo_detectado: uno de "promesa", "contrato", "otrosi", "escritura", "otro", "irrelevante".
- util: true solo si el documento es promesa/contrato/otrosi/escritura relevante y aporta al menos una fecha, meses de entrega, o confirma ser ese tipo de contrato.

Reglas IMPORTANTES si el documento es PROMESA (o contrato de promesa de compraventa):
- fecha_escritura y fecha_entrega suelen estar en la SEGUNDA PAGINA del PDF; prioriza esa zona para esas dos.
- fecha_escritura: busca la clausula o parrafo de "otorgamiento de la escritura publica" (o redacciones muy similares: otorgar escritura, escritura publica). La fecha de escritura esta CERCA de ese texto, en el mismo parrafo o el inmediato.
- fecha_contrato (firma/celebracion): prioriza el texto de aceptacion/firma de las partes, aunque NO este en la ultima hoja. Busca frases como:
  "En señal de aceptación de lo aquí suscrito, firman LAS PARTES, el día …" (o variantes: "en senal de aceptacion", "firman las partes el dia", "en constancia de lo cual firman").
  La fecha va justo despues de "el día" / "el dia" (puede venir como "10 de Octubre de 2.025" o "10 de octubre de 2025"; normalizala a YYYY-MM-DD).
  Si no aparece esa formula, recien entonces busca en la ULTIMA pagina y, si falta, en la PENULTIMA (firmas, "se firma", ciudad y fecha al cierre).
- No confundas fecha_escritura con fecha_entrega: escritura va con otorgamiento de escritura publica; entrega va con entrega del inmueble / entrega material.
- No uses la fecha_contrato (firma/aceptacion) como fecha_escritura ni como fecha_entrega.

ENTREGA RELATIVA (muy frecuente en promesas nuevas, p.ej. "bien futuro" / "Perla Del Mar Territorio Campestre"):
- Busca clausulas tipo "ENTREGA MATERIAL", "entrega del lote", "fecha aproximada de entrega".
- Si NO hay fecha de calendario y dice que la entrega es a los N meses contados a partir de la firma del contrato
  (ej. "se estima una fecha aproximada de entrega del lote, de 13 meses, contados a partir de la firma de este contrato"),
  entonces:
  - entrega_meses_desde_firma = N (entero, ej. 13)
  - fecha_entrega = null (el sistema la calcula como fecha_contrato + N meses)
- Si ademas dice que la fecha cierta de entrega quedara en la escritura publica, NO inventes fecha_entrega de calendario;
  usa solo entrega_meses_desde_firma.
- Si hay fecha de calendario explicita de entrega, usa fecha_entrega y deja entrega_meses_desde_firma en null.

Responde exactamente con este JSON:
{
  "doc_tipo_detectado": "promesa|contrato|otrosi|escritura|otro|irrelevante",
  "util": true,
  "fecha_contrato": "YYYY-MM-DD" o null,
  "fecha_escritura": "YYYY-MM-DD" o null,
  "fecha_entrega": "YYYY-MM-DD" o null,
  "entrega_meses_desde_firma": null o entero,
  "notas": "breve"
}"""

USER_PROMPT_TEMPLATE = (
    "Analiza el siguiente texto extraido de un PDF de venta inmobiliaria.\n\n"
    + FECHAS_RULES.replace('{', '{{').replace('}', '}}')
    + "\n\nTexto del PDF:\n---\n{text}\n---\n"
)

USER_PROMPT_VISION = (
    "Analiza este PDF escaneado/firmado de venta inmobiliaria (imagenes/paginas del documento).\n"
    "Lee el contenido visual del contrato aunque no haya texto seleccionable.\n"
    "Si es promesa: pagina 2 para escritura y entrega (incluye clausula ENTREGA MATERIAL / meses desde firma); "
    "fecha_contrato: busca en TODO el documento la formula "
    "\"En señal de aceptación de lo aquí suscrito, firman LAS PARTES, el día …\" "
    "(no asumas que esta solo al final); si no esta, ultima/penultima pagina.\n\n"
    + FECHAS_RULES
)


def _parse_fecha_carga(value) -> Optional[datetime.date]:
    if value is None or value == '':
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in (
        '%Y-%m-%d %H:%M:%S.%f',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y',
    ):
        try:
            return datetime.datetime.strptime(s[:26], fmt).date()
        except ValueError:
            continue
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        try:
            return datetime.date.fromisoformat(m.group(1))
        except ValueError:
            return None
    return None


def _parse_iso_date(value) -> Optional[datetime.date]:
    if value is None or value == '' or value is False:
        return None
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.datetime):
        return value.date()
    s = str(value).strip()[:10]
    try:
        return datetime.date.fromisoformat(s)
    except ValueError:
        return None


def _tipo_from_descripcion(descripcion: str) -> str:
    name = (descripcion or '').strip()
    for tipo in TIPOS_PRIORIDAD:
        if name.lower().startswith(tipo.lower()):
            return tipo
    return ''


def _doc_storage_key(proyecto: str, adj: str, descripcion_doc: str) -> str:
    """Misma ruta que radicacion/upload_docs_contratos (docs_andinasoft/doc_contratos/...)."""
    nombre = descripcion_doc or ''
    filename = nombre if str(nombre).lower().endswith('.pdf') else f'{nombre}.pdf'
    return f'docs_andinasoft/doc_contratos/{proyecto}/{adj}/{filename}'


def _doc_storage_key_candidates(proyecto: str, adj: str, descripcion_doc: str) -> list[str]:
    """Ruta de produccion + legado local (doc_contratos/... sin prefijo docs_andinasoft)."""
    primary = _doc_storage_key(proyecto, adj, descripcion_doc)
    legacy = primary[len('docs_andinasoft/'):] if primary.startswith('docs_andinasoft/') else primary
    keys = [primary]
    if legacy and legacy != primary:
        keys.append(legacy)
    return keys


def _resolve_doc_key(proyecto: str, adj: str, descripcion_doc: str) -> str:
    """
    Resuelve la key del PDF via media_service (MinIO/S3 en produccion, igual que radicacion).
    """
    from andina.storage import media_service

    keys = _doc_storage_key_candidates(proyecto, adj, descripcion_doc)
    for key in keys:
        if media_service.exists_media(key, private=True):
            return key
    return keys[0]


def doc_url(
    proyecto: str,
    adj: str,
    descripcion_doc: str,
    *,
    check_exists: bool = True,
) -> str:
    """
    URL firmada MinIO/S3 (mismo media_service que produccion).

    check_exists=False: no hace HEAD a MinIO (listados). La firma es local.
    """
    if not descripcion_doc:
        return ''
    from andina.storage import media_service

    if check_exists:
        key = _resolve_doc_key(proyecto, adj, descripcion_doc)
    else:
        key = _doc_storage_key(proyecto, adj, descripcion_doc)
    try:
        return media_service.url_media(key, private=True, check_exists=check_exists)
    except Exception:
        from django.conf import settings
        from urllib.parse import quote

        encoded = '/'.join(quote(seg) for seg in key.split('/'))
        return (getattr(settings, 'MEDIA_URL', '/media/') or '/media/') + encoded


def list_docs_adj(
    proyecto: str,
    adj: str,
    *,
    docs_desde: Optional[datetime.date] = None,
    aplicar_filtro_fecha: bool = True,
) -> list[dict]:
    """
    Documentos relevantes del ADJ (Promesa/Otrosi/Otros/Escritura) con URL.
    Para el modal de consulta, pasar aplicar_filtro_fecha=False para ver todos.
    """
    from andina.storage import media_service

    if aplicar_filtro_fecha:
        desde = docs_desde or DOCS_DESDE_DEFAULT
    else:
        desde = datetime.date(1970, 1, 1)
    out = []
    for tipo_rank, fecha_doc, _id, tipo, doc in _candidate_docs(proyecto, adj, desde):
        key = _resolve_doc_key(proyecto, adj, doc.descripcion_doc or '')
        out.append({
            'descripcion': doc.descripcion_doc or '',
            'tipo': tipo,
            'fecha_carga': str(doc.fecha_carga or ''),
            'usuario_carga': str(doc.usuario_carga or ''),
            'url': doc_url(proyecto, adj, doc.descripcion_doc or ''),
            'en_storage': media_service.exists_media(key, private=True),
        })
    return out


def _load_pdf_bytes(proyecto: str, adj: str, descripcion_doc: str) -> bytes:
    """Lee bytes del PDF desde MinIO/S3 via media_service (mismo camino que produccion)."""
    from andina.storage import media_service

    key = _resolve_doc_key(proyecto, adj, descripcion_doc)
    if not media_service.exists_media(key, private=True):
        raise FileNotFoundError(f'PDF no encontrado: {key}')
    with media_service.open_media(key, mode='rb', private=True) as fh:
        return fh.read()


def _text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise RuntimeError('Falta dependencia pypdf. Instala requirements.') from exc
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or '')
        except Exception:
            continue
    text = '\n'.join(parts)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _pdf_is_docusign_or_form_overlay(pdf_bytes: bytes, text: str = '') -> bool:
    """True si el PDF parece firmado/aplanado por plataforma de firma electronica."""
    return bool(_detect_esign_platform(pdf_bytes, text))


# Plataformas de firma electronica frecuentes en contratos andinos/latam
_ESIGN_MARKERS = (
    # platform, byte needles, text needles (lower)
    ('docusign', (b'DocuSign', b'docusign', b'DOCUSIGN'), ('docusign', 'envelope id')),
    ('zapsign', (b'ZapSign', b'zapsign', b'ZAPSIGN', b'zap-sign'), ('zapsign', 'zap sign')),
    ('adobe_sign', (b'Adobe Sign', b'AdobeSign', b'echosign'), ('adobe sign', 'echosign')),
    ('clicksign', (b'ClickSign', b'clicksign', b'CLICKSIGN'), ('clicksign',)),
    ('hellosign', (b'HelloSign', b'hellosign', b'Dropbox Sign'), ('hellosign', 'dropbox sign')),
)


def _detect_esign_platform(pdf_bytes: bytes, text: str = '') -> str:
    """
    Detecta plataforma de firma electronica por huellas en bytes/texto del PDF.
    Retorna id corto (docusign, zapsign, ...) o '' si no hay senal.
    """
    low = (text or '').lower()
    head = pdf_bytes[:2_500_000] if pdf_bytes else b''
    head_l = head.lower()
    for platform, byte_needles, text_needles in _ESIGN_MARKERS:
        for n in text_needles:
            if n and n in low:
                return platform
        for n in byte_needles:
            if n in head or n.lower() in head_l:
                return platform
    if b'FormXob' in head:
        return 'form_overlay'
    return ''


def _text_usable_for_extraccion(text: str, pdf_bytes: bytes | None = None) -> bool:
    """
    Decide si el camino LLM-texto alcanza.

    - PDF generado por la app (texto embebido normal): basta MIN_TEXT_CHARS.
    - DocuSign / FormXob: exige marcadores de contrato; si no, vision.
    """
    if not text or len(text) < MIN_TEXT_CHARS:
        return False
    if pdf_bytes is not None and _pdf_is_docusign_or_form_overlay(pdf_bytes, text):
        low = text.lower()
        hits = sum(1 for m in TEXT_CONTRACT_MARKERS if m in low)
        return hits >= 2
    return True


def _text_route_reason(text: str, pdf_bytes: bytes) -> str:
    """Motivo legible para logs cuando caemos a vision."""
    if not text:
        return 'sin texto extraible (escaneado o solo imagen)'
    if len(text) < MIN_TEXT_CHARS:
        return f'texto corto ({len(text)} chars)'
    platform = _detect_esign_platform(pdf_bytes, text)
    if platform:
        return (
            f'PDF firmado ({platform}): pypdf solo ve campos '
            f'({len(text)} chars), sin etiquetas de contrato'
        )
    return f'texto no usable ({len(text)} chars)'


def _extract_pdf_text(proyecto: str, adj: str, descripcion_doc: str) -> str:
    return _text_from_pdf_bytes(_load_pdf_bytes(proyecto, adj, descripcion_doc))


OTROS_GATE_KEYWORDS = ('escritura', 'entrega')


def _otros_otrosi_relevante(
    proyecto: str,
    adj: str,
    descripcion_doc: str,
    *,
    keywords: tuple[str, ...] = OTROS_GATE_KEYWORDS,
) -> tuple[bool, str]:
    """
    Gate para Otros / Otrosi (barato, sin LLM).

    1) Si el texto tiene las keywords de fechas -> incluir.
    2) Si no: si hay firma electronica (DocuSign, ZapSign, etc.) -> incluir
       y analizar con vision (asumimos enmienda/otros relevante firmado).
    3) Si no hay keywords ni firma -> omitir.
    """
    try:
        pdf_bytes = _load_pdf_bytes(proyecto, adj, descripcion_doc)
        text = _text_from_pdf_bytes(pdf_bytes)
    except Exception as exc:
        return False, f'no legible: {exc}'[:180]

    low = (text or '').lower()
    if text and len(text) >= MIN_TEXT_CHARS:
        missing = [k for k in keywords if k not in low]
        if not missing:
            return True, 'keywords ok'

    platform = _detect_esign_platform(pdf_bytes, text)
    if platform:
        return True, f'firma:{platform} -> vision'

    if text and len(text) >= MIN_TEXT_CHARS:
        missing = [k for k in keywords if k not in low]
        return False, f'sin palabras ni firma: {", ".join(missing)}'
    return False, 'sin texto util ni firma electronica'


# Compat con llamadas previas
_otros_texto_relevante = _otros_otrosi_relevante


def _filtrar_relevantes_con_gate(proyecto: str, adj: str, candidatos: list) -> tuple[list, list]:
    """Aplica gate keywords/firma. Retorna (elegidos_en_orden, omitidos[(nombre, reason)])."""
    elegidos = []
    omitidos = []
    for c in candidatos:
        ok, reason = _otros_otrosi_relevante(proyecto, adj, c[4].descripcion_doc)
        if ok:
            elegidos.append(c)
        else:
            omitidos.append((c[4].descripcion_doc or c[3], reason))
    return elegidos, omitidos


def _candidate_sort_key(c) -> tuple:
    """fecha_carga ASC, id ASC — para comparar 'posterior a Promesa'."""
    return (c[1] or datetime.date.min, c[2])


def _candidate_docs(proyecto: str, adj: str, docs_desde: datetime.date):
    qs = documentos_contratos.objects.using(proyecto).filter(adj=adj)
    scored = []
    for doc in qs:
        tipo = _tipo_from_descripcion(doc.descripcion_doc or '')
        if not tipo:
            continue
        fecha = _parse_fecha_carga(doc.fecha_carga)
        if fecha and fecha < docs_desde:
            continue
        try:
            tipo_rank = TIPOS_PRIORIDAD.index(tipo)
        except ValueError:
            tipo_rank = 99
        # Orden: tipo prioridad ASC, fecha_carga DESC, id DESC
        scored.append((tipo_rank, fecha or datetime.date.min, doc.id_model, tipo, doc))
    scored.sort(key=lambda x: (x[0], -(x[1].toordinal()), -x[2]))
    return scored


def _forced_doc_candidates(proyecto: str, adj: str, descripcion_doc: str) -> list:
    """Candidato unico forzado (bypass de la seleccion automatica Promesa/Otros)."""
    desc = (descripcion_doc or '').strip()
    if not desc:
        return []
    qs = documentos_contratos.objects.using(proyecto).filter(adj=adj)
    doc = qs.filter(descripcion_doc=desc).first()
    if not doc:
        alt = desc[:-4] if desc.lower().endswith('.pdf') else f'{desc}.pdf'
        doc = qs.filter(descripcion_doc=alt).first()
    if not doc:
        desc_l = desc.lower()
        for row in qs:
            name = (row.descripcion_doc or '').strip()
            if name.lower() == desc_l or name.lower() == f'{desc_l}.pdf':
                doc = row
                break
    if not doc:
        return []
    tipo = _tipo_from_descripcion(doc.descripcion_doc or '') or 'Otros'
    fecha = _parse_fecha_carga(doc.fecha_carga)
    try:
        tipo_rank = TIPOS_PRIORIDAD.index(tipo)
    except ValueError:
        tipo_rank = 99
    return [(tipo_rank, fecha or datetime.date.min, doc.id_model, tipo, doc)]


def _docs_para_analisis(proyecto: str, adj: str, candidates: list) -> tuple[list, str]:
    """
    Regla de seleccion:
    - Si hay Promesa: Promesa mas reciente.
      Otros posteriores y Otrosi: keywords (escritura+entrega) O firma electronica
      (DocuSign/ZapSign/…) → incluir (firma → vision al analizar).
      Luego Escritura.
    - Si no hay Promesa: Otros mas reciente, Otrosi con el mismo gate, Escritura.
    """
    promesas = [c for c in candidates if c[3] == 'Promesa']
    otros = [c for c in candidates if c[3] == 'Otros']
    otrosi = [c for c in candidates if c[3] == 'Otrosi']
    escritura = [c for c in candidates if c[3] == 'Escritura']

    alerta = ''
    out = []
    if promesas:
        promesa = promesas[0]
        out.append(promesa)
        posteriores = [
            c for c in otros
            if _candidate_sort_key(c) > _candidate_sort_key(promesa)
        ]
        elegidos_otros, omitidos_otros = _filtrar_relevantes_con_gate(proyecto, adj, posteriores)
        if elegidos_otros:
            out.append(elegidos_otros[0])
        elif posteriores:
            sample = '; '.join(f'{n} ({r})' for n, r in omitidos_otros[:2])
            alerta = (
                'ALERTA: Otros posterior a Promesa sin keywords ni firma electronica. '
                f'Revisar: {sample}'
            )[:1000]

        elegidos_otrosi, _omitidos_otrosi = _filtrar_relevantes_con_gate(proyecto, adj, otrosi)
        out.extend(elegidos_otrosi)
        out.extend(escritura)
    else:
        if otros:
            elegidos_otros, _ = _filtrar_relevantes_con_gate(proyecto, adj, [otros[0]])
            out.append(elegidos_otros[0] if elegidos_otros else otros[0])
        elegidos_otrosi, _ = _filtrar_relevantes_con_gate(proyecto, adj, otrosi)
        out.extend(elegidos_otrosi)
        out.extend(escritura)
    return out, alerta


DATE_KEYS = ('fecha_contrato', 'fecha_escritura', 'fecha_entrega')
CASCADE_PROVIDER_ORDER = ('openai', 'gemini', 'anthropic')


def _add_months(d: datetime.date, months: int) -> datetime.date:
    """Suma meses de calendario (ajusta dia si no existe en el mes destino)."""
    months = int(months)
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return datetime.date(y, m, day)


def _parse_meses_desde_firma(value) -> Optional[int]:
    if value is None or value == '' or value is False:
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        s = str(value).strip()
        m = re.search(r'(\d{1,3})', s)
        if not m:
            return None
        n = int(m.group(1))
    if 1 <= n <= 120:
        return n
    return None


def _apply_entrega_relativa(payload: dict) -> dict:
    """Si hay meses desde firma y fecha_contrato, calcula fecha_entrega faltante."""
    out = dict(payload)
    meses = out.get('entrega_meses_desde_firma')
    if out.get('fecha_entrega') or not meses or not out.get('fecha_contrato'):
        return out
    try:
        out['fecha_entrega'] = _add_months(out['fecha_contrato'], int(meses))
    except Exception:
        return out
    notas = (out.get('notas') or '').strip()
    hint = f'entrega={meses}m desde firma'
    if hint not in notas:
        out['notas'] = f'{notas}; {hint}'.strip('; ').strip()[:500]
    return out


def _merge_dates(base: dict, new: dict) -> dict:
    out = dict(base)
    for key in DATE_KEYS:
        if new.get(key):
            out[key] = new[key]
    if new.get('entrega_meses_desde_firma') and not out.get('entrega_meses_desde_firma'):
        out['entrega_meses_desde_firma'] = new['entrega_meses_desde_firma']
    return _apply_entrega_relativa(out)


def _merge_fill_gaps(base: dict, new: dict) -> dict:
    """Conserva fechas ya halladas; solo rellena las que faltan."""
    out = dict(base)
    for key in DATE_KEYS:
        if not out.get(key) and new.get(key):
            out[key] = new[key]
    if not out.get('entrega_meses_desde_firma') and new.get('entrega_meses_desde_firma'):
        out['entrega_meses_desde_firma'] = new['entrega_meses_desde_firma']
    return _apply_entrega_relativa(out)


def _has_useful_dates(payload: dict) -> bool:
    if any(payload.get(k) for k in DATE_KEYS):
        return True
    # Meses desde firma cuentan aunque aun no haya fecha_contrato (se combina al merge)
    return bool(payload.get('entrega_meses_desde_firma'))


def _dates_complete(payload: dict) -> bool:
    return all(payload.get(k) for k in DATE_KEYS)


def _active_credential_for_provider(provider: str):
    from andinasoft.models import IntegrationCredential

    return (
        IntegrationCredential.objects.filter(
            provider=(provider or '').strip().lower(),
            activo=True,
        )
        .exclude(api_key='')
        .order_by('id')
        .first()
    )


def list_cascade_credentials() -> list[dict]:
    """Primera credencial activa por proveedor, en orden de cascada."""
    out = []
    for provider in CASCADE_PROVIDER_ORDER:
        cred = _active_credential_for_provider(provider)
        if not cred:
            continue
        model = (cred.default_model or '').strip() or DEFAULT_MODELS.get(provider, '')
        out.append({
            'provider': provider,
            'credential_id': cred.pk,
            'model': model,
            'label': f'{cred.get_provider_display()} ({model})' if model else cred.get_provider_display(),
        })
    return out


def _parse_llm_fechas(data: dict, *, flujo: str) -> dict:
    parsed = {
        'doc_tipo_detectado': (data.get('doc_tipo_detectado') or '').strip().lower(),
        'util': bool(data.get('util')),
        'fecha_contrato': _parse_iso_date(data.get('fecha_contrato')),
        'fecha_escritura': _parse_iso_date(data.get('fecha_escritura')),
        'fecha_entrega': _parse_iso_date(data.get('fecha_entrega')),
        'entrega_meses_desde_firma': _parse_meses_desde_firma(
            data.get('entrega_meses_desde_firma'),
        ),
        'notas': (data.get('notas') or '')[:500],
        'flujo': flujo,
        'raw': data,
    }
    return _apply_entrega_relativa(parsed)


def _analyze_text(text: str, *, config: LlmResolvedConfig | None = None) -> tuple[dict, object]:
    clipped = text[:MAX_TEXT_CHARS]
    user = USER_PROMPT_TEMPLATE.format(text=clipped)
    data, cfg = extract_json(
        system=SYSTEM_PROMPT,
        user=user,
        purpose=PURPOSE_EXTRACCION_FECHAS,
        config=config,
    )
    flujo = 'texto_manual' if config and config.purpose == 'manual_override' else 'texto'
    return _parse_llm_fechas(data, flujo=flujo), cfg


def _analyze_scanned_pdf(
    pdf_bytes: bytes,
    *,
    config: LlmResolvedConfig | None = None,
) -> tuple[dict, object]:
    data, cfg = extract_json_from_pdf(
        system=SYSTEM_PROMPT,
        user=USER_PROMPT_VISION,
        pdf_bytes=pdf_bytes,
        purpose=PURPOSE_EXTRACCION_FECHAS_ESCANEADO,
        config=config,
    )
    flujo = 'vision_manual' if config and config.purpose == 'manual_override' else 'vision'
    return _parse_llm_fechas(data, flujo=flujo), cfg


def _analyze_pdf_document(
    proyecto: str,
    adj: str,
    descripcion_doc: str,
    *,
    llm_config: LlmResolvedConfig | None = None,
    force_direct: bool = False,
) -> tuple[dict, object]:
    """
    Flujo automatico:
    - PDF con texto de contrato usable -> purpose texto
    - Escaneado / formulario DocuSign con texto incompleto -> purpose vision

    Con override manual (force_direct + llm_config):
    - Ignora purpose mappings y manda el PDF directo al LLM elegido (vision/documento).
    """
    pdf_bytes = _load_pdf_bytes(proyecto, adj, descripcion_doc)
    if force_direct and llm_config is not None:
        return _analyze_scanned_pdf(pdf_bytes, config=llm_config)
    text = _text_from_pdf_bytes(pdf_bytes)
    if _text_usable_for_extraccion(text, pdf_bytes=pdf_bytes):
        return _analyze_text(text, config=llm_config)
    logger.info(
        'PDF -> vision proyecto=%s adj=%s doc=%s (%s)',
        proyecto, adj, descripcion_doc, _text_route_reason(text, pdf_bytes),
    )
    return _analyze_scanned_pdf(pdf_bytes, config=llm_config)


def analyze_adj(
    proyecto: str,
    adj: str,
    *,
    docs_desde: Optional[datetime.date] = None,
    force: bool = False,
    resync_promesas: bool = False,
    overwrite_promesas: bool = False,
    dry_run: bool = False,
    credential_id: int | None = None,
    model_override: str = '',
    force_direct: bool | None = None,
    documento_force: str = '',
) -> dict:
    docs_desde = docs_desde or DOCS_DESDE_DEFAULT
    documento_force = (documento_force or '').strip()
    if documento_force:
        # Documento elegido a mano: siempre reprocesar ese PDF
        force = True
    llm_config = None
    use_force_direct = False
    if credential_id:
        llm_config = resolve_credential_config(credential_id, model_override=model_override or '')
        # Override manual del dropdown: PDF directo. Cascada pasa False (texto/vision auto).
        use_force_direct = True if force_direct is None else bool(force_direct)
    force_direct = use_force_direct

    existing = AdjFechaDocumentoExtraccion.objects.filter(proyecto_id=proyecto, adj=adj).first()
    if existing and existing.estado == AdjFechaDocumentoExtraccion.ESTADO_OK and not force:
        return {
            'adj': adj,
            'skipped': True,
            'estado': existing.estado,
            'fecha_contrato': existing.fecha_contrato,
            'fecha_escritura': existing.fecha_escritura,
            'fecha_entrega': existing.fecha_entrega,
            'documento_usado': existing.documento_usado,
            'documento_url': doc_url(proyecto, adj, existing.documento_usado or ''),
            'error_msg': existing.error_msg,
        }

    merged = {
        'fecha_contrato': None,
        'fecha_escritura': None,
        'fecha_entrega': None,
        'entrega_meses_desde_firma': None,
    }
    doc_usado = ''
    tipo_usado = ''
    fecha_carga_doc = ''
    provider = ''
    model = ''
    raw_parts = []
    attempts = 0
    last_error = ''

    if documento_force:
        analisis_docs = _forced_doc_candidates(proyecto, adj, documento_force)
        alerta_otros = ''
    else:
        candidates = _candidate_docs(proyecto, adj, docs_desde)
        analisis_docs, alerta_otros = _docs_para_analisis(proyecto, adj, candidates)
    if not analisis_docs:
        result = {
            'estado': AdjFechaDocumentoExtraccion.ESTADO_SIN_DOCUMENTO,
            'error_msg': (
                f'Documento no encontrado: {documento_force}'
                if documento_force
                else f'Sin documentos Promesa/Otros desde {docs_desde.isoformat()}'
            ),
        }
        if not dry_run:
            obj, _ = AdjFechaDocumentoExtraccion.objects.update_or_create(
                proyecto_id=proyecto,
                adj=adj,
                defaults={
                    'fecha_contrato': None,
                    'fecha_escritura': None,
                    'fecha_entrega': None,
                    'documento_usado': '',
                    'tipo_doc_esperado': '',
                    'fecha_carga_doc': '',
                    'provider': '',
                    'model': '',
                    'raw_json': '',
                    'estado': result['estado'],
                    'error_msg': result['error_msg'][:1000],
                    'synced_to_promesas': False,
                },
            )
            result['id'] = obj.pk
        return {'adj': adj, 'skipped': False, **result, **merged}

    for tipo_rank, fecha_doc, _id, tipo, doc in analisis_docs:
        # Escritura solo si aun falta fecha_escritura
        if tipo == 'Escritura' and merged.get('fecha_escritura'):
            continue
        # Otrosi solo si la promesa/otros base ya aporto algo o aun faltan fechas
        if tipo == 'Otrosi' and not doc_usado and not _has_useful_dates(merged):
            # Si la promesa principal fallo, igual se puede intentar otrosi
            pass
        attempts += 1
        try:
            parsed, cfg = _analyze_pdf_document(
                proyecto, adj, doc.descripcion_doc,
                llm_config=llm_config,
                force_direct=force_direct,
            )
        except FileNotFoundError as exc:
            last_error = f'{doc.descripcion_doc}: {exc}'
            logger.warning('PDF extract fail proyecto=%s adj=%s doc=%s: %s', proyecto, adj, doc.descripcion_doc, exc)
            continue
        except (LlmConfigurationError, LlmRequestError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
            last_error = f'{doc.descripcion_doc}: {exc}'
            logger.warning('LLM fail proyecto=%s adj=%s: %s', proyecto, adj, exc)
            msg = str(exc).lower()
            if isinstance(exc, LlmConfigurationError) and 'escaneado' not in msg and 'vision' not in msg:
                break
            continue

        provider = cfg.provider
        model = cfg.model
        raw_parts.append({
            'documento': doc.descripcion_doc,
            'tipo_esperado': tipo,
            'flujo': parsed.get('flujo') or '',
            'resultado': parsed.get('raw') or {},
        })

        tipo_det = parsed.get('doc_tipo_detectado') or ''
        util = parsed.get('util')
        has_dates = _has_useful_dates(parsed)
        relevant = tipo_det in ('promesa', 'contrato', 'otrosi', 'escritura') or util or has_dates

        def _set_doc_usado():
            nonlocal doc_usado, tipo_usado, fecha_carga_doc
            # Si ya hay Promesa como fuente, no la reemplaza Otros
            if tipo_usado == 'Promesa' and tipo == 'Otros':
                return
            doc_usado = doc.descripcion_doc or doc_usado
            tipo_usado = tipo
            fecha_carga_doc = str(doc.fecha_carga or fecha_carga_doc)

        if not relevant and not has_dates:
            last_error = f'{doc.descripcion_doc}: documento no util ({tipo_det})'
            if tipo == 'Promesa' and not doc_usado:
                _set_doc_usado()
            continue

        merged = _merge_dates(merged, parsed)
        if has_dates or (relevant and tipo in ('Promesa', 'Otrosi', 'Otros')):
            _set_doc_usado()

        if all(merged.get(k) for k in ('fecha_contrato', 'fecha_escritura', 'fecha_entrega')):
            break

    if _has_useful_dates(merged):
        estado = AdjFechaDocumentoExtraccion.ESTADO_OK
        # Alerta informativa (p.ej. Otros posterior escaneado) en OK, no es error de extraccion
        error_msg = alerta_otros or ''
    elif attempts == 0:
        estado = AdjFechaDocumentoExtraccion.ESTADO_SIN_DOCUMENTO
        error_msg = last_error or 'Sin candidatos'
    elif provider == '' and last_error and 'credencial' in last_error.lower():
        estado = AdjFechaDocumentoExtraccion.ESTADO_ERROR
        error_msg = last_error
    elif provider == '' and last_error and 'PDF no encontrado' in last_error:
        # Hubo candidatos en BD pero el archivo no esta en storage
        estado = AdjFechaDocumentoExtraccion.ESTADO_ERROR
        error_msg = last_error
    else:
        estado = AdjFechaDocumentoExtraccion.ESTADO_SIN_FECHAS
        error_msg = last_error or 'No se extrajeron fechas utiles'
        if alerta_otros and not error_msg.startswith('ALERTA:'):
            error_msg = f'{error_msg}. {alerta_otros}'[:1000]

    if alerta_otros:
        raw_parts.insert(0, {'_meta': {'alerta_otros': alerta_otros}})

    synced = False
    if not dry_run:
        obj, _ = AdjFechaDocumentoExtraccion.objects.update_or_create(
            proyecto_id=proyecto,
            adj=adj,
            defaults={
                'fecha_contrato': merged['fecha_contrato'],
                'fecha_escritura': merged['fecha_escritura'],
                'fecha_entrega': merged['fecha_entrega'],
                'documento_usado': (doc_usado or '')[:500],
                'tipo_doc_esperado': (tipo_usado or '')[:64],
                'fecha_carga_doc': (fecha_carga_doc or '')[:64],
                'provider': (provider or '')[:32],
                'model': (model or '')[:128],
                'raw_json': json.dumps(raw_parts, ensure_ascii=False, default=str)[:50000],
                'estado': estado,
                'error_msg': (error_msg or '')[:1000],
            },
        )
        if resync_promesas and estado == AdjFechaDocumentoExtraccion.ESTADO_OK:
            synced = _sync_to_promesas(
                proyecto, adj, merged, overwrite=overwrite_promesas,
            )
            if synced:
                obj.synced_to_promesas = True
                obj.save(update_fields=['synced_to_promesas', 'actualizado'])

    return {
        'adj': adj,
        'skipped': False,
        'estado': estado,
        'fecha_contrato': merged['fecha_contrato'],
        'fecha_escritura': merged['fecha_escritura'],
        'fecha_entrega': merged['fecha_entrega'],
        'documento_usado': doc_usado,
        'documento_url': doc_url(proyecto, adj, doc_usado) if doc_usado else '',
        'tipo_doc_esperado': tipo_usado,
        'provider': provider,
        'model': model,
        'error_msg': error_msg,
        'alerta_otros': alerta_otros,
        'synced_to_promesas': synced,
        'attempts': attempts,
    }


def analyze_adj_cascade_step(
    proyecto: str,
    adj: str,
    *,
    provider: str,
    docs_desde: Optional[datetime.date] = None,
    force: bool = True,
    resync_promesas: bool = False,
    overwrite_promesas: bool = False,
    cascade_reset: bool = False,
    credential_id: int | None = None,
    model_override: str = '',
    documento_force: str = '',
) -> dict:
    """
    Un paso de cascada OpenAI → Gemini → Anthropic.

    - Conserva fechas ya obtenidas (solo rellena huecos).
    - cascade_reset=True limpia la semilla (primer paso).
    - Si ya estan las 3 fechas, no llama al LLM.
    - Guarda tras cada paso (progreso visible / recuperable).
    """
    provider = (provider or '').strip().lower()
    if provider not in CASCADE_PROVIDER_ORDER:
        raise ValueError(f'Proveedor de cascada invalido: {provider}')

    docs_desde = docs_desde or DOCS_DESDE_DEFAULT
    existing = AdjFechaDocumentoExtraccion.objects.filter(proyecto_id=proyecto, adj=adj).first()

    seed = {k: None for k in DATE_KEYS}
    doc_usado = ''
    tipo_usado = ''
    fecha_carga_doc = ''
    prior_chain: list[str] = []
    prior_raw: list = []

    if existing and not cascade_reset:
        seed = {
            'fecha_contrato': existing.fecha_contrato,
            'fecha_escritura': existing.fecha_escritura,
            'fecha_entrega': existing.fecha_entrega,
        }
        doc_usado = existing.documento_usado or ''
        tipo_usado = existing.tipo_doc_esperado or ''
        fecha_carga_doc = existing.fecha_carga_doc or ''
        if existing.model:
            prior_chain = [p for p in str(existing.model).split('>') if p.strip()]
        try:
            loaded = json.loads(existing.raw_json or '[]')
            if isinstance(loaded, list):
                prior_raw = loaded
        except Exception:
            prior_raw = []

    if _dates_complete(seed):
        return {
            'adj': adj,
            'skipped': False,
            'estado': AdjFechaDocumentoExtraccion.ESTADO_OK,
            'fecha_contrato': seed['fecha_contrato'],
            'fecha_escritura': seed['fecha_escritura'],
            'fecha_entrega': seed['fecha_entrega'],
            'documento_usado': doc_usado,
            'documento_url': doc_url(proyecto, adj, doc_usado) if doc_usado else '',
            'tipo_doc_esperado': tipo_usado,
            'provider': 'cascade',
            'model': '>'.join(prior_chain) if prior_chain else (existing.model if existing else ''),
            'error_msg': (existing.error_msg if existing else '') or '',
            'cascade_complete': True,
            'cascade_step': provider,
            'cascade_filled': [],
            'synced_to_promesas': bool(existing.synced_to_promesas) if existing else False,
        }

    cred_id = credential_id
    if not cred_id:
        cred = _active_credential_for_provider(provider)
        if not cred:
            err = f'Cascada: sin credencial activa para {provider}'
            if existing and not cascade_reset:
                # No pisar fechas previas; solo anotar
                return {
                    'adj': adj,
                    'skipped': False,
                    'estado': existing.estado,
                    'fecha_contrato': seed['fecha_contrato'],
                    'fecha_escritura': seed['fecha_escritura'],
                    'fecha_entrega': seed['fecha_entrega'],
                    'documento_usado': doc_usado,
                    'documento_url': doc_url(proyecto, adj, doc_usado) if doc_usado else '',
                    'provider': 'cascade',
                    'model': '>'.join(prior_chain) if prior_chain else '',
                    'error_msg': err,
                    'cascade_complete': False,
                    'cascade_step': provider,
                    'cascade_filled': [],
                    'synced_to_promesas': bool(existing.synced_to_promesas),
                }
            AdjFechaDocumentoExtraccion.objects.update_or_create(
                proyecto_id=proyecto,
                adj=adj,
                defaults={
                    'estado': AdjFechaDocumentoExtraccion.ESTADO_ERROR,
                    'error_msg': err[:1000],
                    'provider': 'cascade',
                    'model': provider,
                },
            )
            return {
                'adj': adj,
                'skipped': False,
                'estado': AdjFechaDocumentoExtraccion.ESTADO_ERROR,
                'fecha_contrato': None,
                'fecha_escritura': None,
                'fecha_entrega': None,
                'documento_usado': '',
                'documento_url': '',
                'error_msg': err,
                'provider': 'cascade',
                'model': provider,
                'cascade_complete': False,
                'cascade_step': provider,
                'cascade_filled': [],
                'synced_to_promesas': False,
            }
        cred_id = cred.pk

    documento_force = (documento_force or '').strip()
    step = analyze_adj(
        proyecto,
        adj,
        docs_desde=docs_desde,
        force=True,
        resync_promesas=False,
        overwrite_promesas=False,
        dry_run=True,
        credential_id=cred_id,
        model_override=model_override or '',
        force_direct=False,
        documento_force=documento_force,
    )

    before = dict(seed)
    merged = _merge_fill_gaps(seed, step)
    filled = [k for k in DATE_KEYS if not before.get(k) and merged.get(k)]

    if documento_force:
        doc_usado = step.get('documento_usado') or documento_force
        tipo_usado = step.get('tipo_doc_esperado') or tipo_usado
    elif step.get('documento_usado') and (
        not doc_usado or (tipo_usado != 'Promesa' and step.get('tipo_doc_esperado') == 'Promesa')
    ):
        doc_usado = step.get('documento_usado') or doc_usado
        tipo_usado = step.get('tipo_doc_esperado') or tipo_usado
        # fecha_carga no viene siempre en step; conservar previa

    step_provider = step.get('provider') or provider
    step_model = step.get('model') or ''
    chain_token = step_provider
    if chain_token not in prior_chain:
        prior_chain.append(chain_token)
    model_chain = '>'.join(prior_chain)

    step_meta = {
        '_cascade_step': {
            'provider': step_provider,
            'model': step_model,
            'estado': step.get('estado'),
            'filled': filled,
            'error_msg': step.get('error_msg') or '',
        }
    }
    raw_parts = [p for p in prior_raw if not (isinstance(p, dict) and '_cascade_step' in p)]
    raw_parts.insert(0, step_meta)

    if _has_useful_dates(merged):
        estado = AdjFechaDocumentoExtraccion.ESTADO_OK
    elif step.get('estado') == AdjFechaDocumentoExtraccion.ESTADO_SIN_DOCUMENTO and not _has_useful_dates(before):
        estado = AdjFechaDocumentoExtraccion.ESTADO_SIN_DOCUMENTO
    elif step.get('estado') == AdjFechaDocumentoExtraccion.ESTADO_ERROR and not _has_useful_dates(merged):
        estado = AdjFechaDocumentoExtraccion.ESTADO_ERROR
    else:
        estado = AdjFechaDocumentoExtraccion.ESTADO_SIN_FECHAS

    complete = _dates_complete(merged)
    missing = [k for k in DATE_KEYS if not merged.get(k)]
    if complete:
        note = f'Cascada completa ({model_chain})'
    elif filled:
        note = f'Cascada {step_provider}: +{", ".join(filled)}. Falta: {", ".join(missing)}'
    else:
        err_step = (step.get('error_msg') or step.get('estado') or 'sin fechas nuevas')[:200]
        note = f'Cascada {step_provider}: sin fechas nuevas ({err_step}). Falta: {", ".join(missing)}'

    synced = False
    obj, _ = AdjFechaDocumentoExtraccion.objects.update_or_create(
        proyecto_id=proyecto,
        adj=adj,
        defaults={
            'fecha_contrato': merged['fecha_contrato'],
            'fecha_escritura': merged['fecha_escritura'],
            'fecha_entrega': merged['fecha_entrega'],
            'documento_usado': (doc_usado or '')[:500],
            'tipo_doc_esperado': (tipo_usado or '')[:64],
            'fecha_carga_doc': (fecha_carga_doc or '')[:64],
            'provider': 'cascade',
            'model': model_chain[:128],
            'raw_json': json.dumps(raw_parts, ensure_ascii=False, default=str)[:50000],
            'estado': estado,
            'error_msg': note[:1000],
        },
    )
    if resync_promesas and estado == AdjFechaDocumentoExtraccion.ESTADO_OK:
        synced = _sync_to_promesas(
            proyecto, adj, merged, overwrite=overwrite_promesas,
        )
        if synced:
            obj.synced_to_promesas = True
            obj.save(update_fields=['synced_to_promesas', 'actualizado'])

    return {
        'adj': adj,
        'skipped': False,
        'estado': estado,
        'fecha_contrato': merged['fecha_contrato'],
        'fecha_escritura': merged['fecha_escritura'],
        'fecha_entrega': merged['fecha_entrega'],
        'documento_usado': doc_usado,
        'documento_url': doc_url(proyecto, adj, doc_usado) if doc_usado else '',
        'tipo_doc_esperado': tipo_usado,
        'provider': 'cascade',
        'model': model_chain,
        'error_msg': note,
        'cascade_complete': complete,
        'cascade_step': provider,
        'cascade_filled': filled,
        'synced_to_promesas': synced,
        'attempts': step.get('attempts') or 0,
    }


def _sync_to_promesas(proyecto: str, adj: str, dates: dict, *, overwrite: bool = False) -> bool:
    qs = Promesas.objects.using(proyecto).filter(idadjudicacion=adj)
    if not qs.exists():
        return False
    p = qs.get()
    changed = False
    mapping = (
        ('fecha_contrato', 'fechapromesa'),
        ('fecha_entrega', 'fechaentrega'),
        ('fecha_escritura', 'fechaescritura'),
    )
    for src, dest in mapping:
        val = dates.get(src)
        if not val:
            continue
        current = getattr(p, dest, None)
        if current and not overwrite:
            continue
        if current != val:
            setattr(p, dest, val)
            changed = True
    if changed:
        p.save()
    return changed


def list_adj_candidates(
    proyecto: str,
    *,
    inmueble_contains: str = '',
    adj_query: str = '',
    titular_query: str = '',
    estado_extraccion: str = '',
    solo_pendientes: bool = False,
    adj_ids: Optional[Iterable[str]] = None,
) -> list[dict]:
    """Lista ADJs activos enriquecidos con estado de extraccion y fechas DB."""
    qs = Adjudicacion.objects.using(proyecto).filter(estado__in=('Aprobado', 'Pagado'))
    if adj_ids is not None:
        ids = [str(a).strip() for a in adj_ids if str(a).strip()]
        qs = qs.filter(idadjudicacion__in=ids)
    if adj_query:
        qs = qs.filter(idadjudicacion__icontains=adj_query.strip())
    if inmueble_contains:
        qs = qs.filter(idinmueble__icontains=inmueble_contains.strip())

    adjs = list(qs.order_by('idadjudicacion'))
    if not adjs:
        return []

    adj_id_list = [a.idadjudicacion for a in adjs]
    promesas = {
        p.idadjudicacion: p
        for p in Promesas.objects.using(proyecto).filter(idadjudicacion__in=adj_id_list)
    }
    extracciones = {
        e.adj: e
        for e in AdjFechaDocumentoExtraccion.objects.filter(
            proyecto_id=proyecto, adj__in=adj_id_list,
        )
    }

    tercero_ids = set()
    for a in adjs:
        if a.idtercero1:
            tercero_ids.add(str(a.idtercero1).strip())
    clientes_map = {}
    if tercero_ids:
        for c in clientes.objects.filter(idTercero__in=list(tercero_ids)):
            clientes_map[str(c.idTercero).strip()] = c

    rows = []
    # Una sola instancia de storage para firmar URLs del listado (sin HEAD MinIO).
    _url_storage = None
    try:
        from andina.storage import media_service as _ms
        if _ms._read_from_s3():
            from andina.storage_backends import PrivateMediaStorage
            _url_storage = PrivateMediaStorage()
        else:
            from andina.storage_backends import LocalMediaStorage
            _url_storage = LocalMediaStorage()
    except Exception:
        _url_storage = None

    for a in adjs:
        tid = str(a.idtercero1).strip() if a.idtercero1 else ''
        titular = ''
        if tid and tid in clientes_map:
            titular = clientes_map[tid].nombrecompleto or ''
        if titular_query:
            q = titular_query.strip().lower()
            if q not in (titular or '').lower() and q not in (a.idadjudicacion or '').lower():
                continue
        p = promesas.get(a.idadjudicacion)
        e = extracciones.get(a.idadjudicacion)
        estado_ext = e.estado if e else AdjFechaDocumentoExtraccion.ESTADO_PENDIENTE
        if solo_pendientes and estado_ext == AdjFechaDocumentoExtraccion.ESTADO_OK:
            continue
        if estado_extraccion and estado_ext != estado_extraccion:
            continue
        doc_name = e.documento_usado if e else ''
        documento_url = ''
        if doc_name:
            key = _doc_storage_key(proyecto, a.idadjudicacion, doc_name)
            try:
                documento_url = (
                    _url_storage.url(key) if _url_storage is not None
                    else doc_url(proyecto, a.idadjudicacion, doc_name, check_exists=False)
                )
            except Exception:
                documento_url = doc_url(
                    proyecto, a.idadjudicacion, doc_name, check_exists=False,
                )
        rows.append({
            'adj': a.idadjudicacion,
            'inmueble': (a.idinmueble or '').strip(),
            'titular': titular,
            'estado_adj': a.estado or '',
            'db_fecha_contrato': p.fechapromesa if p else a.fechacontrato,
            'db_fecha_entrega': p.fechaentrega if p else None,
            'db_fecha_escritura': p.fechaescritura if p else None,
            'ext_fecha_contrato': e.fecha_contrato if e else None,
            'ext_fecha_escritura': e.fecha_escritura if e else None,
            'ext_fecha_entrega': e.fecha_entrega if e else None,
            'estado_extraccion': estado_ext,
            'documento_usado': doc_name,
            'documento_url': documento_url,
            'error_msg': e.error_msg if e else '',
            'provider': e.provider if e else '',
            'model': e.model if e else '',
            'actualizado': e.actualizado if e else None,
        })
    return rows


def format_date_dmy(value) -> str:
    """Fecha para UI/Excel/API: dd/mm/YYYY."""
    if value is None or value == '':
        return ''
    if isinstance(value, datetime.datetime):
        return value.strftime('%d/%m/%Y')
    if isinstance(value, datetime.date):
        return value.strftime('%d/%m/%Y')
    s = str(value).strip()
    if not s:
        return ''
    # ISO u otros -> dd/mm/YYYY si se puede parsear
    parsed = _parse_iso_date(s) or _parse_fecha_carga(s)
    if parsed:
        return parsed.strftime('%d/%m/%Y')
    return s


def export_excel(proyecto: str, rows: list[dict], filename: Optional[str] = None) -> str:
    from openpyxl import Workbook
    from django.conf import settings
    import os

    wb = Workbook()
    ws = wb.active
    ws.title = 'Fechas documentos'
    headers = [
        'ADJ', 'Inmueble', 'Titular', 'Estado adj',
        'Contrato', 'Entrega', 'Escritura',
        'PDF contrato', 'PDF entrega', 'PDF escritura',
        'Estado extraccion', 'Documento', 'Proveedor', 'Error',
    ]
    ws.append(headers)
    for r in rows:
        ws.append([
            r.get('adj'),
            r.get('inmueble'),
            r.get('titular'),
            r.get('estado_adj'),
            format_date_dmy(r.get('db_fecha_contrato')),
            format_date_dmy(r.get('db_fecha_entrega')),
            format_date_dmy(r.get('db_fecha_escritura')),
            format_date_dmy(r.get('ext_fecha_contrato')),
            format_date_dmy(r.get('ext_fecha_entrega')),
            format_date_dmy(r.get('ext_fecha_escritura')),
            r.get('estado_extraccion'),
            r.get('documento_usado'),
            r.get('provider'),
            r.get('error_msg'),
        ])
    name = filename or f'fechas_documentos_{proyecto}_{datetime.date.today().isoformat()}.xlsx'
    name = name.replace('/', '_').replace('\\', '_')
    ruta = os.path.join(settings.DIR_EXPORT, name)
    os.makedirs(os.path.dirname(ruta) or '.', exist_ok=True)
    wb.save(ruta)
    return ruta


_DATE_KEYS = (
    'fecha_contrato', 'fecha_escritura', 'fecha_entrega',
    'db_fecha_contrato', 'db_fecha_entrega', 'db_fecha_escritura',
    'ext_fecha_contrato', 'ext_fecha_entrega', 'ext_fecha_escritura',
)


def serialize_row_dates(row: dict) -> dict:
    out = dict(row)
    for k, v in list(out.items()):
        if k in _DATE_KEYS or isinstance(v, (datetime.date, datetime.datetime)):
            if isinstance(v, datetime.datetime) and k not in _DATE_KEYS:
                out[k] = v.strftime('%d/%m/%Y %H:%M')
            else:
                out[k] = format_date_dmy(v)
    return out
