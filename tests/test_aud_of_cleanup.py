"""Tests de cleanup periódico."""

import datetime
import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role, User
from backend.app.aud.obligaciones_fiscales import cleanup, file_storage, service
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.context import service as ctx_service
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_OF_TMP_DIR", str(tmp_path))
    from importlib import reload

    from backend.app.core import config

    reload(config)
    reload(file_storage)
    init_db()
    yield


def _mk_admin_project():
    db = SessionLocal()
    try:
        tag = uuid.uuid4().hex[:6]
        u = auth_service.create_user(
            db, email=f"a-{tag}@ex.com", password="Sup3rSecret!", role=Role.admin
        )
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


def test_cleanup_marks_expired_jobs_and_deletes_dir():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        fresh_user = db.get(User, user_id)
        job = service.create_job(
            db, user=fresh_user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        # Forzar expires_at en el pasado
        job.expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=2)
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    job_dir = file_storage.create_job_dir(job_id)
    file_storage.save_input(job_dir, "f104", "x.pdf", b"x")
    assert job_dir.exists()

    summary = cleanup.cleanup_once()
    assert summary["expired_jobs"] >= 1
    assert not job_dir.exists()

    db = SessionLocal()
    try:
        reloaded = db.get(ToolJob, job_id)
        assert reloaded.status == "expired"
    finally:
        db.close()


def test_cleanup_removes_downloaded_old_dirs():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        fresh_user = db.get(User, user_id)
        job = service.create_job(
            db, user=fresh_user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        job.status = "done"
        job.downloaded_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(minutes=30)
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    job_dir = file_storage.create_job_dir(job_id)
    assert job_dir.exists()

    summary = cleanup.cleanup_once()
    assert summary["post_download_cleanups"] >= 1
    assert not job_dir.exists()
