"""
Catalogo de modelos LLM por proveedor (IDs de API).

Fuentes oficiales (revisadas Ago 2026):
- OpenAI: https://developers.openai.com/api/docs/models/all
- Gemini: https://ai.google.dev/gemini-api/docs/models
         https://firebase.google.com/docs/ai-logic/models
- Anthropic: https://platform.claude.com/docs/en/about-claude/models/overview
             https://platform.claude.com/docs/en/about-claude/model-deprecations

Cada entrada: (api_id, etiqueta). Agrupados por categoria para <optgroup>.
"""

# OpenAI — listado completo de "All models"
OPENAI_MODELS = [
    (
        'Frontier / GPT-5.6',
        [
            ('gpt-5.6-sol', 'gpt-5.6-sol — Frontier (flagship)'),
            ('gpt-5.6', 'gpt-5.6 — alias → sol'),
            ('gpt-5.6-terra', 'gpt-5.6-terra — balance costo/inteligencia'),
            ('gpt-5.6-luna', 'gpt-5.6-luna — alto volumen / costo'),
            ('gpt-5.6-cyber', 'gpt-5.6-cyber — ciberseguridad (Daybreak)'),
            ('daybreak-red-latest', 'daybreak-red-latest — alias ciber'),
            ('daybreak-blue-latest', 'daybreak-blue-latest — alias defensivo'),
        ],
    ),
    (
        'GPT-5.x',
        [
            ('gpt-5.5', 'gpt-5.5'),
            ('gpt-5.5-pro', 'gpt-5.5-pro'),
            ('gpt-5.4', 'gpt-5.4'),
            ('gpt-5.4-pro', 'gpt-5.4-pro'),
            ('gpt-5.4-mini', 'gpt-5.4-mini'),
            ('gpt-5.4-nano', 'gpt-5.4-nano'),
            ('gpt-5.3-codex', 'gpt-5.3-codex'),
            ('gpt-5.2', 'gpt-5.2'),
            ('gpt-5.2-pro', 'gpt-5.2-pro'),
            ('gpt-5.2-codex', 'gpt-5.2-codex (deprecated)'),
            ('gpt-5.1', 'gpt-5.1'),
            ('gpt-5.1-codex', 'gpt-5.1-codex (deprecated)'),
            ('gpt-5.1-codex-max', 'gpt-5.1-codex-max (deprecated)'),
            ('gpt-5.1-codex-mini', 'gpt-5.1-codex-mini (deprecated)'),
            ('gpt-5.1-chat-latest', 'gpt-5.1-chat-latest (deprecated)'),
            ('gpt-5', 'gpt-5'),
            ('gpt-5-mini', 'gpt-5-mini'),
            ('gpt-5-nano', 'gpt-5-nano'),
            ('gpt-5-pro', 'gpt-5-pro'),
            ('gpt-5-codex', 'gpt-5-codex (deprecated)'),
            ('gpt-5-chat-latest', 'gpt-5-chat-latest (deprecated)'),
            ('gpt-5.3-chat-latest', 'gpt-5.3-chat-latest (deprecated)'),
            ('gpt-5.2-chat-latest', 'gpt-5.2-chat-latest (deprecated)'),
        ],
    ),
    (
        'o-series / reasoning',
        [
            ('o3-pro', 'o3-pro'),
            ('o3', 'o3'),
            ('o3-mini', 'o3-mini (deprecated)'),
            ('o3-deep-research', 'o3-deep-research (deprecated)'),
            ('o4-mini', 'o4-mini (deprecated)'),
            ('o4-mini-deep-research', 'o4-mini-deep-research (deprecated)'),
            ('o1-pro', 'o1-pro (deprecated)'),
            ('o1', 'o1 (deprecated)'),
            ('o1-mini', 'o1-mini (deprecated)'),
            ('o1-preview', 'o1-preview (deprecated)'),
            ('codex-mini-latest', 'codex-mini-latest (deprecated)'),
        ],
    ),
    (
        'GPT-4.x / 4o / 3.5',
        [
            ('gpt-4.1', 'gpt-4.1'),
            ('gpt-4.1-mini', 'gpt-4.1-mini'),
            ('gpt-4.1-nano', 'gpt-4.1-nano (deprecated)'),
            ('gpt-4o', 'gpt-4o'),
            ('gpt-4o-mini', 'gpt-4o-mini'),
            ('gpt-4o-search-preview', 'gpt-4o-search-preview (deprecated)'),
            ('gpt-4o-mini-search-preview', 'gpt-4o-mini-search-preview (deprecated)'),
            ('chatgpt-4o-latest', 'chatgpt-4o-latest (deprecated)'),
            ('gpt-4.5-preview', 'gpt-4.5-preview (deprecated)'),
            ('gpt-4-turbo', 'gpt-4-turbo (deprecated)'),
            ('gpt-4-turbo-preview', 'gpt-4-turbo-preview (deprecated)'),
            ('gpt-4', 'gpt-4 (deprecated)'),
            ('gpt-3.5-turbo', 'gpt-3.5-turbo (deprecated)'),
        ],
    ),
    (
        'Realtime / audio / TTS / STT',
        [
            ('gpt-realtime-2.1', 'gpt-realtime-2.1'),
            ('gpt-realtime-2.1-mini', 'gpt-realtime-2.1-mini'),
            ('gpt-realtime-2', 'gpt-realtime-2'),
            ('gpt-realtime-1.5', 'gpt-realtime-1.5'),
            ('gpt-realtime', 'gpt-realtime (deprecated)'),
            ('gpt-realtime-mini', 'gpt-realtime-mini (deprecated)'),
            ('gpt-realtime-translate', 'gpt-realtime-translate'),
            ('gpt-audio-1.5', 'gpt-audio-1.5'),
            ('gpt-audio', 'gpt-audio (deprecated)'),
            ('gpt-audio-mini', 'gpt-audio-mini (deprecated)'),
            ('gpt-4o-audio-preview', 'gpt-4o-audio-preview (deprecated)'),
            ('gpt-4o-mini-audio-preview', 'gpt-4o-mini-audio-preview (deprecated)'),
            ('gpt-4o-realtime-preview', 'gpt-4o-realtime-preview (deprecated)'),
            ('gpt-4o-mini-realtime-preview', 'gpt-4o-mini-realtime-preview (deprecated)'),
            ('gpt-transcribe', 'gpt-transcribe'),
            ('gpt-live-transcribe', 'gpt-live-transcribe'),
            ('gpt-realtime-whisper', 'gpt-realtime-whisper'),
            ('gpt-4o-transcribe', 'gpt-4o-transcribe'),
            ('gpt-4o-mini-transcribe', 'gpt-4o-mini-transcribe'),
            ('gpt-4o-transcribe-diarize', 'gpt-4o-transcribe-diarize'),
            ('whisper-1', 'whisper-1'),
            ('tts-1', 'tts-1'),
            ('tts-1-hd', 'tts-1-hd'),
            ('gpt-4o-mini-tts', 'gpt-4o-mini-tts'),
        ],
    ),
    (
        'Imagen / video / embeddings / otros',
        [
            ('gpt-image-2', 'gpt-image-2'),
            ('gpt-image-1.5', 'gpt-image-1.5 (deprecated)'),
            ('gpt-image-1', 'gpt-image-1 (deprecated)'),
            ('gpt-image-1-mini', 'gpt-image-1-mini (deprecated)'),
            ('chatgpt-image-latest', 'chatgpt-image-latest (deprecated)'),
            ('sora-2', 'sora-2 (deprecated)'),
            ('sora-2-pro', 'sora-2-pro (deprecated)'),
            ('text-embedding-3-large', 'text-embedding-3-large'),
            ('text-embedding-3-small', 'text-embedding-3-small'),
            ('text-embedding-ada-002', 'text-embedding-ada-002'),
            ('omni-moderation-latest', 'omni-moderation-latest'),
            ('text-moderation-latest', 'text-moderation-latest (deprecated)'),
            ('text-moderation-stable', 'text-moderation-stable (deprecated)'),
            ('computer-use-preview', 'computer-use-preview (deprecated)'),
            ('gpt-oss-120b', 'gpt-oss-120b (open-weight)'),
            ('gpt-oss-20b', 'gpt-oss-20b (open-weight)'),
            ('babbage-002', 'babbage-002 (deprecated)'),
            ('davinci-002', 'davinci-002 (deprecated)'),
            ('chat-latest', 'chat-latest (ChatGPT, no recomendado API)'),
        ],
    ),
]

