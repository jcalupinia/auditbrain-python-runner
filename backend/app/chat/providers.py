"""Abstracción de proveedores LLM.

Mantiene las API keys server-side (NUNCA llegan al navegador). Devuelve
una respuesta normalizada o levanta ProviderUnavailable cuando no hay
proveedor configurado, para que la UI muestre un error honesto en vez
de inventar respuestas.
"""

from __future__ import annotations

import json
import logging
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
    # Sin default: si el operador no fija una preferencia explícita, se aplica
    # el orden free-first definido en _providers_with_keys() y no se quema
    # saldo de pago por accidente cuando hay varias keys configuradas.
    return os.getenv("AUDITBRAIN_LLM_PROVIDER", "").strip().lower()


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


def _groq_key() -> str:
    return os.getenv("GROQ_API_KEY", "").strip()


def _openrouter_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def _anthropic_model() -> str:
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6").strip()


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def _gemini_model() -> str:
    # Default a Gemini 2.0 Flash (cuota gratis muy generosa en AI Studio).
    return os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()


def _groq_model() -> str:
    # Llama 3.3 70B en Groq: rápido y dentro del tier gratis (~14k req/día).
    return os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile").strip()


def _openrouter_model() -> str:
    # Modelo :free de OpenRouter — sin coste, rate-limit por minuto.
    return os.getenv(
        "OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free"
    ).strip()


def _local_base_url() -> str:
    # Gateway LOCAL compatible con la API de OpenAI (LiteLLM en el servidor de
    # IA propio). DEBE incluir el sufijo /v1 (ej. https://host/v1); abajo se le
    # concatena /chat/completions. Es lo que decide si "local" está disponible:
    # basta la URL, la key puede ser opcional según el gateway.
    return os.getenv("LOCAL_LLM_BASE_URL", "").strip()


def _local_key() -> str:
    # Master key del gateway LiteLLM. Puede ir vacía si el gateway no la exige;
    # en _call_local se envía un Bearer no-vacío de todas formas.
    return os.getenv("LOCAL_LLM_API_KEY", "").strip()


def _local_model() -> str:
    # Nombre lógico del modelo servido por el gateway local.
    return os.getenv("LOCAL_LLM_MODEL", "auditia-rutina").strip()


def _local_timeout() -> int:
    # Timeout CORTO propio del proveedor local (no los 60s por defecto).
    # El servidor local es el primario: si responde lento (modelo cargando,
    # VRAM saturada, enlace lento) queremos degradar RÁPIDO a la nube en vez
    # de congelar la UI. Ajustable por env.
    try:
        return int(os.getenv("LOCAL_LLM_TIMEOUT_SECONDS", "15"))
    except ValueError:
        return 15


def _max_tokens() -> int:
    # Techo de tokens de SALIDA del LLM. Default alto para permitir documentos
    # largos (contratos, dictámenes, informes) sin que la respuesta se corte.
    # Es un TECHO, no un mínimo: no encarece ni alarga las respuestas cortas
    # (el modelo se detiene cuando termina). Ajustable por env si algún
    # proveedor gratuito lo limita: AUDITBRAIN_LLM_MAX_TOKENS.
    try:
        return int(os.getenv("AUDITBRAIN_LLM_MAX_TOKENS", "8192"))
    except ValueError:
        return 8192


def _providers_with_keys() -> list[str]:
    """Lista de proveedores realmente configurados, en orden de preferencia.

    Preferencia: el valor explícito de AUDITBRAIN_LLM_PROVIDER primero, y luego
    el resto. Sin override, el servidor de IA LOCAL va primero (privacidad +
    coste cero), y los gratuitos antes que los de pago como respaldo:
        local > gemini > groq > openrouter > anthropic > openai
    """
    have = {
        # "local" está disponible con solo la base URL configurada; la key es
        # opcional según el gateway.
        "local": bool(_local_base_url()),
        "anthropic": bool(_anthropic_key()),
        "openai": bool(_openai_key()),
        "gemini": bool(_gemini_key()),
        "groq": bool(_groq_key()),
        "openrouter": bool(_openrouter_key()),
    }
    preferred = _provider()
    if preferred == "google":
        preferred = "gemini"
    default_order = ["local", "gemini", "groq", "openrouter", "anthropic", "openai"]
    order: list[str] = []
    if preferred in have and have[preferred]:
        order.append(preferred)
    for p in default_order:
        if p not in order and have.get(p):
            order.append(p)
    return order


def available_provider() -> str | None:
    """Devuelve qué proveedor se intentará primero (o None si ninguno)."""
    chain = _providers_with_keys()
    return chain[0] if chain else None


# ---------------------------------------------------------------------------
# Cliente principal
# ---------------------------------------------------------------------------

def _dispatch(provider: str, messages: list[dict], system: str | None) -> LLMResponse:
    if provider == "local":
        return _call_local(messages, system)
    if provider == "anthropic":
        return _call_anthropic(messages, system)
    if provider == "openai":
        return _call_openai(messages, system)
    if provider == "gemini":
        return _call_gemini(messages, system)
    if provider == "groq":
        return _call_groq(messages, system)
    if provider == "openrouter":
        return _call_openrouter(messages, system)
    raise ProviderUnavailable(f"Proveedor desconocido: {provider}")


