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

ESTADO: SCAFFOLD. Firmas + docstrings; lógica levanta NotImplementedError.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.execution.models import ExecutionRun

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
    raise NotImplementedError(
        "build_idempotency_key: implementar el hash canónico en Task 2."
    )


def enqueue(db: Session, req: EnqueueRequest) -> ExecutionRun:
    """Encola una corrida de forma idempotente (AUT-004).

    Si ya existe una corrida NO cancelada/dead-letter con la misma
    ``idempotency_key``, devuelve ESA (no crea una segunda). Si no, inserta
    una nueva en estado ``queued`` con ``available_at=now``.

    En Postgres la unicidad la respalda el índice único parcial (ver
    ``models.MIGRACION``); en SQLite se emula con un SELECT dentro de la misma
    transacción antes del INSERT. Devuelve siempre la corrida "viva".

    Implementar en Task 3 del plan.
    """
    raise NotImplementedError("enqueue: implementar el upsert idempotente en Task 3.")


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
    raise NotImplementedError("lease_next: implementar la toma con lock en Task 4.")


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
    raise NotImplementedError("heartbeat: implementar la renovación de lease en Task 4.")


def mark_running(db: Session, run: ExecutionRun, *, worker_id: str) -> None:
    """Transición ``leased`` → ``running`` al empezar la ejecución real.

    Implementar en Task 4.
    """
    raise NotImplementedError("mark_running: implementar en Task 4.")


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
    raise NotImplementedError("mark_succeeded: implementar el sellado de salida en Task 4.")


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
    raise NotImplementedError("mark_failed: implementar backoff/dead-letter en Task 5.")


def compute_backoff(attempts: int, now: datetime.datetime) -> datetime.datetime:
    """Instante del próximo intento tras ``attempts`` fallos (backoff expo).

    Usa ``BACKOFF_SECONDS[min(attempts-1, len-1)]``. Implementar en Task 5.
    """
    raise NotImplementedError("compute_backoff: implementar en Task 5.")


def reclaim_expired_leases(
    db: Session, *, now: datetime.datetime | None = None
) -> int:
    """Devuelve a la cola las corridas cuyo lease venció (workers muertos).

    Barre ``leased``/``running`` con ``lease_expires_at < now`` y las vuelve
    ``queued`` (respetando ``max_attempts``: si ya no quedan intentos, van a
    ``dead_letter``). Lo corre periódicamente el scheduler. Devuelve cuántas
    recuperó. Parte de AUT-005. Implementar en Task 6.
    """
    raise NotImplementedError("reclaim_expired_leases: implementar el barrido en Task 6.")


def list_dead_letter(db: Session, *, engagement_id: int | None = None) -> list[ExecutionRun]:
    """Lista las corridas en dead-letter para revisión humana (AUT-006).

    Implementar en Task 6.
    """
    raise NotImplementedError("list_dead_letter: implementar en Task 6.")


def requeue(db: Session, run: ExecutionRun, *, executed_by: int | None = None) -> ExecutionRun:
    """Reencola manualmente una corrida en dead-letter tras corregir la causa.

    Resetea ``attempts=0``, estado ``queued``, ``available_at=now`` y limpia
    ``error_trace``. Es una acción explícita del operador (no automática).
    Implementar en Task 6.
    """
    raise NotImplementedError("requeue: implementar el reencolado manual en Task 6.")
