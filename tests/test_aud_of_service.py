"""Tests del service layer + jobs orchestrator."""

import uuid
from pathlib import Path

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role, User
from backend.app.aud.obligaciones_fiscales import (
    file_storage,
    jobs,
    service as of_service,
)
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


@pytest.fixture()
def tmp_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(file_storage)
    yield tmp_path


def _mk_admin_project():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:6]
        email = f"a-{tag}@ex.com"
        u = auth_service.create_user(db, email=email, password="Sup3rSecret!", role=Role.admin)
        u = ctx_service.ensure_user_has_organization(db, u)
        c = ctx_service.create_client(
            db, organization_id=u.organization_id, name=f"Cliente-{tag}"
        )
        p = ctx_service.create_project(
            db, organization_id=u.organization_id, client_id=c.id,
            name=f"Aud-{tag}", module_code="AUD",
        )
        ctx_service.add_project_member(db, p.id, u.id, "lead")
        return u.id, p.id
    finally:
        db.close()


def test_create_job_pending_with_expires_at():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        job = of_service.create_job(
            db, user=user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        assert job.id is not None
        assert job.status == "pending"
        assert job.expires_at > job.created_at
        assert job.tool_code == of_service.TOOL_CODE
    finally:
        db.close()


def test_create_job_no_access_raises():
    _, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        other = auth_service.create_user(
            db, email=f"o-{uuid.uuid4().hex[:6]}@ex.com",
            password="Sup3rSecret!", role=Role.user,
        )
        other = ctx_service.ensure_user_has_organization(db, other)
        with pytest.raises(PermissionError):
            of_service.create_job(
                db, user=other, project_id=project_id,
                cliente_name="C", period_label="2025",
            )
    finally:
        db.close()


def test_mark_done_updates_status_and_summary():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        job = of_service.create_job(
            db, user=user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        of_service.mark_done(db, job.id, {"x": 1})
        reloaded = db.get(ToolJob, job.id)
        assert reloaded.status == "done"
        assert reloaded.summary_json == {"x": 1}
        assert reloaded.finished_at is not None
    finally:
        db.close()


def test_list_jobs_filters_by_project_and_orders_desc():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        j1 = of_service.create_job(db, user=user, project_id=project_id,
                                   cliente_name="A", period_label="2025")
        j2 = of_service.create_job(db, user=user, project_id=project_id,
                                   cliente_name="B", period_label="2025")
        items = of_service.list_jobs_for_project(db, user, project_id)
        assert len(items) == 2
        assert items[0].id == j2.id
    finally:
        db.close()


def test_process_job_end_to_end_with_real_pdf(tmp_root):
    """Sube el F-104 enero real, ejecuta process_job, verifica output.xlsx."""
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        job = of_service.create_job(
            db, user=user, project_id=project_id,
            cliente_name="NEGOCIOS MORACOSTA S.A.", period_label="2025",
        )
        job_id = job.id
    finally:
        db.close()

    # Subir el PDF al directorio del job
    job_dir = file_storage.create_job_dir(job_id)
    pdf_bytes = (FIXTURES / "f104_enero.pdf").read_bytes()
    file_storage.save_input(job_dir, "f104", "f104_enero.pdf", pdf_bytes)

    # Ejecutar el orquestador en foreground (sin BackgroundTask)
    jobs.process_job(job_id)

    # Verificar estado + output
    db = SessionLocal()
    try:
        final = db.get(ToolJob, job_id)
        assert final.status == "done", f"status={final.status}, error={final.error_message}"
        assert final.summary_json["dm7_months_with_data"] == 1
        assert final.summary_json["dm6_months_with_data"] == 1
    finally:
        db.close()

    out = file_storage.output_path(job_dir)
    assert out.exists()
    assert out.stat().st_size > 1000  # Excel real, no vacío
