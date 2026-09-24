"""Integración del motor de ejecución con el pipeline de ToolJob (Task 13).

`ExecutionRun` NO reemplaza a `ToolJob`: lo ENVUELVE. Cada job del portal que
pasa por ``client_portal/jobs.py::process_tool_job`` deja además una corrida
reproducible (versiones, hashes, snapshot, historial), enlazada por
``engagement_id = project_id`` y con el ``run_id`` guardado en
``ToolJob.summary_json``.

El pipeline actual es SÍNCRONO (BackgroundTasks, un worker): aquí no se usa la
cola distribuida (`lease_next`), sino que se registra el ciclo de vida de la
corrida directamente (queued→running→succeeded/dead_letter). La cola y el
scheduler quedan disponibles para el worker asíncrono futuro.

Regla de oro: el seguimiento NUNCA puede tumbar el job real. Todo lo de este
módulo va envuelto en try/except que registra y sigue (misma filosofía que el
montaje aislado de Forge): si `execution_runs` no existe o algo falla, el job
del cliente se procesa igual.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import socket

from sqlalchemy.orm import Session

from backend.app.execution.models import ExecutionRun, STATUS_RUNNING, _utcnow
from backend.app.execution.queue import EnqueueRequest, enqueue, mark_failed, mark_succeeded

log = logging.getLogger(__name__)

#: Versión del runner que ejecuta las tools del portal. Se sella en cada
#: corrida para reproducibilidad (DATA-011). Súbela en cada cambio de lógica
#: de procesamiento con impacto en resultados.
RUNNER_ENGINE_VERSION = "1.0.0"


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _hash(payload) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def begin_job_run(db: Session, job) -> ExecutionRun:
    """Crea (idempotente) la corrida de un ToolJob y la marca en ejecución.

    La clave de idempotencia incorpora el ``tool_job_id``: reprocesar el mismo
    job mapea a la misma corrida. ``max_attempts=1`` porque el pipeline
    síncrono no reintenta solo (un fallo es terminal → dead_letter, visible
    para reencolar).
    """
    req = EnqueueRequest(
        engagement_id=job.project_id,
        app_id=job.tool_code,
        app_version="1",
        engine_version=RUNNER_ENGINE_VERSION,
        input_hashes={"tool_job_id": str(job.id)},
        parameter_snapshot={
            "period_label": job.period_label,
            "cliente": job.cliente_name,
            "firma_auditora": job.firma_auditora,
        },
        executed_by=job.user_id,
        trigger_source=job.initiated_from or "manual",
        max_attempts=1,
    )
    run = enqueue(db, req)
    # Pipeline síncrono: se toma directamente (no hay cola distribuida aún).
    run.status = STATUS_RUNNING
    run.worker_id = _worker_id()
    run.started_at = _utcnow()
    run.attempts = (run.attempts or 0) + 1
    db.commit()
    db.refresh(run)
    return run


def finish_job_run(db: Session, run: ExecutionRun, *, ok: bool,
                   summary: dict | None = None, error: str | None = None) -> None:
    """Sella la corrida al terminar el job: éxito o dead_letter."""
    if ok:
        output_hashes = {"summary": _hash(summary)} if summary else {}
        mark_succeeded(db, run, output_hashes=output_hashes, summary_json=summary)
    else:
        mark_failed(db, run, error_trace=error or "job terminó en error")


# --- Envoltorios seguros para el pipeline (nunca tumban el job) -------------
def track_begin(job_id: int) -> str | None:
    """Abre sesión, arranca la corrida del job y guarda el run_id en el job.

    Devuelve el ``run_id`` o None si el seguimiento falló (no fatal).
    """
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(ToolJob, job_id)
        if job is None:
            return None
        run = begin_job_run(db, job)
        # Enlaza el run_id en el summary del job sin pisar lo que haya.
        resumen = dict(job.summary_json or {})
        resumen["execution_run_id"] = run.run_id
        job.summary_json = resumen
        db.commit()
        return run.run_id
    except Exception:  # noqa: BLE001 - el seguimiento no puede tumbar el job
        log.exception("execution.track_begin falló para job %s (no fatal)", job_id)
        db.rollback()
        return None
    finally:
        db.close()


def track_finish(job_id: int, run_id: str | None, *, ok: bool,
                 error: str | None = None) -> None:
    """Cierra la corrida asociada a un job. No fatal."""
    if not run_id:
        return
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.db.session import SessionLocal
    from backend.app.execution.run_history import get_run

    db = SessionLocal()
    try:
        run = get_run(db, run_id)
        if run is None:
            return
        job = db.get(ToolJob, job_id)
        summary = dict(job.summary_json) if (job and job.summary_json) else None
        finish_job_run(db, run, ok=ok, summary=summary, error=error)
    except Exception:  # noqa: BLE001
        log.exception("execution.track_finish falló para job %s (no fatal)", job_id)
        db.rollback()
    finally:
        db.close()
