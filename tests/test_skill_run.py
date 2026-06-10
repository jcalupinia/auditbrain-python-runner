"""Tests del endpoint stateless /api/v1/skill_run.

No invocamos proveedores LLM reales: mockeamos providers.chat_complete con
monkeypatch. Validamos:
- Happy path: aplica la skill oficial del módulo y devuelve el output del LLM,
  con el system prompt correcto (módulo activo + skill por defecto).
- Sin proveedor LLM: 503 honesto (no se inventa respuesta).
- Auth por X-API-Key cuando AUDITBRAIN_API_KEY está configurada.
"""

import pytest

from backend.app.chat import providers as chat_providers
from backend.app.chat.providers import LLMResponse, ProviderUnavailable
from backend.app.core.config import settings


def test_skill_run_happy_path(client, monkeypatch):
    captured: dict = {}

    def fake_complete(messages, system=None):
        captured["messages"] = messages
        captured["system"] = system
        return LLMResponse(
            content="Informe de hallazgos generado.",
            model="claude-opus-4-8-test",
            tokens_in=120,
            tokens_out=350,
        )

    monkeypatch.setattr(chat_providers, "chat_complete", fake_complete)

    r = client.post(
        "/api/v1/skill_run",
        json={"module_code": "AUD", "input": "Encontré 3 facturas sin soporte."},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["output"] == "Informe de hallazgos generado."
    assert body["model"] == "claude-opus-4-8-test"
    assert body["module_code"] == "AUD"
    # AUD usa por defecto la skill audit-report-writer (primera del mapping).
    assert body["skill"] == "audit-report-writer"
    assert body["tokens_out"] == 350
    # El system prompt lleva el módulo activo y NO va vacío (trae el prompt oficial).
    assert "Módulo activo: AUD" in (captured["system"] or "")
    assert len(captured["system"]) > 200
    # Solo se manda el input del usuario como único turno.
    assert captured["messages"] == [
        {"role": "user", "content": "Encontré 3 facturas sin soporte."}
    ]


def test_skill_run_explicit_skill_id(client, monkeypatch):
    captured: dict = {}

    def fake_complete(messages, system=None):
        captured["system"] = system
        return LLMResponse(content="ok", model="m", tokens_in=1, tokens_out=1)

    monkeypatch.setattr(chat_providers, "chat_complete", fake_complete)

    r = client.post(
        "/api/v1/skill_run",
        json={
            "module_code": "TAX",
            "skill_id": "tax-structuring-brief",
            "input": "Holding en España con 3 operadoras.",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["skill"] == "tax-structuring-brief"


def test_skill_run_provider_unavailable(client, monkeypatch):
    def boom(messages, system=None):
        raise ProviderUnavailable("No hay proveedor LLM configurado.")

    monkeypatch.setattr(chat_providers, "chat_complete", boom)

    r = client.post(
        "/api/v1/skill_run",
        json={"module_code": "ADV", "input": "Resume esto."},
    )
    assert r.status_code == 503, r.text
    assert "proveedor" in r.json()["detail"].lower()


def test_skill_run_requires_api_key_when_auth_enabled(client, monkeypatch):
    # Activar auth: AUDITBRAIN_API_KEY definida.
    monkeypatch.setattr(settings, "API_KEY", "secreto-de-prueba")

    def fake_complete(messages, system=None):
        return LLMResponse(content="ok", model="m", tokens_in=1, tokens_out=1)

    monkeypatch.setattr(chat_providers, "chat_complete", fake_complete)

    # Sin X-API-Key -> 401
    r = client.post(
        "/api/v1/skill_run", json={"module_code": "ADV", "input": "x"}
    )
    assert r.status_code == 401, r.text

    # Con X-API-Key correcta -> 200
    r = client.post(
        "/api/v1/skill_run",
        headers={"X-API-Key": "secreto-de-prueba"},
        json={"module_code": "ADV", "input": "x"},
    )
    assert r.status_code == 200, r.text
