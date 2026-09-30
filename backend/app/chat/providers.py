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
    """No hay proveedor LLM configurado o el proveedor falló al responder.

    ``billing`` marca el subtipo "sin saldo / sin cuota" (HTTP 400/402/429 con
    un cuerpo de facturación). Es un fallo NO transitorio del proveedor: no
    tiene sentido reintentarlo, pero SÍ degradar a otro proveedor. Distinguirlo
    permite (a) un log claro y (b) un mensaje final accionable acorde al
    principio M16 ("la indisponibilidad de un proveedor no debe bloquear
    AuditBrain"). El kwarg es opcional para no romper ``ProviderUnavailable(msg)``.
    """

    def __init__(self, *args: object, billing: bool = False) -> None:
        super().__init__(*args)
        self.billing = billing


# Señales de agotamiento de saldo/cuota en el cuerpo de error del proveedor.
# Cubre a Anthropic ("your credit balance is too low"), OpenAI/OpenRouter
# ("insufficient_quota", "exceeded your current quota") y variantes genéricas
# de facturación. Se comparan en minúsculas contra el cuerpo crudo del error.
_BILLING_SIGNALS = (
    "credit balance",          # Anthropic: "Your credit balance is too low…"
    "insufficient_quota",      # OpenAI
    "insufficient quota",
    "exceeded your current quota",
    "billing",
    "payment required",
    "out of credits",
    "not enough credits",
)


def _is_billing_error(detail: str) -> bool:
    """True si el cuerpo de error indica saldo/cuota agotada (no un fallo transitorio)."""
    low = detail.lower()
    return any(signal in low for signal in _BILLING_SIGNALS)


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


_LOG = logging.getLogger("auditbrain")

# Proveedores sin coste (o de coste cero para AuditBrain) que un operador puede
# poner por delante de los de pago para cumplir M16. Se citan en el mensaje de
# error cuando toda la cadena cae por saldo/cuota.
_FREE_FALLBACKS = "LOCAL_LLM_BASE_URL (servidor propio), GEMINI_API_KEY, GROQ_API_KEY u OPENROUTER_API_KEY"


def _log_provider_failure(provider: str, exc: "ProviderUnavailable") -> None:
    """Registra el fallo de un proveedor distinguiendo saldo/cuota del resto."""
    if getattr(exc, "billing", False):
        _LOG.warning(
            "Proveedor %s sin saldo/cuota (%s). Degradando al siguiente (M16)…",
            provider, exc,
        )
    else:
        _LOG.warning(
            "Proveedor %s falló (%s). Probando siguiente…", provider, exc
        )


def _exhausted_chain_error(
    chain: list[str], last_exc: "ProviderUnavailable", saw_billing: bool
) -> "ProviderUnavailable":
    """Excepción a propagar cuando TODA la cadena falló.

    Si el bloqueo fue por saldo/cuota, devuelve un error accionable acorde a
    M16 (no depender de un proveedor de pago) en vez del texto crudo del
    proveedor ("Your credit balance is too low…"). En cualquier otro caso
    conserva la última excepción real.
    """
    if saw_billing:
        return ProviderUnavailable(
            "Todos los proveedores LLM configurados están sin saldo o cuota "
            f"(se intentaron: {', '.join(chain)}). Para no depender del saldo "
            "de un proveedor de pago, configura uno gratuito o local por "
            f"delante en Render: {_FREE_FALLBACKS}. Último detalle: {last_exc}",
            billing=True,
        )
    return last_exc


def chat_complete(
    messages: list[dict[str, str]],
    system: str | None = None,
) -> LLMResponse:
    """Envía una conversación al proveedor activo y devuelve la respuesta.

    Intenta el proveedor preferido y, si falla (sin saldo, modelo retirado,
    timeout puntual, etc.), reintenta con el siguiente proveedor configurado.
    Se prioriza la lista calculada en ``_providers_with_keys()``.

    Si NINGÚN proveedor responde con éxito, propaga un error accionable (o la
    última excepción real) para que la UI muestre el problema al usuario (no se
    inventa respuesta).
    """
    chain = _providers_with_keys()
    if not chain:
        raise ProviderUnavailable(
            "No hay proveedor LLM configurado en el servidor. Define una de: "
            "GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY, "
            "ANTHROPIC_API_KEY u OPENAI_API_KEY en Render."
        )
    last_exc: ProviderUnavailable | None = None
    saw_billing = False
    for provider in chain:
        try:
            return _dispatch(provider, messages, system)
        except ProviderUnavailable as exc:
            last_exc = exc
            saw_billing = saw_billing or getattr(exc, "billing", False)
            _log_provider_failure(provider, exc)
            continue
    assert last_exc is not None
    raise _exhausted_chain_error(chain, last_exc, saw_billing)


def _http_post(url: str, headers: dict[str, str], payload: dict, timeout: int = 60) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        # HTTP 402 (Payment Required) o un cuerpo de facturación (típico de un
        # 400/429 de Anthropic sin saldo) => marcar como billing para que el
        # failover degrade a un proveedor gratuito/local en vez de cortar.
        billing = e.code == 402 or _is_billing_error(detail)
        raise ProviderUnavailable(
            f"HTTP {e.code} del proveedor: {detail[:400]}", billing=billing
        )
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
        # HTTP 402 (Payment Required) o un cuerpo de facturación (típico de un
        # 400/429 de Anthropic sin saldo) => marcar como billing para que el
        # failover degrade a un proveedor gratuito/local en vez de cortar.
        billing = e.code == 402 or _is_billing_error(detail)
        raise ProviderUnavailable(
            f"HTTP {e.code} del proveedor: {detail[:400]}", billing=billing
        )
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
                # gpt-oss (modelo de razonamiento) emite primero varios
                # segundos de reasoning_content ANTES del content real. Lo
                # señalamos como "reasoning" para que la UI muestre actividad
                # ("Analizando…") en vez de un "Pensando…" que parece congelado.
                if delta.get("reasoning_content"):
                    yield {"type": "reasoning"}
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
    saw_billing = False
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
            saw_billing = saw_billing or getattr(exc, "billing", False)
            if emitted:
                raise  # ya se entregó texto: no hay failover transparente
            _LOG.warning(
                "Streaming: proveedor %s falló antes del primer token (%s). Siguiente…",
                provider, exc,
            )
            continue
    if last_exc is None:
        raise ProviderUnavailable("Streaming no disponible con la configuración actual.")
    raise _exhausted_chain_error(chain, last_exc, saw_billing)
