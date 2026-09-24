"""Historial de corridas (AUT-007).

Consulta del rastro de ejecuciones de un encargo/app: qué corrió, cuándo,
con qué versión de motor y parámetros, quién la disparó y con qué resultado.
Es la cara de lectura de ``ExecutionRun`` para el portal y para la
reproducibilidad ("¿con qué parámetros salió el entregable del 2026-03?").

No muta nada: solo lee. La escritura la hace ``queue.py``. Devuelve vistas
livianas (sin insumos ni salidas por contenido, solo por hash) aptas para
tablas/tarjetas.

ESTADO: SCAFFOLD. Firmas + docstrings; lógica levanta NotImplementedError.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.execution.models import ExecutionRun


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
    raise NotImplementedError("list_runs: implementar la consulta paginada en Task 7.")


def get_run(db: Session, run_id: str) -> ExecutionRun | None:
    """Devuelve una corrida por su ``run_id`` público, o None. Task 7."""
    raise NotImplementedError("get_run: implementar en Task 7.")


def latest_successful_run(
    db: Session, *, engagement_id: int, app_id: str
) -> ExecutionRun | None:
    """Última corrida ``succeeded`` de esa app en ese encargo.

    Es el ancla del continuous auditing: ``scheduler/continuo.py`` la usa como
    ``previous_run_id`` para el diff. Implementar en Task 7.
    """
    raise NotImplementedError("latest_successful_run: implementar en Task 7.")


def run_lineage(db: Session, run_id: str) -> dict:
    """Ficha de reproducibilidad de una corrida (para auditor/QA).

    Reúne ``engine_version``, ``app_version``, ``input_hashes``, el
    ``parameter_snapshot`` (incluye el hash del ruleset) y ``output_hashes``:
    todo lo necesario para responder "cómo se produjo esta salida" y para
    re-ejecutar de forma idéntica. DATA-011/012 sobre la cara de lectura.
    Implementar en Task 7.
    """
    raise NotImplementedError("run_lineage: implementar la ficha de lineage en Task 7.")
