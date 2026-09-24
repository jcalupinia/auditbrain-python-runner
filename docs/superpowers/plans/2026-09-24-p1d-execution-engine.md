# P1-D · Motor de ejecución (execution engine) — Plan de implementación TDD

> **For agentic workers:** REQUIRED SUB-SKILL: usar superpowers:subagent-driven-development
> (recomendado) o superpowers:executing-plans para implementar este plan
> task-by-task. Los pasos usan checkbox (`- [ ]`) para tracking.

**Goal:** que AUDIT-IA ejecute apps de auditoría como **corridas reproducibles**:
una cola persistente en Postgres con reintentos idempotentes y dead-letter,
historial de corridas, snapshots inmutables (parámetros + engine_version +
ruleset) y un scheduler que dispara corridas programadas y auditoría continua
(diff vs corrida previa + notificación de éxito Y fallo).

**Agente responsable:** D · Execution engine (Agente D de
`../../../../motor-auditoria-analitica/docs/ARQUITECTURA_CONVERGENCIA_v1.md`).
Dueño de un conjunto de archivos **disjunto**: SOLO `backend/app/execution/`
(+ el registro en `db/session.py` y `requirements*.txt`, cambios de una línea).

**Capacidades cerradas (benchmark):** AUT-003/004/005/006/007/008/009/010/011/012,
DATA-011/012.

**Architecture:** `ExecutionRun` (SQLAlchemy) es el contrato §2 y la fila de la
cola. `snapshots.py` congela lo reproducible ANTES de encolar. `queue.py` es la
máquina de estados (queued→leased→running→succeeded/failed→dead_letter) con
idempotencia por `idempotency_key` y backoff. `run_history.py` es la cara de
lectura. `scheduler/planificador.py` dispara por cron (APScheduler in-process o
Render Cron; ambos convergen en `run_due_schedules`). `scheduler/continuo.py`
hace el diff vs la corrida previa y notifica reutilizando
`notifications/email.py`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Postgres (SQLite en
CI/tests), pytest. **Dependencia nueva a registrar:** `APScheduler` (solo si se
elige el backend in-process; ver Task 10). Convenciones del repo: español en
docstrings/comentarios; UTC naive (`_utcnow`) como el resto (`ToolJob`,
`ForgeBrain`); import del módulo de modelos en `db/session.py::init_db`.

**Contrato canónico:** `../../../../motor-auditoria-analitica/docs/ARQUITECTURA_CONVERGENCIA_v1.md`
§2 (`ExecutionRun`).

**⚠️ Por qué scaffold + plan y no verde aquí:** fastapi y sqlalchemy NO corren
en el contenedor del agente. El scaffold ya está escrito (interfaces tipadas +
docstrings + `raise NotImplementedError` con referencia a su task). Este plan
lleva cada NotImplementedError a verde **en el servidor**, con TDD estricto
(test que falla → código → test verde).

**Regla del proyecto (CLAUDE.md · REGLA SUPREMA):** nada se marca "listo" sin
verificación empírica. Para este módulo: correr `pytest tests/test_execution_*.py`
y confirmar el output; para la integración, disparar una corrida real y verificar
que el historial, el snapshot y el diff quedan bien.

---

## Estructura de archivos

| Archivo | Estado | Responsabilidad |
|---|---|---|
| `backend/app/execution/__init__.py` | CREADO | Docstring del paquete, `__all__` |
| `backend/app/execution/models.py` | SCAFFOLD | `ExecutionRun` + constantes de estado + nota MIGRACION |
| `backend/app/execution/queue.py` | SCAFFOLD | Cola: idempotencia, lease, backoff, dead-letter, requeue |
| `backend/app/execution/run_history.py` | SCAFFOLD | Historial (AUT-007) + lineage |
| `backend/app/execution/snapshots.py` | SCAFFOLD | Snapshot inmutable + ruleset_hash |
| `backend/app/execution/scheduler/__init__.py` | CREADO | Docstring subpaquete |
| `backend/app/execution/scheduler/planificador.py` | SCAFFOLD | Cron/APScheduler + mantenimiento (AUT-003) |
| `backend/app/execution/scheduler/continuo.py` | SCAFFOLD | Diff + notificación éxito/fallo (AUT-008/011/012) |
| `backend/app/db/session.py` | MODIFICAR (1 línea) | Registrar import del modelo en `init_db` + índice único parcial |
| `requirements.txt` / `requirements-prod.txt` | MODIFICAR (1 línea) | `APScheduler` (solo si backend in-process) |
| `tests/test_execution_models.py` … `test_execution_continuo.py` | CREAR | Pruebas por capacidad |

