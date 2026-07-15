"""Tests del módulo Forge: persistencia del cerebro, compilación y aislamiento.

Usa la BD por defecto (SQLite) y emails únicos por test. Reutiliza el motor
determinista vendorizado en ``backend/app/forge/engine``.
"""

import uuid

from backend.app.auth import service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db


def _mk_admin():
    init_db()
    email = f"forge-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        service.create_user(db, email=email, password=password, role=Role.admin)
    finally:
        db.close()
    return email, password


def _login(client, email, password):
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _brain_payload():
    return {
        "name": "Mi Proyecto",
        "slug": "mi-proyecto",
        "organization": "AuditConsulting",
        "targets": ["claude-code"],
        "rules": [{"id": "general", "title": "General", "body": "# General\n\n- Regla."}],
        "memory": [
            {"slug": "ctx", "name": "Contexto", "description": "Punto de partida", "type": "project", "body": "x"}
        ],
        "skills": [{"slug": "ej", "name": "Ejemplo", "description": "Skill", "body": "cuerpo"}],
        "agents": [{"slug": "rev", "name": "revisor", "description": "Revisa", "prompt": "Eres revisor."}],
        "connectors": [
            {"slug": "demo", "name": "Demo", "purpose": "p", "type": "mcp", "command": "node", "args": ["s.js"]}
        ],
        "capabilities": [{"name": "analizar", "modules": ["scanner"], "covered": True}],
    }


def test_targets_lista_seis_adaptadores(client):
    email, pw = _mk_admin()
    h = _login(client, email, pw)
    r = client.get("/api/v1/forge/targets", headers=h)
    assert r.status_code == 200, r.text
    assert set(r.json()) == {"claude-code", "codex", "copilot", "cursor", "gemini", "windsurf"}


def test_crear_y_compilar_cerebro(client):
    email, pw = _mk_admin()
    h = _login(client, email, pw)

    r = client.post("/api/v1/forge/brains", json=_brain_payload(), headers=h)
    assert r.status_code == 201, r.text
    brain_id = r.json()["id"]

    # aparece en la lista del usuario
    lst = client.get("/api/v1/forge/brains", headers=h).json()
    assert any(b["id"] == brain_id for b in lst)

    # compila a claude-code
    r = client.post(
        f"/api/v1/forge/brains/{brain_id}/compile",
        json={"target": "claude-code"},
        headers=h,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == 4
    files = data["files"]
    assert set(files) == {
        "CLAUDE.md",
        ".mcp.json",
        ".claude/skills/ej/SKILL.md",
        ".claude/agents/rev.md",
    }
    assert "# Mi Proyecto" in files["CLAUDE.md"]
    assert "## Reglas" in files["CLAUDE.md"]
    assert '"demo"' in files[".mcp.json"]
    assert "\r" not in files["CLAUDE.md"]  # LF puro


def test_compila_a_cursor(client):
    email, pw = _mk_admin()
    h = _login(client, email, pw)
    brain_id = client.post(
        "/api/v1/forge/brains", json=_brain_payload(), headers=h
    ).json()["id"]
    r = client.post(
        f"/api/v1/forge/brains/{brain_id}/compile", json={"target": "cursor"}, headers=h
    )
    assert r.status_code == 200, r.text
    assert ".cursor/rules/project.mdc" in r.json()["files"]


def test_target_invalido_da_400(client):
    email, pw = _mk_admin()
    h = _login(client, email, pw)
    brain_id = client.post(
        "/api/v1/forge/brains", json=_brain_payload(), headers=h
    ).json()["id"]
    r = client.post(
        f"/api/v1/forge/brains/{brain_id}/compile", json={"target": "noexiste"}, headers=h
    )
    assert r.status_code == 400, r.text


def test_aislamiento_entre_usuarios(client):
    e1, p1 = _mk_admin()
    h1 = _login(client, e1, p1)
    brain_id = client.post(
        "/api/v1/forge/brains", json=_brain_payload(), headers=h1
    ).json()["id"]

    e2, p2 = _mk_admin()
    h2 = _login(client, e2, p2)
    # el segundo usuario NO ve ni accede al cerebro del primero
    assert brain_id not in [b["id"] for b in client.get("/api/v1/forge/brains", headers=h2).json()]
    r = client.get(f"/api/v1/forge/brains/{brain_id}", headers=h2)
    assert r.status_code == 404


def test_requiere_autenticacion(client):
    r = client.get("/api/v1/forge/brains")
    assert r.status_code == 401
