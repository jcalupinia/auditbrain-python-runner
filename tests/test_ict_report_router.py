"""Tests de los endpoints HTTP del Informe de Cumplimiento Tributario."""

import uuid
from pathlib import Path

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.db.session import SessionLocal, init_db

FIX = Path(__file__).parent / "fixtures" / "informe_cumplimiento_tributario"
BASE = "/api/v1/aud/informe-cumplimiento-tributario"


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload
    from backend.app.core import config
    reload(config)
    reload(file_storage)
    init_db()
    yield


def _mk_user(role=Role.admin):
    tag = uuid.uuid4().hex[:6]
    email, pw = f"u-{tag}@ex.com", "Sup3rSecret!"
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


def _admin_project(client):
    tag = uuid.uuid4().hex[:6]
    email, pw = _mk_user(Role.admin)
    tok = _login(client, email, pw)
    cid = client.post("/api/v1/context/clients", headers=_h(tok),
                      json={"name": f"C-{tag}"}).json()["id"]
    pid = client.post("/api/v1/context/projects", headers=_h(tok),
                      json={"client_id": cid, "name": f"P-{tag}", "module_code": "AUD"}).json()["id"]
    return tok, pid


def _files():
    return [
        ("informe_auditoria_externa", ("inf.pdf",
            (FIX / "informe_auditoria_externa_axxis.pdf").read_bytes(), "application/pdf")),
        ("declaracion_ir", ("f101.pdf",
            (FIX / "f101_axxis.pdf").read_bytes(), "application/pdf")),
    ]


def test_create_requires_both_pdfs(client):
    tok, pid = _admin_project(client)
    r = client.post(f"{BASE}/jobs", headers=_h(tok),
                    data={"project_id": pid, "cliente_name": "X", "ejercicio": "2025",
                          "firma_auditora": "audit_consulting", "fecha_carga_sri": "08 de julio de 2026"},
                    files=[])
    assert r.status_code == 400


def test_end_to_end_create_and_download_docx(client):
    tok, pid = _admin_project(client)
    r = client.post(f"{BASE}/jobs", headers=_h(tok),
                    data={"project_id": pid, "cliente_name": "AXXISGASTRO CIA. LTDA.",
                          "ejercicio": "2025", "firma_auditora": "audit_consulting",
                          "fecha_carga_sri": "08 de julio de 2026",
                          "hay_recomendaciones": "false"},
                    files=_files())
    assert r.status_code == 201, r.text
    jid = r.json()["id"]
    assert r.json()["tool_code"] == "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO"

    # TestClient corre el BackgroundTask sync al cerrar el context.
    r = client.get(f"{BASE}/jobs/{jid}", headers=_h(tok))
    assert r.json()["status"] == "done", r.json()

    r = client.get(f"{BASE}/jobs/{jid}/download", headers=_h(tok))
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(r.content) > 2000


def test_parse_preview_devuelve_datos(client):
    tok, pid = _admin_project(client)
    r = client.post(f"{BASE}/parse-preview", headers=_h(tok), files=_files())
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fecha_emision"] == "27 de febrero de 2026"
    assert body["marco_contable"] == "pymes"
    assert body["fecha_declaracion_ir"] == "09 de abril de 2026"