# Gemini — generateContent + imagen / live / embeddings (docs Google + Firebase AI Logic)
GEMINI_MODELS = [
    (
        'Gemini 3.x',
        [
            ('gemini-3.6-flash', 'gemini-3.6-flash'),
            ('gemini-3.5-flash', 'gemini-3.5-flash'),
            ('gemini-3.5-flash-lite', 'gemini-3.5-flash-lite'),
            ('gemini-3.1-flash-lite', 'gemini-3.1-flash-lite'),
            ('gemini-3.1-pro-preview', 'gemini-3.1-pro-preview'),
            ('gemini-3-flash-preview', 'gemini-3-flash-preview'),
            ('gemini-3-pro-preview', 'gemini-3-pro-preview (retired preview)'),
        ],
    ),
    (
        'Gemini 2.5',
        [
            ('gemini-2.5-pro', 'gemini-2.5-pro'),
            ('gemini-2.5-flash', 'gemini-2.5-flash'),
            ('gemini-2.5-flash-lite', 'gemini-2.5-flash-lite'),
            ('gemini-2.5-flash-preview-05-20', 'gemini-2.5-flash-preview-05-20'),
            ('gemini-2.5-pro-preview-05-06', 'gemini-2.5-pro-preview-05-06'),
            ('gemini-2.5-pro-preview-06-05', 'gemini-2.5-pro-preview-06-05'),
        ],
    ),
    (
        'Gemini 2.0',
        [
            ('gemini-2.0-flash', 'gemini-2.0-flash'),
            ('gemini-2.0-flash-001', 'gemini-2.0-flash-001'),
            ('gemini-2.0-flash-lite', 'gemini-2.0-flash-lite'),
            ('gemini-2.0-flash-lite-001', 'gemini-2.0-flash-lite-001'),
            ('gemini-2.0-flash-thinking-exp', 'gemini-2.0-flash-thinking-exp'),
            ('gemini-2.0-flash-thinking-exp-01-21', 'gemini-2.0-flash-thinking-exp-01-21'),
            ('gemini-2.0-pro-exp', 'gemini-2.0-pro-exp'),
            ('gemini-2.0-flash-exp', 'gemini-2.0-flash-exp'),
        ],
    ),
    (
        'Gemini 1.5 / legacy',
        [
            ('gemini-1.5-pro', 'gemini-1.5-pro'),
            ('gemini-1.5-pro-latest', 'gemini-1.5-pro-latest'),
            ('gemini-1.5-pro-002', 'gemini-1.5-pro-002'),
            ('gemini-1.5-pro-001', 'gemini-1.5-pro-001'),
            ('gemini-1.5-flash', 'gemini-1.5-flash'),
            ('gemini-1.5-flash-latest', 'gemini-1.5-flash-latest'),
            ('gemini-1.5-flash-002', 'gemini-1.5-flash-002'),
            ('gemini-1.5-flash-001', 'gemini-1.5-flash-001'),
            ('gemini-1.5-flash-8b', 'gemini-1.5-flash-8b'),
            ('gemini-1.5-flash-8b-latest', 'gemini-1.5-flash-8b-latest'),
            ('gemini-1.5-flash-8b-001', 'gemini-1.5-flash-8b-001'),
            ('gemini-pro', 'gemini-pro (legacy)'),
            ('gemini-pro-vision', 'gemini-pro-vision (legacy)'),
            ('gemini-1.0-pro', 'gemini-1.0-pro (legacy)'),
            ('gemini-1.0-pro-001', 'gemini-1.0-pro-001 (legacy)'),
            ('gemini-1.0-pro-latest', 'gemini-1.0-pro-latest (legacy)'),
            ('gemini-1.0-pro-vision-latest', 'gemini-1.0-pro-vision-latest (legacy)'),
        ],
    ),
    (
        'Imagen / Live / embeddings / otros',
        [
            ('gemini-3-pro-image', 'gemini-3-pro-image (Nano Banana Pro)'),
            ('gemini-3-pro-image-preview', 'gemini-3-pro-image-preview'),
            ('gemini-3.1-flash-image', 'gemini-3.1-flash-image (Nano Banana 2)'),
            ('gemini-3.1-flash-image-preview', 'gemini-3.1-flash-image-preview'),
            ('gemini-3.1-flash-lite-image', 'gemini-3.1-flash-lite-image'),
            ('gemini-2.5-flash-image', 'gemini-2.5-flash-image (Nano Banana)'),
            ('gemini-3.1-flash-live-preview', 'gemini-3.1-flash-live-preview'),
            ('gemini-2.5-flash-native-audio-preview-12-2025', 'gemini-2.5-flash-native-audio-preview-12-2025'),
            ('gemini-2.5-flash-native-audio-preview-09-2025', 'gemini-2.5-flash-native-audio-preview-09-2025'),
            ('imagen-3.0-generate-002', 'imagen-3.0-generate-002'),
            ('imagen-3.0-generate-001', 'imagen-3.0-generate-001'),
            ('imagen-3.0-fast-generate-001', 'imagen-3.0-fast-generate-001'),
            ('veo-2.0-generate-001', 'veo-2.0-generate-001'),
            ('text-embedding-004', 'text-embedding-004'),
            ('embedding-001', 'embedding-001'),
            ('gemini-embedding-001', 'gemini-embedding-001'),
            ('gemini-embedding-exp', 'gemini-embedding-exp'),
            ('aqa', 'aqa'),
        ],
    ),
]

