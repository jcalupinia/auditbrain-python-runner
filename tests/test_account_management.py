"""Tests: reseteo de claves y borrado de cuentas (clientes y operadores)."""
import datetime
import uuid

import pytest

from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import ClientDevice, Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.context.models import Client, Organization
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _email(p):
    return f"{p}-{uuid.uuid4().hex[:8]}@example.com"


def _slug(p):
    return f"{p}-{uuid.uuid4().hex[:6]}"


@pytest.fixture()
def admin_token(db_session):
    u = create_user(db_session, email=_email("admin"), password="x", role=Role.admin)
    return create_access_token(subject=u.email, role="admin")


@pytest.fixture()
def org_client(db_session):
    slug = _slug("acg")
    org = Organization(name=f"ACG-{slug}", slug=slug, is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-{slug}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return org, cli


def _create_portal_user(client, admin_token, cli):
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": _email("pu")},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.json()
    return r.json()


def test_reset_portal_user_password(client, admin_token, org_client):
    _, cli = org_client
    pu = _create_portal_user(client, admin_token, cli)
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users/{pu['user_id']}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["email"] == pu["email"]
    assert len(body["temp_password"]) >= 12
    assert body["temp_password"] != pu["temp_password"]


def test_delete_portal_user_with_device(client, admin_token, org_client, db_session):
    """El borrado duro debe limpiar dispositivos (y revoked_by) sin fallar por FK."""
    _, cli = org_client
    pu = _create_portal_user(client, admin_token, cli)
    uid = pu["user_id"]
    now = datetime.datetime.now()
    dev = ClientDevice(
        user_id=uid, device_id=uuid.uuid4().hex, fingerprint_hash="fp",
        is_active=True, registered_at=now, last_seen_at=now, revoked_by_user_id=uid,
    )
    db_session.add(dev); db_session.commit()

    r = client.delete(
        f"/api/v1/staff/clients/{cli.id}/portal-users/{uid}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.json()
    db_session.expire_all()
    assert get_user_by_email(db_session, pu["email"]) is None


def test_operator_list_reset_and_delete(client, admin_token, db_session):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": _email("op"), "password": "secret123", "role": "user"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.json()
    op = r.json()

    rl = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert rl.status_code == 200
    assert any(u["email"] == op["email"] for u in rl.json())

    rr = client.post(
        f"/api/v1/auth/users/{op['id']}/reset-password",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rr.status_code == 200 and len(rr.json()["temp_password"]) >= 12

    rd = client.delete(
        f"/api/v1/auth/users/{op['id']}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert rd.status_code == 200, rd.json()
    db_session.expire_all()
    assert get_user_by_email(db_session, op["email"]) is None


def test_disable_enable_portal_user(client, admin_token, org_client):
    _, cli = org_client
    pu = _create_portal_user(client, admin_token, cli)
    uid = pu["user_id"]
    h = {"Authorization": f"Bearer {admin_token}"}
    rd = client.post(f"/api/v1/staff/clients/{cli.id}/portal-users/{uid}/disable", headers=h)
    assert rd.status_code == 200, rd.json()
    re_ = client.post(f"/api/v1/staff/clients/{cli.id}/portal-users/{uid}/enable", headers=h)
    assert re_.status_code == 200, re_.json()


def test_disable_enable_operator(client, admin_token, db_session):
    r = client.post(
        "/api/v1/auth/users",
        json={"email": _email("op2"), "password": "secret123", "role": "user"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201
    op = r.json()
    h = {"Authorization": f"Bearer {admin_token}"}
    rd = client.post(f"/api/v1/auth/users/{op['id']}/disable", headers=h)
    assert rd.status_code == 200, rd.json()
    re_ = client.post(f"/api/v1/auth/users/{op['id']}/enable", headers=h)
    assert re_.status_code == 200, re_.json()


def test_cannot_disable_self(client, db_session):
    u = create_user(db_session, email=_email("selfadm2"), password="x", role=Role.admin)
    token = create_access_token(subject=u.email, role="admin")
    r = client.post(
        f"/api/v1/auth/users/{u.id}/disable",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_cannot_delete_self(client, db_session):
    u = create_user(db_session, email=_email("selfadmin"), password="x", role=Role.admin)
    token = create_access_token(subject=u.email, role="admin")
    r = client.delete(
        f"/api/v1/auth/users/{u.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
