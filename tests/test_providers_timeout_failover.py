"""Regresión: un timeout de lectura NO debe romper el failover ni dar HTTP 500.

Incidente 2026-08-05. `/api/v1/skill_run` devolvía 500 con traceback cuando
Anthropic tardaba más de 60s en responder. La cadena era:

    urllib.request.urlopen(timeout=60)
      -> TimeoutError            (timeout de LECTURA, no de conexión)
      -> escapa de _http_post    (solo capturaba HTTPError y URLError)
      -> escapa de chat_complete (solo captura ProviderUnavailable)
         => gemini y groq, configurados y sanos, NUNCA se probaban
      -> escapa de skill_run     (solo captura ProviderUnavailable)
         => FastAPI -> 500 en vez del 503 que declara el contrato OpenAPI

La raíz es una sutileza de la jerarquía de excepciones: `urllib` envuelve en
`URLError` los fallos de CONEXIÓN, pero un timeout de LECTURA sube crudo como
`TimeoutError`, que NO es subclase de `URLError` (son hermanas bajo `OSError`).

Disparador: el PR #105 subió max_tokens de 1024 a 8192. Sin streaming,
Anthropic no envía el primer byte hasta terminar de generar, y ~8192 tokens
no caben en 60s.
"""

import urllib.error

import pytest

from backend.app.chat import providers


# ---------------------------------------------------------------------------
# La jerarquía de excepciones que causó el bug
# ---------------------------------------------------------------------------

def test_timeout_error_no_es_subclase_de_urlerror():
    """El hecho que hacía que `except URLError` no atrapara el timeout."""
    assert not issubclass(TimeoutError, urllib.error.URLError)
    # Ambas cuelgan de OSError como hermanas: por eso el catch-all es OSError.
    assert issubclass(TimeoutError, OSError)
    assert issubclass(urllib.error.URLError, OSError)


# ---------------------------------------------------------------------------
# _http_post traduce los fallos de red a ProviderUnavailable
# ---------------------------------------------------------------------------

def _forzar_urlopen(monkeypatch, excepcion):
    def _boom(*args, **kwargs):
        raise excepcion

    monkeypatch.setattr(providers.urllib.request, "urlopen", _boom)


def test_http_post_convierte_timeout_de_lectura(monkeypatch):
    """El caso exacto del traceback de producción."""
    _forzar_urlopen(monkeypatch, TimeoutError("The read operation timed out"))

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {}, timeout=60)

    mensaje = str(exc.value)
    assert "60s" in mensaje
    assert "AUDITBRAIN_LLM_MAX_TOKENS" in mensaje, (
        "el mensaje debe orientar al operador hacia la causa real"
    )


def test_http_post_convierte_errores_de_socket(monkeypatch):
    """ConnectionResetError y similares también deben permitir failover."""
    _forzar_urlopen(monkeypatch, ConnectionResetError("connection reset by peer"))

    with pytest.raises(providers.ProviderUnavailable):
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {})


def test_http_post_sigue_convirtiendo_urlerror(monkeypatch):
    """No se rompe el comportamiento que ya existía (fallo de conexión)."""
    _forzar_urlopen(monkeypatch, urllib.error.URLError("dns failure"))

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {})
    assert "Error de red" in str(exc.value)


def test_http_post_sigue_convirtiendo_httperror(monkeypatch):
    """HTTPError va PRIMERO en la cadena: es subclase de URLError."""
    err = urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=None,
    )
    monkeypatch.setattr(err, "read", lambda: b'{"error":"rate_limit"}')
    _forzar_urlopen(monkeypatch, err)

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {})
    assert "HTTP 429" in str(exc.value)


# ---------------------------------------------------------------------------
# Lo que de verdad importaba: el failover vuelve a funcionar
# ---------------------------------------------------------------------------

def test_timeout_del_primario_hace_failover_al_siguiente(monkeypatch):
    """ESTE es el test que justifica el arreglo.

    Producción tiene configurados anthropic (primario), gemini y groq. Antes
    del fix, un timeout de Anthropic rompía el bucle de `chat_complete` y los
    otros dos nunca se intentaban. Ahora el timeout es un ProviderUnavailable
    y la cadena continúa.
    """
    monkeypatch.setattr(
        providers, "_providers_with_keys", lambda: ["anthropic", "gemini", "groq"]
    )

    intentados: list[str] = []

    def _anthropic_lento(messages, system):
        intentados.append("anthropic")
        # Exactamente lo que hacía urlopen en producción.
        raise providers.ProviderUnavailable(
            "El proveedor no respondió en 60s (timeout de lectura)."
        )

    def _gemini_ok(messages, system):
        intentados.append("gemini")
        return providers.LLMResponse(
            content="respuesta de respaldo",
            model="gemini-2.0-flash",
            tokens_in=None,
            tokens_out=None,
        )

    monkeypatch.setattr(providers, "_call_anthropic", _anthropic_lento)
    monkeypatch.setattr(providers, "_call_gemini", _gemini_ok)

    resultado = providers.chat_complete(messages=[{"role": "user", "content": "hola"}])

    assert intentados == ["anthropic", "gemini"], (
        "el failover no se activó: gemini debía tomar el relevo tras el timeout"
    )
    assert resultado.content == "respuesta de respaldo"


def test_si_todos_fallan_propaga_provider_unavailable(monkeypatch):
    """Con toda la cadena caída se propaga ProviderUnavailable — que skill_run
    traduce a 503, no a 500."""
    monkeypatch.setattr(providers, "_providers_with_keys", lambda: ["anthropic", "gemini"])

    def _falla(messages, system):
        raise providers.ProviderUnavailable("timeout")

    monkeypatch.setattr(providers, "_call_anthropic", _falla)
    monkeypatch.setattr(providers, "_call_gemini", _falla)

    with pytest.raises(providers.ProviderUnavailable):
        providers.chat_complete(messages=[{"role": "user", "content": "hola"}])


# ---------------------------------------------------------------------------
# Contrato HTTP: 503, nunca 500
# ---------------------------------------------------------------------------

def test_skill_run_devuelve_503_no_500_ante_timeout(client, monkeypatch):
    """El contrato OpenAPI del GPT declara 503 ('Ningún proveedor LLM
    disponible'). Un timeout debe respetarlo en vez de reventar en 500."""

    def _timeout(*args, **kwargs):
        raise providers.ProviderUnavailable(
            "El proveedor no respondió en 60s (timeout de lectura)."
        )

    monkeypatch.setattr(providers, "chat_complete", _timeout)

    r = client.post(
        "/api/v1/skill_run",
        json={"module_code": "AUD", "input": "prueba de timeout"},
    )

    assert r.status_code == 503, (
        f"esperado 503, recibido {r.status_code}: un timeout del proveedor no "
        "debe salir como error interno del servidor"
    )
    assert "60s" in r.json()["detail"]
