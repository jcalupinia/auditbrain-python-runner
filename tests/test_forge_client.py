"""Tests de los endpoints de Forge para el portal de clientes (/client/forge).

Rol client + device + entitlement FORGE_CONSOLE. Reutiliza el patrón de
test_entitlements_job_enforcement.py.
"""

import uuid

import pytest

from backend.app.client_portal import entitlements as ent
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Client, Organization
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture()
def db_session():
    init_db()
    db = SessionLocal()
    yield db
    db.close()


def _login(client, db, granted):
    sfx = uuid.uuid4().hex[:8]
    org = Organization(name=f"FG-{sfx}", slug=f"fg-{sfx}", is_active=True)
    db.add(org)
    db.commit()
    db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CLFG-{sfx}", is_active=True)
    db.add(cli)
    db.commit()
    db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"fg-{sfx}@example.com")
    if granted:
        ent.set_user_entitlements(db, user.id, set(granted))
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    device_id = r.cookies.get("device_id")
    return {
        "headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
        "cookies": {"device_id": device_id} if device_id else {},
    }


def test_sin_entitlement_forge_403(client, db_session):
    auth = _login(client, db_session, granted=set())
    r = client.get("/api/v1/client/forge/brains", **auth)
    assert r.status_code == 403, r.text


def test_cliente_con_forge_crea_y_compila(client, db_session):
    auth = _login(client, db_session, granted={"FORGE_CONSOLE"})

    # targets
    r = client.get("/api/v1/client/forge/targets", **auth)
    assert r.status_code == 200 and "claude-code" in r.json()

    # plan free por defecto
    sub = client.get("/api/v1/client/forge/subscription", **auth).json()
    assert sub["plan"] == "free"

    # crear cerebro
    payload = {"name": "P", "slug": "p", "rules": [{"id": "g", "title": "G", "body": "b"}]}
    r = client.post("/api/v1/client/forge/brains", json=payload, **auth)
    assert r.status_code == 201, r.text
    bid = r.json()["id"]

    # compilar a claude-code (permitido en free)
    r = client.post(
        f"/api/v1/client/forge/brains/{bid}/compile", json={"target": "claude-code"}, **auth
    )
    assert r.status_code == 200, r.text
    assert "CLAUDE.md" in r.json()["files"]

    # cursor NO permitido en free
    r = client.post(
        f"/api/v1/client/forge/brains/{bid}/compile", json={"target": "cursor"}, **auth
    )
    assert r.status_code == 402, r.text
