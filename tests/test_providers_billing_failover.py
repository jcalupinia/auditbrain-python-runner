"""Regresión: quedarse sin saldo en un proveedor NO debe bloquear AuditBrain.

Incidente 2026-09-24 (módulo LEG / "Abogado"). Una skill vía `/api/v1/skill_run`
no se ejecutó porque el proveedor devolvió:

    HTTP 400: "Your credit balance is too low to access the Anthropic API."

El enrutamiento de proveedores es GLOBAL y "gratis primero" (no depende del
módulo: LEG, AUD y TAX comparten cadena). El principio M16 del ecosistema
—documentado en `auditbrain-site`— exige que la indisponibilidad de un
proveedor (incluido quedarse sin saldo) NO bloquee a AuditBrain: debe degradar
a otro proveedor y, si se agota toda la cadena, dar un error accionable en vez
del texto crudo del proveedor.

Estos tests fijan ese contrato:
  1. Un cuerpo de facturación (o un HTTP 402) se marca como ``billing``.
  2. Un fallo de saldo del primario hace failover al siguiente proveedor.
  3. Si TODA la cadena cae por saldo, el mensaje final orienta a configurar un
     proveedor gratuito/local (no repite sólo "credit balance too low").
"""

import urllib.error

import pytest

from backend.app.chat import providers


# ---------------------------------------------------------------------------
# 1. Detección: cuerpo de facturación / HTTP 402 => billing=True
# ---------------------------------------------------------------------------

def _forzar_httperror(monkeypatch, code: str | int, body: bytes) -> None:
    err = urllib.error.HTTPError(
        url="https://api.anthropic.com/v1/messages",
        code=int(code),
        msg="error",
        hdrs=None,
        fp=None,
    )
    monkeypatch.setattr(err, "read", lambda: body)

    def _boom(*args, **kwargs):
        raise err

    monkeypatch.setattr(providers.urllib.request, "urlopen", _boom)


def test_cuerpo_de_saldo_bajo_se_marca_billing(monkeypatch):
    """El caso exacto del incidente: 400 con 'credit balance is too low'."""
    body = (
        b'{"type":"error","error":{"type":"invalid_request_error",'
        b'"message":"Your credit balance is too low to access the Anthropic API."}}'
    )
    _forzar_httperror(monkeypatch, 400, body)

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {})

    assert exc.value.billing is True
    assert "HTTP 400" in str(exc.value)


def test_http_402_se_trata_como_saldo(monkeypatch):
    """402 Payment Required es billing aunque el cuerpo no traiga la frase."""
    _forzar_httperror(monkeypatch, 402, b'{"error":"payment required"}')

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {})

    assert exc.value.billing is True


def test_insufficient_quota_de_openai_es_billing(monkeypatch):
    """OpenAI/OpenRouter usan 'insufficient_quota'."""
    _forzar_httperror(monkeypatch, 429, b'{"error":{"code":"insufficient_quota"}}')

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.openai.com/v1/chat/completions", {}, {})

    assert exc.value.billing is True


def test_error_no_de_saldo_no_se_marca_billing(monkeypatch):
    """Un 500 genérico NO es billing: sigue siendo un fallo transitorio."""
    _forzar_httperror(monkeypatch, 500, b'{"error":"internal"}')

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers._http_post("https://api.anthropic.com/v1/messages", {}, {})

    assert exc.value.billing is False


# ---------------------------------------------------------------------------
# 2. Failover: sin saldo en el primario => tomar el siguiente proveedor
# ---------------------------------------------------------------------------

def test_saldo_bajo_del_primario_hace_failover(monkeypatch):
    """Reproduce el incidente con un proveedor gratuito detrás: NO debe cortar."""
    monkeypatch.setattr(
        providers, "_providers_with_keys", lambda: ["anthropic", "gemini"]
    )

    intentados: list[str] = []

    def _anthropic_sin_saldo(messages, system):
        intentados.append("anthropic")
        raise providers.ProviderUnavailable(
            "HTTP 400 del proveedor: Your credit balance is too low", billing=True
        )

    def _gemini_ok(messages, system):
        intentados.append("gemini")
        return providers.LLMResponse(
            content="respuesta de respaldo", model="gemini-2.0-flash",
            tokens_in=None, tokens_out=None,
        )

    monkeypatch.setattr(providers, "_call_anthropic", _anthropic_sin_saldo)
    monkeypatch.setattr(providers, "_call_gemini", _gemini_ok)

    resultado = providers.chat_complete(messages=[{"role": "user", "content": "hola"}])

    assert intentados == ["anthropic", "gemini"], (
        "el failover por saldo no se activó: gemini debía tomar el relevo"
    )
    assert resultado.content == "respuesta de respaldo"


# ---------------------------------------------------------------------------
# 3. Cadena agotada por saldo => mensaje accionable acorde a M16
# ---------------------------------------------------------------------------

def test_toda_la_cadena_sin_saldo_da_mensaje_accionable(monkeypatch):
    monkeypatch.setattr(
        providers, "_providers_with_keys", lambda: ["anthropic", "openai"]
    )

    def _sin_saldo(messages, system):
        raise providers.ProviderUnavailable(
            "HTTP 400 del proveedor: Your credit balance is too low", billing=True
        )

    monkeypatch.setattr(providers, "_call_anthropic", _sin_saldo)
    monkeypatch.setattr(providers, "_call_openai", _sin_saldo)

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers.chat_complete(messages=[{"role": "user", "content": "hola"}])

    mensaje = str(exc.value)
    assert exc.value.billing is True
    # Nombra los proveedores intentados y orienta a un fallback gratuito/local.
    assert "anthropic" in mensaje and "openai" in mensaje
    assert "GEMINI_API_KEY" in mensaje
    assert "LOCAL_LLM_BASE_URL" in mensaje


def test_fallo_no_de_saldo_conserva_la_excepcion_real(monkeypatch):
    """Si el motivo NO fue saldo, se propaga el error real (p. ej. timeout),
    sin el envoltorio de billing."""
    monkeypatch.setattr(providers, "_providers_with_keys", lambda: ["anthropic", "gemini"])

    def _timeout(messages, system):
        raise providers.ProviderUnavailable("El proveedor no respondió en 60s")

    monkeypatch.setattr(providers, "_call_anthropic", _timeout)
    monkeypatch.setattr(providers, "_call_gemini", _timeout)

    with pytest.raises(providers.ProviderUnavailable) as exc:
        providers.chat_complete(messages=[{"role": "user", "content": "hola"}])

    assert exc.value.billing is False
    assert "60s" in str(exc.value)