**Archivos de OTROS agentes que este plan NO toca** (solo se integra por
interfaz): `client_portal/jobs.py`, `client_portal/tool_registry.py`,
`aud/obligaciones_fiscales/models.py` (`ToolJob`), `notifications/email.py`,
`motor/nucleo.py` (Agente A). Los puntos de contacto están en la sección
"Puntos de integración".

---

### Task 1: `ExecutionRun` y su migración

**Files:**
- Modify: `backend/app/execution/models.py` (quitar el NotImplementedError de `resumen`)
- Modify: `backend/app/db/session.py` (registro del import + índice único parcial)
- Test: `tests/test_execution_models.py`

- [ ] **Step 1: Pruebas que fallan** — `tests/test_execution_models.py`

```python
"""Modelo ExecutionRun (contrato §2)."""
from backend.app.db.session import Base, SessionLocal, init_db
from backend.app.execution.models import (
    ExecutionRun, STATUS_QUEUED, STATUS_DEAD_LETTER, TERMINAL_STATUSES,
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
```

- [ ] **Step 2: Correr y ver que falla** — `pytest tests/test_execution_models.py -q`
  → falla: `init_db` no registra la tabla / `resumen` lanza NotImplementedError.

- [ ] **Step 3: Implementar**
  1. En `db/session.py::init_db`, junto a los demás imports de modelos:
     `from backend.app.execution import models as _execution_models  # noqa: F401`.
     `Base.metadata.create_all` crea `execution_runs` (tabla nueva).
  2. Tras `create_all`, en Postgres, crear el índice único parcial de
     idempotencia con SQL idempotente (patrón `_ensure_forge_append_only_triggers`):
     `CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_runs_idem_live ON
     execution_runs (idempotency_key) WHERE status NOT IN ('canceled','dead_letter');`
     (en SQLite es no-op; la garantía se emula en `enqueue`, Task 3).
  3. Implementar `ExecutionRun.resumen()` devolviendo dict liviano:
     `run_id, engagement_id, app_id, app_version, engine_version, status,
     trigger_source, attempts, max_attempts, created_at, started_at,
     completed_at, executed_by, worker_id, output_hashes, previous_run_id`
     (sin `input_hashes` ni `parameter_snapshot` completos).

- [ ] **Step 4: Correr pruebas** — `pytest tests/test_execution_models.py -q` → 4 passed.
- [ ] **Step 5: Commit** — `feat(execution): modelo ExecutionRun (contrato §2) + registro en init_db`

---

### Task 2: `build_idempotency_key`

**Files:**
- Modify: `backend/app/execution/queue.py` (`build_idempotency_key`)
- Test: `tests/test_execution_idempotency.py`

- [ ] **Step 1: Pruebas que fallan**

```python
from backend.app.execution.queue import EnqueueRequest, build_idempotency_key


def _req(**k):
    base = dict(engagement_id=1, app_id="ICT_2025", app_version="1",
                engine_version="0.1.0", input_hashes={"f101": "ab"},
                parameter_snapshot={"materialidad": "25000.00"})
    base.update(k)
    return EnqueueRequest(**base)


def test_misma_entrada_misma_clave():
    assert build_idempotency_key(_req()) == build_idempotency_key(_req())


def test_orden_de_dict_no_cambia_la_clave():
    a = _req(input_hashes={"f101": "ab", "f103": "cd"})
    b = _req(input_hashes={"f103": "cd", "f101": "ab"})
    assert build_idempotency_key(a) == build_idempotency_key(b)


def test_cambiar_parametros_cambia_la_clave():
    a = build_idempotency_key(_req(parameter_snapshot={"materialidad": "25000.00"}))
    b = build_idempotency_key(_req(parameter_snapshot={"materialidad": "30000.00"}))
    assert a != b


def test_cambiar_engine_version_cambia_la_clave():
    assert build_idempotency_key(_req(engine_version="0.1.0")) != \
           build_idempotency_key(_req(engine_version="0.2.0"))


def test_es_sha256_hex():
    k = build_idempotency_key(_req())
    assert len(k) == 64 and all(c in "0123456789abcdef" for c in k)
```

