"""Cola persistente de corridas con reintentos idempotentes y dead-letter.

Reemplaza el almacén en memoria del motor externo
(``motor-auditoria-analitica/servicio/trabajos.py``, mini-ciclo
``en_cola|procesando|listo|error`` que se pierde al reiniciar) por una cola
respaldada en Postgres a través de ``ExecutionRun``. Sobrevive reinicios,
soporta varios workers y garantiza idempotencia y recuperación de fallos.

Capacidades:
  * **AUT-004** — Idempotencia: dos encolados con la misma
    ``idempotency_key`` (mismos insumos + parámetros + versiones) NO generan
    dos corridas efectivas; el segundo devuelve la corrida viva existente.
  * **AUT-005** — Reintentos: un fallo transitorio reintenta con backoff
    exponencial; un lease vencido (worker muerto) vuelve la corrida tomable.
  * **AUT-006** — Dead-letter: al agotar ``max_attempts`` la corrida pasa a
    ``dead_letter`` (no se reintenta sola; requiere intervención humana).

Diseño de concurrencia (a implementar en el servidor):
  * ``lease_next`` toma UNA corrida disponible con ``SELECT ... FOR UPDATE
    SKIP LOCKED`` (Postgres) para que N workers no tomen la misma. En SQLite
    (tests) se serializa con la transacción.
  * El worker renueva el lease mientras procesa (``heartbeat``) y lo cierra al
    terminar (``mark_succeeded`` / ``mark_failed``).

Integración con el pipeline actual: el worker que hoy invoca
``client_portal/jobs.py::process_tool_job`` puede envolver la ejecución en
``lease_next``/``mark_*``; el ``ToolConfig.processor`` sigue siendo el que
hace el trabajo real. Ver los puntos de integración del plan.

ESTADO: IMPLEMENTADO a verde con TDD (Task P1-D). Pruebas en
tests/test_execution_*.py.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.app.execution.models import (
    ExecutionRun,
    STATUS_CANCELED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED,
    STATUS_LEASED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    _utcnow,
)

#: Estados en los que una corrida NO cuenta como "viva" para la idempotencia:
#: se puede reencolar una clave si su única corrida está cancelada o en
#: dead-letter (patrón del índice único parcial de Postgres).
_ESTADOS_NO_VIVOS = frozenset({STATUS_CANCELED, STATUS_DEAD_LETTER})

# Backoff exponencial entre reintentos (segundos): intento 1→60s, 2→300s,
# 3→900s. Configurable por env var en el servidor (ver Task 3 del plan).
BACKOFF_SECONDS: tuple[int, ...] = (60, 300, 900)
#: Duración por defecto de un lease. Un lease vencido se considera de un worker
#: muerto y la corrida vuelve a ser tomable.
DEFAULT_LEASE_SECONDS = 600


class DeadLetter(Exception):
    """Una corrida agotó sus reintentos y quedó en dead-letter (AUT-006)."""


@dataclass(frozen=True)
class EnqueueRequest:
    """Todo lo necesario para materializar una corrida (contrato §2).

    ``input_hashes`` y ``parameter_snapshot`` ya vienen calculados/sellados
    por ``snapshots.py``; la cola no re-lee archivos ni parámetros crudos.
    """

    engagement_id: int
    app_id: str
    app_version: str
    engine_version: str
    input_hashes: dict[str, str]
    parameter_snapshot: dict
    executed_by: int | None = None
    trigger_source: str = "manual"
    max_attempts: int = 3
    previous_run_id: str | None = None


def build_idempotency_key(req: EnqueueRequest) -> str:
    """sha256 canónico de (inputs + parámetros + app_version + engine_version).

    Determinista: mismas entradas → misma clave. Ordena claves y usa JSON
    canónico (sort_keys, separadores fijos) para que el hash no dependa del
    orden de inserción de los dicts. Esta es la base de AUT-004.

    Implementación de referencia (activarla en Task 2 del plan):

        material = {
            "input_hashes": req.input_hashes,
            "parameter_snapshot": req.parameter_snapshot,
            "app_id": req.app_id,
            "app_version": req.app_version,
            "engine_version": req.engine_version,
        }
        blob = json.dumps(material, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    """
    material = {
        "engagement_id": req.engagement_id,
        "input_hashes": req.input_hashes,
        "parameter_snapshot": req.parameter_snapshot,
        "app_id": req.app_id,
        "app_version": req.app_version,
        "engine_version": req.engine_version,
    }
    blob = json.dumps(
        material, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def enqueue(
    db: Session, req: EnqueueRequest, *, now: datetime.datetime | None = None
) -> ExecutionRun:
    """Encola una corrida de forma idempotente (AUT-004).

    Si ya existe una corrida NO cancelada/dead-letter con la misma
    ``idempotency_key``, devuelve ESA (no crea una segunda). Si no, inserta
    una nueva en estado ``queued`` con ``available_at=now``.

    En Postgres la unicidad la respalda el índice único parcial (ver
    ``models.MIGRACION``); en SQLite se emula con un SELECT dentro de la misma
    transacción antes del INSERT. Devuelve siempre la corrida "viva".

    Implementar en Task 3 del plan.
    """
    key = build_idempotency_key(req)
    viva = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.idempotency_key == key,
            ExecutionRun.status.notin_(tuple(_ESTADOS_NO_VIVOS)),
        )
        .order_by(ExecutionRun.id.desc())
        .first()
    )
    if viva is not None:
        return viva

    ahora = now or _utcnow()
    run = ExecutionRun(
        run_id=uuid.uuid4().hex,
        engagement_id=req.engagement_id,
        app_id=req.app_id,
        app_version=req.app_version,
        engine_version=req.engine_version,
        input_hashes=req.input_hashes,
        parameter_snapshot=req.parameter_snapshot,
        idempotency_key=key,
        attempts=0,
        max_attempts=req.max_attempts,
        available_at=ahora,
        status=STATUS_QUEUED,
        executed_by=req.executed_by,
        trigger_source=req.trigger_source,
        previous_run_id=req.previous_run_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def lease_next(
    db: Session,
    *,
    worker_id: str,
    now: datetime.datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> ExecutionRun | None:
    """Toma la próxima corrida disponible y la marca ``leased`` para un worker.

    "Disponible" = estado ``queued`` o ``failed`` reintentable, con
    ``available_at <= now`` y sin lease vigente (o con lease vencido). Fija
    ``worker_id``, ``lease_expires_at = now + lease_seconds``, incrementa
    ``attempts`` y ``started_at`` si es el primer intento. Devuelve None si no
    hay nada tomable.

    Concurrencia: ``FOR UPDATE SKIP LOCKED`` en Postgres. Implementar en
    Task 4 del plan.
    """
    ahora = now or _utcnow()
    stmt = (
        select(ExecutionRun)
        .where(
            ExecutionRun.status.in_((STATUS_QUEUED, STATUS_FAILED)),
            ExecutionRun.available_at <= ahora,
        )
        .order_by(ExecutionRun.available_at.asc(), ExecutionRun.id.asc())
        .limit(1)
    )
    # En Postgres serializamos la toma con FOR UPDATE SKIP LOCKED para que N
    # workers no tomen la misma corrida. SQLite no soporta el flag: la propia
    # transacción serializa y se ignora.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        stmt = stmt.with_for_update(skip_locked=True)
    try:
        run = db.execute(stmt).scalars().first()
    except OperationalError:
        db.rollback()
        return None
    if run is None:
        return None

    run.status = STATUS_LEASED
    run.worker_id = worker_id
    run.lease_expires_at = ahora + datetime.timedelta(seconds=lease_seconds)
    run.attempts = (run.attempts or 0) + 1
    if run.started_at is None:
        run.started_at = ahora
    db.commit()
    db.refresh(run)
    return run


def heartbeat(
    db: Session,
    run: ExecutionRun,
    *,
    worker_id: str,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    now: datetime.datetime | None = None,
) -> None:
    """Renueva el lease de una corrida en curso (corridas largas).

    Extiende ``lease_expires_at`` mientras el worker siga vivo, para que otro
    worker no la reclame. Falla si el lease ya lo tiene otro worker (evita
    doble ejecución). Implementar en Task 4.
    """
    if run.worker_id != worker_id:
        raise PermissionError(
            f"heartbeat rechazado: la corrida {run.run_id} la retiene "
            f"{run.worker_id!r}, no {worker_id!r}"
        )
    ahora = now or _utcnow()
    run.lease_expires_at = ahora + datetime.timedelta(seconds=lease_seconds)
    db.commit()


def mark_running(db: Session, run: ExecutionRun, *, worker_id: str) -> None:
    """Transición ``leased`` → ``running`` al empezar la ejecución real.

    Implementar en Task 4.
    """
    if run.worker_id != worker_id:
        raise PermissionError(
            f"mark_running rechazado: la corrida {run.run_id} la retiene "
            f"{run.worker_id!r}, no {worker_id!r}"
        )
    run.status = STATUS_RUNNING
    db.commit()


def mark_succeeded(
    db: Session,
    run: ExecutionRun,
    *,
    output_hashes: dict[str, str],
    summary_json: dict | None = None,
    now: datetime.datetime | None = None,
) -> None:
    """Cierra la corrida OK: sella ``output_hashes``, ``completed_at``, estado.

    ``output_hashes`` es el lineage de salida (AUT + DATA). Libera el lease.
    Implementar en Task 4.
    """
    ahora = now or _utcnow()
    run.status = STATUS_SUCCEEDED
    run.output_hashes = output_hashes
    if summary_json is not None:
        run.summary_json = summary_json
    run.completed_at = ahora
    run.lease_expires_at = None
    db.commit()


def mark_failed(
    db: Session,
    run: ExecutionRun,
    *,
    error_trace: str,
    now: datetime.datetime | None = None,
) -> ExecutionRun:
    """Registra un fallo y decide reintento vs dead-letter (AUT-005/006).

    Si ``attempts < max_attempts``: estado ``failed``, agenda
    ``available_at = now + compute_backoff(attempts)`` para reintento.
    Si se agotaron: estado ``dead_letter``, ``completed_at`` fijado, NO se
    reagenda. Puebla ``error_trace`` en ambos casos. Devuelve la corrida.

    Implementar en Task 5 del plan.
    """
    ahora = now or _utcnow()
    run.error_trace = error_trace
    run.lease_expires_at = None
    if (run.attempts or 0) < (run.max_attempts or 0):
        # Quedan intentos: reintento con backoff exponencial.
        run.status = STATUS_FAILED
        run.available_at = compute_backoff(run.attempts or 1, ahora)
    else:
        # Agotó los reintentos: dead-letter, requiere intervención humana.
        run.status = STATUS_DEAD_LETTER
        run.completed_at = ahora
    db.commit()
    db.refresh(run)
    return run


def compute_backoff(attempts: int, now: datetime.datetime) -> datetime.datetime:
    """Instante del próximo intento tras ``attempts`` fallos (backoff expo).

    Usa ``BACKOFF_SECONDS[min(attempts-1, len-1)]``. Implementar en Task 5.
    """
    idx = min(max(attempts, 1) - 1, len(BACKOFF_SECONDS) - 1)
    return now + datetime.timedelta(seconds=BACKOFF_SECONDS[idx])


def reclaim_expired_leases(
    db: Session, *, now: datetime.datetime | None = None
) -> int:
    """Devuelve a la cola las corridas cuyo lease venció (workers muertos).

    Barre ``leased``/``running`` con ``lease_expires_at < now`` y las vuelve
    ``queued`` (respetando ``max_attempts``: si ya no quedan intentos, van a
    ``dead_letter``). Lo corre periódicamente el scheduler. Devuelve cuántas
    recuperó. Parte de AUT-005. Implementar en Task 6.
    """
    ahora = now or _utcnow()
    vencidas = (
        db.query(ExecutionRun)
        .filter(
            ExecutionRun.status.in_((STATUS_LEASED, STATUS_RUNNING)),
            ExecutionRun.lease_expires_at.isnot(None),
            ExecutionRun.lease_expires_at < ahora,
        )
        .all()
    )
    for run in vencidas:
        run.lease_expires_at = None
        run.worker_id = None
        if (run.attempts or 0) < (run.max_attempts or 0):
            run.status = STATUS_QUEUED
            run.available_at = ahora
        else:
            run.status = STATUS_DEAD_LETTER
            run.completed_at = ahora
            run.error_trace = (run.error_trace or "") + "\n[reclaim] lease vencido sin reintentos"
    if vencidas:
        db.commit()
    return len(vencidas)


def list_dead_letter(db: Session, *, engagement_id: int | None = None) -> list[ExecutionRun]:
    """Lista las corridas en dead-letter para revisión humana (AUT-006).

    Implementar en Task 6.
    """
    q = db.query(ExecutionRun).filter(ExecutionRun.status == STATUS_DEAD_LETTER)
    if engagement_id is not None:
        q = q.filter(ExecutionRun.engagement_id == engagement_id)
    return q.order_by(ExecutionRun.completed_at.desc(), ExecutionRun.id.desc()).all()


def requeue(db: Session, run: ExecutionRun, *, executed_by: int | None = None) -> ExecutionRun:
    """Reencola manualmente una corrida en dead-letter tras corregir la causa.

    Resetea ``attempts=0``, estado ``queued``, ``available_at=now`` y limpia
    ``error_trace``. Es una acción explícita del operador (no automática).
    Implementar en Task 6.
    """
    run.status = STATUS_QUEUED
    run.attempts = 0
    run.available_at = _utcnow()
    run.lease_expires_at = None
    run.worker_id = None
    run.error_trace = None
    run.completed_at = None
    if executed_by is not None:
        run.executed_by = executed_by
    db.commit()
    db.refresh(run)
    return run
