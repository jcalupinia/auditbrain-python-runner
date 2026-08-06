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


def test_crear_job_sin_archivos_lo_deja_en_borrador(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "borrador"


def test_ya_no_existen_los_slots_de_mayor_de_compras_y_ventas(client):
    from backend.app.aud.obligaciones_fiscales import router as router_mod

    assert "mayor_compras" not in router_mod.ALLOWED_MIMES
    assert "mayor_ventas" not in router_mod.ALLOWED_MIMES
    assert "mayor_general" in router_mod.ALLOWED_MIMES
    assert "mayor_especifico" in router_mod.ALLOWED_MIMES


def test_create_job_unauthenticated_returns_401(client):
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        data={"project_id": 1, "cliente_name": "C", "period_label": "2025"},
    )
    assert r.status_code == 401


def test_create_job_returns_201_en_borrador(client):
    """El job nace en 'borrador': ya no se suben archivos en el mismo POST.

    Se manda un campo multipart legacy (``files_f104``) que el endpoint ya no
    declara, para confirmar que un cliente viejo que aún lo envíe no rompe la
    creación (FastAPI ignora los campos no declarados)."""
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
    assert body["status"] == "borrador"
    assert body["tool_code"] == "AUD.IMPUESTOS.OBLIGACIONES_FISCALES"


def test_get_job_returns_detail(client):
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    jid = r.json()["id"]
    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["id"] == jid


def test_list_jobs_filters_by_project(client):
    tok, pid = _mk_admin_project(client)
    for _ in range(2):
        client.post(
            "/api/v1/aud/obligaciones-fiscales/jobs",
            headers=_h(tok),
            data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
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
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
    )
    assert r.status_code == 403


def test_reject_non_pdf_for_f104_ya_no_se_valida_al_crear(client):
    """La validación de tipo de archivo se mudó al endpoint de slots (Task 6,
    ver ``tests/test_aud_of_slots.py``): crear el job ya no recibe archivos,
    así que un content-type inválido para f104 ya no es rechazable aquí."""
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "C", "period_label": "2025"},
        files=[("files_f104", ("a.xlsx", b"not a pdf",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "borrador"


def test_job_recien_creado_no_se_auto_procesa_y_no_se_puede_descargar(client):
    """Antes: el job se auto-procesaba (BackgroundTask) al crearse. Ahora es
    una sesión persistente: nace en 'borrador' y solo pasa a 'done' tras el
    ciclo completo (subir archivos → procesar → revisar → aprobar), fuera del
    alcance de las tasks 5-6. Por eso la descarga debe fallar con 409."""
    tok, pid = _mk_admin_project(client)
    r = client.post(
        "/api/v1/aud/obligaciones-fiscales/jobs",
        headers=_h(tok),
        data={"project_id": pid, "cliente_name": "X", "period_label": "2025"},
    )
    assert r.status_code == 201, r.text
    jid = r.json()["id"]

    r = client.get(f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}", headers=_h(tok))
    assert r.json()["status"] == "borrador", r.json()

    r = client.get(
        f"/api/v1/aud/obligaciones-fiscales/jobs/{jid}/download",
        headers=_h(tok),
    )
    assert r.status_code == 409
