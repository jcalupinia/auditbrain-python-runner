"""El admin puede ASIGNAR una clave específica al resetear (operadores y clientes).

Regla de negocio (2026-06-29): al resetear, el administrador puede escribir la
nueva clave en un recuadro. Si la provee, esa queda como clave DEFINITIVA
(password_reset_required=False) y el usuario entra directo con ella. Si NO la
provee (body vacío), se mantiene el comportamiento histórico: clave temporal
aleatoria + password_reset_required=True.
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
    slug = f"rst-{uuid.uuid4().hex[:6]}"
    o = Organization(name=f"ORG-{slug}", slug=slug, is_active=True)
    db_session.add(o); db_session.commit(); db_session.refresh(o)
    return o


def _admin_token(client, db_session):
    e = f"admin-rst-{uuid.uuid4().hex[:6]}@x.com"
    create_user(db_session, email=e, password="AdminRst1!", role=Role.admin)
    r = client.post("/api/v1/auth/login", data={"username": e, "password": "AdminRst1!"})
    return r.json()["access_token"]


# ---------- Operadores (rol user) ----------

def test_reset_operator_with_admin_password(client, db_session):
    """Si el admin escribe la clave, esa se asigna y el operador entra con ella."""
    tok = _admin_token(client, db_session)
    e = f"op-{uuid.uuid4().hex[:6]}@auditconsulting.ec"
    op = create_user(db_session, email=e, password="Inicial1!", role=Role.user)

    nueva = "ClaveDefinida2026"
    r = client.post(
        f"/api/v1/auth/users/{op.id}/reset-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"new_password": nueva},
    )
    assert r.status_code == 200, r.text
    assert r.json()["temp_password"] == nueva  # devuelve la clave asignada

    db_session.expire_all()
    u = get_user_by_email(db_session, e)
    assert u.password_reset_required is False  # definitiva, no fuerza cambio
    # entra directo con la clave asignada
    log = client.post("/api/v1/auth/login", data={"username": e, "password": nueva})
    assert log.status_code == 200, log.text


def test_reset_operator_without_password_generates_random(client, db_session):
    """Sin clave en el body → aleatoria + fuerza cambio (retrocompat)."""
    tok = _admin_token(client, db_session)
    e = f"op2-{uuid.uuid4().hex[:6]}@auditconsulting.ec"
    op = create_user(db_session, email=e, password="Inicial1!", role=Role.user)

    r = client.post(
        f"/api/v1/auth/users/{op.id}/reset-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={},
    )
    assert r.status_code == 200, r.text
    temp = r.json()["temp_password"]
    assert temp and len(temp) >= 8
    db_session.expire_all()
    assert get_user_by_email(db_session, e).password_reset_required is True


def test_reset_operator_rejects_short_password(client, db_session):
    """Una clave manual demasiado corta se rechaza (mín. 8)."""
    tok = _admin_token(client, db_session)
    e = f"op3-{uuid.uuid4().hex[:6]}@auditconsulting.ec"
    op = create_user(db_session, email=e, password="Inicial1!", role=Role.user)
    r = client.post(
        f"/api/v1/auth/users/{op.id}/reset-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"new_password": "123"},
    )
    assert r.status_code in (400, 422), r.text


# ---------- Clientes (rol client, gestión global) ----------

def test_reset_portal_client_with_admin_password(client, db_session, org):
    from backend.app.staff_portal.service import bulk_create_portal_clients
    tok = _admin_token(client, db_session)
    e = f"cli-{uuid.uuid4().hex[:6]}@x.com"
    res = bulk_create_portal_clients(
        db_session, organization_id=org.id,
        rows=[{"cliente": "X", "ruc": "111", "email": e}],
    )
    uid = res["creados"][0]["user_id"]

    nueva = "ClienteClave2026"
    r = client.post(
        f"/api/v1/staff/portal-users/{uid}/reset-password",
        headers={"Authorization": f"Bearer {tok}"},
        json={"new_password": nueva},
    )
    assert r.status_code == 200, r.text
    assert r.json()["temp_password"] == nueva
    db_session.expire_all()
    assert get_user_by_email(db_session, e).password_reset_required is False
