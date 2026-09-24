"""Modelos SQLAlchemy del motor de ejecución (Agente D).

Define ``ExecutionRun``, el contrato canónico de una corrida reproducible
(``docs/ARQUITECTURA_CONVERGENCIA_v1.md`` §2). Una corrida es la unidad
atómica de trabajo del motor: encapsula QUÉ app/versión se ejecutó, SOBRE
qué insumos (por hash, no por contenido), CON qué parámetros (snapshot
inmutable), QUIÉN la disparó, en qué WORKER, cuándo, con qué resultado y —
si falló — con qué traza.

Principios no negociables que este modelo hace cumplir:
  * **Reproducibilidad**: ``engine_version`` + ``input_hashes`` +
    ``parameter_snapshot`` + ruleset hash bastan para reproducir la corrida.
  * **Lineage**: ``output_hashes`` sella lo producido; se enlaza con
    ``motor/nucleo.py::Excepcion.run_id`` (Agente A) y con la evidencia
    (Agente E) para trazar salida → insumo.
  * **Idempotencia**: ``idempotency_key`` = sha256(input_hashes + parameter
    snapshot + app_version + engine_version); dos encolados con la misma
    clave NO producen dos corridas efectivas (ver ``queue.py``).

Solo metadata en DB. Los archivos de insumo/salida NO se persisten en la
fila (viven en almacenamiento de archivos / se referencian por hash), igual
que ``ToolJob``.

ESTADO: SCAFFOLD. Migración: ver nota ``MIGRACION`` al pie y la Task 1 del
plan. Registrar el import de este módulo en ``db/session.py::init_db`` para
que ``Base.metadata.create_all`` cree la tabla.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    """UTC naive, homogéneo con el resto del repo (ToolJob, ForgeBrain)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


# --- Estados de una corrida (máquina de estados de la cola) -----------------
# queued     : encolada, aún no tomada por un worker.
# leased     : un worker la tomó (lease con timeout, ver queue.py).
# running     : el worker está ejecutando la app.
# succeeded  : terminó OK; output_hashes sellado.
# failed     : terminó en error; error_trace poblado. Reintentable si quedan
#              intentos (ver max_attempts).
# dead_letter: agotó los reintentos; requiere intervención humana (AUT-006).
# canceled   : cancelada antes de completarse (por operador o supersedida).
STATUS_QUEUED = "queued"
STATUS_LEASED = "leased"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_DEAD_LETTER = "dead_letter"
STATUS_CANCELED = "canceled"

TERMINAL_STATUSES = frozenset(
    {STATUS_SUCCEEDED, STATUS_DEAD_LETTER, STATUS_CANCELED}
)
#: Estados desde los que un lease puede reintentarse (no terminales).
RETRIABLE_STATUSES = frozenset({STATUS_QUEUED, STATUS_LEASED, STATUS_RUNNING, STATUS_FAILED})


