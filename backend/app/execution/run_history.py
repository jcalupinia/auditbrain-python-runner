"""Historial de corridas (AUT-007).

Consulta del rastro de ejecuciones de un encargo/app: qué corrió, cuándo,
con qué versión de motor y parámetros, quién la disparó y con qué resultado.
Es la cara de lectura de ``ExecutionRun`` para el portal y para la
reproducibilidad ("¿con qué parámetros salió el entregable del 2026-03?").

No muta nada: solo lee. La escritura la hace ``queue.py``. Devuelve vistas
livianas (sin insumos ni salidas por contenido, solo por hash) aptas para
tablas/tarjetas.

ESTADO: IMPLEMENTADO a verde con TDD (Task P1-D). Pruebas en
tests/test_execution_*.py.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.execution.models import ExecutionRun, STATUS_SUCCEEDED


@dataclass(frozen=True)
class HistoryFilter:
    """Filtros de consulta del historial. Todos opcionales."""

    engagement_id: int | None = None
    app_id: str | None = None
    status: str | None = None
    executed_by: int | None = None
    trigger_source: str | None = None
    since: datetime.datetime | None = None
    until: datetime.datetime | None = None


@dataclass(frozen=True)
class Page:
    """Página de resultados del historial."""

    total: int
    page: int
    size: int
    runs: list[dict]


def list_runs(
    db: Session,
    flt: HistoryFilter,
    *,
    page: int = 1,
    size: int = 50,
) -> Page:
    """Lista corridas que cumplen ``flt``, ordenadas por ``created_at`` desc.

    Cada elemento es ``ExecutionRun.resumen()`` (vista liviana). Paginada.
    AUT-007. Implementar en Task 7 del plan.
    """
    q = db.query(ExecutionRun)
    if flt.engagement_id is not None:
        q = q.filter(ExecutionRun.engagement_id == flt.engagement_id)
    if flt.app_id is not None:
        q = q.filter(ExecutionRun.app_id == flt.app_id)
    if flt.status is not None:
        q = q.filter(ExecutionRun.status == flt.status)
    if flt.executed_by is not None:
        q = q.filter(ExecutionRun.executed_by == flt.executed_by)
    if flt.trigger_source is not None:
        q = q.filter(ExecutionRun.trigger_source == flt.trigger_source)
    if flt.since is not None:
        q = q.filter(ExecutionRun.created_at >= flt.since)
    if flt.until is not None:
        q = q.filter(ExecutionRun.created_at <= flt.until)

    total = q.count()
    page = max(page, 1)
    size = max(size, 1)
    runs = (
        q.order_by(ExecutionRun.created_at.desc(), ExecutionRun.id.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )
    return Page(total=total, page=page, size=size, runs=[r.resumen() for r in runs])


def get_run(db: Session, run_id: str) -> ExecutionRun | None:
    """Devuelve una corrida por su ``run_id`` público, o None. Task 7."""
    return db.query(ExecutionRun).filter(ExecutionRun.run_id == run_id).first()


def latest_successful_run(
    db: Session, *, engagement_id: int, app_id: str
) -> ExecutionRun | None:
    """Última corrida ``succeeded`` de esa app en ese encargo.

    Es el ancla del continuous auditing: ``scheduler/continuo.py`` la usa como
    ``previous_run_id`` para el diff. Implementar en Task 7.
    """
    return (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.engagement_id == engagement_id,
            ExecutionRun.app_id == app_id,
            ExecutionRun.status == STATUS_SUCCEEDED,
        )
        .order_by(ExecutionRun.completed_at.desc(), ExecutionRun.id.desc())
        .first()
    )


def run_lineage(db: Session, run_id: str) -> dict:
    """Ficha de reproducibilidad de una corrida (para auditor/QA).

    Reúne ``engine_version``, ``app_version``, ``input_hashes``, el
    ``parameter_snapshot`` (incluye el hash del ruleset) y ``output_hashes``:
    todo lo necesario para responder "cómo se produjo esta salida" y para
    re-ejecutar de forma idéntica. DATA-011/012 sobre la cara de lectura.
    Implementar en Task 7.
    """
    run = get_run(db, run_id)
    if run is None:
        return {}
    return {
        "run_id": run.run_id,
        "engagement_id": run.engagement_id,
        "app_id": run.app_id,
        "app_version": run.app_version,
        "engine_version": run.engine_version,
        "input_hashes": run.input_hashes,
        "parameter_snapshot": run.parameter_snapshot,
        "output_hashes": run.output_hashes,
        "previous_run_id": run.previous_run_id,
    }
