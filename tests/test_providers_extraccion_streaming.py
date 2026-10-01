"""Extracción afinada: streaming + temperature=0 (agilizar el servidor local).

Contrato de `providers.completar_para_extraccion` y del threading de
`temperature`:
  1. Consume el stream y ACUMULA el texto completo (los tokens del local fluyen,
     así la conexión no se queda muda y no se corta por timeout).
  2. El `reasoning` previo de gpt-oss no ensucia el texto.
  3. Cae al no-streaming (`chat_complete`) si el stream viene vacío o si el
     primario no streamea / falla antes del primer token — SIEMPRE con
     `temperature=0`.
  4. `temperature` viaja al payload solo cuando no es None (no se fuerza en el
     resto de la plataforma, que sigue sin enviar el campo).
  5. La extracción (`extraccion_ia`) usa este helper por defecto.
"""
import pytest

from backend.app.chat import providers


# --------------------------------------------------------------------------- #
#  1 · completar_para_extraccion: acumula el stream                           #
# --------------------------------------------------------------------------- #
def test_completar_para_extraccion_acumula_el_stream(monkeypatch):
    vistos = {}

    def _stream(messages, system=None, *, temperature=None):
        vistos["temperature"] = temperature
        yield {"type": "reasoning"}  # ruido de gpt-oss: no debe entrar al texto
        yield {"type": "token", "text": '{"filas": '}
        yield {"type": "token", "text": "[]}"}
        yield {"type": "done", "model": "auditia-rutina", "tokens_out": 3}

    monkeypatch.setattr(providers, "stream_chat_complete", _stream)
    resp = providers.completar_para_extraccion([{"role": "user", "content": "x"}], system="s")
    assert resp.content == '{"filas": []}'
    assert resp.model == "auditia-rutina"
    assert vistos["temperature"] == 0  # la extracción pide salida determinista


# --------------------------------------------------------------------------- #
#  2 · Fallback a no-streaming                                                 #
# --------------------------------------------------------------------------- #
def test_cae_a_no_stream_si_el_stream_viene_vacio(monkeypatch):
    def _stream_vacio(messages, system=None, *, temperature=None):
        yield {"type": "reasoning"}  # solo reasoning, sin content
        yield {"type": "done", "model": "x"}

    llamado = {}

    def _no_stream(messages, system=None, *, temperature=None):
        llamado["temperature"] = temperature
        return providers.LLMResponse(content='{"filas": []}', model="nube", tokens_in=1, tokens_out=1)

    monkeypatch.setattr(providers, "stream_chat_complete", _stream_vacio)
    monkeypatch.setattr(providers, "chat_complete", _no_stream)
    resp = providers.completar_para_extraccion([{"role": "user", "content": "x"}])
    assert resp.content == '{"filas": []}' and resp.model == "nube"
    assert llamado["temperature"] == 0  # el fallback también es determinista


def test_cae_a_no_stream_si_el_primario_no_streamea(monkeypatch):
    def _stream_rechaza(messages, system=None, *, temperature=None):
        raise providers.ProviderUnavailable("gemini no streamea (usar fallback no-streaming)")
        yield  # pragma: no cover  (lo vuelve generador)

    def _no_stream(messages, system=None, *, temperature=None):
        return providers.LLMResponse(content="ok", model="gemini", tokens_in=None, tokens_out=None)

    monkeypatch.setattr(providers, "stream_chat_complete", _stream_rechaza)
    monkeypatch.setattr(providers, "chat_complete", _no_stream)
    resp = providers.completar_para_extraccion([{"role": "user", "content": "x"}])
    assert resp.content == "ok" and resp.model == "gemini"


# --------------------------------------------------------------------------- #
#  3 · temperature viaja al payload solo cuando no es None                    #
# --------------------------------------------------------------------------- #
def test_temperature_en_payload_openai_compatible_solo_si_no_es_none(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://gateway-local:8080/v1")
    capturado = {}

    def _fake_post(url, headers, payload, timeout=60):
        capturado["payload"] = payload
        return {"choices": [{"message": {"content": "pong"}}], "model": "auditia-rutina"}

    monkeypatch.setattr(providers, "_http_post", _fake_post)

    providers._call_local([{"role": "user", "content": "x"}], None, 0)
    assert capturado["payload"]["temperature"] == 0

    capturado.clear()
    providers._call_local([{"role": "user", "content": "x"}], None)  # sin temperature
    assert "temperature" not in capturado["payload"]


def test_temperature_en_payload_anthropic_solo_si_no_es_none(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    capturado = {}

    def _fake_post(url, headers, payload, timeout=60):
        capturado["payload"] = payload
        return {"content": [{"text": "ok"}], "model": "claude", "usage": {}}

    monkeypatch.setattr(providers, "_http_post", _fake_post)

    providers._call_anthropic([{"role": "user", "content": "x"}], None, 0)
    assert capturado["payload"]["temperature"] == 0

    capturado.clear()
    providers._call_anthropic([{"role": "user", "content": "x"}], None)
    assert "temperature" not in capturado["payload"]


# --------------------------------------------------------------------------- #
#  4 · La extracción usa el helper afinado por defecto                        #
# --------------------------------------------------------------------------- #
def test_extraccion_usa_completar_para_extraccion_por_defecto(monkeypatch):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://gateway-local:8080/v1")
    monkeypatch.setenv("NIIF_EXTRACCION_ENABLED", "true")
    from backend.app.aud.niif.ciclo import extraccion_ia

    monkeypatch.setattr(extraccion_ia, "EXTRACCION_ENABLED", True)
    chat = extraccion_ia._chat_por_defecto()
    assert chat is providers.completar_para_extraccion
