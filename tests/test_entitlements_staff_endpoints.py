"""Endpoints admin de entitlements: GET /staff/tools, GET/PUT entitlements."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def admin_token(db_session):
    email = f"admin-ent-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.admin
    )
    return create_access_token(subject=u.email, role="admin")


@pytest.fixture()
def portal_user(db_session):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-ent-{suffix}", slug=f"acg-ent-{suffix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-ent-{suffix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    user, _ = create_portal_user(db_session, client_id=cli.id, email=f"pu-{suffix}@example.com")
    return user


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_staff_tools_lists_catalog(client, admin_token):
    r = client.get("/api/v1/staff/tools", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    cats = {c["id"]: c for c in r.json()}
    assert "TRIBUTARIAS" in cats
    assert "TESTING" not in cats  # categoría interna no se expone
    codes = [t["code"] for t in cats["TRIBUTARIAS"]["tools"]]
    assert "ICT_2025" in codes


def test_get_and_put_entitlements(client, admin_token, portal_user):
    r = client.get(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        headers=_h(admin_token),
    )
    assert r.status_code == 200
    assert r.json()["enabled_tool_codes"] == []

    r2 = client.put(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        json={"tool_codes": ["ICT_2025"]},
        headers=_h(admin_token),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["enabled_tool_codes"] == ["ICT_2025"]

    r3 = client.put(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        json={"tool_codes": []},
        headers=_h(admin_token),
    )
    assert r3.json()["enabled_tool_codes"] == []


def test_put_ignores_unknown_codes(client, admin_token, portal_user):
    """PUT con un código inexistente: se ignora en silencio y la respuesta
    trae solo los códigos válidos (contrato: no devuelve 400)."""
    r = client.put(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        json={"tool_codes": ["ICT_2025", "NO_EXISTE_XYZ"]},
        headers=_h(admin_token),
    )
    assert r.status_code == 200, r.text
    assert r.json()["enabled_tool_codes"] == ["ICT_2025"]


def test_entitlements_404_for_unknown_user(client, admin_token):
    r = client.get(
        "/api/v1/staff/portal-users/99999999/entitlements",
        headers=_h(admin_token),
    )
    assert r.status_code == 404


def test_entitlements_requires_admin(client, db_session, portal_user):
    email = f"op-{uuid.uuid4().hex[:8]}@example.com"
    u = create_user(db_session, email=email, password="x", role=Role.user)
    token = create_access_token(subject=u.email, role="user")
    r = client.get(
        f"/api/v1/staff/portal-users/{portal_user.id}/entitlements",
        headers=_h(token),
    )
    assert r.status_code == 403