# Anthropic — overview + model-deprecations (activos, aliases y retirados)
ANTHROPIC_MODELS = [
    (
        'Actuales (Claude 5 / Haiku 4.5)',
        [
            ('claude-fable-5', 'claude-fable-5 — Fable 5'),
            ('claude-opus-5', 'claude-opus-5 — Opus 5'),
            ('claude-sonnet-5', 'claude-sonnet-5 — Sonnet 5'),
            ('claude-haiku-4-5', 'claude-haiku-4-5 — alias'),
            ('claude-haiku-4-5-20251001', 'claude-haiku-4-5-20251001 — snapshot'),
            ('claude-mythos-5', 'claude-mythos-5 — limitado Glasswing'),
            ('claude-mythos-preview', 'claude-mythos-preview — deprecated'),
        ],
    ),
    (
        'Disponibles (4.x activos)',
        [
            ('claude-opus-4-8', 'claude-opus-4-8'),
            ('claude-opus-4-7', 'claude-opus-4-7'),
            ('claude-opus-4-6', 'claude-opus-4-6'),
            ('claude-sonnet-4-6', 'claude-sonnet-4-6'),
            ('claude-sonnet-4-5', 'claude-sonnet-4-5 — alias'),
            ('claude-sonnet-4-5-20250929', 'claude-sonnet-4-5-20250929'),
            ('claude-opus-4-5', 'claude-opus-4-5 — alias'),
            ('claude-opus-4-5-20251101', 'claude-opus-4-5-20251101'),
        ],
    ),
    (
        'Retirados / legacy (pueden fallar)',
        [
            ('claude-opus-4-1', 'claude-opus-4-1 — alias (retired)'),
            ('claude-opus-4-1-20250805', 'claude-opus-4-1-20250805 (retired)'),
            ('claude-opus-4-0', 'claude-opus-4-0 — alias (retired)'),
            ('claude-opus-4-20250514', 'claude-opus-4-20250514 (retired)'),
            ('claude-sonnet-4-0', 'claude-sonnet-4-0 — alias (retired)'),
            ('claude-sonnet-4-20250514', 'claude-sonnet-4-20250514 (retired)'),
            ('claude-3-7-sonnet-latest', 'claude-3-7-sonnet-latest (retired)'),
            ('claude-3-7-sonnet-20250219', 'claude-3-7-sonnet-20250219 (retired)'),
            ('claude-3-5-sonnet-latest', 'claude-3-5-sonnet-latest (retired)'),
            ('claude-3-5-sonnet-20241022', 'claude-3-5-sonnet-20241022 (retired)'),
            ('claude-3-5-sonnet-20240620', 'claude-3-5-sonnet-20240620 (retired)'),
            ('claude-3-5-haiku-latest', 'claude-3-5-haiku-latest (retired)'),
            ('claude-3-5-haiku-20241022', 'claude-3-5-haiku-20241022 (retired)'),
            ('claude-3-opus-latest', 'claude-3-opus-latest (retired)'),
            ('claude-3-opus-20240229', 'claude-3-opus-20240229 (retired)'),
            ('claude-3-sonnet-20240229', 'claude-3-sonnet-20240229 (retired)'),
            ('claude-3-haiku-20240307', 'claude-3-haiku-20240307 (retired)'),
            ('claude-2.1', 'claude-2.1 (retired)'),
            ('claude-2.0', 'claude-2.0 (retired)'),
            ('claude-instant-1.2', 'claude-instant-1.2 (retired)'),
        ],
    ),
]

