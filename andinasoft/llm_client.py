"""Cliente LLM unificado (OpenAI / Gemini / Anthropic) por proposito de integracion."""
from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass

import httpx
from django.conf import settings

from andinasoft.llm_models_catalog import DEFAULT_MODELS, DEFAULT_VISION_MODELS

logger = logging.getLogger(__name__)


class LlmConfigurationError(Exception):
    pass


class LlmRequestError(Exception):
    pass


@dataclass
class LlmResolvedConfig:
    provider: str
    api_key: str
    model: str
    credential_id: int | None = None
    purpose: str = ''


PURPOSE_EXTRACCION_FECHAS = 'extraccion_fechas_contrato'
PURPOSE_EXTRACCION_FECHAS_ESCANEADO = 'extraccion_fechas_escaneado'

MAX_VISION_PAGES = 8
MAX_PDF_BYTES = 18 * 1024 * 1024


def resolve_credential_config(
    credential_id: int,
    *,
    model_override: str = '',
) -> LlmResolvedConfig:
    """Resuelve una credencial guardada (override manual de modelo)."""
    from andinasoft.models import IntegrationCredential

    try:
        cred = IntegrationCredential.objects.get(pk=int(credential_id))
    except (IntegrationCredential.DoesNotExist, TypeError, ValueError) as exc:
        raise LlmConfigurationError('Credencial no encontrada.') from exc
    if not cred.activo:
        raise LlmConfigurationError(f'La credencial "{cred}" esta inactiva.')
    key = (cred.api_key or '').strip()
    if not key:
        raise LlmConfigurationError(f'La credencial "{cred}" no tiene API key.')
    model = (model_override or '').strip() or (cred.default_model or '').strip()
    if not model:
        model = DEFAULT_MODELS.get(cred.provider) or DEFAULT_VISION_MODELS.get(
            cred.provider, 'gpt-4o-mini'
        )
    return LlmResolvedConfig(
        provider=cred.provider,
        api_key=key,
        model=model,
        credential_id=cred.pk,
        purpose='manual_override',
    )


def list_saved_model_options() -> list[dict]:
    """Opciones para el dropdown de override (credenciales activas)."""
    from andinasoft.models import IntegrationCredential

    out = []
    for cred in IntegrationCredential.objects.filter(activo=True).order_by('provider', 'label', 'id'):
        model = (cred.default_model or '').strip() or DEFAULT_MODELS.get(cred.provider, '')
        provider_label = cred.get_provider_display()
        label_bits = [provider_label]
        custom = (cred.label or '').strip()
        if custom and custom.lower() != provider_label.lower():
            label_bits.append(custom)
        if model:
            label_bits.append(model)
        out.append({
            'credential_id': cred.pk,
            'provider': cred.provider,
            'model': model,
            'label': ' — '.join(label_bits),
        })
    return out


