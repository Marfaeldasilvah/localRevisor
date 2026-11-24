"""Comunicação com provedores compatíveis com a API da OpenAI."""
from __future__ import annotations

import os
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from openai import APIStatusError, BadRequestError, OpenAI, OpenAIError

from .models import GradingError, ModelOutputError
from .prompts import DEFAULT_TIMEOUT, REPAIR_PROMPT


def provider_name(base_url: str) -> str:
    try:
        return urlparse(base_url).hostname or base_url
    except ValueError:
        return base_url


def is_local_endpoint(base_url: str) -> bool:
    try:
        host = (urlparse(base_url).hostname or "").lower()
    except ValueError:
        return False
    return host in {"localhost", "127.0.0.1", "::1"}


def validate_base_url(base_url: str) -> str:
    base_url = (base_url or "").strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise GradingError("Informe uma URL base http(s) válida.")
    return base_url


def opencode_headers(base_url: str, session_id: str | None = None) -> dict[str, str]:
    hostname = urlparse(base_url).hostname or ""
    if hostname != "opencode.ai" and not hostname.endswith(".opencode.ai"):
        return {}
    return {
        "x-opencode-session": session_id or uuid4().hex,
        "User-Agent": "localRevisor/1.0",
    }


def api_client(settings: dict[str, str], session_id: str | None = None) -> OpenAI:
    base_url = validate_base_url(settings.get("base_url", ""))
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key and not is_local_endpoint(base_url):
        raise GradingError(
            "OPENAI_API_KEY não configurada. Salve a chave em Configurações "
            "ou defina-a no .env."
        )
    return OpenAI(
        api_key=api_key or "local",
        base_url=base_url,
        default_headers=opencode_headers(base_url, session_id) or None,
        timeout=DEFAULT_TIMEOUT,
        max_retries=1,
    )


def _error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return ""
    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict) and err.get("message"):
            return f": {err['message']}"
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return f": {value.strip()}"
    return ""


def _extract_model_ids(payload: object, url: str) -> list[str]:
    if isinstance(payload, dict):
        if isinstance(payload.get("data"), list):
            items = payload["data"]
        elif isinstance(payload.get("models"), list):
            items = payload["models"]
        else:
            raise GradingError(
                f"GET {url} retornou JSON sem lista de modelos ('data' ou 'models')."
            )
    elif isinstance(payload, list):
        items = payload
    else:
        raise GradingError(f"GET {url} retornou formato inesperado de modelos.")

    ids: set[str] = set()
    for item in items:
        if isinstance(item, str):
            model_id = item.strip()
        elif isinstance(item, dict):
            raw = item.get("id") or item.get("name") or ""
            model_id = str(raw).strip()
        else:
            continue
        if model_id:
            ids.add(model_id)
    return sorted(ids)


def fetch_models(base_url: str, api_key: str = "") -> list[str]:
    """Consulta GET {base_url}/models para obter a lista real de modelos."""
    base_url = validate_base_url(base_url)
    url = f"{base_url}/models"
    headers = {
        "Accept": "application/json",
        **opencode_headers(base_url),
    }
    token = (api_key or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif is_local_endpoint(base_url):
        headers["Authorization"] = "Bearer local"

    try:
        response = httpx.get(
            url,
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )
    except httpx.HTTPError as exc:
        raise GradingError(f"Não foi possível conectar a {url}: {exc}") from exc

    if response.status_code == 404:
        raise GradingError(
            f"Endpoint de modelos não encontrado: GET {url} retornou 404. "
            "Verifique a URL base (ex.: inclua /v1 se o provedor exigir)."
        )
    if response.status_code >= 400:
        detail = _error_detail(response)
        raise GradingError(
            f"Não foi possível conectar: GET {url} retornou HTTP "
            f"{response.status_code}{detail}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise GradingError(
            f"GET {url} não devolveu JSON válido. "
            "Verifique se a URL base é um endpoint compatível com a API da OpenAI."
        ) from exc

    return _extract_model_ids(payload, url)


def _usage(response) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return int(getattr(usage, "prompt_tokens", 0) or 0), int(
        getattr(usage, "completion_tokens", 0) or 0
    )


def _content(response) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise ModelOutputError("O provedor não devolveu nenhuma alternativa.")
    choice = choices[0]
    content = getattr(getattr(choice, "message", None), "content", None)
    if not isinstance(content, str) or not content.strip():
        finish = getattr(choice, "finish_reason", None)
        raise ModelOutputError(
            f"O provedor devolveu conteúdo vazio (finish_reason={finish!r})."
        )
    if getattr(choice, "finish_reason", None) == "length":
        raise ModelOutputError(
            "A resposta do modelo foi cortada por limite de tokens. "
            "Tente novamente ou use um modelo com mais contexto."
        )
    return content


def create_completion(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict],
    max_tokens: int,
    json_mode: bool,
) -> tuple[str, int, int]:
    """Tenta JSON mode e temperature 0, caindo para variantes compatíveis."""
    base = {"model": model, "messages": messages, "max_tokens": max_tokens}
    # Alguns provedores compatíveis rejeitam response_format, temperature ou
    # max_tokens. Tenta do mais rico para o mais básico, mas só repete quando o
    # erro realmente menciona o parâmetro removido na próxima variante.
    variants: list[tuple[dict, tuple[str, ...]]] = []
    if json_mode:
        variants.append(
            (
                {
                    **base,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
                ("response_format", "json", "temperature", "max_tokens"),
            )
        )
    variants.append(({**base, "temperature": 0}, ("temperature", "max_tokens")))
    variants.append((dict(base), ("max_tokens",)))
    variants.append(({"model": model, "messages": messages}, ()))
    last_error: Exception | None = None
    for kwargs, retry_terms in variants:
        try:
            response = client.chat.completions.create(**kwargs)
        except BadRequestError as exc:
            last_error = exc
            message = str(exc).lower()
            if any(term in message for term in retry_terms):
                continue
            raise GradingError(f"O provedor recusou a requisição: {exc}") from exc
        except APIStatusError as exc:
            if getattr(exc, "status_code", None) == 404:
                raise GradingError(
                    f"O provedor retornou 404 para o modelo '{model}' ({exc}). "
                    "Verifique a URL base (ex.: /v1) e se o modelo suporta /chat/completions."
                ) from exc
            raise GradingError(f"O provedor respondeu com erro: {exc}") from exc
        except OpenAIError as exc:
            raise GradingError(f"Falha ao chamar o provedor: {exc}") from exc
        content = _content(response)
        tokens_in, tokens_out = _usage(response)
        return content, tokens_in, tokens_out
    raise GradingError(f"O provedor recusou a requisição: {last_error}")


def repair_completion(
    client: OpenAI,
    *,
    model: str,
    messages: list[dict],
    invalid_content: str,
    schema: str,
    max_tokens: int,
) -> tuple[str, int, int]:
    repair_messages = [
        *messages,
        {"role": "assistant", "content": invalid_content},
        {
            "role": "user",
            "content": REPAIR_PROMPT
            + schema
            + "\nResponda somente com o JSON corrigido.",
        },
    ]
    return create_completion(
        client,
        model=model,
        messages=repair_messages,
        max_tokens=max_tokens,
        json_mode=False,
    )
