"""CRUD de ToolJob para el Informe de Cumplimiento Tributario + autorización."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.context import service as ctx_service
from backend.app.context.models import Project
from backend.app.core.config import settings

TOOL_CODE = "AUD.CONCLUSION.INFORME_CUMPLIMIENTO_TRIBUTARIO"


def _ensure_project_access(db: Session, user, project_id: int) -> Project:
    proj = db.get(Project, project_id)
    if not proj or not ctx_service.user_can_access_project(db, user, proj):
        raise PermissionError("Sin acceso al proyecto.")
    return proj


def create_job(
    db: Session,
    *,
    user,
    project_id: int,
    cliente_name: str,
    ejercicio: str,
    firma_auditora: str,
) -> ToolJob:
    _ensure_project_access(db, user, project_id)
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    job = ToolJob(
        user_id=user.id,
        project_id=project_id,
        tool_code=TOOL_CODE,
        status="pending",
        cliente_name=cliente_name,
        period_label=ejercicio,  # reutilizamos period_label para el ejercicio
        firma_auditora=firma_auditora,
        created_at=now,
        expires_at=now + datetime.timedelta(minutes=settings.AUD_OF_JOB_TTL_MINUTES),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, user, job_id: int) -> ToolJob:
    job = db.get(ToolJob, job_id)
    if not job or job.tool_code != TOOL_CODE:
        raise PermissionError("Job no encontrado.")
    _ensure_project_access(db, user, job.project_id)
    return job


def list_jobs_for_project(db: Session, user, project_id: int, limit: int = 20):
    _ensure_project_access(db, user, project_id)
    return list(
        db.execute(
            select(ToolJob)
            .where(ToolJob.project_id == project_id, ToolJob.tool_code == TOOL_CODE)
            .order_by(ToolJob.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def mark_running(db: Session, job_id: int) -> None:
    _set_status(db, job_id, "running")


def mark_done(db: Session, job_id: int, summary: dict) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "done"
        job.finished_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        job.summary_json = summary
        db.add(job)
        db.commit()


def mark_failed(db: Session, job_id: int, error_message: str) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = "failed"
        job.finished_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        job.error_message = error_message[:5000]
        db.add(job)
        db.commit()


def mark_downloaded(db: Session, job_id: int) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.downloaded_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        db.add(job)
        db.commit()


def delete_job(db: Session, user, job_id: int) -> None:
    job = get_job(db, user, job_id)
    db.delete(job)
    db.commit()


def _set_status(db: Session, job_id: int, status: str) -> None:
    job = db.get(ToolJob, job_id)
    if job:
        job.status = status
        db.add(job)
        db.commit()
