"""Crear un job de una herramienta NO concedida devuelve 403 (rol client)."""
import io
import uuid
import pytest
from backend.app.client_portal.service import create_portal_user
from backend.app.client_portal import entitlements as ent
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _login(client, db, granted):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-job-{suffix}", slug=f"acg-job-{suffix}", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-job-{suffix}", is_active=True)
    db.add(cli); db.commit(); db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"job-{suffix}@example.com")
    if granted:
        ent.set_user_entitlements(db, user.id, set(granted))
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {"headers": {"Authorization": f"Bearer {token}"},
            "cookies": {"device_id": device_id} if device_id else {}}


def test_job_denied_without_entitlement(client, db_session):
    auth = _login(client, db_session, granted=set())
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files={"input": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        **auth,
    )
    assert r.status_code == 403, r.text


def test_job_allowed_with_entitlement(client, db_session):
    auth = _login(client, db_session, granted={"STUB_ECHO"})
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files={"input": ("x.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        **auth,
    )
    assert r.status_code == 201, r.text
