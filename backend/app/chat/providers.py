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


def _anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


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
    # Fallback automático si el preferido no está pero el otro sí.
    if _anthropic_key():
        return "anthropic"
    if _openai_key():
        return "openai"
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
    raise ProviderUnavailable(
        "No hay proveedor LLM configurado en el servidor. "
        "Define ANTHROPIC_API_KEY o OPENAI_API_KEY en Render."
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
