"""Creación INDIVIDUAL de un cliente de portal (no solo por carga masiva).

Regla de negocio (2026-06-30): el admin puede crear UN cliente a la vez desde
USR·Cuentas indicando empresa, RUC y correo. La clave puede escribirla el admin
o, si la deja vacía, se autogenera con la regla dominio+RUC (igual que el bulk).
"""
import uuid

import pytest

from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.context.models import Organization
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def org(db_session):
    slug = f"sgl-{uuid.uuid4().hex[:6]}"
    o = Organization(name=f"ORG-{slug}", slug=slug, is_active=True)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _admin_token(client, db_session, org):
    e = f"admin-sgl-{uuid.uuid4().hex[:6]}@x.com"
    admin = create_user(db_session, email=e, password="AdminSgl1!", role=Role.admin)
    admin.organization_id = org.id
    db_session.add(admin); db_session.commit()
    r = client.post("/api/v1/auth/login", data={"username": e, "password": "AdminSgl1!"})
    return r.json()["access_token"]


def test_create_single_client_auto_password(client, db_session, org):
    """Sin clave en el body → autogenera dominio+RUC4 (regla del bulk)."""
    tok = _admin_token(client, db_session, org)
    e = f"cli-{uuid.uuid4().hex[:6]}@corpx.com"
    r = client.post(
        "/api/v1/staff/portal-users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"cliente": "EMPRESA X", "ruc": "1790012345001", "email": e},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == e
    assert body["temp_password"] == "corpx1790"  # dominio(sin .com) + 4 dígitos RUC
    u = get_user_by_email(db_session, e)
    assert u is not None and u.role == Role.client


def test_create_single_client_manual_password(client, db_session, org):
    """Si el admin escribe la clave, esa se usa."""
    tok = _admin_token(client, db_session, org)
    e = f"cli2-{uuid.uuid4().hex[:6]}@x.com"
    r = client.post(
        "/api/v1/staff/portal-users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"cliente": "EMPRESA Y", "ruc": "111", "email": e,
              "new_password": "ClaveManual123"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["temp_password"] == "ClaveManual123"
    log = client.post("/api/v1/client/auth/login",
                      json={"email": e, "password": "ClaveManual123"})
    # el login del portal puede pedir cambio, pero NO debe ser 401 por credenciales
    assert log.status_code != 401, log.text


def test_create_single_rejects_invalid_email(client, db_session, org):
    tok = _admin_token(client, db_session, org)
    r = client.post(
        "/api/v1/staff/portal-users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"cliente": "Z", "ruc": "1", "email": "no-es-correo"},
    )
    assert r.status_code == 400, r.text


def test_create_single_rejects_duplicate_email(client, db_session, org):
    tok = _admin_token(client, db_session, org)
    e = f"dup-{uuid.uuid4().hex[:6]}@x.com"
    create_user(db_session, email=e, password="Existe123!", role=Role.client)
    r = client.post(
        "/api/v1/staff/portal-users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"cliente": "DUP", "ruc": "1", "email": e},
    )
    assert r.status_code == 400, r.text


def test_create_single_requires_admin(client, db_session, org):
    e = f"user-{uuid.uuid4().hex[:6]}@x.com"
    create_user(db_session, email=e, password="User1234!", role=Role.user)
    r = client.post("/api/v1/auth/login", data={"username": e, "password": "User1234!"})
    tok = r.json()["access_token"]
    r2 = client.post(
        "/api/v1/staff/portal-users",
        headers={"Authorization": f"Bearer {tok}"},
        json={"cliente": "X", "ruc": "1", "email": f"a-{uuid.uuid4().hex[:5]}@x.com"},
    )
    assert r2.status_code == 403
