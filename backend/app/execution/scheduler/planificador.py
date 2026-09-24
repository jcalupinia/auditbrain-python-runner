"""Scheduler de corridas programadas y mantenimiento de la cola (AUT-003).

Dispara corridas según un horario (cron), sin intervención humana:
declaraciones recurrentes, continuous auditing periódico, y las tareas de
mantenimiento de la cola (recuperar leases vencidos, barrer dead-letter).

Dos backends posibles (se elige por entorno, ver el plan):
  * **APScheduler** (in-process, ``BackgroundScheduler``): útil cuando el
    servicio corre siempre-activo. Requiere la dependencia ``APScheduler``
    (registrar en requirements — ver el plan). Un solo scheduler activo a la
    vez (un solo worker), o con jobstore compartido + lock para no duplicar.
  * **Render Cron Job**: un cron externo de Render invoca un endpoint/CLI
    (``run_due_schedules``) cada N minutos. No necesita proceso vivo ni
    dependencia nueva; encaja con el modelo actual del repo (1 CPU, workers 1).

Ambos backends convergen en las MISMAS funciones puras de este módulo
(``run_due_schedules``, ``run_maintenance``), que son las que se prueban con
un reloj inyectado. El backend solo decide QUIÉN las llama y CUÁNDO.

Idempotencia: como el disparo pasa por ``queue.enqueue`` (idempotente por
``idempotency_key``), un cron que se solape o se dispare dos veces NO produce
corridas duplicadas.

ESTADO: SCAFFOLD. Firmas + docstrings; lógica levanta NotImplementedError.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Schedule:
    """Una programación de corridas (dato persistente, tabla aparte o config).

    NOTA de diseño para la implementación: la definición de horarios puede
    vivir (a) en una tabla ``execution_schedules`` (si el cliente los edita
    desde el portal) o (b) en configuración/manifest de la audit app. El
    scaffold no fija la tabla todavía (decisión de la Task 9); modela el
    contrato mínimo que ``run_due_schedules`` necesita.
    """

    schedule_id: str
    engagement_id: int
    app_id: str
    app_version: str
    cron: str  # expresión cron estándar, evaluada en UTC
    enabled: bool = True
    #: "schedule" para corrida programada simple; "continuous" para que además
    #: dispare el flujo de diff+notificación de ``continuo.py``.
    mode: str = "schedule"


def due_schedules(
    schedules: list[Schedule], *, now: datetime.datetime, last_fired: dict[str, datetime.datetime]
) -> list[Schedule]:
    """Filtra las programaciones que deben dispararse en ``now``.

    Función pura (sin DB, sin reloj real): recibe la lista, el instante y el
    último disparo por schedule. Facilita el test con reloj inyectado.
    Evalúa la expresión ``cron`` en UTC. Implementar en Task 9 del plan.
    """
    raise NotImplementedError("due_schedules: implementar la evaluación cron en Task 9.")


def run_due_schedules(
    db: Session,
    *,
    now: datetime.datetime | None = None,
) -> list[str]:
    """Encola las corridas de las programaciones vencidas (AUT-003).

    Para cada schedule vencido construye el snapshot (``snapshots.build_snapshot``
    con los parámetros vigentes del encargo y el ruleset activo) y llama a
    ``queue.enqueue`` con ``trigger_source="schedule"`` (o delega en
    ``continuo.run_continuous`` si ``mode == "continuous"``). Devuelve los
    ``run_id`` encolados. Es lo que invoca el cron de Render o el job de
    APScheduler. Implementar en Task 9.
    """
    raise NotImplementedError("run_due_schedules: implementar el disparo en Task 9.")


def run_maintenance(db: Session, *, now: datetime.datetime | None = None) -> dict:
    """Tareas periódicas de salud de la cola (las corre el mismo cron).

    Llama a ``queue.reclaim_expired_leases`` (recupera workers muertos) y, si
    procede, purga corridas terminales muy viejas según la política de
    retención. Devuelve un resumen (cuántas recuperadas, etc.). Implementar en
    Task 9.
    """
    raise NotImplementedError("run_maintenance: implementar el mantenimiento en Task 9.")


def start_apscheduler(db_factory) -> object:
    """Arranca un ``BackgroundScheduler`` de APScheduler (backend in-process).

    Registra ``run_due_schedules`` y ``run_maintenance`` como jobs periódicos
    usando ``db_factory`` (``SessionLocal``) para abrir una sesión por tick.
    Devuelve el scheduler ya iniciado (para poder pararlo en el shutdown de
    FastAPI). Solo se usa si se elige el backend in-process; con Render Cron
    NO se llama. Requiere la dependencia ``APScheduler``. Implementar en
    Task 10 del plan.
    """
    raise NotImplementedError(
        "start_apscheduler: implementar el arranque in-process en Task 10 "
        "(requiere la dependencia APScheduler; ver el plan)."
    )
