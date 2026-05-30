"""Tests for /api/v1/staff/clients/{id}/portal-users + /devices."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


def _unique_slug(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


@pytest.fixture()
def admin_token(db_session):
    email = _unique_email("admin")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.admin
    )
    return create_access_token(subject=u.email, role="admin")


@pytest.fixture()
def org_client(db_session):
    slug = _unique_slug("acg-staff")
    org = Organization(name=f"ACG-{slug}", slug=slug, is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-{slug}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return org, cli


def test_admin_creates_portal_user_returns_temp_password(client, admin_token, org_client):
    _, cli = org_client
    email = _unique_email("newportal")
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": email},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["email"] == email
    assert "temp_password" in body
    assert len(body["temp_password"]) >= 12


def test_user_role_cannot_create_portal_users(client, db_session, org_client):
    _, cli = org_client
    email = _unique_email("staffuser")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.user
    )
    token = create_access_token(subject=u.email, role="user")
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": _unique_email("denied")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_user_role_cannot_list_portal_users(client, db_session, org_client):
    """Staff con rol=user no debe ver lista de portal users (info sensible)."""
    import uuid
    _, cli = org_client
    email = f"staffuser-list-{uuid.uuid4().hex[:8]}@x.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.user
    )
    token = create_access_token(subject=u.email, role="user")
    r = client.get(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
