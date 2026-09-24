"""Historial de corridas y lineage (Task 7 del plan P1-D)."""
import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.execution.models import ExecutionRun, STATUS_SUCCEEDED, STATUS_FAILED
from backend.app.execution import run_history as H
from backend.app.execution.queue import EnqueueRequest, enqueue, lease_next, mark_succeeded

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


def _mk(db, **k):
    base = dict(engagement_id=1, app_id="ICT_2025", app_version="1",
                engine_version="0.1.0", input_hashes={"f": "h"},
                parameter_snapshot={"snapshot_hash": "s", "ruleset_hash": "rr"})
    base.update(k)
    return enqueue(db, EnqueueRequest(**base))


def test_list_runs_filtra_y_pagina(db):
    _mk(db, input_hashes={"f": "1"})
    _mk(db, input_hashes={"f": "2"}, app_id="OTRA")
    page = H.list_runs(db, H.HistoryFilter(app_id="ICT_2025"))
    assert page.total == 1 and page.runs[0]["app_id"] == "ICT_2025"
    p2 = H.list_runs(db, H.HistoryFilter(), page=1, size=1)
    assert p2.total == 2 and len(p2.runs) == 1


def test_get_run(db):
    r = _mk(db)
    assert H.get_run(db, r.run_id).run_id == r.run_id
    assert H.get_run(db, "noexiste") is None


def test_latest_successful_ignora_fallida_posterior(db):
    ok = _mk(db, input_hashes={"f": "1"})
    ok.status = STATUS_SUCCEEDED
    ok.completed_at = T0
    mala = _mk(db, input_hashes={"f": "2"})
    mala.status = STATUS_FAILED
    mala.completed_at = T0 + datetime.timedelta(hours=1)
    db.commit()
    got = H.latest_successful_run(db, engagement_id=1, app_id="ICT_2025")
    assert got.run_id == ok.run_id


def test_run_lineage(db):
    r = _mk(db)
    r.output_hashes = {"xlsx": "zz"}
    db.commit()
    lin = H.run_lineage(db, r.run_id)
    assert lin["engine_version"] == "0.1.0"
    assert lin["parameter_snapshot"]["ruleset_hash"] == "rr"
    assert lin["output_hashes"] == {"xlsx": "zz"}
    assert H.run_lineage(db, "noexiste") == {}
