"""Endpoints HTTP del motor de ejecución (AUT-003/006/007).

Solo staff (`require_staff`): historial de corridas, ficha de lineage,
bandeja de dead-letter, reencolado manual, disparo manual y mantenimiento de
la cola (recuperación de leases; lo invoca el Render Cron).

No expone insumos por contenido, solo por hash. No reescribe el pipeline de
ToolJob (eso lo hace ``execution/integration.py``): aquí solo se lee/opera la
tabla ``execution_runs``.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.db.session import get_db
from backend.app.execution import queue as Q
from backend.app.execution import run_history as H
from backend.app.execution.scheduler import planificador as P

router = APIRouter(prefix="/execution", tags=["execution"])


class ManualRunIn(BaseModel):
    """Disparo manual de una corrida (staff)."""

    engagement_id: int
    app_id: str = Field(min_length=1, max_length=64)
    app_version: str = "1"
    engine_version: str = "1.0.0"
    input_hashes: dict[str, str] = Field(default_factory=dict)
    parameter_snapshot: dict = Field(default_factory=dict)


@router.get("/runs")
def listar_corridas(
    engagement_id: int | None = None,
    app_id: str | None = None,
    estado: str | None = Query(default=None, alias="status"),
    trigger_source: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> dict:
    """Historial paginado de corridas (AUT-007), más reciente primero."""
    flt = H.HistoryFilter(
        engagement_id=engagement_id, app_id=app_id, status=estado,
        trigger_source=trigger_source,
    )
    pg = H.list_runs(db, flt, page=page, size=size)
    return {"total": pg.total, "page": pg.page, "size": pg.size, "runs": pg.runs}


@router.get("/dead-letter")
def bandeja_dead_letter(
    engagement_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> dict:
    """Corridas en dead-letter que requieren intervención humana (AUT-006)."""
    runs = Q.list_dead_letter(db, engagement_id=engagement_id)
    return {"total": len(runs), "runs": [r.resumen() for r in runs]}


@router.get("/runs/{run_id}")
def detalle_corrida(
    run_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> dict:
    run = H.get_run(db, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "corrida no encontrada")
    return run.resumen()


@router.get("/runs/{run_id}/lineage")
def lineage_corrida(
    run_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> dict:
    """Ficha de reproducibilidad (DATA-011/012): versiones, hashes, snapshot."""
    lin = H.run_lineage(db, run_id)
    if not lin:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "corrida no encontrada")
    return lin


@router.post("/runs/{run_id}/requeue")
def reencolar(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> dict:
    """Reencola manualmente una corrida en dead-letter tras corregir la causa."""
    run = H.get_run(db, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "corrida no encontrada")
    if run.status != Q.STATUS_DEAD_LETTER:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"solo se reencola desde dead_letter (estado actual: {run.status})",
        )
    Q.requeue(db, run, executed_by=user.id)
    return run.resumen()


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def disparar_manual(
    payload: ManualRunIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_staff),
) -> dict:
    """Encola una corrida manualmente (idempotente por insumos+parámetros)."""
    req = Q.EnqueueRequest(
        engagement_id=payload.engagement_id,
        app_id=payload.app_id,
        app_version=payload.app_version,
        engine_version=payload.engine_version,
        input_hashes=payload.input_hashes,
        parameter_snapshot=payload.parameter_snapshot,
        executed_by=user.id,
        trigger_source="manual",
    )
    run = Q.enqueue(db, req)
    return run.resumen()


@router.post("/maintenance")
def mantenimiento(
    db: Session = Depends(get_db),
    _: User = Depends(require_staff),
) -> dict:
    """Recupera leases vencidos (workers muertos). Lo invoca el Render Cron
    (o un job de APScheduler); también disponible como acción manual staff."""
    return P.run_maintenance(db, now=datetime.datetime.utcnow())
