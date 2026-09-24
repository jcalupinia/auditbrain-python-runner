"""Modelo ExecutionRun (contrato §2) — Task 1 del plan P1-D."""
from backend.app.db.session import Base, init_db
from backend.app.execution.models import (
    ExecutionRun,
    STATUS_QUEUED,
    STATUS_DEAD_LETTER,
    TERMINAL_STATUSES,
)


def test_la_tabla_se_crea_en_init_db():
    init_db()  # no debe lanzar; execution_runs queda registrada en metadata
    assert "execution_runs" in Base.metadata.tables


def test_campos_del_contrato_estan_presentes():
    cols = set(Base.metadata.tables["execution_runs"].columns.keys())
    esperados = {
        "run_id", "engagement_id", "app_id", "app_version", "engine_version",
        "input_hashes", "parameter_snapshot", "started_at", "completed_at",
        "status", "executed_by", "worker_id", "output_hashes", "error_trace",
        "idempotency_key", "attempts", "max_attempts", "previous_run_id",
    }
    assert esperados <= cols


def test_resumen_no_expone_insumos_por_contenido():
    run = ExecutionRun(
        run_id="r1", engagement_id=1, app_id="ICT_2025", app_version="1",
        engine_version="0.1.0", input_hashes={"f101": "ab" * 32},
        parameter_snapshot={"snapshot_hash": "cd" * 32}, idempotency_key="ef" * 32,
        status=STATUS_QUEUED,
    )
    r = run.resumen()
    assert r["run_id"] == "r1" and r["status"] == STATUS_QUEUED
    assert "input_hashes" not in r  # el resumen es liviano


def test_estados_terminales():
    assert STATUS_DEAD_LETTER in TERMINAL_STATUSES
    assert STATUS_QUEUED not in TERMINAL_STATUSES
