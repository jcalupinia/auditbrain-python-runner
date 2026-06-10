"""Cleanup periódico de jobs expirados y /tmp huérfanos.

Se ejecuta en background al arrancar la app (ver app.py startup hook).
Borra:
- Jobs con expires_at < ahora → marca status='expired', borra /tmp.
- Jobs descargados hace > N min → borra /tmp (DB se mantiene para historial).
- Directorios /tmp huérfanos (sin job en DB pero con mtime > TTL).
"""

from __future__ import annotations

import asyncio
import datetime
import logging

from sqlalchemy import select

from backend.app.aud.obligaciones_fiscales import file_storage
from backend.app.aud.obligaciones_fiscales.models import ToolJob
from backend.app.core.config import settings
from backend.app.db.session import SessionLocal

log = logging.getLogger(__name__)


def cleanup_once() -> dict:
    """Una pasada de cleanup. Devuelve resumen de acciones."""
    from backend.app.ict import service as ict_service

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    summary = {"expired_jobs": 0, "post_download_cleanups": 0, "orphan_dirs": 0, "zombie_jobs": 0, "ict_files_deleted": 0}

    db = SessionLocal()
    try:
        # 1. Jobs expirados por TTL
        expired = db.execute(
            select(ToolJob).where(
                ToolJob.expires_at < now,
                ToolJob.status.in_(["pending", "running", "processing", "done"]),
            )
        ).scalars().all()
        for j in expired:
            file_storage.delete_job_dir(j.id)
            j.status = "expired"
            db.add(j)
            summary["expired_jobs"] += 1

        # 2. Jobs descargados hace > N min
        post_dl_threshold = now - datetime.timedelta(
            minutes=settings.AUD_OF_POST_DOWNLOAD_TTL_MINUTES
        )
        downloaded_old = db.execute(
            select(ToolJob).where(
                ToolJob.downloaded_at.is_not(None),
                ToolJob.downloaded_at < post_dl_threshold,
                ToolJob.status == "done",
            )
        ).scalars().all()
        for j in downloaded_old:
            file_storage.delete_job_dir(j.id)
            summary["post_download_cleanups"] += 1

        # 4. Zombie jobs: status 'processing' por > 30 min → error
        zombie_threshold = now - datetime.timedelta(minutes=30)
        zombies = db.execute(
            select(ToolJob).where(
                ToolJob.status == "processing",
                ToolJob.created_at < zombie_threshold,
            )
        ).scalars().all()
        for j in zombies:
            j.status = "error"
            j.error_message = (
                "Tiempo de procesamiento excedido (zombie detectado por cleanup). "
                "Reintenta el trabajo."
            )
            db.add(j)
            summary["zombie_jobs"] += 1

        db.commit()
    finally:
        db.close()

    # 3. Directorios /tmp huérfanos
    orphans = file_storage.list_orphan_job_dirs(
        max_age_seconds=settings.AUD_OF_JOB_TTL_MINUTES * 60
    )
    for d in orphans:
        try:
            file_storage.delete_job_dir(int(d.name))
            summary["orphan_dirs"] += 1
        except Exception:
            pass

    summary["ict_files_deleted"] = ict_service.cleanup_ict_orphan_files(max_age_hours=24)

    return summary


async def cleanup_loop() -> None:
    """Loop infinito que ejecuta cleanup cada AUD_OF_CLEANUP_INTERVAL_SECONDS."""
    interval = settings.AUD_OF_CLEANUP_INTERVAL_SECONDS
    while True:
        try:
            s = cleanup_once()
            if any(s.values()):
                log.info("aud_of cleanup: %s", s)
        except Exception:
            log.exception("aud_of cleanup failed")
        await asyncio.sleep(interval)
