"""Integración ExecutionRun ↔ ToolJob (Task 13 del plan P1-D)."""
import os
import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.execution.models import (
    ExecutionRun,
    STATUS_DEAD_LETTER,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
)
from backend.app.execution import integration as I


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    from backend.app.execution import models  # noqa: F401
    import backend.app.auth.models  # noqa: F401  (registra users)
    import backend.app.context.models  # noqa: F401  (registra projects)
    Base.metadata.create_all(eng, tables=[ExecutionRun.__table__])
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _job(**k):
    base = dict(id=42, project_id=7, tool_code="ICT_2025", period_label="2025",
                cliente_name="ACME", firma_auditora="audit_consulting",
                user_id=3, initiated_from="client", summary_json=None)
    base.update(k)
    return types.SimpleNamespace(**base)


def test_begin_marca_running_y_enlaza_engagement(db):
    run = I.begin_job_run(db, _job())
    assert run.status == STATUS_RUNNING and run.engagement_id == 7
    assert run.app_id == "ICT_2025" and run.attempts == 1
    assert run.engine_version == I.RUNNER_ENGINE_VERSION


def test_begin_es_idempotente_por_job(db):
    a = I.begin_job_run(db, _job())
    b = I.begin_job_run(db, _job())
    assert a.run_id == b.run_id
    assert db.query(ExecutionRun).count() == 1


def test_finish_ok_sella_succeeded(db):
    run = I.begin_job_run(db, _job())
    I.finish_job_run(db, run, ok=True, summary={"excepciones": [1, 2]})
    assert run.status == STATUS_SUCCEEDED and run.output_hashes.get("summary")
    assert run.completed_at is not None


def test_finish_error_va_a_dead_letter(db):
    run = I.begin_job_run(db, _job())  # max_attempts=1
    I.finish_job_run(db, run, ok=False, error="boom")
    assert run.status == STATUS_DEAD_LETTER and "boom" in run.error_trace


# --- track_begin/track_finish contra el SessionLocal global -----------------
def test_track_begin_y_finish_end_to_end():
    """El pipeline síncrono deja la corrida sellada y el run_id en el job.

    Usa el ``SessionLocal`` global (la DB temporal la fija ``DATABASE_URL`` del
    comando de pytest) e ``init_db()`` para crear ``tool_jobs`` +
    ``execution_runs``. En SQLite las FK no se fuerzan, así que no hace falta un
    proyecto real.
    """
    from backend.app.db.session import SessionLocal, init_db
    from backend.app.aud.obligaciones_fiscales.models import ToolJob
    from backend.app.execution.run_history import get_run

    init_db()

    import datetime as _dt
    db = SessionLocal()
    job = ToolJob(project_id=1, tool_code="FLUJO_EFECTIVO", cliente_name="ACME",
                  period_label="2025", status="pending",
                  expires_at=_dt.datetime.utcnow() + _dt.timedelta(days=1))
    db.add(job)
    db.commit()
    job_id = job.id
    db.close()

    run_id = I.track_begin(job_id)
    assert run_id

    db = SessionLocal()
    job = db.get(ToolJob, job_id)
    assert job.summary_json.get("execution_run_id") == run_id
    job.status = "done"
    db.commit()
    db.close()

    I.track_finish(job_id, run_id, ok=True)

    db = SessionLocal()
    assert get_run(db, run_id).status == STATUS_SUCCEEDED
    db.close()
