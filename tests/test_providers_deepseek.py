"""DeepSeek como proveedor de nube (API compatible con OpenAI) y corrección del
modelo por defecto de Gemini (el anterior gemini-2.0-flash fue retirado).

Contrato:
  1. Defaults vigentes: Gemini = gemini-2.5-flash-lite; DeepSeek = deepseek-flash.
  2. Con DEEPSEEK_API_KEY, 'deepseek' entra en la cadena, en el orden
     local > gemini > groq > deepseek > openrouter > anthropic > openai.
  3. _dispatch('deepseek') llega al endpoint OpenAI-compatible de DeepSeek.
  4. deepseek es streameable (va por _stream_openai_compatible al host de DeepSeek).
"""
import pytest

from backend.app.chat import providers

_KEYS = ("LOCAL_LLM_BASE_URL", "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY",
         "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
         "AUDITBRAIN_LLM_PROVIDER", "GEMINI_MODEL", "DEEPSEEK_MODEL")


@pytest.fixture
def limpio(monkeypatch):
    for k in _KEYS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_defaults_vigentes(limpio):
    assert providers._gemini_model() == "gemini-2.5-flash-lite"   # no el retirado gemini-2.0-flash
    assert providers._deepseek_model() == "deepseek-flash"        # no el retirado deepseek-chat


def test_deepseek_entra_en_la_cadena_y_en_su_orden(limpio):
    # Solo DeepSeek y Groq configurados → orden groq antes que deepseek.
    limpio.setenv("GROQ_API_KEY", "gk")
    limpio.setenv("DEEPSEEK_API_KEY", "dk")
    assert providers._providers_with_keys() == ["groq", "deepseek"]
    assert providers.available_provider() == "groq"
    # Como override explícito, DeepSeek va primero.
    limpio.setenv("AUDITBRAIN_LLM_PROVIDER", "deepseek")
    assert providers._providers_with_keys()[0] == "deepseek"


def test_estado_reporta_deepseek(limpio):
    limpio.setenv("DEEPSEEK_API_KEY", "dk")
    assert providers.estado_proveedores()["configurados"]["deepseek"] is True


def test_dispatch_deepseek_usa_endpoint_openai_compatible(limpio):
    limpio.setenv("DEEPSEEK_API_KEY", "dk")
    capturado = {}

    def _fake(url, key, model, messages, system, temperature=None, **kw):
        capturado.update(url=url, key=key, model=model)
        return providers.LLMResponse(content="ok", model=model, tokens_in=None, tokens_out=None)

    limpio.setattr(providers, "_call_openai_compatible", _fake)
    r = providers._dispatch("deepseek", [{"role": "user", "content": "x"}], None, 0)
    assert r.content == "ok"
    assert capturado["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert capturado["key"] == "dk" and capturado["model"] == "deepseek-flash"


def test_deepseek_es_streameable(limpio):
    assert "deepseek" in providers._STREAMABLE
    limpio.setenv("DEEPSEEK_API_KEY", "dk")
    capturado = {}

    def _fake_stream(url, key, model, messages, system, timeout, extra_headers=None, temperature=None):
        capturado.update(url=url, model=model)
        yield {"type": "token", "text": "ok"}

    limpio.setattr(providers, "_stream_openai_compatible", _fake_stream)
    list(providers._stream_provider("deepseek", [{"role": "user", "content": "x"}], None))
    assert capturado["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert capturado["model"] == "deepseek-flash"
