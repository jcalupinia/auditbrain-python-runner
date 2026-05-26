"""Tests de los endpoints HTTP de AUD obligaciones fiscales."""

import uuid
from pathlib import Path

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db

FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(file_storage)
    init_db()
    yield


def _mk_user(role=Role.user):
    tag = uuid.uuid4().hex[:6]
    email = f"u-{tag}@ex.com"
    pw = "Sup3rSecret!"
    db = SessionLocal()
    try:
        auth_service.create_user(db, email=email, password=pw, role=role)
    finally:
        db.close()
    return email, pw


def _login(client, email, pw):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _mk_admin_project(client):
    tag = uuid.uuid4().hex[:6]
    email, pw = _mk_user(Role.admin)
    tok = _login(client, email, pw)
    r = client.post(
        "/api/v1/context/clients", headers=_h(tok), json={"name": f"Cliente-{tag}"}
    )
    cid = r.json()["id"]
    r = client.post(
        "/api/v1/context/projects", headers=_h(tok),
        json={"client_id": cid, "name": f"Aud-{tag}", "module_code": "AUD"},
    )
    return tok, r.json()["id"]


def test_create_job_requires_at_least_one_pdf(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[],
    )
    assert r.status_code == 400


def test_create_job_unauthenticated_returns_401(client):
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        data={"project_id": 1, "cliente_name": "C", "period_label": "2025"},
    )
    assert r.status_code == 401


def test_create_job_with_f104_returns_201(client):
    tok, pid = _mk_admin_project(client)
    pdf_bytes = (FIXTURES / "f104_enero.pdf").read_bytes()
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "NEGOCIOS MORACOSTA S.A.",
              "period_label": "2025"},
        files=[("files_f104", ("f104.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project_id"] == pid
    assert body["status"] in ("pending", "running", "done")
    assert body["tool_code"] == "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"


def test_get_job_returns_detail(client):
    tok, pid = _mk_admin_project(client)
    pdf_bytes = (FIXTURES / "f104_enero.pdf").read_bytes()
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[("files_f104", ("a.pdf", pdf_bytes, "application/pdf"))],
    )
    jid = r.json()["id"]
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == jid


def test_list_jobs_filters_by_project(client):
    tok, pid = _mk_admin_project(client)
    pdf_bytes = (FIXTURES / "f104_enero.pdf").read_bytes()
    for _ in range(2):
        client.post(
            "/api/v1/aud/obligaciones-fiscales/jobs",
            headers=_h(tok),
            data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
            files=[("files_f104", ("a.pdf", pdf_bytes, "application/pdf"))],
        )
    r = client.get(
        f"/api/v1/aud/obligaciones-fiscales/jobs?project_id={pid}",
        headers=_h(tok),
    )
    assert r.status_code == 200, r.text
    assert len(r.json()) == 2


def test_user_without_project_access_403(client):
    tok_admin, pid = _mk_admin_project(client)
    email, pw = _mk_user(Role.user)
    tok = _login(client, email, pw)
    pdf_bytes = (FIXTURES / "f104_enero.pdf").read_bytes()
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[("files_f104", ("a.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 403


def test_reject_non_pdf_for_f104(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[("files_f104", ("a.xlsx", b"not a pdf",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    assert r.status_code == 415


def test_end_to_end_create_run_download(client):
    """Crea job, procesa BackgroundTask (sync por TestClient), descarga Excel."""
    tok, pid = _mk_admin_project(client)
    pdf_bytes = (FIXTURES / "f104_enero.pdf").read_bytes()
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "X", "period_label": "2025"},
        files=[("files_f104", ("f104.pdf", pdf_bytes, "application/pdf"))],
    )
    assert r.status_code == 201, r.text
    jid = r.json()["id"]

    # FastAPI TestClient ejecuta BackgroundTasks de forma síncrona al salir
    # del context manager. Como nuestro client fixture usa `with`, los tasks
    # ya corrieron cuando retorna la respuesta.
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r.json()["status"] == "done", r.json()

    r = client.get(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/download",
        headers=_h(tok),
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(r.content) > 1000
