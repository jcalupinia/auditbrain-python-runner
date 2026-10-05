"""El servidor local NO debe exceder su ventana de contexto (max-model-len).

Incidente 2026-10-05 (extracción del informe): el gateway local servía con
max-model-len = 24576 y la extracción pedía 16384 de salida; con ~8193 de entrada
el total daba 24577 y el local fallaba SIEMPRE con ContextWindowExceededError,
cayendo a la nube (sin saldo). El techo de salida del local debe acotarse a lo que
cabe en su ventana; la nube conserva el techo completo.
"""
import pytest

from backend.app.chat import providers


@pytest.fixture
def limpio(monkeypatch):
    for k in ("LOCAL_LLM_CONTEXT_WINDOW", "AUDITBRAIN_LLM_MAX_TOKENS",
              "AUDITBRAIN_LLM_MAX_TOKENS_EXTRACCION"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_cap_local_deja_espacio_para_la_salida(limpio):
    # Un prompt de ~8193 tokens (≈12300 chars) con ventana 24576 y techo 16384
    # NO puede pedir 16384 de salida: debe recortarse a lo que cabe.
    limpio.setenv("AUDITBRAIN_LLM_MAX_TOKENS_EXTRACCION", "16384")
    limpio.setenv("LOCAL_LLM_CONTEXT_WINDOW", "24576")
    tok = providers._EN_EXTRACCION.set(True)
    try:
        chars = 12300
        messages = [{"role": "user", "content": "x" * chars}]
        cap = providers._local_max_tokens(messages, None)
    finally:
        providers._EN_EXTRACCION.reset(tok)
    input_est = int(chars / 1.5) + 1
    assert cap <= 24576 - input_est  # cabe con margen
    assert input_est + cap < 24576   # input + output NO supera la ventana
    assert cap > 0


def test_cap_no_supera_el_techo_pedido(limpio):
    # Con ventana enorme, el cap no infla por encima del techo general.
    limpio.setenv("LOCAL_LLM_CONTEXT_WINDOW", "131072")
    limpio.setenv("AUDITBRAIN_LLM_MAX_TOKENS", "8192")
    messages = [{"role": "user", "content": "hola"}]
    assert providers._local_max_tokens(messages, None) == 8192


def test_prompt_que_casi_llena_la_ventana_deja_minimo(limpio):
    limpio.setenv("LOCAL_LLM_CONTEXT_WINDOW", "24576")
    # ~24000 tokens de entrada (≈36000 chars): casi no queda espacio.
    messages = [{"role": "user", "content": "x" * 36000}]
    assert providers._local_max_tokens(messages, None) == 1024


def test_solo_el_local_recibe_el_recorte(limpio, monkeypatch):
    """La nube (deepseek) recibe el techo completo; el local, el recortado."""
    limpio.setenv("LOCAL_LLM_CONTEXT_WINDOW", "24576")
    limpio.setenv("AUDITBRAIN_LLM_MAX_TOKENS_EXTRACCION", "16384")
    limpio.setenv("LOCAL_LLM_BASE_URL", "http://localhost:4000/v1")
    limpio.setenv("DEEPSEEK_API_KEY", "dk")
    vistos = {}

    def _fake(url, key, model, messages, system, extra_headers=None, timeout=60,
              temperature=None, max_tokens=None):
        vistos[url] = max_tokens
        return providers.LLMResponse(content="ok", model=model, tokens_in=None, tokens_out=None)

    monkeypatch.setattr(providers, "_call_openai_compatible", _fake)
    tok = providers._EN_EXTRACCION.set(True)
    try:
        msgs = [{"role": "user", "content": "x" * 12300}]
        providers._call_local(msgs, None)
        providers._call_deepseek(msgs, None)
    finally:
        providers._EN_EXTRACCION.reset(tok)

    local_url = [u for u in vistos if "localhost" in u][0]
    ds_url = [u for u in vistos if "deepseek" in u][0]
    assert vistos[local_url] is not None and vistos[local_url] < 16384  # recortado
    assert vistos[ds_url] is None  # nube: techo completo (_max_tokens dentro)
