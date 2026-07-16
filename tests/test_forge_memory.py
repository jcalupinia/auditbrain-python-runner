"""Tests de los endpoints de memoria de Forge (L8)."""

import uuid

from backend.app.auth import service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db


def _admin(client):
    init_db()
    email = f"forgemem-{uuid.uuid4().hex[:8]}@example.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        service.create_user(db, email=email, password=pw, role=Role.admin)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _brain(client, h):
    return client.post(
        "/api/v1/forge/brains", json={"name": "Demo", "slug": "demo"}, headers=h
    ).json()["id"]


def test_memoria_crud(client):
    h = _admin(client)
    bid = _brain(client, h)

    # vacía al inicio
    assert client.get(f"/api/v1/forge/brains/{bid}/memory", headers=h).json() == []

    # añadir
    r = client.post(
        f"/api/v1/forge/brains/{bid}/memory",
        json={"name": "Usamos PostgreSQL 18", "description": "BD productiva"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    assert r.json()["slug"] == "usamos-postgresql-18"

    # aparece en la lista
    lst = client.get(f"/api/v1/forge/brains/{bid}/memory", headers=h).json()
    assert any(m["slug"] == "usamos-postgresql-18" for m in lst)

    # y en la compilación
    files = client.post(
        f"/api/v1/forge/brains/{bid}/compile", json={"target": "claude-code"}, headers=h
    ).json()["files"]
    assert "Usamos PostgreSQL 18" in files["CLAUDE.md"]


def test_memoria_type_invalido(client):
    h = _admin(client)
    bid = _brain(client, h)
    r = client.post(
        f"/api/v1/forge/brains/{bid}/memory",
        json={"name": "X", "description": "d", "type": "malo"},
        headers=h,
    )
    assert r.status_code == 400, r.text
