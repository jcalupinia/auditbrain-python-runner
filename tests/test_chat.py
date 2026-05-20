"""Tests del chat cognitivo (Fase 2 · M2).

No invocamos proveedores LLM reales: mockeamos chat_complete con
monkeypatch para validar:
- Creación de conversación scope org + proyecto accesible
- Persistencia de mensajes (user + assistant)
- Aislamiento estricto: un usuario no ve conversaciones de otro
- Sin proveedor configurado: el mensaje del usuario se persiste y
  la respuesta es None con provider_error legible (sin inventar)
"""

import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.chat import providers as chat_providers
from backend.app.chat.providers import LLMResponse, ProviderUnavailable
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk(role: Role = Role.user):
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=password, role=role)
    finally:
        db.close()
    return email, password


def _login(client, email, pw):
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": pw}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_create_conversation_minimal(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.post("/api/v1/chat/conversations", headers=_h(tok), json={})
    assert r.status_code == 201, r.text
    conv = r.json()
    assert conv["title"] == "Nueva conversación"
    assert conv["project_id"] is None


def test_send_message_with_provider_mocked(client, monkeypatch):
    captured: dict = {}

    def fake_complete(messages, system=None):
        captured["messages"] = messages
        captured["system"] = system
        return LLMResponse(
            content="Respuesta sintetizada del agente.",
            model="claude-sonnet-4-6-test",
            tokens_in=42,
            tokens_out=7,
        )

    monkeypatch.setattr(chat_providers, "chat_complete", fake_complete)
    # Y desde service.* también:
    from backend.app.chat import service as chat_service

    monkeypatch.setattr(chat_service, "chat_complete", fake_complete)

    email, pw = _mk()
    tok = _login(client, email, pw)
    conv = client.post(
        "/api/v1/chat/conversations",
        headers=_h(tok),
        json={"module_code": "ADV"},
    ).json()

    r = client.post(
        f"/api/v1/chat/conversations/{conv['id']}/messages",
        headers=_h(tok),
        json={"content": "¿Cómo planteo un Due Diligence rápido?"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider_error"] is None
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["model"] == "claude-sonnet-4-6-test"
    # System prompt contiene el módulo activo
    assert "ADV" in (captured["system"] or "")
    # El historial enviado al provider incluye solo el primer turno
    assert len(captured["messages"]) == 1

    detail = client.get(
        f"/api/v1/chat/conversations/{conv['id']}", headers=_h(tok)
    ).json()
    assert len(detail["messages"]) == 2
    # Autotitulado
    assert "Due Diligence" in detail["title"]


def test_send_message_without_provider_returns_error_not_fake(client, monkeypatch):
    def fake_complete(messages, system=None):
        raise ProviderUnavailable("Sin clave configurada.")

    from backend.app.chat import service as chat_service

    monkeypatch.setattr(chat_service, "chat_complete", fake_complete)

    email, pw = _mk()
    tok = _login(client, email, pw)
    conv = client.post("/api/v1/chat/conversations", headers=_h(tok), json={}).json()
    r = client.post(
        f"/api/v1/chat/conversations/{conv['id']}/messages",
        headers=_h(tok),
        json={"content": "hola"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["assistant_message"] is None
    assert body["provider_error"]
    # Honestidad: el mensaje del usuario sí persiste
    detail = client.get(
        f"/api/v1/chat/conversations/{conv['id']}", headers=_h(tok)
    ).json()
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["role"] == "user"


def test_cross_user_isolation(client):
    a_email, a_pw = _mk()
    b_email, b_pw = _mk()
    a_tok = _login(client, a_email, a_pw)
    b_tok = _login(client, b_email, b_pw)
    conv = client.post("/api/v1/chat/conversations", headers=_h(a_tok), json={}).json()
    # B no ve la conversación de A
    r = client.get("/api/v1/chat/conversations", headers=_h(b_tok))
    assert r.status_code == 200
    assert all(c["id"] != conv["id"] for c in r.json())
    # B no puede leerla por id
    r = client.get(f"/api/v1/chat/conversations/{conv['id']}", headers=_h(b_tok))
    assert r.status_code == 404


def test_conversation_with_inaccessible_project_rejected(client):
    """Crear conversación atada a un proyecto al que no perteneces -> 403."""
    admin_email, admin_pw = _mk(Role.admin)
    admin_tok = _login(client, admin_email, admin_pw)
    cid = client.post(
        "/api/v1/context/clients", headers=_h(admin_tok), json={"name": "Cliente Z"}
    ).json()["id"]
    pid = client.post(
        "/api/v1/context/projects",
        headers=_h(admin_tok),
        json={"client_id": cid, "name": "Proyecto privado"},
    ).json()["id"]

    user_email, user_pw = _mk()
    user_tok = _login(client, user_email, user_pw)
    r = client.post(
        "/api/v1/chat/conversations",
        headers=_h(user_tok),
        json={"project_id": pid},
    )
    assert r.status_code == 403


def test_provider_availability_defaults_to_none(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert chat_providers.available_provider() is None


def test_gemini_available_when_key_set(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assert chat_providers.available_provider() == "gemini"


def test_failover_when_primary_provider_fails(monkeypatch):
    """Si el preferido (Anthropic) revienta sin saldo, debe caer a Gemini
    automáticamente sin que el usuario tenga que cambiar nada."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    monkeypatch.setenv("AUDITBRAIN_LLM_PROVIDER", "anthropic")

    def fail_anthropic(messages, system=None):
        raise chat_providers.ProviderUnavailable(
            "HTTP 400 del proveedor: credit_balance_too_low"
        )

    def ok_gemini(messages, system=None):
        return chat_providers.LLMResponse(
            content="respuesta de gemini", model="gemini-2.0-flash",
            tokens_in=5, tokens_out=10,
        )

    monkeypatch.setattr(chat_providers, "_call_anthropic", fail_anthropic)
    monkeypatch.setattr(chat_providers, "_call_gemini", ok_gemini)

    r = chat_providers.chat_complete([{"role": "user", "content": "hola"}])
    assert r.content == "respuesta de gemini"
    assert r.model == "gemini-2.0-flash"


def test_failover_propagates_last_error_when_all_fail(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")

    def fail_any(messages, system=None):
        raise chat_providers.ProviderUnavailable("nope")

    monkeypatch.setattr(chat_providers, "_call_anthropic", fail_any)
    monkeypatch.setattr(chat_providers, "_call_gemini", fail_any)

    try:
        chat_providers.chat_complete([{"role": "user", "content": "hola"}])
        assert False, "debería haber lanzado ProviderUnavailable"
    except chat_providers.ProviderUnavailable as exc:
        assert "nope" in str(exc)


def test_gemini_call_maps_payload_and_response(monkeypatch):
    captured = {}

    def fake_http_post(url, headers, payload, timeout=60):
        captured["url"] = url
        captured["payload"] = payload
        return {
            "candidates": [
                {"content": {"role": "model", "parts": [{"text": "respuesta gemini"}]}}
            ],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 22},
        }

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("AUDITBRAIN_LLM_PROVIDER", "gemini")
    monkeypatch.setattr(chat_providers, "_http_post", fake_http_post)

    r = chat_providers.chat_complete(
        messages=[{"role": "user", "content": "hola"}],
        system="Eres AuditBrain IA.",
    )
    assert r.content == "respuesta gemini"
    assert r.tokens_in == 11 and r.tokens_out == 22
    # auth por query string, no header
    assert "key=test-key" in captured["url"]
    # rol del asistente sería "model" en Gemini; el system va aparte
    assert captured["payload"]["system_instruction"]["parts"][0]["text"].startswith("Eres AuditBrain")
    assert captured["payload"]["contents"][0]["role"] == "user"
