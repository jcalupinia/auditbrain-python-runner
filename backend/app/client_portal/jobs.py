"""Dispatcher genérico que el worker invoca desde BackgroundTasks."""

from __future__ import annotations

import logging

from backend.app.client_portal.tool_registry import get_tool

log = logging.getLogger(__name__)


def process_tool_job(job_id: int) -> None:
    """Lee el job, busca su tool_code en el registry, invoca el processor."""
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_tool_job: job %s not found", job_id)
            return
        tool_code = job.tool_code
    finally:
        db.close()

    try:
        tool = get_tool(tool_code)
    except KeyError:
        log.error("process_tool_job: tool %s not registered", tool_code)
        _mark_error(job_id, f"Tool {tool_code} no registrada.")
        return

    try:
        tool.processor(job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("process_tool_job %s failed", job_id)
        _mark_error(job_id, str(e))


def _mark_error(job_id: int, message: str) -> None:
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return
        job.status = "error"
        job.error_message = message
        db.commit()
    finally:
        db.close()
