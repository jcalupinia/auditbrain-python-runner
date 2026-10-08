"""Tests de cleanup periódico."""

import datetime
import os
import time
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


def _job_expirado_con_dir():
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        fresh_user = db.get(User, user_id)
        job = service.create_job(
            db, user=fresh_user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        job.expires_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - datetime.timedelta(hours=2)
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()
    job_dir = file_storage.create_job_dir(job_id)
    file_storage.save_input(job_dir, "f104", "x.pdf", b"x")
    assert job_dir.exists()
    return job_id, job_dir


def test_retencion_manual_por_defecto_no_borra_aunque_este_expirado(monkeypatch):
    """Decisión del dueño (2026-10-07): BORRADO MANUAL. Sin activar la
    retención, un encargo no se autoelimina por tiempo aunque expire; se
    mantiene hasta que el auditor le da «borrar»/«Encerar»."""
    monkeypatch.setattr(cleanup.settings, "AUD_OF_RETENCION_ENABLED", False)
    job_id, job_dir = _job_expirado_con_dir()

    summary = cleanup.cleanup_once()
    assert summary["expired_jobs"] == 0
    assert job_dir.exists()  # NO se borró

    db = SessionLocal()
    try:
        assert db.get(ToolJob, job_id).status != "expired"
    finally:
        db.close()


def test_con_retencion_activada_borra_expirados(monkeypatch):
    """Con AUD_OF_RETENCION_ENABLED=true (red de seguridad opcional) sí se
    limpia lo que lleva todo el TTL sin tocarse."""
    monkeypatch.setattr(cleanup.settings, "AUD_OF_RETENCION_ENABLED", True)
    job_id, job_dir = _job_expirado_con_dir()

    summary = cleanup.cleanup_once()
    assert summary["expired_jobs"] >= 1
    assert not job_dir.exists()

    db = SessionLocal()
    try:
        assert db.get(ToolJob, job_id).status == "expired"
    finally:
        db.close()


def test_descargar_no_borra_los_documentos():
    """Decisión del dueño (2026-10-07): descargar NO borra los documentos.

    Durante la revisión el auditor descarga, detecta un dato mal cargado,
    reabre, corrige y vuelve a descargar sin perder los documentos. La limpieza
    es por INACTIVIDAD: solo borra cuando el TTL (que se reinicia en cada
    acción) vence."""
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        fresh_user = db.get(User, user_id)
        job = service.create_job(
            db, user=fresh_user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        job.status = "done"
        db.add(job)
        db.commit()
        job_id = job.id
    finally:
        db.close()

    job_dir = file_storage.create_job_dir(job_id)
    assert job_dir.exists()

    # El auditor descarga: queda registrado, pero reinicia el TTL (no expira).
    db = SessionLocal()
    try:
        service.mark_downloaded(db, job_id)
        reloaded = db.get(ToolJob, job_id)
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        assert reloaded.downloaded_at is not None
        assert reloaded.expires_at > now  # sigue vivo tras descargar
    finally:
        db.close()

    summary = cleanup.cleanup_once()
    assert "post_download_cleanups" not in summary  # la acción ya no existe
    assert job_dir.exists()  # NO se borró por haber descargado


def _envejecer(path, segundos):
    """Mueve la mtime de un directorio al pasado para simular inactividad."""
    viejo = time.time() - segundos
    os.utime(path, (viejo, viejo))


def test_un_encargo_vigente_sin_tocar_no_se_borra_como_huerfano():
    """Regresión del #69: la limpieza de «huérfanos» borraba cualquier carpeta
    con mtime > TTL SIN mirar la base. Un encargo vivo (con fila en DB) que
    llevaba horas sin tocarse perdía sus documentos y «editar» daba 410. Ahora
    solo se borran carpetas SIN fila en la base."""
    job_id, job_dir = _job_expirado_con_dir()  # tiene fila en DB
    _envejecer(job_dir, 10 * 60 * 60)  # 10 h sin tocar (> TTL de 4 h)

    summary = cleanup.cleanup_once()
    assert summary["orphan_dirs"] == 0
    assert job_dir.exists()  # el encargo vigente conserva sus documentos


def test_una_carpeta_sin_job_en_la_base_si_se_borra_como_huerfano():
    """La contraparte: una carpeta en disco cuyo job ya no existe en la base
    (p. ej. se borró la fila pero quedó la carpeta) sí es huérfana y se limpia
    cuando supera el TTL."""
    huerfano = file_storage.job_dir(999_999)
    huerfano.mkdir(parents=True, exist_ok=True)
    _envejecer(huerfano, 10 * 60 * 60)

    summary = cleanup.cleanup_once()
    assert summary["orphan_dirs"] >= 1
    assert not huerfano.exists()


def test_borrar_un_encargo_elimina_tambien_la_carpeta_del_disco():
    """«Borrar» se lleva la fila Y los documentos del disco, sin dejar
    huérfanos ocupando espacio."""
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        fresh_user = db.get(User, user_id)
        job = service.create_job(
            db, user=fresh_user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        job_id = job.id
    finally:
        db.close()
    job_dir = file_storage.create_job_dir(job_id)
    file_storage.save_input(job_dir, "f104", "x.pdf", b"x")
    assert job_dir.exists()

    db = SessionLocal()
    try:
        service.delete_job(db, db.get(User, user_id), job_id)
    finally:
        db.close()
    assert not job_dir.exists()


def test_touch_job_reinicia_el_ttl():
    """Cada acción del auditor (subir, procesar, aprobar, descargar, reabrir)
    reinicia el TTL por inactividad: un encargo a punto de expirar vuelve a
    quedar vivo."""
    user_id, project_id = _mk_admin_project()
    db = SessionLocal()
    try:
        fresh_user = db.get(User, user_id)
        job = service.create_job(
            db, user=fresh_user, project_id=project_id,
            cliente_name="C", period_label="2025",
        )
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        job.expires_at = now - datetime.timedelta(minutes=1)  # casi vencido
        db.add(job)
        db.commit()
        job_id = job.id

        service.touch_job(db, job_id)
        reloaded = db.get(ToolJob, job_id)
        assert reloaded.expires_at > now  # revivido
    finally:
        db.close()
