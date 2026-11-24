"""Presets de endpoints compatíveis com a API da OpenAI dos provedores mais populares."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    id: str
    label: str
    base_url: str
    hint: str = ""
    local: bool = False


PROVIDER_PRESETS: tuple[ProviderPreset, ...] = (
    ProviderPreset(
        id="opencode-go",
        label="OpenCode Go",
        base_url="https://opencode.ai/zen/go/v1",
        hint="Plano OpenCode Go (endpoint compatível com OpenAI).",
    ),
    ProviderPreset(
        id="opencode-go-inference",
        label="OpenCode Go (Inference)",
        base_url="https://opencode.ai/inference/go/v1",
        hint="Endpoint alternativo de inferência do OpenCode Go.",
    ),
    ProviderPreset(
        id="opencode-zen",
        label="OpenCode Zen",
        base_url="https://opencode.ai/zen/v1",
        hint="Gateway OpenCode Zen.",
    ),
    ProviderPreset(
        id="z-ai",
        label="Z.ai (GLM)",
        base_url="https://api.z.ai/api/paas/v4",
        hint="API geral da Z.ai (modelos GLM).",
    ),
    ProviderPreset(
        id="z-ai-coding",
        label="Z.ai (GLM Coding Plan)",
        base_url="https://api.z.ai/api/coding/paas/v4",
        hint="Endpoint do GLM Coding Plan da Z.ai.",
    ),
    ProviderPreset(
        id="claude",
        label="Claude (Anthropic)",
        base_url="https://api.anthropic.com/v1",
        hint="Camada compatível com OpenAI da Anthropic (Claude).",
    ),
    ProviderPreset(
        id="google-ai",
        label="Google AI (Gemini)",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        hint="Endpoint compatível com OpenAI do Google AI Studio (Gemini).",
    ),
    ProviderPreset(
        id="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        hint="API oficial da OpenAI.",
    ),
    ProviderPreset(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com",
        hint="API oficial da DeepSeek.",
    ),
    ProviderPreset(
        id="openrouter",
        label="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        hint="Agregador OpenRouter.",
    ),
    ProviderPreset(
        id="groq",
        label="Groq",
        base_url="https://api.groq.com/openai/v1",
        hint="Inferência rápida na Groq.",
    ),
    ProviderPreset(
        id="ollama",
        label="Ollama (local — porta 11434)",
        base_url="http://localhost:11434/v1",
        hint="Servidor local do Ollama. Altere a porta na URL base se usar outra.",
        local=True,
    ),
    ProviderPreset(
        id="lm-studio",
        label="LM Studio (local — porta 1234)",
        base_url="http://localhost:1234/v1",
        hint="Servidor local do LM Studio.",
        local=True,
    ),
)


def match_preset_url(base_url: str) -> str:
    """Devolve o base_url canônico do preset correspondente, ou '' se personalizado."""
    normalized = (base_url or "").strip().rstrip("/")
    for preset in PROVIDER_PRESETS:
        if preset.base_url.rstrip("/") == normalized:
            return preset.base_url
    return ""