def chat_complete(
    messages: list[dict[str, str]],
    system: str | None = None,
) -> LLMResponse:
    """Envía una conversación al proveedor activo y devuelve la respuesta.

    Intenta el proveedor preferido y, si falla (sin saldo, modelo retirado,
    timeout puntual, etc.), reintenta con el siguiente proveedor configurado.
    Se prioriza la lista calculada en ``_providers_with_keys()``.

    Si NINGÚN proveedor responde con éxito, propaga la última excepción para
    que la UI muestre el error real al usuario (no se inventa respuesta).
    """
    chain = _providers_with_keys()
    if not chain:
        raise ProviderUnavailable(
            "No hay proveedor LLM configurado en el servidor. Define una de: "
            "GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, "
            "ANTHROPIC_API_KEY u OPENAI_API_KEY en Render."
        )
    last_exc: ProviderUnavailable | None = None
    for provider in chain:
        try:
            return _dispatch(provider, messages, system)
        except ProviderUnavailable as exc:
            last_exc = exc
            import logging

            logging.getLogger("auditbrain").warning(
                "Proveedor %s falló (%s). Probando siguiente…", provider, exc
            )
            continue
    assert last_exc is not None
    raise last_exc


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
    # ------------------------------------------------------------------
    # Timeout de LECTURA (incidente 2026-08-05).
    #
    # `urllib` envuelve en `URLError` los fallos de CONEXIÓN, pero una vez
    # establecida la conexión el timeout del socket sube crudo como
    # `TimeoutError`. Y `TimeoutError` NO es subclase de `URLError`: ambas
    # cuelgan de `OSError` como hermanas. Sin estas dos cláusulas la
    # excepción escapaba de `_http_post`, escapaba del bucle de failover de
    # `chat_complete` (que solo captura ProviderUnavailable) —de modo que
    # gemini y groq nunca llegaban a probarse— y escapaba del `except` de
    # skill_run, terminando en un HTTP 500 con traceback en vez del 503 que
    # el propio contrato OpenAPI declara.
    #
    # Caso real: `max_tokens` subió de 1024 a 8192 y, al no usarse streaming,
    # Anthropic no envía el primer byte hasta terminar de generar. La lectura
    # excedía los 60s y el proveedor primario se llevaba por delante toda la
    # cadena de respaldo.
    #
    # El orden importa: `URLError` va ANTES porque también es subclase de
    # `OSError`; `TimeoutError` va antes que `OSError` solo para dar un
    # mensaje más preciso (es subclase suya).
    # ------------------------------------------------------------------
    except TimeoutError as e:
        raise ProviderUnavailable(
            f"El proveedor no respondió en {timeout}s (timeout de lectura). "
            f"Si es recurrente, baja AUDITBRAIN_LLM_MAX_TOKENS: sin streaming "
            f"la respuesta no empieza a llegar hasta que termina de generarse. "
            f"Detalle: {e}"
        )
    except OSError as e:
        raise ProviderUnavailable(f"Error de socket contactando al proveedor: {e}")
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


