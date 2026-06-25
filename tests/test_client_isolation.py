"""CRITICAL: aislamiento entre clientes y entre roles."""
import io
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


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _make_logged_client(db_session, email_prefix):
    """Each call uses a fresh TestClient so cookies don't bleed.

    Returns a dict with:
    - tc: TestClient instance (already used for login, device cookie set)
    - headers: Authorization header dict
    - cookies: device_id cookie dict (pass explicitly to avoid httpx domain mismatch)
    - user, client_record
    """
    from fastapi.testclient import TestClient
    import app as legacy_app

    suffix = _unique(email_prefix)
    org = Organization(name=f"Org-{suffix}", slug=f"org-{suffix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"Cli-{suffix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    email = f"{email_prefix}-{suffix}@iso.com"
    user, pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    tc = TestClient(legacy_app.app)
    r = tc.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": pwd},
    )
    assert r.status_code == 200, r.json()
    device_id = r.cookies.get("device_id")
    return {
        "user": user, "client_record": cli, "tc": tc,
        "headers": {"Authorization": f"Bearer {r.json()['access_token']}"},
        "cookies": {"device_id": device_id} if device_id else {},
    }


def test_client_a_cannot_get_client_b_job(client, db_session):
    a = _make_logged_client(db_session, "alpha")
    b = _make_logged_client(db_session, "bravo")

    r = a["tc"].post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files={"input": ("a.pdf", io.BytesIO(b"%PDF-A"), "application/pdf")},
        headers=a["headers"],
        cookies=a["cookies"],
    )
    assert r.status_code == 201, r.json()
    job_id_a = r.json()["id"]

    r2 = b["tc"].get(
        f"/api/v1/client/tools/jobs/{job_id_a}",
        headers=b["headers"],
        cookies=b["cookies"],
    )
    assert r2.status_code == 403

    r3 = b["tc"].get(
        f"/api/v1/client/tools/jobs/{job_id_a}/download",
        headers=b["headers"],
        cookies=b["cookies"],
    )
    assert r3.status_code == 403


def test_staff_jwt_can_access_client_endpoints(client, db_session):
    """Los operadores (admin/user) SÍ pueden entrar al portal con su mismo
    usuario (sin cuenta cliente aparte). La separación que importa —que un
    cliente NO acceda al staff— se valida en test_client_jwt_cannot_access_staff."""
    email = f"staff-{uuid.uuid4().hex[:8]}@iso.com"
    staff = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.admin
    )
    token = create_access_token(subject=staff.email, role="admin")
    r = client.get("/api/v1/client/catalog", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.json()


def test_operator_can_login_to_portal(client, db_session):
    """Un operador inicia sesión en el portal con su email+contraseña de staff."""
    email = f"op-portal-{uuid.uuid4().hex[:8]}@iso.com"
    create_user(db_session, email=email, password="operador123", role=Role.user)
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": "operador123"},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["access_token"]


def test_client_jwt_cannot_access_staff_endpoints(client, db_session):
    suffix = _unique("iso")
    org = Organization(name=f"O-{suffix}", slug=f"o-{suffix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"C-{suffix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    email = f"cli-iso-{suffix}@x.com"
    user, _ = create_portal_user(db_session, client_id=cli.id, email=email)
    token = create_access_token(subject=user.email, role="client")
    r = client.post(
        f"/api/v1/staff/clients/{cli.id}/portal-users",
        json={"email": f"wont-{suffix}@happen.com"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (401, 403)  # rejected by either layer
