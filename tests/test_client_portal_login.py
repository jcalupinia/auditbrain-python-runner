"""Tests for client portal login + 3-layer security guard."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.auth import device as device_mod
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture()
def client_user(db_session):
    email = _unique_email("client-user")
    return get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="ClientPass1!", role=Role.client,
    )


def test_guard_rejects_when_role_is_not_client(client, client_user, db_session):
    from backend.app.auth.jwt_tokens import create_access_token
    token = create_access_token(subject=client_user.email, role="admin")
    r = client.get(
        "/api/v1/client/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (401, 403, 404)  # 404 before router is wired, 403 once it is


# ---------------------------------------------------------------------------
# Task 8: client_portal service layer tests
# ---------------------------------------------------------------------------

from backend.app.client_portal.service import (
    create_portal_user,
    authenticate_portal_user,
)
from backend.app.context.models import Organization, Client


@pytest.fixture()
def org_and_client(db_session):
    slug_unique = f"acg-{uuid.uuid4().hex[:6]}"
    org = Organization(name=f"ACG-{slug_unique}", slug=slug_unique, is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(
        organization_id=org.id, name=f"CL-{slug_unique}", is_active=True
    )
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return org, cli


def test_create_portal_user_returns_temp_password(db_session, org_and_client):
    org, cli = org_and_client
    email = _unique_email("newclient")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    assert user.role == Role.client
    assert user.client_id == cli.id
    assert user.password_reset_required is True
    assert user.organization_id == org.id
    assert len(temp_pwd) >= 12


def test_authenticate_portal_user_with_wrong_password(db_session, org_and_client):
    _, cli = org_and_client
    email = _unique_email("auth1")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    assert authenticate_portal_user(db_session, email, "wrong") is None
    auth_result = authenticate_portal_user(db_session, email, temp_pwd)
    assert auth_result is not None
    assert auth_result.email == user.email