- [ ] **Step 2: Correr y ver que falla** — NotImplementedError.
- [ ] **Step 3: Implementar** el hash canónico (JSON `sort_keys`, separadores
  fijos, `default=str`) sobre `input_hashes + parameter_snapshot + app_id +
  app_version + engine_version` — como en el docstring de referencia. **No**
  incluir `engagement_id`/`executed_by` (misma app+insumos en dos encargos son
  corridas distintas por el `engagement_id` de la fila, no por la clave; decidir
  y documentar: se recomienda incluir `engagement_id` para aislar por encargo —
  ajustar el test si se decide así).
- [ ] **Step 4: Correr pruebas** → 5 passed.
- [ ] **Step 5: Commit** — `feat(execution): idempotency_key canónica sha256 (AUT-004)`

---

### Task 3: `enqueue` idempotente

**Files:**
- Modify: `backend/app/execution/queue.py` (`enqueue`)
- Test: `tests/test_execution_queue_enqueue.py` (usa SQLite en memoria)

- [ ] **Step 1: Pruebas que fallan**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.execution.models import ExecutionRun, STATUS_QUEUED, STATUS_CANCELED
from backend.app.execution.queue import EnqueueRequest, enqueue


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    # importar modelos para poblar metadata
    from backend.app.execution import models  # noqa: F401
    Base.metadata.create_all(eng, tables=[ExecutionRun.__table__])
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _req():
    return EnqueueRequest(engagement_id=1, app_id="ICT_2025", app_version="1",
                          engine_version="0.1.0", input_hashes={"f101": "ab"},
                          parameter_snapshot={"snapshot_hash": "cd"})


def test_encolar_crea_una_corrida_queued(db):
    run = enqueue(db, _req())
    assert run.status == STATUS_QUEUED and run.run_id
    assert db.query(ExecutionRun).count() == 1


def test_encolar_dos_veces_lo_mismo_devuelve_la_misma(db):
    a = enqueue(db, _req())
    b = enqueue(db, _req())
    assert a.run_id == b.run_id
    assert db.query(ExecutionRun).count() == 1  # idempotente (AUT-004)


def test_una_cancelada_no_bloquea_reencolar(db):
    a = enqueue(db, _req())
    a.status = STATUS_CANCELED
    db.commit()
    b = enqueue(db, _req())  # la viva no existe → crea nueva
    assert b.run_id != a.run_id and db.query(ExecutionRun).count() == 2
