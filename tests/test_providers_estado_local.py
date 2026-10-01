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


def test_resolucion_forzada_a_ipv4():
    """El gateway local (*.ts.net) es dual-stack y Render no rutea IPv6: importar
    providers debe forzar IPv4 en la resolución stdlib (urllib.request la usa).
    `localhost` puede resolver a 127.0.0.1 (IPv4) y ::1 (IPv6); con el forzado
    solo deben volver entradas IPv4."""
    import socket
    from backend.app.chat import providers  # noqa: F401  (el import aplica el parche)

    assert getattr(socket, "_auditbrain_ipv4_forzado", False) is True
    res = socket.getaddrinfo("localhost", 80)
    assert res, "localhost no resolvió"
    assert all(familia == socket.AF_INET for familia, *_ in res), (
        "la resolución devolvió entradas no-IPv4 pese al forzado"
    )
    # Quien pida IPv6 explícito se respeta (no rompemos ese camino).
    assert socket.getaddrinfo("::1", 80, socket.AF_INET6)[0][0] == socket.AF_INET6
