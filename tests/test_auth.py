"""Tests de auth F2: hashing, JWT, roles y gating del runner.

Usa la BD por defecto (SQLite). Emails únicos por test para no colisionar.
"""

import uuid

import pytest

from backend.app.auth import service
from backend.app.auth.models import Role
from backend.app.auth.password import hash_password, verify_password
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk(role: Role):
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        service.create_user(db, email=email, password=password, role=role)
    finally:
        db.close()
    return email, password


def _token(client, email, password):
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_password_hash_roundtrip():
    h = hash_password("clave-larga-segura")
    assert h != "clave-larga-segura"
    assert verify_password("clave-larga-segura", h)
    assert not verify_password("incorrecta", h)


def test_login_bad_credentials(client):
    email, _ = _mk(Role.user)
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": "mala"}
    )
    assert r.status_code == 401


def test_login_and_me(client):
    email, pw = _mk(Role.admin)
    tok = _token(client, email, pw)
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == email
    assert body["role"] == "admin"


def test_non_admin_cannot_create_users(client):
    email, pw = _mk(Role.user)
    tok = _token(client, email, pw)
    r = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"email": "x@example.com", "password": "abcdefgh", "role": "user"},
    )
    assert r.status_code == 403


def test_admin_creates_user_and_conflict(client):
    email, pw = _mk(Role.admin)
    tok = _token(client, email, pw)
    new_email = f"new-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"email": new_email, "password": "abcdefgh", "role": "user"},
    )
    assert r.status_code == 201, r.text
    r2 = client.post(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"email": new_email, "password": "abcdefgh", "role": "user"},
    )
    assert r2.status_code == 409


def test_runner_rejects_non_admin_jwt(client):
    """Garantía 'runner solo admin': un JWT de usuario normal -> 403."""
    email, pw = _mk(Role.user)
    tok = _token(client, email, pw)
    r = client.post(
        "/api/v1/python/run",
        headers={"Authorization": f"Bearer {tok}"},
        json={"script": "result = 1"},
    )
    assert r.status_code == 403


def test_runner_allows_admin_jwt(client):
    email, pw = _mk(Role.admin)
    tok = _token(client, email, pw)
    r = client.post(
        "/api/v1/python/run",
        headers={"Authorization": f"Bearer {tok}"},
        json={"script": "result = 21 * 2"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["result"] == 42


class _FakeDocResp:
    status_code = 200
    text = ""

    def json(self):
        return {"url": "https://example.com/doc.pdf"}


def test_documents_allows_normal_user(client, monkeypatch):
    """El panel de Documentos es accesible para usuario normal (JWT),
    no solo admin ni solo X-API-Key."""
    from backend.app.document_services import universal_document_client

    monkeypatch.setattr(
        universal_document_client.requests,
        "post",
        lambda *a, **k: _FakeDocResp(),
    )
    email, pw = _mk(Role.user)
    tok = _token(client, email, pw)
    r = client.post(
        "/api/v1/documents/generate",
        headers={"Authorization": f"Bearer {tok}"},
        json={"result": {"a": 1}, "output_expectations": {"format": "pdf"}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "ok"
