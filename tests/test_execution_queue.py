"""Cola de ejecución: idempotencia, enqueue, lease, reintentos, dead-letter,
recuperación (Tasks 2-6 del plan P1-D)."""
import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.execution.models import (
    ExecutionRun,
    STATUS_CANCELED,
    STATUS_DEAD_LETTER,
    STATUS_FAILED,
    STATUS_LEASED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
)
from backend.app.execution import queue as Q
from backend.app.execution.queue import EnqueueRequest, build_idempotency_key, enqueue

T0 = datetime.datetime(2026, 3, 1, 8, 0, 0)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    from backend.app.execution import models  # noqa: F401
    import backend.app.auth.models  # noqa: F401  (registra users)
    import backend.app.context.models  # noqa: F401  (registra projects)
    Base.metadata.create_all(eng, tables=[ExecutionRun.__table__])
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _req(**k):
    base = dict(engagement_id=1, app_id="ICT_2025", app_version="1",
                engine_version="0.1.0", input_hashes={"f101": "ab"},
                parameter_snapshot={"snapshot_hash": "cd"})
    base.update(k)
    return EnqueueRequest(**base)


# --- Task 2: idempotency_key -------------------------------------------------
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


# --- Task 3: enqueue idempotente --------------------------------------------
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


# --- Task 4: lease ----------------------------------------------------------
def test_lease_toma_la_mas_antigua_y_la_marca(db):
    enqueue(db, _req(input_hashes={"a": "1"}), now=T0)
    enqueue(db, _req(input_hashes={"a": "2"}), now=T0)
    run = Q.lease_next(db, worker_id="w1", now=T0)
    assert run is not None and run.status == STATUS_LEASED
    assert run.worker_id == "w1" and run.attempts == 1 and run.started_at == T0
    assert run.lease_expires_at == T0 + datetime.timedelta(seconds=Q.DEFAULT_LEASE_SECONDS)


def test_lease_none_si_no_hay(db):
    assert Q.lease_next(db, worker_id="w1", now=T0) is None


def test_lease_no_toma_available_at_futuro(db):
    r = enqueue(db, _req(), now=T0)
    r.available_at = T0 + datetime.timedelta(hours=1)
    db.commit()
    assert Q.lease_next(db, worker_id="w1", now=T0) is None


def test_heartbeat_extiende_y_rechaza_ajeno(db):
    enqueue(db, _req(), now=T0)
    run = Q.lease_next(db, worker_id="w1", now=T0)
    Q.heartbeat(db, run, worker_id="w1", now=T0 + datetime.timedelta(seconds=30))
    assert run.lease_expires_at == T0 + datetime.timedelta(seconds=30 + Q.DEFAULT_LEASE_SECONDS)
    with pytest.raises(PermissionError):
        Q.heartbeat(db, run, worker_id="otro", now=T0)


def test_mark_running_y_succeeded(db):
    enqueue(db, _req(), now=T0)
    run = Q.lease_next(db, worker_id="w1", now=T0)
    Q.mark_running(db, run, worker_id="w1")
    assert run.status == STATUS_RUNNING
    Q.mark_succeeded(db, run, output_hashes={"xlsx": "ff"}, now=T0)
    assert run.status == STATUS_SUCCEEDED and run.output_hashes == {"xlsx": "ff"}
    assert run.completed_at == T0 and run.lease_expires_at is None


# --- Task 5: reintentos y dead-letter ---------------------------------------
def test_compute_backoff():
    assert Q.compute_backoff(1, T0) == T0 + datetime.timedelta(seconds=60)
    assert Q.compute_backoff(2, T0) == T0 + datetime.timedelta(seconds=300)
    assert Q.compute_backoff(3, T0) == T0 + datetime.timedelta(seconds=900)
    assert Q.compute_backoff(4, T0) == T0 + datetime.timedelta(seconds=900)  # satura


def test_primer_fallo_reintenta(db):
    enqueue(db, _req(), now=T0)
    run = Q.lease_next(db, worker_id="w1", now=T0)  # attempts=1
    Q.mark_failed(db, run, error_trace="boom", now=T0)
    assert run.status == STATUS_FAILED
    assert run.available_at == T0 + datetime.timedelta(seconds=60)
    assert run.error_trace == "boom"


def test_agotar_intentos_va_a_dead_letter(db):
    run = enqueue(db, _req())
    run.attempts = 3  # ya consumió los 3
    db.commit()
    Q.mark_failed(db, run, error_trace="boom", now=T0)
    assert run.status == STATUS_DEAD_LETTER and run.completed_at == T0


# --- Task 6: recuperación y dead-letter ops ---------------------------------
def test_reclaim_devuelve_a_queued_si_quedan_intentos(db):
    enqueue(db, _req(), now=T0)
    run = Q.lease_next(db, worker_id="w1", now=T0)  # attempts=1, leased
    n = Q.reclaim_expired_leases(db, now=T0 + datetime.timedelta(seconds=Q.DEFAULT_LEASE_SECONDS + 1))
    assert n == 1 and run.status == STATUS_QUEUED and run.worker_id is None


def test_reclaim_a_dead_letter_sin_intentos(db):
    run = enqueue(db, _req())
    run.status = STATUS_LEASED
    run.attempts = 3
    run.worker_id = "w1"
    run.lease_expires_at = T0
    db.commit()
    n = Q.reclaim_expired_leases(db, now=T0 + datetime.timedelta(seconds=1))
    assert n == 1 and run.status == STATUS_DEAD_LETTER


def test_list_dead_letter_y_requeue(db):
    run = enqueue(db, _req())
    run.status = STATUS_DEAD_LETTER
    run.attempts = 3
    run.error_trace = "x"
    db.commit()
    assert [r.run_id for r in Q.list_dead_letter(db)] == [run.run_id]
    assert Q.list_dead_letter(db, engagement_id=999) == []
    Q.requeue(db, run, executed_by=7)
    assert run.status == STATUS_QUEUED and run.attempts == 0
    assert run.error_trace is None and run.executed_by == 7
