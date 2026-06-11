import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.client_portal.rate_limit import reset_for_key
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture(autouse=True)
def _no_real_notify(monkeypatch):
    # Evita red real / sleeps de backoff en los tests del router.
    monkeypatch.setattr(
        "backend.app.events.notify.process_registration_notifications",
        lambda *a, **k: None,
    )


@pytest.fixture(autouse=True)
def _reset_rate_limit():
    reset_for_key("event-reg:testclient")
    yield
    reset_for_key("event-reg:testclient")


SLUG = "charla-anexos-2026-06"


def _payload(email=None):
    return {
        "nombre": "María Pérez",
        "email": email or f"r-{uuid.uuid4().hex[:8]}@example.com",
        "telefono": "0987654321",
        "telefono_pais": "+593",
        "documento": "1791240154001",
        "empresa": "Empresa S.A.",
    }


def _admin_token(client):
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=Role.admin)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_register_ok_201(client):
    r = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["ya_inscrito"] is False


def test_register_idempotent(client):
    email = f"r-{uuid.uuid4().hex[:8]}@example.com"
    client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload(email))
    r2 = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload(email))
    assert r2.status_code == 201, r2.text
    assert r2.json()["ya_inscrito"] is True


def test_register_unknown_slug_404(client):
    r = client.post("/api/v1/events/no-existe/registrations", json=_payload())
    assert r.status_code == 404


def test_register_invalid_documento_422(client):
    bad = _payload()
    bad["documento"] = "123"
    r = client.post(f"/api/v1/events/{SLUG}/registrations", json=bad)
    assert r.status_code == 422


def test_rate_limit_429(client):
    last = None
    for _ in range(11):
        last = client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    assert last.status_code == 429


def test_list_requires_admin(client):
    r = client.get(f"/api/v1/events/{SLUG}/registrations")
    assert r.status_code == 401


def test_list_with_admin_ok(client):
    client.post(f"/api/v1/events/{SLUG}/registrations", json=_payload())
    tok = _admin_token(client)
    r = client.get(
        f"/api/v1/events/{SLUG}/registrations",
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200, r.text
    assert isinstance(r.json(), list)
