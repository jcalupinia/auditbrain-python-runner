"""El catálogo del portal filtra por los entitlements del usuario."""
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
    org = Organization(name=f"ACG-gate-{suffix}", slug=f"acg-gate-{suffix}", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-gate-{suffix}", is_active=True)
    db.add(cli); db.commit(); db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"gate-{suffix}@example.com")
    if granted:
        ent.set_user_entitlements(db, user.id, set(granted))
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {"headers": {"Authorization": f"Bearer {token}"},
            "cookies": {"device_id": device_id} if device_id else {}}


def _codes_by_cat(body):
    return {c["id"]: [t["code"] for t in c["tools"]] for c in body["categories"]}


def test_catalog_hides_tools_without_entitlement(client, db_session):
    auth = _login(client, db_session, granted=set())
    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = _codes_by_cat(r.json())
    assert "TRIBUTARIAS" in by_cat
    assert by_cat["TRIBUTARIAS"] == []


def test_catalog_shows_only_granted_tool(client, db_session):
    auth = _login(client, db_session, granted={"ICT_2025"})
    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = _codes_by_cat(r.json())
    assert by_cat["TRIBUTARIAS"] == ["ICT_2025"]
