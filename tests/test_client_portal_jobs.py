"""Tests for /client/tools/* endpoints (catalog + jobs)."""
import io
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def logged_client(client, db_session):
    """Fixture: cliente logueado con device cookie ya seteada.
    Uses uuid-suffixed slug/email so the SQLite test DB can be reused across runs.

    Returns a dict with:
      - user, token, client (record), headers (Authorization only)
      - device_id: the cookie value (must be passed explicitly in requests
        because httpx/TestClient domain mismatch between testserver and
        testserver.local prevents auto-forwarding)
    """
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-jobs-{suffix}", slug=f"acg-jobs-{suffix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-jobs-{suffix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    email = f"jobs-{suffix}@example.com"
    user, pwd = create_portal_user(
        db_session, client_id=cli.id, email=email
    )
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": pwd},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {
        "user": user,
        "token": token,
        "client": cli,
        "headers": {"Authorization": f"Bearer {token}"},
        "device_id": device_id,
        "cookies": {"device_id": device_id} if device_id else {},
    }


def test_catalog_returns_categories_with_stub_tool(client, logged_client):
    """El catálogo público debe exponer las 4 categorías de cara al cliente
    (Tributarias, NIIF, Laborales, Societarias) e incluir ICT_2025 en
    Tributarias. La categoría TESTING (que contiene STUB_ECHO) se omite
    intencionalmente para que el cliente final no vea herramientas internas.
    """
    r = client.get(
        "/api/v1/client/catalog",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 200
    body = r.json()
    cats = {c["id"]: c for c in body["categories"]}
    # Las 4 categorías de cara al cliente
    for expected in ("TRIBUTARIAS", "NIIF", "LABORALES", "SOCIETARIAS"):
        assert expected in cats, f"Falta categoría {expected}"
    # ICT 2025 vive en TRIBUTARIAS
    trib_codes = [t["code"] for t in cats["TRIBUTARIAS"]["tools"]]
    assert "ICT_2025" in trib_codes
    # TESTING no debe salir al cliente
    assert "TESTING" not in cats


def test_catalog_rejects_unauthenticated(client):
    r = client.get("/api/v1/client/catalog")
    assert r.status_code in (401, 403)


def test_create_stub_job_and_complete(client, logged_client, db_session):
    # Upload a small file
    fake_pdf = b"%PDF-1.4 fake content"
    files = {
        "input": ("test.pdf", io.BytesIO(fake_pdf), "application/pdf"),
    }
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files=files,
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 201
    job_id = r.json()["id"]

    # Poll until done (BackgroundTasks runs synchronously in TestClient)
    r2 = client.get(
        f"/api/v1/client/tools/jobs/{job_id}",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "done"


def test_create_job_with_wrong_mime_rejected(client, logged_client):
    files = {
        "input": ("test.docx", io.BytesIO(b"x"),
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    }
    r = client.post(
        "/api/v1/client/tools/STUB_ECHO/jobs",
        files=files,
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 415


def test_create_job_with_unknown_tool_returns_404(client, logged_client):
    r = client.post(
        "/api/v1/client/tools/DOES_NOT_EXIST/jobs",
        files={"input": ("x.pdf", io.BytesIO(b"x"), "application/pdf")},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 404
