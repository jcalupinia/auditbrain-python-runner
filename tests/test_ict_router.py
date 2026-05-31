"""Tests for /api/v1/client/ict/* endpoints."""
import io
import uuid

import pytest

from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def logged_client(client, db_session):
    suffix = _unique("ictrouter")
    org = Organization(name=f"O-{suffix}", slug=f"o-{suffix}", is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(organization_id=org.id, name=f"C-{suffix}", is_active=True)
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    email = f"ictr-{suffix}@x.com"
    user, pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": pwd},
    )
    assert r.status_code == 200, r.json()
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {
        "user": user,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "device_id": device_id,
        "cookies": {"device_id": device_id} if device_id else {},
    }


def test_create_session_returns_201_with_session(client, logged_client):
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={
            "ejercicio_fiscal": "2025",
            "ruc": "1234567890001",
            "razon_social": "Test S.A.",
        },
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 201, r.json()
    body = r.json()
    assert body["ejercicio_fiscal"] == "2025"
    assert body["status"] == "in_progress"
    assert len(body["anexos"]) == 10


def test_get_active_session_returns_404_if_no_session(client, logged_client):
    r = client.get(
        "/api/v1/client/ict/sessions/active",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 404


def test_get_active_session_returns_existing(client, logged_client):
    client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "X"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    r = client.get(
        "/api/v1/client/ict/sessions/active",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 200
    assert r.json()["ejercicio_fiscal"] == "2025"


def test_patch_session_updates_razon_social(client, logged_client):
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "Old"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    session_id = r.json()["id"]
    r2 = client.patch(
        f"/api/v1/client/ict/sessions/{session_id}",
        json={"razon_social": "New Name"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r2.status_code == 200
    assert r2.json()["razon_social"] == "New Name"


def test_download_returns_excel_for_existing_session(client, logged_client):
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "X"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 201, r.json()
    session_id = r.json()["id"]

    r2 = client.get(
        f"/api/v1/client/ict/sessions/{session_id}/download",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r2.status_code == 200
    assert len(r2.content) > 1000


def test_delete_session_expires_it(client, logged_client):
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "X"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    session_id = r.json()["id"]
    r2 = client.delete(
        f"/api/v1/client/ict/sessions/{session_id}",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r2.status_code == 200
    # Now active session should be 404
    r3 = client.get(
        "/api/v1/client/ict/sessions/active",
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r3.status_code == 404


def test_upload_balance_excel_for_a1(client, logged_client, db_session):
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "X"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    session_id = r.json()["id"]

    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Código", "Nombre", "Saldo Final"])
    ws.append(("1.1.01.01.01", "CAJA", 300.0))
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    r2 = client.post(
        f"/api/v1/client/ict/sessions/{session_id}/anexos/A1/upload",
        files={"files": ("balance.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"slot_name": "balance"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r2.status_code == 200, r2.json()
    body = r2.json()
    assert body["anexo_code"] == "A1"
    assert body["status"] in ("partial", "ready")


def test_upload_unsupported_slot_returns_400(client, logged_client):
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "X"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    session_id = r.json()["id"]
    r2 = client.post(
        f"/api/v1/client/ict/sessions/{session_id}/anexos/A1/upload",
        files={"files": ("x.txt", io.BytesIO(b"x"), "text/plain")},
        data={"slot_name": "unsupported_slot"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r2.status_code == 400


def test_upload_multiple_f104_pdfs_in_one_call(client, logged_client):
    """Multi-upload: subir 2 F-104 PDFs (de 2 meses distintos) en un solo POST."""
    r = client.post(
        "/api/v1/client/ict/sessions",
        json={"ejercicio_fiscal": "2025", "ruc": "1234567890001", "razon_social": "X"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    assert r.status_code == 201, r.json()
    session_id = r.json()["id"]

    def make_fake_f104_pdf(month: int) -> bytes:
        """PDF mínimo con texto que referencia un mes; pdfplumber puede no extraer datos,
        pero el endpoint debe aceptar el multipart y responder 200."""
        text = f"Mes: {month:02d} Ano: 2025  411  1000.50"
        content = f"BT /F1 12 Tf 100 700 Td ({text}) Tj ET"
        stream = content.encode()
        return (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/Resources<<>>/MediaBox[0 0 612 792]/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length " + str(len(stream)).encode() + b">>stream\n"
            + stream
            + b"\nendstream endobj\n"
            b"xref\n0 5\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000210 00000 n \n"
            b"trailer<</Size 5/Root 1 0 R>>\n"
            b"startxref\n300\n%%EOF\n"
        )

    files_payload = [
        ("files", (f"f104_{m:02d}.pdf", io.BytesIO(make_fake_f104_pdf(m)), "application/pdf"))
        for m in [1, 2]
    ]
    r2 = client.post(
        f"/api/v1/client/ict/sessions/{session_id}/anexos/A2/upload",
        files=files_payload,
        data={"slot_name": "f104"},
        headers=logged_client["headers"],
        cookies=logged_client["cookies"],
    )
    # El endpoint debe aceptar el payload multipart y responder 200
    assert r2.status_code == 200, r2.json()
    body = r2.json()
    assert body["anexo_code"] == "A2"
    # files_processed puede ser 0 si el parser no extrae datos del PDF mínimo, pero la
    # respuesta debe tener la estructura correcta
    assert "files_processed" in body
    assert "per_file" in body
    assert isinstance(body["per_file"], list)
