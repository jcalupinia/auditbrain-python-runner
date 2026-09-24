"""Scheduler: cron, disparo, mantenimiento y backend (Tasks 9-10 del plan P1-D)."""
import datetime
import importlib.util

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.execution.models import ExecutionRun, STATUS_LEASED
from backend.app.execution.queue import EnqueueRequest
from backend.app.execution.scheduler import planificador as P
from backend.app.execution.scheduler.planificador import Schedule, cron_matches, due_schedules

T0 = datetime.datetime(2026, 3, 1, 8, 0, 0)  # minuto 0, hora 8


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


def _sched(**k):
    base = dict(schedule_id="s1", engagement_id=1, app_id="ICT_2025",
                app_version="1", cron="0 8 * * *", enabled=True)
    base.update(k)
    return Schedule(**base)


def _build_request(s: Schedule) -> EnqueueRequest:
    return EnqueueRequest(
        engagement_id=s.engagement_id, app_id=s.app_id, app_version=s.app_version,
        engine_version="0.1.0", input_hashes={"f": "h"},
        parameter_snapshot={"snapshot_hash": s.schedule_id}, trigger_source="schedule",
    )


def test_cron_matches_basico():
    assert cron_matches("0 8 * * *", T0)
    assert not cron_matches("30 8 * * *", T0)
    assert cron_matches("*/5 * * * *", T0)  # minuto 0 divisible por 5


def test_due_schedules_respeta_enabled_y_ventana():
    activos = due_schedules([_sched(), _sched(schedule_id="off", enabled=False)],
                            now=T0, last_fired={})
    assert [s.schedule_id for s in activos] == ["s1"]
    # ya disparado este minuto → no repite
    assert due_schedules([_sched()], now=T0, last_fired={"s1": T0}) == []
    # cron que no cae ahora
    assert due_schedules([_sched(cron="30 8 * * *")], now=T0, last_fired={}) == []


def test_run_due_schedules_encola_idempotente(db):
    last: dict = {}
    ids = P.run_due_schedules(db, schedules=[_sched()], build_request=_build_request,
                              now=T0, last_fired=last)
    assert len(ids) == 1 and db.query(ExecutionRun).count() == 1
    # segunda pasada en el mismo minuto no duplica (ventana + idempotencia)
    ids2 = P.run_due_schedules(db, schedules=[_sched()], build_request=_build_request,
                               now=T0, last_fired=last)
    assert ids2 == [] and db.query(ExecutionRun).count() == 1


def test_run_maintenance_recupera_leases(db):
    run = ExecutionRun(
        run_id="r1", engagement_id=1, app_id="A", app_version="1",
        engine_version="0.1.0", input_hashes={}, parameter_snapshot={},
        idempotency_key="k", status=STATUS_LEASED, attempts=1, max_attempts=3,
        worker_id="w1", lease_expires_at=T0,
    )
    db.add(run)
    db.commit()
    res = P.run_maintenance(db, now=T0 + datetime.timedelta(minutes=30))
    assert res["reclaimed"] == 1


@pytest.mark.skipif(
    importlib.util.find_spec("apscheduler") is None,
    reason="APScheduler no instalado (backend Render Cron por defecto)",
)
def test_start_apscheduler_arranca_y_para(db):
    sched = P.start_apscheduler(lambda: db)
    try:
        assert sched is not None
    finally:
        sched.shutdown(wait=False)