def _call_openai_compatible(
    url: str,
    key: str,
    model: str,
    messages: list[dict],
    system: str | None,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> LLMResponse:
    """Backend común para OpenAI, Groq, OpenRouter y el gateway local (mismo
    wire format). ``timeout`` permite un tope de lectura propio por proveedor
    (el local usa uno corto para degradar rápido a la nube)."""
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = _http_post(
        url,
        headers=headers,
        payload={"model": model, "messages": msgs, "max_tokens": _max_tokens()},
        timeout=timeout,
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


def _call_local(messages: list[dict], system: str | None) -> LLMResponse:
    # Gateway LiteLLM propio (OpenAI-compatible). LOCAL_LLM_BASE_URL incluye
    # /v1, aquí se le añade /chat/completions. Se envía un Bearer no-vacío por
    # si el gateway valida el header aunque la master key sea opcional. Usa el
    # timeout CORTO propio del local para no congelar la UI si va lento.
    base = _local_base_url().rstrip("/")
    return _call_openai_compatible(
        url=f"{base}/chat/completions",
        key=_local_key() or "sk-noauth",
        model=_local_model(),
        messages=messages,
        system=system,
        timeout=_local_timeout(),
    )


def _call_openai(messages: list[dict], system: str | None) -> LLMResponse:
    return _call_openai_compatible(
        url="https://api.openai.com/v1/chat/completions",
        key=_openai_key(),
        model=_openai_model(),
        messages=messages,
        system=system,
    )


def _call_groq(messages: list[dict], system: str | None) -> LLMResponse:
    return _call_openai_compatible(
        url="https://api.groq.com/openai/v1/chat/completions",
        key=_groq_key(),
        model=_groq_model(),
        messages=messages,
        system=system,
    )


def _call_openrouter(messages: list[dict], system: str | None) -> LLMResponse:
    # OpenRouter recomienda enviar HTTP-Referer y X-Title para atribución;
    # opcionales, pero útiles para ver el tráfico en su dashboard.
    referer = os.getenv("OPENROUTER_SITE_URL", "").strip()
    title = os.getenv("OPENROUTER_APP_NAME", "AuditBrain").strip()
    extra: dict[str, str] = {"X-Title": title}
    if referer:
        extra["HTTP-Referer"] = referer
    return _call_openai_compatible(
        url="https://openrouter.ai/api/v1/chat/completions",
        key=_openrouter_key(),
        model=_openrouter_model(),
        messages=messages,
        system=system,
        extra_headers=extra,
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


# ---------------------------------------------------------------------------
# Streaming (SSE token por token) — aditivo, no altera el path clásico
# ---------------------------------------------------------------------------
#
# Solo los proveedores OpenAI-compatibles (local, openai, groq, openrouter)
# soportan streaming aquí. Si el primario es gemini/anthropic, o si el stream
# falla ANTES del primer token, se levanta ProviderUnavailable para que el
# caller (service) caiga limpio a chat_complete() no-streaming, que recorre
# toda la cadena de failover. Una vez emitido el primer token ya no hay
# failover transparente (se propaga el error con el parcial ya entregado).

_STREAMABLE = {"local", "openai", "groq", "openrouter"}


def _stream_openai_compatible(url, key, model, messages, system, timeout, extra_headers=None):
    """Generador de deltas desde un endpoint OpenAI-compatible con stream=True.

    Emite dicts: {"type": "token", "text": ...} y al final
    {"type": "done", "model", "tokens_in", "tokens_out"} (si el gateway envía
    usage vía stream_options). Traduce cualquier fallo de red a ProviderUnavailable.
    """
    msgs: list[dict] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.extend(messages)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    body = json.dumps(
        {
            "model": model,
            "messages": msgs,
            "max_tokens": _max_tokens(),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise ProviderUnavailable(f"HTTP {e.code} del proveedor: {detail[:400]}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise ProviderUnavailable(f"Error de red/timeout contactando al proveedor: {e}")

    try:
        for raw in resp:  # el file-object de urllib itera línea por línea (SSE)
            line = raw.decode("utf-8", errors="replace").strip()
            if not line or not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                piece = delta.get("content")
                if piece:
                    yield {"type": "token", "text": piece}
            usage = chunk.get("usage")
            if usage:
                yield {
                    "type": "done",
                    "model": model,
                    "tokens_in": usage.get("prompt_tokens"),
                    "tokens_out": usage.get("completion_tokens"),
                }
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _stream_provider(provider, messages, system):
    if provider == "local":
        base = _local_base_url().rstrip("/")
        return _stream_openai_compatible(
            f"{base}/chat/completions", _local_key() or "sk-noauth",
            _local_model(), messages, system, _local_timeout(),
        )
    if provider == "openai":
        return _stream_openai_compatible(
            "https://api.openai.com/v1/chat/completions", _openai_key(),
            _openai_model(), messages, system, 60,
        )
    if provider == "groq":
        return _stream_openai_compatible(
            "https://api.groq.com/openai/v1/chat/completions", _groq_key(),
            _groq_model(), messages, system, 60,
        )
    if provider == "openrouter":
        title = os.getenv("OPENROUTER_APP_NAME", "AuditBrain").strip()
        extra = {"X-Title": title}
        referer = os.getenv("OPENROUTER_SITE_URL", "").strip()
        if referer:
            extra["HTTP-Referer"] = referer
        return _stream_openai_compatible(
            "https://openrouter.ai/api/v1/chat/completions", _openrouter_key(),
            _openrouter_model(), messages, system, 60, extra_headers=extra,
        )
    raise ProviderUnavailable(f"Proveedor {provider} no soporta streaming")


def stream_chat_complete(messages, system=None):
    """Versión en streaming de chat_complete. Generador de deltas
    {"type": "token"|"done", ...}. Failover ANTES del primer token; si el
    primario no es streameable, levanta ProviderUnavailable para que el caller
    use el path no-streaming."""
    chain = _providers_with_keys()
    if not chain:
        raise ProviderUnavailable(
            "No hay proveedor LLM configurado. Define una API key "
            "(GEMINI_API_KEY, ANTHROPIC_API_KEY, etc.) o LOCAL_LLM_BASE_URL."
        )
    last_exc: ProviderUnavailable | None = None
    for provider in chain:
        if provider not in _STREAMABLE:
            last_exc = ProviderUnavailable(f"{provider} no streamea (usar fallback no-streaming)")
            continue
        emitted = False
        try:
            for delta in _stream_provider(provider, messages, system):
                emitted = True
                yield delta
            return  # el proveedor terminó correctamente
        except ProviderUnavailable as exc:
            last_exc = exc
            if emitted:
                raise  # ya se entregó texto: no hay failover transparente
            logging.getLogger("auditbrain").warning(
                "Streaming: proveedor %s falló antes del primer token (%s). Siguiente…",
                provider, exc,
            )
            continue
    raise last_exc or ProviderUnavailable("Streaming no disponible con la configuración actual.")