def resolve_purpose_config(purpose: str = PURPOSE_EXTRACCION_FECHAS) -> LlmResolvedConfig:
    from andinasoft.models import IntegrationCredential, IntegrationPurposeMapping

    mapping = (
        IntegrationPurposeMapping.objects.select_related('credential')
        .filter(purpose=purpose)
        .first()
    )
    if mapping and mapping.credential and mapping.credential.activo:
        cred = mapping.credential
        model = mapping.resolved_model()
        if purpose == PURPOSE_EXTRACCION_FECHAS_ESCANEADO and not (mapping.model_override or '').strip():
            # Preferir default vision del proveedor si no hay override explicito
            # y el default de la credencial es generico de texto
            vision_default = DEFAULT_VISION_MODELS.get(cred.provider)
            if vision_default and not (cred.default_model or '').strip():
                model = vision_default
        key = (cred.api_key or '').strip()
        if not key:
            raise LlmConfigurationError(
                f'La credencial "{cred}" no tiene API key configurada.'
            )
        return LlmResolvedConfig(
            provider=cred.provider,
            api_key=key,
            model=model,
            credential_id=cred.pk,
            purpose=purpose,
        )

    # Fallback vision: primera credencial Gemini activa
    if purpose == PURPOSE_EXTRACCION_FECHAS_ESCANEADO:
        gemini = (
            IntegrationCredential.objects.filter(
                provider=IntegrationCredential.PROVIDER_GEMINI,
                activo=True,
            )
            .exclude(api_key='')
            .first()
        )
        if gemini:
            model = (gemini.default_model or '').strip() or DEFAULT_VISION_MODELS['gemini']
            return LlmResolvedConfig(
                provider=gemini.provider,
                api_key=gemini.api_key.strip(),
                model=model,
                credential_id=gemini.pk,
                purpose=purpose,
            )

    env_key = (getattr(settings, 'OPENAI_API_KEY', None) or '').strip()
    if env_key and purpose == PURPOSE_EXTRACCION_FECHAS:
        return LlmResolvedConfig(
            provider=IntegrationCredential.PROVIDER_OPENAI,
            api_key=env_key,
            model=DEFAULT_MODELS['openai'],
            credential_id=None,
            purpose=purpose,
        )

    if purpose == PURPOSE_EXTRACCION_FECHAS_ESCANEADO:
        raise LlmConfigurationError(
            'No hay credencial para PDF escaneado (vision). '
            'Asigna Gemini (recomendado: gemini-2.0-flash) en Integraciones LLM.'
        )
    raise LlmConfigurationError(
        'No hay credencial LLM activa para este uso. '
        'Configurala en Integraciones (API keys).'
    )


def _extract_json_object(text: str) -> dict:
    if not text:
        raise LlmRequestError('Respuesta vacia del modelo.')
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[\s\S]*\}', text)
    if not match:
        raise LlmRequestError('No se encontro JSON en la respuesta del modelo.')
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise LlmRequestError('El JSON de respuesta no es un objeto.')
    return data


