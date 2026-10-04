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


# --------------------------------------------------------------------------- #
#  5 · Un timeout de CHAT corto NO estrangula la extracción (piso propio)      #
# --------------------------------------------------------------------------- #
def test_timeout_local_normal_respeta_la_env_var(monkeypatch):
    """Fuera de extracción, el timeout local es LOCAL_LLM_TIMEOUT_SECONDS tal cual."""
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "15")  # failover veloz del chat
    assert not providers._EN_EXTRACCION.get()
    assert providers._local_timeout() == 15


def test_extraccion_usa_timeout_dedicado_no_el_corto_del_chat(monkeypatch):
    """Un operador bajó el timeout del chat a 15s para failover veloz a la nube.
    Esa env var NO debe cortar la lectura del documento en el servidor local: la
    extracción usa su timeout DEDICADO (150s por defecto), independiente del chat."""
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "15")

    timeouts_vistos: list[int] = []

    def _stream_captura(messages, system=None, *, temperature=None):
        # Lo que ve el gateway local al abrir el stream: el timeout vigente.
        timeouts_vistos.append(providers._local_timeout())
        yield {"type": "token", "text": "{}"}
        yield {"type": "done", "model": "auditia-rutina"}

    monkeypatch.setattr(providers, "stream_chat_complete", _stream_captura)
    providers.completar_para_extraccion([{"role": "user", "content": "doc largo"}])

    assert timeouts_vistos == [150], (
        "durante la extracción el timeout local debe ser el dedicado (150s), no "
        "los 15s del failover de chat"
    )
    # Y al salir, la bandera queda limpia (no contamina requests de chat).
    assert not providers._EN_EXTRACCION.get()
    assert providers._local_timeout() == 15


def test_timeout_de_extraccion_es_dedicado_e_independiente_del_general(monkeypatch):
    """El timeout de extracción es configurable y ACOTADO: no hereda un timeout de
    chat alto (así el failover a la nube ocurre a tiempo cuando el local va lento)."""
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_SECONDS", "600")  # chat general alto
    monkeypatch.setenv("LOCAL_LLM_TIMEOUT_EXTRACCION_SECONDS", "200")
    tok = providers._EN_EXTRACCION.set(True)
    try:
        assert providers._local_timeout() == 200  # el dedicado, no el 600 del chat
    finally:
        providers._EN_EXTRACCION.reset(tok)


def test_extraccion_failover_a_la_nube_si_el_local_excede_el_presupuesto(monkeypatch):
    """Local LENTO (streamea despacio y se pasa del presupuesto wall-clock): se
    descarta su intento y la extracción cae a un proveedor de nube rápido. Además,
    queda STICKY: el siguiente bloque del documento va directo a la nube."""
    monkeypatch.setenv("LOCAL_LLM_EXTRACCION_BUDGET_SECONDS", "30")
    monkeypatch.setattr(providers, "_extraccion_budget", lambda: 0)  # fuerza "excedido" al primer delta

    def _stream_lento(messages, system=None, *, temperature=None):
        yield {"type": "token", "text": "{"}   # emite algo, pero ya pasó el presupuesto
        yield {"type": "token", "text": "}"}

    nube = {"llamadas": 0}

    def _no_stream(messages, system=None, *, temperature=None, exclude=()):
        nube["llamadas"] += 1
        assert "local" in exclude      # el failover salta el local lento
        return providers.LLMResponse(content='{"filas": []}', model="gemini", tokens_in=None, tokens_out=None)

    monkeypatch.setattr(providers, "stream_chat_complete", _stream_lento)
    monkeypatch.setattr(providers, "chat_complete", _no_stream)
    _reset = providers._EXTRACCION_SKIP_LOCAL.set(False)
    try:
        r1 = providers.completar_para_extraccion([{"role": "user", "content": "bloque 1"}])
        assert r1.model == "gemini" and providers._EXTRACCION_SKIP_LOCAL.get() is True
        # Sticky: el segundo bloque NI SIQUIERA intenta el stream local.
        def _stream_no_debe_llamarse(*a, **k):
            raise AssertionError("no debe intentarse el local tras marcarse lento")
            yield  # pragma: no cover
        monkeypatch.setattr(providers, "stream_chat_complete", _stream_no_debe_llamarse)
        r2 = providers.completar_para_extraccion([{"role": "user", "content": "bloque 2"}])
        assert r2.model == "gemini" and nube["llamadas"] == 2
    finally:
        providers._EXTRACCION_SKIP_LOCAL.reset(_reset)


# --------------------------------------------------------------------------- #
#  6 · Techo de tokens: la extracción da más margen al modelo de razonamiento #
# --------------------------------------------------------------------------- #
def test_max_tokens_normal_respeta_la_env_var(monkeypatch):
    """Fuera de extracción, el techo es AUDITBRAIN_LLM_MAX_TOKENS tal cual."""
    monkeypatch.setenv("AUDITBRAIN_LLM_MAX_TOKENS", "8192")
    assert not providers._EN_EXTRACCION.get()
    assert providers._max_tokens() == 8192


def test_extraccion_sube_el_techo_de_tokens_para_que_el_modelo_responda(monkeypatch):
    """Incidente de la carta: el modelo de razonamiento local gastaba los 8192
    tokens pensando y devolvía contenido vacío. En extracción el techo sube a un
    piso propio (16384 por defecto) para dejarle espacio a razonar Y responder."""
    monkeypatch.setenv("AUDITBRAIN_LLM_MAX_TOKENS", "8192")
    tok = providers._EN_EXTRACCION.set(True)
    try:
        assert providers._max_tokens() == 16384
    finally:
        providers._EN_EXTRACCION.reset(tok)
    # Fuera del contexto de extracción, vuelve al techo normal.
    assert providers._max_tokens() == 8192


def test_techo_de_extraccion_nunca_baja_del_general(monkeypatch):
    """Si el techo general ya es mayor que el piso de extracción, manda el mayor."""
    monkeypatch.setenv("AUDITBRAIN_LLM_MAX_TOKENS", "32000")
    monkeypatch.setenv("AUDITBRAIN_LLM_MAX_TOKENS_EXTRACCION", "16384")
    tok = providers._EN_EXTRACCION.set(True)
    try:
        assert providers._max_tokens() == 32000
    finally:
        providers._EN_EXTRACCION.reset(tok)
