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

ESTADO: IMPLEMENTADO a verde con TDD (Task P1-D). Pruebas en
tests/test_execution_*.py.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session


# --- Evaluación de cron (5 campos, UTC) sin dependencia nueva ---------------
def _parse_field(expr: str, lo: int, hi: int) -> set[int]:
    """Expande un campo cron a su conjunto de valores. Soporta ``*``, listas
    (``a,b``), rangos (``a-b``) y pasos (``*/n``, ``a-b/n``)."""
    valores: set[int] = set()
    for parte in expr.split(","):
        paso = 1
        cuerpo = parte
        if "/" in parte:
            cuerpo, paso_txt = parte.split("/", 1)
            paso = int(paso_txt)
        if cuerpo in ("*", ""):
            ini, fin = lo, hi
        elif "-" in cuerpo:
            a, b = cuerpo.split("-", 1)
            ini, fin = int(a), int(b)
        else:
            ini = fin = int(cuerpo)
        valores.update(v for v in range(ini, fin + 1) if (v - ini) % paso == 0)
    return {v for v in valores if lo <= v <= hi}


def cron_matches(cron: str, dt: datetime.datetime) -> bool:
    """True si la expresión cron de 5 campos (min hora dom mes dow) cae en
    ``dt`` (resolución de minuto, UTC). ``dow``: 0=domingo..6=sábado (7=domingo)."""
    campos = cron.split()
    if len(campos) != 5:
        raise ValueError(f"cron inválido (se esperan 5 campos): {cron!r}")
    minuto, hora, dom, mes, dow = campos
    dow_cron = (dt.weekday() + 1) % 7  # lunes=0(py) -> domingo=0(cron)
    dow_set = _parse_field(dow, 0, 7)
    if 7 in dow_set:
        dow_set.add(0)
    return (
        dt.minute in _parse_field(minuto, 0, 59)
        and dt.hour in _parse_field(hora, 0, 23)
        and dt.day in _parse_field(dom, 1, 31)
        and dt.month in _parse_field(mes, 1, 12)
        and dow_cron in dow_set
    )


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
    minuto = now.replace(second=0, microsecond=0)
    listos: list[Schedule] = []
    for s in schedules:
        if not s.enabled:
            continue
        if not cron_matches(s.cron, minuto):
            continue
        ultimo = last_fired.get(s.schedule_id)
        # No re-disparar dos veces en el mismo minuto.
        if ultimo is not None and ultimo.replace(second=0, microsecond=0) >= minuto:
            continue
        listos.append(s)
    return listos


def run_due_schedules(
    db: Session,
    *,
    schedules: list[Schedule],
    build_request: Callable[[Schedule], object],
    now: datetime.datetime | None = None,
    last_fired: dict[str, datetime.datetime] | None = None,
) -> list[str]:
    """Encola las corridas de las programaciones vencidas (AUT-003).

    Por cada schedule vencido, ``build_request`` (inyectado por el llamador,
    que conoce los parámetros vigentes del encargo y el ruleset activo)
    produce un ``EnqueueRequest`` ya sellado, y se llama a ``queue.enqueue``
    con ``trigger_source`` según el modo. La idempotencia de ``enqueue``
    garantiza que un cron solapado NO duplique corridas. Devuelve los
    ``run_id`` encolados.
    """
    from backend.app.execution.queue import enqueue

    ahora = now or _utcnow()
    last_fired = last_fired if last_fired is not None else {}
    run_ids: list[str] = []
    for s in due_schedules(schedules, now=ahora, last_fired=last_fired):
        req = build_request(s)
        run = enqueue(db, req, now=ahora)
        run_ids.append(run.run_id)
        last_fired[s.schedule_id] = ahora
    return run_ids


def run_maintenance(db: Session, *, now: datetime.datetime | None = None) -> dict:
    """Tareas periódicas de salud de la cola (las corre el mismo cron).

    Llama a ``queue.reclaim_expired_leases`` (recupera workers muertos) y, si
    procede, purga corridas terminales muy viejas según la política de
    retención. Devuelve un resumen (cuántas recuperadas, etc.).
    """
    from backend.app.execution.queue import reclaim_expired_leases

    ahora = now or _utcnow()
    recuperadas = reclaim_expired_leases(db, now=ahora)
    return {"reclaimed": recuperadas, "at": ahora.isoformat()}


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


def start_apscheduler(db_factory) -> object:
    """Arranca un ``BackgroundScheduler`` de APScheduler (backend in-process).

    Registra ``run_due_schedules`` y ``run_maintenance`` como jobs periódicos
    usando ``db_factory`` (``SessionLocal``) para abrir una sesión por tick.
    Devuelve el scheduler ya iniciado (para poder pararlo en el shutdown de
    FastAPI). Solo se usa si se elige el backend in-process; con Render Cron
    NO se llama. Requiere la dependencia ``APScheduler``. Implementar en
    Task 10 del plan.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError as exc:  # pragma: no cover - depende del backend elegido
        raise RuntimeError(
            "start_apscheduler requiere la dependencia 'APScheduler'. "
            "Con el backend Render Cron (recomendado) NO se usa esta función: "
            "el cron externo invoca run_due_schedules + run_maintenance."
        ) from exc

    def _tick_due() -> None:
        db = db_factory()
        try:
            run_maintenance(db)
        finally:
            db.close()

    sched = BackgroundScheduler(timezone="UTC")
    # El disparo de schedules concretos necesita su fuente (tabla/config) y el
    # build_request del encargo; se registra desde el arranque de la app, que
    # conoce ese cableado. Aquí dejamos el mantenimiento periódico de la cola.
    sched.add_job(_tick_due, "interval", minutes=1, id="execution_maintenance")
    sched.start()
    return sched
