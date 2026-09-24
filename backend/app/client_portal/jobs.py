"""Dispatcher genérico que el worker invoca desde BackgroundTasks."""

from __future__ import annotations

import logging

from backend.app.client_portal.tool_registry import get_tool

log = logging.getLogger(__name__)


def process_tool_job(job_id: int) -> None:
    """Lee el job, busca su tool_code en el registry, invoca el processor,
    envía email al completar (solo si initiated_from='client' y notify_email seteado).
    """
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal
    from backend.app.execution import integration as _exec
    from backend.app.notifications.email import send_job_ready_email

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            log.error("process_tool_job: job %s not found", job_id)
            return
        tool_code = job.tool_code
        notify_email = job.notify_email
        initiated_from = job.initiated_from
    finally:
        db.close()

    # Seguimiento reproducible de la corrida (Task 13). No fatal: si falla,
    # el job se procesa igual y run_id queda None.
    run_id = _exec.track_begin(job_id)

    try:
        tool = get_tool(tool_code)
    except KeyError:
        log.error("process_tool_job: tool %s not registered", tool_code)
        _mark_error(job_id, f"Tool {tool_code} no registrada.")
        _exec.track_finish(job_id, run_id, ok=False, error=f"Tool {tool_code} no registrada.")
        return

    if tool.processor is None:
        # Tool externa (p. ej. ICT_2025): tiene su propio flujo y nunca
        # debería llegar al pipeline genérico. Marca el job en error
        # explícito para diagnóstico, en lugar de un AttributeError.
        log.error("process_tool_job: tool %s has no processor (external flow)", tool_code)
        _mark_error(job_id, f"Tool {tool_code} usa flujo dedicado, no pipeline genérico.")
        _exec.track_finish(job_id, run_id, ok=False,
                           error=f"Tool {tool_code} usa flujo dedicado, no pipeline genérico.")
        return

    try:
        tool.processor(job_id)
    except Exception as e:  # noqa: BLE001
        log.exception("process_tool_job %s failed", job_id)
        _mark_error(job_id, str(e))
        _exec.track_finish(job_id, run_id, ok=False, error=str(e))
        return

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        final_status = job.status if job else "unknown"
        final_error = job.error_message if job else None
    finally:
        db.close()

    _exec.track_finish(job_id, run_id, ok=(final_status == "done"),
                       error=None if final_status == "done" else final_error)

    if final_status == "done" and initiated_from == "client" and notify_email:
        try:
            send_job_ready_email(job_id=job_id, to=notify_email, tool_label=tool.label)
        except Exception:
            log.exception("Email notification failed for job %s (non-fatal)", job_id)


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