def _openai_chat(api_key: str, model: str, system: str, user: str, timeout: float = 90.0) -> str:
    url = 'https://api.openai.com/v1/chat/completions'
    payload = {
        'model': model,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LlmRequestError(f'Error de red OpenAI: {exc}') from exc
    if resp.status_code >= 400:
        raise LlmRequestError(f'OpenAI HTTP {resp.status_code}: {resp.text[:500]}')
    body = resp.json()
    try:
        return body['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRequestError(f'Respuesta OpenAI inesperada: {body!r}') from exc


def _openai_vision(
    api_key: str,
    model: str,
    system: str,
    user: str,
    images_png: list[bytes],
    timeout: float = 120.0,
) -> str:
    if not images_png:
        raise LlmRequestError('No hay imagenes para enviar a OpenAI vision.')
    content = [{'type': 'text', 'text': user}]
    for img in images_png[:MAX_VISION_PAGES]:
        b64 = base64.b64encode(img).decode('ascii')
        content.append({
            'type': 'image_url',
            'image_url': {'url': f'data:image/png;base64,{b64}'},
        })
    url = 'https://api.openai.com/v1/chat/completions'
    payload = {
        'model': model,
        'temperature': 0,
        'response_format': {'type': 'json_object'},
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': content},
        ],
    }
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LlmRequestError(f'Error de red OpenAI vision: {exc}') from exc
    if resp.status_code >= 400:
        raise LlmRequestError(f'OpenAI vision HTTP {resp.status_code}: {resp.text[:500]}')
    body = resp.json()
    try:
        return body['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRequestError(f'Respuesta OpenAI vision inesperada: {body!r}') from exc


def _gemini_generate(api_key: str, model: str, system: str, user: str, timeout: float = 90.0) -> str:
    model_id = model.replace('models/', '') if model.startswith('models/') else model
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model_id}:generateContent?key={api_key}'
    )
    payload = {
        'system_instruction': {'parts': [{'text': system}]},
        'contents': [{'role': 'user', 'parts': [{'text': user}]}],
        'generationConfig': {
            'temperature': 0,
            'responseMimeType': 'application/json',
        },
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise LlmRequestError(f'Error de red Gemini: {exc}') from exc
    if resp.status_code >= 400:
        raise LlmRequestError(f'Gemini HTTP {resp.status_code}: {resp.text[:500]}')
    body = resp.json()
    try:
        parts = body['candidates'][0]['content']['parts']
        return ''.join(p.get('text', '') for p in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRequestError(f'Respuesta Gemini inesperada: {body!r}') from exc


def _gemini_vision_pdf(
    api_key: str,
    model: str,
    system: str,
    user: str,
    pdf_bytes: bytes,
    timeout: float = 120.0,
) -> str:
    if not pdf_bytes:
        raise LlmRequestError('PDF vacio para Gemini vision.')
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise LlmRequestError(
            f'PDF demasiado grande para vision ({len(pdf_bytes)} bytes; max {MAX_PDF_BYTES}).'
        )
    model_id = model.replace('models/', '') if model.startswith('models/') else model
    url = (
        f'https://generativelanguage.googleapis.com/v1beta/models/'
        f'{model_id}:generateContent?key={api_key}'
    )
    payload = {
        'system_instruction': {'parts': [{'text': system}]},
        'contents': [{
            'role': 'user',
            'parts': [
                {'text': user},
                {
                    'inline_data': {
                        'mime_type': 'application/pdf',
                        'data': base64.b64encode(pdf_bytes).decode('ascii'),
                    }
                },
            ],
        }],
        'generationConfig': {
            'temperature': 0,
            'responseMimeType': 'application/json',
        },
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise LlmRequestError(f'Error de red Gemini vision: {exc}') from exc
    if resp.status_code >= 400:
        raise LlmRequestError(f'Gemini vision HTTP {resp.status_code}: {resp.text[:500]}')
    body = resp.json()
    try:
        parts = body['candidates'][0]['content']['parts']
        return ''.join(p.get('text', '') for p in parts)
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRequestError(f'Respuesta Gemini vision inesperada: {body!r}') from exc


def _anthropic_messages(api_key: str, model: str, system: str, user: str, timeout: float = 90.0) -> str:
    # No enviar temperature: en Opus 4.7+ / Sonnet 5+ un valor distinto al default da 400.
    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': model,
        'max_tokens': 4096,
        'system': (
            system
            + '\n\nResponde solo con un objeto JSON valido, sin markdown ni texto adicional.'
        ),
        'messages': [
            {'role': 'user', 'content': user},
        ],
    }
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LlmRequestError(f'Error de red Anthropic: {exc}') from exc
    if resp.status_code >= 400:
        raise LlmRequestError(f'Anthropic HTTP {resp.status_code}: {resp.text[:500]}')
    body = resp.json()
    try:
        parts = body.get('content') or []
        texts = [p.get('text', '') for p in parts if isinstance(p, dict) and p.get('type') == 'text']
        if not texts and parts and isinstance(parts[0], dict):
            texts = [parts[0].get('text', '')]
        return ''.join(texts)
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRequestError(f'Respuesta Anthropic inesperada: {body!r}') from exc


def _anthropic_vision_pdf(
    api_key: str,
    model: str,
    system: str,
    user: str,
    pdf_bytes: bytes,
    timeout: float = 120.0,
) -> str:
    if not pdf_bytes:
        raise LlmRequestError('PDF vacio para Anthropic vision.')
    if len(pdf_bytes) > MAX_PDF_BYTES:
        raise LlmRequestError(
            f'PDF demasiado grande para vision ({len(pdf_bytes)} bytes; max {MAX_PDF_BYTES}).'
        )
    url = 'https://api.anthropic.com/v1/messages'
    payload = {
        'model': model,
        'max_tokens': 4096,
        'system': (
            system
            + '\n\nResponde solo con un objeto JSON valido, sin markdown ni texto adicional.'
        ),
        'messages': [{
            'role': 'user',
            'content': [
                {
                    'type': 'document',
                    'source': {
                        'type': 'base64',
                        'media_type': 'application/pdf',
                        'data': base64.b64encode(pdf_bytes).decode('ascii'),
                    },
                },
                {'type': 'text', 'text': user},
            ],
        }],
    }
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    }
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LlmRequestError(f'Error de red Anthropic vision: {exc}') from exc
    if resp.status_code >= 400:
        raise LlmRequestError(f'Anthropic vision HTTP {resp.status_code}: {resp.text[:500]}')
    body = resp.json()
    try:
        parts = body.get('content') or []
        texts = [p.get('text', '') for p in parts if isinstance(p, dict) and p.get('type') == 'text']
        return ''.join(texts)
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmRequestError(f'Respuesta Anthropic vision inesperada: {body!r}') from exc


def pdf_to_png_pages(pdf_bytes: bytes, *, max_pages: int = MAX_VISION_PAGES) -> list[bytes]:
    """Rasteriza paginas del PDF a PNG (OpenAI vision)."""
    try:
        from pdf2image import convert_from_bytes
    except ImportError as exc:
        raise LlmRequestError(
            'Falta pdf2image para vision OpenAI. Instala requirements.'
        ) from exc
    try:
        images = convert_from_bytes(
            pdf_bytes,
            dpi=140,
            first_page=1,
            last_page=max_pages,
            fmt='png',
        )
    except Exception as exc:
        raise LlmRequestError(f'No se pudo rasterizar el PDF: {exc}') from exc
    out = []
    for img in images:
        buf = __import__('io').BytesIO()
        img.save(buf, format='PNG', optimize=True)
        out.append(buf.getvalue())
    return out


def extract_json(
    *,
    system: str,
    user: str,
    purpose: str = PURPOSE_EXTRACCION_FECHAS,
    config: LlmResolvedConfig | None = None,
) -> tuple[dict, LlmResolvedConfig]:
    """Llama al LLM de texto y devuelve (dict_json, config_usada)."""
    cfg = config or resolve_purpose_config(purpose)
    provider = (cfg.provider or '').lower().strip()
    if provider == 'openai':
        content = _openai_chat(cfg.api_key, cfg.model, system, user)
    elif provider == 'gemini':
        content = _gemini_generate(cfg.api_key, cfg.model, system, user)
    elif provider == 'anthropic':
        content = _anthropic_messages(cfg.api_key, cfg.model, system, user)
    else:
        raise LlmConfigurationError(f'Proveedor no soportado: {cfg.provider}')
    return _extract_json_object(content), cfg


def extract_json_from_pdf(
    *,
    system: str,
    user: str,
    pdf_bytes: bytes,
    purpose: str = PURPOSE_EXTRACCION_FECHAS_ESCANEADO,
    config: LlmResolvedConfig | None = None,
) -> tuple[dict, LlmResolvedConfig]:
    """
    Flujo vision para PDF escaneado.
    Gemini/Anthropic: PDF nativo. OpenAI: paginas PNG.
    """
    cfg = config or resolve_purpose_config(purpose)
    provider = (cfg.provider or '').lower().strip()
    if provider == 'gemini':
        content = _gemini_vision_pdf(cfg.api_key, cfg.model, system, user, pdf_bytes)
    elif provider == 'anthropic':
        content = _anthropic_vision_pdf(cfg.api_key, cfg.model, system, user, pdf_bytes)
    elif provider == 'openai':
        images = pdf_to_png_pages(pdf_bytes)
        content = _openai_vision(cfg.api_key, cfg.model, system, user, images)
    else:
        raise LlmConfigurationError(f'Proveedor no soportado para vision: {cfg.provider}')
    return _extract_json_object(content), cfg
