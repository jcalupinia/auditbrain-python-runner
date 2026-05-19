"""Tests del registry de módulos sectoriales (Fase 2 · M3).

Cubre:
- /api/v1/modules devuelve los 11 módulos esperados, en orden, sin
  exponer el system_prompt al cliente.
- /api/v1/modules/{code} para uno específico y 404 para inexistente.
- El system prompt del chat incorpora el system_prompt del módulo
  cuando la conversación tiene module_code (mockeando el provider).
"""

import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.chat.providers import LLMResponse
from backend.app.db.session import SessionLocal, init_db
from backend.app.modules.registry import all_modules


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk():
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=password, role=Role.user)
    finally:
        db.close()
    return email, password


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


EXPECTED_CODES = [
    "ADV", "AUD", "TAX", "LEG", "FIN", "CYB", "DATA", "AUT", "GOV", "MKT", "CRE",
]


def test_module_registry_has_eleven_in_order():
    codes = [m.code for m in all_modules()]
    assert codes == EXPECTED_CODES


def test_list_modules_endpoint(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/modules", headers=_h(tok))
    assert r.status_code == 200
    body = r.json()
    assert [m["code"] for m in body] == EXPECTED_CODES
    # NUNCA se expone el system_prompt en la respuesta de la API
    for m in body:
        assert "system_prompt" not in m
        assert isinstance(m["suggested_actions"], list)
        assert isinstance(m["kpi_hints"], list)


def test_get_module_404(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/modules/XX", headers=_h(tok))
    assert r.status_code == 404


def test_get_module_one(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/modules/ADV", headers=_h(tok))
    assert r.status_code == 200
    assert r.json()["code"] == "ADV"
    assert r.json()["label"] == "Executive Advisory"


def test_modules_endpoint_requires_auth(client):
    r = client.get("/api/v1/modules")
    assert r.status_code == 401


def test_chat_system_prompt_includes_module_specifics(client, monkeypatch):
    captured = {}

    def fake_complete(messages, system=None):
        captured["system"] = system or ""
        return LLMResponse(content="ok", model="m", tokens_in=1, tokens_out=1)

    from backend.app.chat import service as chat_service

    monkeypatch.setattr(chat_service, "chat_complete", fake_complete)

    email, pw = _mk()
    tok = _login(client, email, pw)
    conv = client.post(
        "/api/v1/chat/conversations",
        headers=_h(tok),
        json={"module_code": "TAX"},
    ).json()
    r = client.post(
        f"/api/v1/chat/conversations/{conv['id']}/messages",
        headers=_h(tok),
        json={"content": "Caso"},
    )
    assert r.status_code == 200, r.text
    # El system prompt enviado al LLM contiene la frase específica del módulo TAX
    assert "Tax Partner" in captured["system"]
    assert "TAX · Tax Structuring" in captured["system"]
