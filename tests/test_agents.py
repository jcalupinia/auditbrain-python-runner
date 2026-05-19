"""Tests de agentes especializados (Fase 2 · M4).

Cubre:
- /api/v1/agents lista por módulo y filtra.
- Validación de inputs requeridos -> 400 con mensaje legible.
- Lanzamiento de run -> 202 con run en estado queued/running/succeeded.
- Ejecución persiste output cuando el provider responde (mockeado).
- Sin provider -> run.status = failed con error legible (sin fingir
  respuesta).
- Aislamiento cross-user: no veo runs ajenos.
- Proyecto no accesible -> 403 al lanzar el run.
"""

import uuid

import pytest

from backend.app.agents import service as agents_service
from backend.app.agents.registry import AGENTS
from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.chat.providers import LLMResponse, ProviderUnavailable
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk(role: Role = Role.user):
    email = f"u-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=password, role=role)
    finally:
        db.close()
    return email, password


def _login(client, email, pw):
    return client.post(
        "/api/v1/auth/login", data={"username": email, "password": pw}
    ).json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_registry_has_one_agent_per_module():
    modules = {a.module_code for a in AGENTS}
    expected = {"ADV", "AUD", "TAX", "LEG", "FIN", "CYB", "DATA", "AUT", "GOV", "MKT", "CRE"}
    assert expected.issubset(modules)


def test_list_agents_filter_by_module(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/agents?module=ADV", headers=_h(tok))
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    assert all(a["module_code"] == "ADV" for a in body)


def test_agent_not_found(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.get("/api/v1/agents/NO.SUCH.AGENT", headers=_h(tok))
    assert r.status_code == 404


def test_run_validates_required_inputs(client):
    email, pw = _mk()
    tok = _login(client, email, pw)
    # ADV.resumen-ejecutivo requiere 'brief'
    r = client.post(
        "/api/v1/agents/ADV.resumen-ejecutivo/runs",
        headers=_h(tok),
        json={"inputs": {}},
    )
    assert r.status_code == 400
    assert "brief" in r.text.lower() or "Brief" in r.text


def test_run_executes_and_persists_output(client, monkeypatch):
    def fake_complete(messages, system=None):
        return LLMResponse(
            content="## Tesis\nOK\n## Riesgos clave\nNinguno",
            model="claude-test",
            tokens_in=20, tokens_out=12,
        )

    monkeypatch.setattr(agents_service, "chat_complete", fake_complete)

    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.post(
        "/api/v1/agents/ADV.resumen-ejecutivo/runs",
        headers=_h(tok),
        json={"inputs": {"brief": "Inversión X en mercado Y"}},
    )
    assert r.status_code == 202, r.text
    run = r.json()
    # BackgroundTasks de TestClient se ejecutan sincrónicamente al cerrar
    # la respuesta, así que al re-leer ya debe estar succeeded.
    r2 = client.get(f"/api/v1/runs/{run['id']}", headers=_h(tok))
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "succeeded"
    assert "Tesis" in body["output"]
    assert body["model"] == "claude-test"
    assert body["tokens_in"] == 20


def test_run_marks_failed_without_provider(client, monkeypatch):
    def fake_complete(messages, system=None):
        raise ProviderUnavailable("Sin clave configurada.")

    monkeypatch.setattr(agents_service, "chat_complete", fake_complete)

    email, pw = _mk()
    tok = _login(client, email, pw)
    r = client.post(
        "/api/v1/agents/ADV.resumen-ejecutivo/runs",
        headers=_h(tok),
        json={"inputs": {"brief": "X"}},
    )
    assert r.status_code == 202
    run_id = r.json()["id"]
    r2 = client.get(f"/api/v1/runs/{run_id}", headers=_h(tok))
    body = r2.json()
    assert body["status"] == "failed"
    assert body["output"] is None
    assert "Proveedor LLM no disponible" in body["error"]


def test_cross_user_isolation_runs(client, monkeypatch):
    monkeypatch.setattr(
        agents_service, "chat_complete",
        lambda messages, system=None: LLMResponse(content="x", model="m", tokens_in=1, tokens_out=1),
    )

    a_email, a_pw = _mk()
    b_email, b_pw = _mk()
    a_tok = _login(client, a_email, a_pw)
    b_tok = _login(client, b_email, b_pw)
    r = client.post(
        "/api/v1/agents/ADV.resumen-ejecutivo/runs",
        headers=_h(a_tok),
        json={"inputs": {"brief": "X"}},
    )
    run_id = r.json()["id"]
    # B no ve el run de A
    rb = client.get(f"/api/v1/runs/{run_id}", headers=_h(b_tok))
    assert rb.status_code == 404
    # Ni en su lista
    rl = client.get("/api/v1/runs", headers=_h(b_tok))
    assert all(x["id"] != run_id for x in rl.json())


def test_inaccessible_project_blocked(client):
    admin_email, admin_pw = _mk(Role.admin)
    admin_tok = _login(client, admin_email, admin_pw)
    cid = client.post(
        "/api/v1/context/clients", headers=_h(admin_tok), json={"name": "Z"}
    ).json()["id"]
    pid = client.post(
        "/api/v1/context/projects",
        headers=_h(admin_tok),
        json={"client_id": cid, "name": "Privado"},
    ).json()["id"]

    user_email, user_pw = _mk()
    user_tok = _login(client, user_email, user_pw)
    r = client.post(
        "/api/v1/agents/ADV.resumen-ejecutivo/runs",
        headers=_h(user_tok),
        json={"inputs": {"brief": "X"}, "project_id": pid},
    )
    assert r.status_code == 403