class ExecutionRun(Base):
    """Una corrida reproducible del motor (contrato §2 del benchmark).

    Cubre AUT-004/005/006/007/009/010 y DATA-011/012 como estructura de
    datos; la lógica que la puebla vive en ``queue.py`` (ciclo de vida),
    ``snapshots.py`` (sellado inmutable) y ``run_history.py`` (consulta).
    """

    __tablename__ = "execution_runs"
    __table_args__ = (
        # Idempotencia dura a nivel de motor: no puede haber DOS corridas
        # "vivas" con la misma clave. Se implementa como índice único parcial
        # sobre (idempotency_key) filtrando estados no-cancelados en Postgres;
        # en SQLite (tests) se emula en queue.py. Ver Task 3 del plan.
        UniqueConstraint("run_id", name="uq_execution_run_run_id"),
        Index("ix_execution_runs_engagement_status", "engagement_id", "status"),
        Index("ix_execution_runs_idempotency", "idempotency_key"),
        Index("ix_execution_runs_status_available", "status", "available_at"),
    )

    # --- Identidad --------------------------------------------------------
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: UUID4 público de la corrida (lo que aparece en URLs, lineage y evidencia).
    run_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    # --- Qué se ejecutó (contrato §2) ------------------------------------
    #: Encargo/engagement al que pertenece. FK a projects (el "engagement" del
    #: dominio). ondelete=CASCADE: si se borra el proyecto, su historial se va.
    engagement_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: Id de la audit app / tool ejecutada (ej. "ICT_2025", "FLUJO_EFECTIVO",
    #: o el id de un manifest de ``audit_apps``). No es FK: las apps externas y
    #: los manifests coexisten; se valida en la capa de servicio.
    app_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    #: Versión de la app/manifest (semver o hash). Parte de la idempotencia.
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    #: Versión del motor analítico determinista (motor-auditoria-analitica) con
    #: el que corrió. DATA-011: sin esto la corrida no es reproducible.
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # --- Sobre qué corrió (por hash, nunca por contenido) ----------------
    #: {slot|nombre_logico: sha256}. Sella los insumos sin guardarlos.
    input_hashes: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    #: Snapshot INMUTABLE de los parámetros del encargo (bloque U) + hash del
    #: ruleset activo. AUT-009/010 + DATA-012. Lo construye ``snapshots.py``.
    #: Una vez escrito NO se muta (la reproducibilidad depende de ello).
    parameter_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # --- Idempotencia / cola ---------------------------------------------
    #: sha256(input_hashes + parameter_snapshot + app_version + engine_version).
    #: Ver ``queue.build_idempotency_key``. AUT-004/005.
    idempotency_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    #: Intentos consumidos y tope. Al alcanzar el tope → dead_letter (AUT-006).
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    #: No visible para tomar antes de este instante (backoff exponencial entre
    #: reintentos). Ver ``queue.compute_backoff``.
    available_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, index=True, nullable=False
    )
    #: Lease: hasta cuándo el worker que la tomó la retiene. Un lease vencido
    #: la vuelve tomable (recupera corridas de workers muertos). AUT-005.
    lease_expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Estado + tiempos -------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(16), default=STATUS_QUEUED, index=True, nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    # --- Quién / dónde ----------------------------------------------------
    #: Usuario que disparó la corrida (o NULL si la disparó el scheduler).
    executed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: Identificador del worker/proceso que tomó el lease (hostname:pid o el id
    #: del scheduler). Diagnóstico y recuperación de leases muertos.
    worker_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Origen del disparo: "manual" | "schedule" | "continuous" | "api".
    trigger_source: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)

    # --- Resultado --------------------------------------------------------
    #: {nombre_artefacto: sha256}. Sella lo producido (lineage salida→corrida).
    output_hashes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Resumen liviano para la tarjeta/historial (conteos por severidad, etc.).
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    #: Traza del error en fallo (tipo + mensaje + traceback recortado). AUT-006.
    error_trace: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Continuous auditing (AUT-008) ------------------------------------
    #: run_id de la corrida previa comparable (misma app+engagement+inputs
    #: lógicos). Lo fija ``scheduler/continuo.py`` para el diff. NULL = primera.
    previous_run_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    #: Snapshot del diff calculado contra ``previous_run_id`` (nuevas/resueltas/
    #: cambiadas excepciones). Se persiste para no recalcularlo al mostrarlo.
    diff_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    def resumen(self) -> dict:
        """Vista liviana para el historial (AUT-007). No incluye insumos.

        Deliberadamente NO expone ``input_hashes`` ni el
        ``parameter_snapshot`` completo: el historial/tarjeta es liviano y no
        debe filtrar el detalle sellado de la corrida (se consulta aparte con
        ``run_history.run_lineage``).
        """
        def _iso(dt: datetime.datetime | None) -> str | None:
            return dt.isoformat() if dt is not None else None

        return {
            "run_id": self.run_id,
            "engagement_id": self.engagement_id,
            "app_id": self.app_id,
            "app_version": self.app_version,
            "engine_version": self.engine_version,
            "status": self.status,
            "trigger_source": self.trigger_source,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "created_at": _iso(self.created_at),
            "started_at": _iso(self.started_at),
            "completed_at": _iso(self.completed_at),
            "executed_by": self.executed_by,
            "worker_id": self.worker_id,
            "output_hashes": self.output_hashes,
            "previous_run_id": self.previous_run_id,
        }


# ---------------------------------------------------------------------------
# MIGRACION
# ---------------------------------------------------------------------------
# Este repo NO usa Alembic todavía (ver db/session.py::init_db, "Migraciones
# formales (Alembic) quedan en el roadmap"). El patrón vigente es:
#
#   1. Añadir en ``db/session.py::init_db`` el import del módulo para que la
#      tabla se registre en ``Base.metadata`` ANTES de ``create_all``:
#
#         from backend.app.execution import models as _execution_models  # noqa: F401
#
#      ``Base.metadata.create_all(bind=engine)`` crea ``execution_runs`` si no
#      existe. (Tabla nueva → no requiere ALTER idempotente.)
#
#   2. En Postgres, crear el índice único PARCIAL de idempotencia (no
#      expresable en ``__table_args__`` de forma portable) con SQL idempotente
#      dentro de ``init_db``, análogo a ``_ensure_forge_append_only_triggers``:
#
#         CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_runs_idem_live
#         ON execution_runs (idempotency_key)
#         WHERE status NOT IN ('canceled', 'dead_letter');
#
#      En SQLite (CI/tests) esta garantía se emula en ``queue.enqueue`` con un
#      SELECT ... antes del INSERT dentro de la misma transacción. Ver Task 3.
#
#   3. Cuando se adopte Alembic (deuda técnica del roadmap), portar 1 y 2 a una
#      revisión formal. Mientras tanto, documentar el delta aquí.
