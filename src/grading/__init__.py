"""Correção de redações: prompts, contrato JSON, provedor OpenAI e BERT."""
from __future__ import annotations

from .. import bert_notas, files
from .models import COMPETENCIAS, GradingError, ModelOutputError, ReviewResult
from .parser import (
    extract_json_object,
    normalize_competency,
    normalize_errors,
    normalize_note,
    parse_hybrid,
    parse_review,
    parse_scores,
    verify_quotes,
)
from .presets import PROVIDER_PRESETS, ProviderPreset, match_preset_url
from .prompts import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT,
    HYBRID_PROMPT,
    PROMPT_VERSION_HYBRID,
    PROMPT_VERSION_REVIEW,
    PROMPT_VERSION_TRANSCRIBE,
    REPAIR_PROMPT,
    REVIEW_PROMPT,
    TRANSCRIBE_MAX_TOKENS,
    TRANSCRIBE_PROMPT,
)
from .provider import (
    api_client,
    create_completion as _create_completion,
    fetch_models,
    is_local_endpoint,
    opencode_headers,
    provider_name,
    repair_completion as _repair,
    validate_base_url,
)
from .service import obtain_text, review, transcribe

__all__ = [
    "COMPETENCIAS",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TIMEOUT",
    "GradingError",
    "HYBRID_PROMPT",
    "ModelOutputError",
    "PROMPT_VERSION_HYBRID",
    "PROMPT_VERSION_REVIEW",
    "PROMPT_VERSION_TRANSCRIBE",
    "PROVIDER_PRESETS",
    "ProviderPreset",
    "REPAIR_PROMPT",
    "REVIEW_PROMPT",
    "ReviewResult",
    "TRANSCRIBE_MAX_TOKENS",
    "TRANSCRIBE_PROMPT",
    "_create_completion",
    "_repair",
    "api_client",
    "bert_notas",
    "extract_json_object",
    "fetch_models",
    "files",
    "is_local_endpoint",
    "match_preset_url",
    "normalize_competency",
    "normalize_errors",
    "normalize_note",
    "obtain_text",
    "opencode_headers",
    "parse_hybrid",
    "parse_review",
    "parse_scores",
    "provider_name",
    "review",
    "transcribe",
    "validate_base_url",
    "verify_quotes",
]
