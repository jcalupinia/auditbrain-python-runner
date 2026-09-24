"""Endpoints del motor de ejecución (Task 13 / endpoints P1-D)."""
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base, get_db
from backend.app.auth.deps import require_staff
from backend.app.execution.models import ExecutionRun, STATUS_DEAD_LETTER
from backend.app.execution.queue import EnqueueRequest, enqueue
from backend.app.execution.router import router


@pytest.fixture
def client():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    from backend.app.execution import models  # noqa: F401
    import backend.app.auth.models  # noqa: F401
    import backend.app.context.models  # noqa: F401
    Base.metadata.create_all(eng, tables=[ExecutionRun.__table__])
    Session = sessionmaker(bind=eng)
    db = Session()

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[require_staff] = lambda: types.SimpleNamespace(id=99)

    yield TestClient(app), db
    db.close()


def _req(**k):
    base = dict(engagement_id=1, app_id="ICT_2025", app_version="1",
                engine_version="1.0.0", input_hashes={"f": "h"},
                parameter_snapshot={"snapshot_hash": "s"})
    base.update(k)
    return EnqueueRequest(**base)


def test_listar_y_detalle(client):
    c, db = client
    run = enqueue(db, _req())
    r = c.get("/execution/runs")
    assert r.status_code == 200 and r.json()["total"] == 1
    d = c.get(f"/execution/runs/{run.run_id}")
    assert d.status_code == 200 and d.json()["run_id"] == run.run_id
    assert c.get("/execution/runs/noexiste").status_code == 404


def test_lineage(client):
    c, db = client
    run = enqueue(db, _req())
    lin = c.get(f"/execution/runs/{run.run_id}/lineage")
    assert lin.status_code == 200
    assert lin.json()["engine_version"] == "1.0.0"


def test_dead_letter_y_requeue(client):
    c, db = client
    run = enqueue(db, _req())
    run.status = STATUS_DEAD_LETTER
    run.attempts = 1
    db.commit()
    dl = c.get("/execution/dead-letter")
    assert dl.status_code == 200 and dl.json()["total"] == 1
    # requeue solo desde dead_letter
    rq = c.post(f"/execution/runs/{run.run_id}/requeue")
    assert rq.status_code == 200 and rq.json()["status"] == "queued"
    # ya no está en dead_letter → 409
    assert c.post(f"/execution/runs/{run.run_id}/requeue").status_code == 409


def test_disparo_manual_idempotente(client):
    c, db = client
    body = {"engagement_id": 5, "app_id": "FLUJO_EFECTIVO",
            "input_hashes": {"x": "1"}, "parameter_snapshot": {"m": "1"}}
    a = c.post("/execution/runs", json=body)
    assert a.status_code == 202
    b = c.post("/execution/runs", json=body)
    assert b.json()["run_id"] == a.json()["run_id"]  # idempotente


def test_maintenance(client):
    c, db = client
    assert c.post("/execution/maintenance").json()["reclaimed"] == 0
