"""Cleanup periódico de jobs expirados y /tmp huérfanos.

Se ejecuta en background al arrancar la app (ver app.py startup hook).

Retención por INACTIVIDAD (decisión del dueño, 2026-10-07): descargar NO borra
nada. El TTL (`expires_at`) se reinicia en cada acción del auditor (subir,
procesar, aprobar, descargar, reabrir), así que un encargo solo se limpia tras
un buen rato sin tocarlo, o cuando el auditor le da «Encerar». Esto permite
descargar → revisar → corregir un dato mal cargado → volver a descargar sin
perder los documentos.

Borra:
- Jobs con expires_at < ahora (sin actividad en todo el TTL) → marca
  status='expired', borra /tmp.
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
    summary = {"expired_jobs": 0, "orphan_dirs": 0, "zombie_jobs": 0, "ict_files_deleted": 0}

    db = SessionLocal()
    try:
        # 1. Jobs expirados por INACTIVIDAD (el TTL se reinicia en cada acción;
        #    si expires_at ya pasó, el encargo lleva todo el TTL sin tocarse).
        #    Descargar NO expira el encargo: no se borra por haber descargado.
        expired = db.execute(
            select(ToolJob).where(
                ToolJob.expires_at < now,
                ToolJob.status.in_(
                    ["borrador", "revision", "pending", "running", "processing", "done"]
                ),
            )
        ).scalars().all()
        for j in expired:
            file_storage.delete_job_dir(j.id)
            j.status = "expired"
            db.add(j)
            summary["expired_jobs"] += 1

        # 2. Zombie jobs: status 'processing' por > 30 min → error
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
    """Loop infinito que ejecuta cleanup cada AUD_OF_CLEANUP_INTERVAL_SECONDS.

    ``cleanup_once`` es SÍNCRONO y bloqueante: abre una sesión Postgres, hace
    tres SELECT + commit, recorre directorios del disco montado y llama a
    ``cleanup_ict_orphan_files``. Ejecutarlo directamente aquí congelaba el
    event loop —y con él el health check— durante toda su duración, cada 5
    minutos. Se despacha a un hilo para que el loop siga atendiendo requests.
    """
    interval = settings.AUD_OF_CLEANUP_INTERVAL_SECONDS
    while True:
        try:
            s = await asyncio.to_thread(cleanup_once)
            if any(s.values()):
                log.info("aud_of cleanup: %s", s)
        except asyncio.CancelledError:
            # Shutdown ordenado: propagar para que la tarea termine.
            raise
        except Exception:
            log.exception("aud_of cleanup failed")
        await asyncio.sleep(interval)
