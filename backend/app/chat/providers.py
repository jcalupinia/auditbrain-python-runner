"""Abstracción de proveedores LLM.

Mantiene las API keys server-side (NUNCA llegan al navegador). Devuelve
una respuesta normalizada o levanta ProviderUnavailable cuando no hay
proveedor configurado, para que la UI muestre un error honesto en vez
de inventar respuestas.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


class ProviderUnavailable(RuntimeError):
    """No hay proveedor LLM configurado o el proveedor falló al responder."""


@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_in: int | None
    tokens_out: int | None


# ---------------------------------------------------------------------------
# Configuración (resuelta cada llamada para soportar tests con monkeypatch)
# ---------------------------------------------------------------------------

def _provider() -> str:
    return os.getenv("AUDITBRAIN_LLM_PROVIDER", "anthropic").strip().lower()


def _anthropic_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "").strip()


def _openai_key() -> str:
    return os.getenv("OPENAI_API_KEY", "").strip()


def _gemini_key() -> str:
    # Soporta GEMINI_API_KEY (Google AI Studio) y GOOGLE_API_KEY como alias.
    return (
        os.getenv("GEMINI_API_KEY", "").strip()
        or os.getenv("GOOGLE_API_KEY", "").strip()
    )


def _anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def _gemini_model() -> str:
    # Default a Gemini 2.0 Flash (cuota gratis muy generosa en AI Studio).
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()


def _max_tokens() -> int:
    try:
        return int(os.getenv("AUDITBRAIN_LLM_MAX_TOKENS", "1024"))
    except ValueError:
        return 1024


def available_provider() -> str | None:
    """Devuelve qué proveedor está disponible (o None si ninguno)."""
    p = _provider()
    if p == "anthropic" and _anthropic_key():
        return "anthropic"
    if p == "openai" and _openai_key():
        return "openai"
    if p in ("gemini", "google") and _gemini_key():
        return "gemini"
    # Fallback automático: cualquier otro que tenga clave.
    if _anthropic_key():
        return "anthropic"
    if _openai_key():
        return "openai"
    if _gemini_key():
        return "gemini"
    return None


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------

def chat_complete(
    messages: list[dict[str, str]],
    system: str | None = None,
) -> LLMResponse:
    """Envía una conversación al proveedor activo y devuelve la respuesta.

    ``messages``: lista de {"role": "user"|"assistant", "content": str}.
    ``system``: prompt del sistema (rol del agente).
    """
    provider = available_provider()
    if provider == "anthropic":
        return _call_anthropic(messages, system)
    if provider == "openai":
        return _call_openai(messages, system)
    if provider == "gemini":
        return _call_gemini(messages, system)
    raise ProviderUnavailable(
        "No hay proveedor LLM configurado en el servidor. "
        "Define ANTHROPIC_API_KEY, OPENAI_API_KEY o GEMINI_API_KEY en Render."
    )


def _http_post(url: str, headers: dict[str, str], payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise ProviderUnavailable(f"HTTP {e.code} del proveedor: {detail[:400]}")
    except urllib.error.URLError as e:
        raise ProviderUnavailable(f"Error de red contactando al proveedor: {e}")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise ProviderUnavailable("El proveedor devolvió un cuerpo no-JSON.")


def _call_anthropic(messages: list[dict], system: str | None) -> LLMResponse:
    model = _anthropic_model()
    payload: dict = {
        "model": model,
        "max_tokens": _max_tokens(),
        "messages": messages,
    }
    if system:
        payload["system"] = system
    data = _http_post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": _anthropic_key(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload=payload,
    )
    parts = data.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
    usage = data.get("usage", {})
    return LLMResponse(
        content=text or "(respuesta vacía del proveedor)",
        model=model,
        tokens_in=usage.get("input_tokens"),
        tokens_out=usage.get("output_tokens"),
    )


def _call_openai(messages: list[dict], system: str | None) -> LLMResponse:
    model = _openai_model()
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    data = _http_post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {_openai_key()}",
            "Content-Type": "application/json",
        },
        payload={"model": model, "messages": msgs, "max_tokens": _max_tokens()},
    )
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    text = (msg.get("content") or "").strip()
    usage = data.get("usage", {})
    return LLMResponse(
        content=text or "(respuesta vacía del proveedor)",
        model=model,
        tokens_in=usage.get("prompt_tokens"),
        tokens_out=usage.get("completion_tokens"),
    )


def _call_gemini(messages: list[dict], system: str | None) -> LLMResponse:
    """Llama a Google Gemini (AI Studio).

    Diferencias con Anthropic/OpenAI:
    - Auth por query string (?key=...), no por header.
    - El rol del asistente se llama ``model``, no ``assistant``.
    - El system prompt va aparte como ``system_instruction``.
    """
    model = _gemini_model()
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={_gemini_key()}"
    )
    contents = []
    for m in messages:
        role = "model" if m.get("role") == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": m.get("content", "")}]})

    payload: dict = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": _max_tokens()},
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    data = _http_post(
        url,
        headers={"Content-Type": "application/json"},
        payload=payload,
    )
    candidates = data.get("candidates") or []
    text = ""
    if candidates:
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts).strip()
    usage = data.get("usageMetadata") or {}
    return LLMResponse(
        content=text or "(respuesta vacía del proveedor)",
        model=model,
        tokens_in=usage.get("promptTokenCount"),
        tokens_out=usage.get("candidatesTokenCount"),
    )
