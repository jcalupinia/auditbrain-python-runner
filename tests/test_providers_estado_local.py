"""Diagnóstico de la cadena de IA y ping al servidor local.

Verifica el contrato del endpoint `/api/v1/chat/ia/estado`:
  1. El orden respeta «local primero, Anthropic al final».
  2. `probar_local()` reporta OK cuando el gateway local responde.
  3. `probar_local()` reporta el fallo real cuando el local NO responde,
     sin inventar (y marca `configurado=False` si falta LOCAL_LLM_BASE_URL).
"""
import pytest

from backend.app.chat import providers


@pytest.fixture(autouse=True)
def _env_limpio(monkeypatch):
    for k in ("AUDITBRAIN_LLM_PROVIDER", "LOCAL_LLM_BASE_URL", "GEMINI_API_KEY",
              "GROQ_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)


def test_orden_local_primero_anthropic_al_final(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://gateway-local:8080/v1")
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    estado = providers.estado_proveedores()
    assert estado["orden"] == ["local", "gemini", "groq", "anthropic"]
    assert estado["preferido"] == "local"
    assert estado["orden"].index("local") < estado["orden"].index("anthropic")


def test_local_sin_url_no_esta_configurado():
    r = providers.probar_local()
    assert r["configurado"] is False and r["ok"] is False
    assert "LOCAL_LLM_BASE_URL" in r["detalle"]


def test_local_conectado(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://gateway-local:8080/v1")
    monkeypatch.setattr(providers, "_call_local",
                        lambda messages, system: providers.LLMResponse(content="pong", model="local", tokens_in=1, tokens_out=1))
    r = providers.probar_local()
    assert r["configurado"] is True and r["ok"] is True
    assert "respondió" in r["detalle"] and "latencia_ms" in r


def test_local_caido_reporta_el_fallo_real(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://gateway-local:8080/v1")

    def _caido(messages, system):
        raise providers.ProviderUnavailable("Connection refused")

    monkeypatch.setattr(providers, "_call_local", _caido)
    r = providers.probar_local()
    assert r["configurado"] is True and r["ok"] is False
    assert "Connection refused" in r["detalle"]


def test_timeout_local_default_180_y_override(monkeypatch):
    """El timeout del local es 180s por defecto (la extracción pide un JSON grande
    sin streaming y 15s se quedaba corto), y se puede sobreescribir por env var."""
    monkeypatch.delenv("LOCAL_LLM_TIMEOUT_SECONDS", raising=False)
    assert providers._local_timeout() == 180
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "45")
    assert providers._local_timeout() == 45
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "no-numero")
    assert providers._local_timeout() == 180