```

- [ ] **Step 2: Correr y ver que falla** — NotImplementedError.
- [ ] **Step 3: Implementar** `enqueue`: calcular `idempotency_key`; SELECT de
  una corrida con esa clave y estado NO en `{canceled, dead_letter}`; si existe,
  devolverla; si no, INSERT con `run_id=uuid4().hex`, `available_at=_utcnow()`.
  Todo en la misma transacción (emula el índice parcial en SQLite).
- [ ] **Step 4: Correr pruebas** → 3 passed.
- [ ] **Step 5: Commit** — `feat(execution): enqueue idempotente sobre ExecutionRun (AUT-004)`

---

### Task 4: Lease del worker (`lease_next`, `heartbeat`, `mark_running`, `mark_succeeded`)

**Files:**
- Modify: `backend/app/execution/queue.py`
- Test: `tests/test_execution_lease.py`

- [ ] **Step 1: Pruebas que fallan** (reloj inyectado; fixture `db` como Task 3)
  Casos: `lease_next` devuelve la corrida más antigua disponible y la marca
  `leased` con `worker_id`, `lease_expires_at`, `attempts=1`, `started_at`;
  `lease_next` devuelve None si no hay disponibles; una corrida con
  `available_at` futuro NO se toma; `heartbeat` extiende el lease; `heartbeat`
  de otro worker sobre un lease ajeno falla; `mark_running` pasa a `running`;
  `mark_succeeded` sella `output_hashes`, `completed_at`, estado `succeeded` y
  limpia el lease.
- [ ] **Step 2: Correr y ver que falla** — NotImplementedError.
- [ ] **Step 3: Implementar**. En Postgres, `lease_next` usa
  `with_for_update(skip_locked=True)`; en SQLite se ignora el flag (serializa la
  transacción) — abstraerlo con `try/except` o `dialect`.
- [ ] **Step 4: Correr pruebas** → verde.
- [ ] **Step 5: Commit** — `feat(execution): lease de corridas con heartbeat y sellado de salida (AUT-005)`

---

### Task 5: Reintentos y dead-letter (`mark_failed`, `compute_backoff`)

**Files:**
- Modify: `backend/app/execution/queue.py`
- Test: `tests/test_execution_retries.py`

- [ ] **Step 1: Pruebas que fallan**
  Casos: primer fallo con `max_attempts=3` → estado `failed`, `available_at`
  futuro según `BACKOFF_SECONDS[0]`, `error_trace` poblado; tras agotar los 3
  intentos → estado `dead_letter`, `completed_at` fijado, NO reagenda;
  `compute_backoff(1)` = now+60s, `(2)`=+300s, `(3)`=+900s, `(4)`=+900s (satura).
- [ ] **Step 2: Correr y ver que falla** — NotImplementedError.
- [ ] **Step 3: Implementar** la lógica de decisión reintento/dead-letter.
- [ ] **Step 4: Correr pruebas** → verde.
- [ ] **Step 5: Commit** — `feat(execution): backoff exponencial y dead-letter (AUT-005/006)`

---

### Task 6: Recuperación y dead-letter ops (`reclaim_expired_leases`, `list_dead_letter`, `requeue`)

**Files:**
- Modify: `backend/app/execution/queue.py`
- Test: `tests/test_execution_reclaim.py`

- [ ] **Step 1: Pruebas que fallan**
  Casos: una corrida `leased` con `lease_expires_at` pasado vuelve a `queued` si
  quedan intentos, o a `dead_letter` si no; `reclaim_expired_leases` devuelve el
  conteo; `list_dead_letter` filtra por estado (y por `engagement_id` si se
  pasa); `requeue` resetea `attempts=0`, estado `queued`, limpia `error_trace`.
- [ ] **Step 2/3/4:** implementar y verde.
- [ ] **Step 5: Commit** — `feat(execution): recuperación de leases muertos y reencolado manual (AUT-005/006)`

---

### Task 7: Historial de corridas (`run_history.py`)

**Files:**
- Modify: `backend/app/execution/run_history.py`
- Test: `tests/test_execution_history.py`

- [ ] **Step 1: Pruebas que fallan**
  Casos: `list_runs` filtra por `engagement_id`/`app_id`/`status`/rango de
  fechas y pagina (orden `created_at` desc); cada item es `resumen()`;
  `get_run` por `run_id`; `latest_successful_run` devuelve la última `succeeded`
  (no una `failed` posterior); `run_lineage` reúne `engine_version`,
  `app_version`, `input_hashes`, `parameter_snapshot` (con `ruleset_hash`) y
  `output_hashes`.
- [ ] **Step 2/3/4:** implementar y verde.
- [ ] **Step 5: Commit** — `feat(execution): historial de corridas y ficha de lineage (AUT-007, DATA-011/012)`

---

### Task 8: Snapshots inmutables (`snapshots.py`)

**Files:**
- Modify: `backend/app/execution/snapshots.py`
- Test: `tests/test_execution_snapshots.py`

- [ ] **Step 1: Pruebas que fallan**
  Casos: `compute_ruleset_hash` estable frente al orden de la lista;
  `build_snapshot` produce dict con `schema_version`, `engine_version`,
  `ruleset_hash`, `rules`, `parameters` y `snapshot_hash`; `verify_snapshot`
  True sobre uno recién construido; `verify_snapshot` False si se muta un
  parámetro sin recalcular el hash (AUT-010); dos snapshots con los mismos
  parámetros pero distinto `ruleset_hash` difieren en `snapshot_hash` (DATA-012).
- [ ] **Step 2/3/4:** implementar y verde. Los importes van como `str` (Decimal
  serializado) — nunca `float` — para hash estable.
- [ ] **Step 5: Commit** — `feat(execution): snapshot inmutable parámetros+engine+ruleset (AUT-009/010, DATA-011/012)`

---

### Task 9: Scheduler — funciones puras (`due_schedules`, `run_due_schedules`, `run_maintenance`)

**Files:**
- Modify: `backend/app/execution/scheduler/planificador.py`
- Decision: dónde viven los `Schedule` (tabla `execution_schedules` vs
  config/manifest). Recomendado: tabla nueva si el cliente los edita; documentar
  la decisión en el commit y, si es tabla, agregarla a `models.py` + `init_db`.
- Test: `tests/test_execution_scheduler.py`

- [ ] **Step 1: Pruebas que fallan**
  Casos (reloj inyectado): `due_schedules` devuelve solo los `enabled` cuya
  expresión cron cae en `now` y no dispararon aún en esa ventana; deshabilitado
  nunca dispara; `run_due_schedules` llama a `enqueue` con
  `trigger_source="schedule"` por cada vencido y devuelve los `run_id`; un
  segundo `run_due_schedules` en la misma ventana NO duplica (idempotencia via
  `enqueue`); `run_maintenance` invoca `reclaim_expired_leases` y devuelve
  resumen.
- [ ] **Step 2/3/4:** implementar y verde. Evaluar cron en UTC (usar `croniter`
  si se prefiere una lib, o parseo propio de 5 campos; si se usa `croniter`,
  registrarla como dependencia — pero se recomienda empezar sin lib nueva).
- [ ] **Step 5: Commit** — `feat(execution): scheduler de corridas programadas + mantenimiento (AUT-003)`

---

### Task 10: Backend del scheduler (APScheduler in-process **o** Render Cron)

**Files:**
- Modify: `backend/app/execution/scheduler/planificador.py` (`start_apscheduler`)
- Modify: `requirements.txt` + `requirements-prod.txt` (si APScheduler)
- Modify (fuera del paquete, coordinar): arranque en el `lifespan`/startup de
  FastAPI **o** un CLI `python -m backend.app.execution.scheduler.tick` para el
  Render Cron.
- Test: `tests/test_execution_scheduler_backend.py` (marca `apscheduler` skip si
  no está instalado)

- [ ] **Step 1: Decidir backend.** Recomendación: **Render Cron** primero (no
  añade dependencia, encaja con "1 CPU / workers 1" y con el modelo actual de
  `BackgroundTasks`); dejar `start_apscheduler` implementado pero opcional para
  cuando haya un proceso siempre-activo.
- [ ] **Step 2: Si APScheduler:** agregar `APScheduler==3.10.4` (compatible con
  el resto del pin) a `requirements.txt` y `requirements-prod.txt`. Implementar
  `start_apscheduler` registrando `run_due_schedules` y `run_maintenance` como
  `interval`/`cron` jobs, abriendo `SessionLocal()` por tick, y devolviendo el
  scheduler para pararlo en el shutdown.
- [ ] **Step 3: Si Render Cron:** crear el entrypoint `tick` que abre una
  sesión, llama a `run_due_schedules` + `run_maintenance` y cierra; documentar
  en el README el Cron Job de Render (`*/5 * * * *`).
- [ ] **Step 4:** test que arranca/para el scheduler (skip sin la lib) o que el
  `tick` corre sin error contra SQLite.
- [ ] **Step 5: Commit** — `feat(execution): backend del scheduler (Render Cron / APScheduler opcional) (AUT-003)`

---

### Task 11: Diff vs corrida previa (`diff_runs`, `RunDiff`, `run_continuous`)

**Files:**
- Modify: `backend/app/execution/scheduler/continuo.py`
- Test: `tests/test_execution_diff.py`

- [ ] **Step 1: Pruebas que fallan**
  Casos: `diff_runs(current, None)` → todo en `nuevas`; excepción presente en
  ambas sin cambio → ni nuevas ni resueltas ni cambiadas; presente solo antes →
  `resueltas`; solo ahora → `nuevas`; misma clave con monto/severidad distinta →
  `cambiadas`; `RunDiff.hay_cambios` refleja el estado; `a_dict` serializable
  para `diff_json`. El emparejamiento es por clave estable (record_key/rule_id),
  no por orden.
- [ ] **Step 2/3/4:** implementar y verde. El diff consume el resumen persistido
  de cada corrida (`summary_json` / artefacto sellado), no recalcula reglas.
- [ ] **Step 5: Commit** — `feat(execution): diff de auditoría continua vs corrida previa (AUT-008)`

---

### Task 12: Notificación de éxito Y fallo (`on_run_finished`, `notify_success`, `notify_failure`)

**Files:**
- Modify: `backend/app/execution/scheduler/continuo.py`
- Create: `backend/app/notifications/templates/run_success.html`,
  `run_failure.html` (análogos a `job_ready.html`) — **coordinar con el dueño de
  `notifications/`**; si no procede tocar ese paquete, renderizar el HTML dentro
  de `continuo.py` con `send_email` directo.
- Test: `tests/test_execution_notify.py` (mockea `send_email`)

- [ ] **Step 1: Pruebas que fallan**
  Casos: `on_run_finished` sobre `succeeded` con `trigger_source="continuous"`
  calcula el diff, persiste `run.diff_json` y llama a `notify_success`;
  `on_run_finished` sobre `dead_letter` llama a `notify_failure`; una corrida
  `manual` no notifica; `notify_success`/`notify_failure` invocan
  `email.send_email` con destinatarios y asunto correctos (mock, sin red).
- [ ] **Step 2/3/4:** implementar y verde. Reutilizar
  `backend.app.notifications.email.send_email` (Resend + retry ya resuelto). El
  fallo NUNCA es silencioso (AUT-012).
- [ ] **Step 5: Commit** — `feat(execution): notificación de éxito y fallo en auditoría continua (AUT-011/012)`

---

### Task 13: Integración con el worker (ToolJob / jobs.py) — coordinada

**Files:**
- Test: `tests/test_execution_integration.py`
- Modify (coordinar con dueño del pipeline): envoltura en `client_portal/jobs.py`.

Este task conecta el motor de ejecución con el pipeline de jobs existente SIN
reescribirlo. Ver "Puntos de integración". El scaffold NO modifica `jobs.py`;
este task propone el cambio mínimo y lo prueba.

- [ ] **Step 1: Prueba de integración** — un `process_tool_job` (o su sucesor)
  que: (a) crea/toma una `ExecutionRun` para el job, (b) corre el
  `ToolConfig.processor`, (c) sella `mark_succeeded`/`mark_failed`, (d) si es
  continuo, llama `on_run_finished`. Verificar que el historial refleja la
  corrida y que un reintento del mismo job es idempotente.
- [ ] **Step 2/3/4:** implementar el wrapper (delgado) y verde.
- [ ] **Step 5: Commit** — `feat(execution): integrar la cola con el pipeline de ToolJob`

---

### Task 14: Cierre (lo hace el controlador, no un subagente)

- [ ] **Step 1:** `pytest tests/test_execution_*.py -v` TODO en verde + suite
  completa sin regresiones (recordar los 6 tests legacy conocidos que fallan por
  aislamiento, documentados en CLAUDE.md — no son de este módulo).
- [ ] **Step 2:** `security-review` de la rama (entra estado por HTTP; revisar
  aislamiento por `engagement_id`, que `executed_by` sea la identidad real, y que
  el snapshot no filtre datos del cliente).
- [ ] **Step 3:** Verificación empírica (REGLA SUPREMA): disparar una corrida
  programada real, confirmar historial + snapshot inmutable + diff + correos
  (éxito y fallo forzado). Contar y reportar, no asumir.
- [ ] **Step 4:** PR hacia `main` y despliegue.

---

## Puntos de integración (contratos con otros agentes/módulos)

1. **`client_portal/jobs.py::process_tool_job` (pipeline actual).**
   Hoy: lee `ToolJob`, busca el `ToolConfig`, corre `processor(job_id)`, marca
   `done`/`error`, envía email si `initiated_from="client"`. **Integración
   propuesta (Task 13):** el worker envuelve la ejecución en el ciclo de la cola
   — `lease_next`/`mark_running`/`mark_succeeded`/`mark_failed` — manteniendo el
   `processor` como el que hace el trabajo real. Cambio mínimo, sin reescribir el
   pipeline. Coordinar con el dueño de `client_portal/`.

2. **`ToolJob` (`aud/obligaciones_fiscales/models.py`).**
   `ExecutionRun` NO reemplaza a `ToolJob`: `ToolJob` es el trabajo del portal
   (slots, expiración 24h, notify_email); `ExecutionRun` es la corrida
   reproducible (versiones, hashes, snapshot, reintentos, historial). Se enlazan
   por `engagement_id`=`project_id` y, opcionalmente, guardando `run_id` en
   `ToolJob.summary_json`. NO se toca la tabla `tool_jobs` en este plan.

3. **`notifications/email.py`.**
   `continuo.py` reutiliza `send_email(to, subject, html)` (Resend + retry ya
   resuelto). Solo se agregan templates/render de corrida (Task 12); NO se
   reimplementa el transporte.

4. **Motor determinista (Agente A, `motor/nucleo.py`).**
   `snapshots.compute_ruleset_hash` consume `resumen_catalogo()` (id+version por
   regla). `diff_runs` empareja por la clave estable de `Excepcion`
   (record_key/rule_id) que el Agente A sella con `run_id`/`source_refs`. Contrato
   §2: `AnalyticException.run_id` apunta al `ExecutionRun.run_id`.

5. **`db/session.py::init_db`.**
   Registrar el import del modelo (1 línea) y el índice único parcial de
   idempotencia (SQL idempotente, patrón `_ensure_forge_append_only_triggers`).

6. **`audit_apps/` (Agente G, futuro).**
   `app_id`/`app_version` de `ExecutionRun` se resolverán contra el
   `AuditAppManifest` cuando exista; hoy aceptan también los `tool_code` del
   registry (ICT_2025, FLUJO_EFECTIVO). Sin acople duro.

---

## Dependencias nuevas a registrar

| Dependencia | Requerida | Dónde | Notas |
|---|---|---|---|
| `APScheduler` (`==3.10.4`) | **Opcional** | `requirements.txt`, `requirements-prod.txt` | SOLO si se elige el backend in-process (Task 10). Con **Render Cron** (recomendado primero) NO se agrega ninguna dependencia. |
| `croniter` | Opcional | idem | Solo si se prefiere una lib para evaluar cron en vez de parseo propio de 5 campos (Task 9). Evaluar antes de sumarla. |

Ninguna otra dependencia nueva: SQLAlchemy 2.0.36, FastAPI 0.115 y pytest ya
están en el repo.

---

## Qué queda EXPLÍCITAMENTE para implementar en el servidor

Todo el scaffold (`raise NotImplementedError`) porque fastapi/sqlalchemy no
corren en el contenedor del agente. En concreto, a llevar a verde con `pytest`
en el servidor:

- **models.py** — `ExecutionRun.resumen()`; registro en `init_db` + índice único
  parcial de idempotencia (Task 1).
- **queue.py** — `build_idempotency_key`, `enqueue`, `lease_next`, `heartbeat`,
  `mark_running`, `mark_succeeded`, `mark_failed`, `compute_backoff`,
  `reclaim_expired_leases`, `list_dead_letter`, `requeue` (Tasks 2-6).
- **run_history.py** — `list_runs`, `get_run`, `latest_successful_run`,
  `run_lineage` (Task 7).
- **snapshots.py** — `compute_ruleset_hash`, `build_snapshot`, `snapshot_hash`,
  `verify_snapshot` (Task 8).
- **scheduler/planificador.py** — `due_schedules`, `run_due_schedules`,
  `run_maintenance`, `start_apscheduler`, y la decisión backend
  (Render Cron vs APScheduler) + entrypoint del tick (Tasks 9-10).
- **scheduler/continuo.py** — `diff_runs`, `RunDiff.hay_cambios`/`a_dict`,
  `run_continuous`, `on_run_finished`, `notify_success`, `notify_failure`, y los
  templates de correo (Tasks 11-12).
- **Integración** con `client_portal/jobs.py` (Task 13, coordinada con su dueño).
- **Migración a Alembic** cuando el repo la adopte (deuda técnica del roadmap):
  portar el registro de la tabla y el índice parcial a una revisión formal.
- **Endpoints/CLI** de disparo manual, historial y reencolado desde dead-letter
  (fuera del alcance del paquete `execution/`; planificar con el dueño del
  portal/api cuando se exponga a la UI).