PROVIDER_MODELS = {
    'openai': OPENAI_MODELS,
    'gemini': GEMINI_MODELS,
    'anthropic': ANTHROPIC_MODELS,
}

DEFAULT_MODELS = {
    'openai': 'gpt-4o-mini',
    'gemini': 'gemini-2.0-flash',
    'anthropic': 'claude-haiku-4-5',
}

# Defaults recomendados para PDF escaneado (vision / documento)
DEFAULT_VISION_MODELS = {
    'openai': 'gpt-4o-mini',
    'gemini': 'gemini-2.0-flash',
    'anthropic': 'claude-haiku-4-5',
}


def models_for_provider(provider: str):
    return PROVIDER_MODELS.get((provider or '').strip().lower(), [])


def catalog_as_dict():
    """Estructura JSON-serializable para la UI."""
    out = {}
    for provider, groups in PROVIDER_MODELS.items():
        out[provider] = [
            {
                'label': group_label,
                'models': [{'id': mid, 'label': mlabel} for mid, mlabel in models],
            }
            for group_label, models in groups
        ]
    return out


def all_model_ids(provider: str = None):
    ids = []
    providers = [provider] if provider else PROVIDER_MODELS.keys()
    for p in providers:
        for _label, models in models_for_provider(p):
            for mid, _ in models:
                ids.append(mid)
    return ids
