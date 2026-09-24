"""Auditoría continua: diff vs corrida previa y notificación (Tasks 11-12)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.execution.models import ExecutionRun, STATUS_SUCCEEDED, STATUS_DEAD_LETTER
from backend.app.execution.scheduler import continuo as C


def _run(run_id, excepciones, **k):
    base = dict(run_id=run_id, engagement_id=1, app_id="ICT_2025", app_version="1",
                engine_version="0.1.0", input_hashes={}, parameter_snapshot={},
                idempotency_key=run_id, summary_json={"excepciones": excepciones})
    base.update(k)
    return ExecutionRun(**base)


E1 = {"clave": "k1", "monto": "100", "severidad": "P1"}
E2 = {"clave": "k2", "monto": "50", "severidad": "P2"}


# --- Task 11: diff ----------------------------------------------------------
def test_primera_corrida_todo_nuevo():
    d = C.diff_runs(_run("r1", [E1, E2]), None)
    assert len(d.nuevas) == 2 and not d.resueltas and not d.cambiadas
    assert d.hay_cambios()


def test_sin_cambios():
    d = C.diff_runs(_run("r2", [E1]), _run("r1", [E1]))
    assert not d.hay_cambios()


def test_resueltas_y_nuevas():
    d = C.diff_runs(_run("r2", [E2]), _run("r1", [E1]))
    assert [e["clave"] for e in d.nuevas] == ["k2"]
    assert [e["clave"] for e in d.resueltas] == ["k1"]


def test_cambiadas_por_monto():
    antes = _run("r1", [E1])
    ahora = _run("r2", [{"clave": "k1", "monto": "999", "severidad": "P1"}])
    d = C.diff_runs(ahora, antes)
    assert [e["clave"] for e in d.cambiadas] == ["k1"]
    assert d.a_dict()["conteos"] == {"nuevas": 0, "resueltas": 0, "cambiadas": 1}


# --- Task 12: notificación --------------------------------------------------
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


@pytest.fixture
def correos(monkeypatch):
    enviados = []
    from backend.app.notifications import email
    monkeypatch.setattr(
        email, "send_email",
        lambda *, to, subject, html: enviados.append((to, subject)) or {"id": "x"},
    )
    return enviados


def test_on_run_finished_exito_notifica_y_persiste_diff(db, correos):
    run = _run("r1", [E1], trigger_source="continuous", status=STATUS_SUCCEEDED,
               previous_run_id=None)
    db.add(run)
    db.commit()
    C.on_run_finished(db, run, to=["auditor@firma.ec"])
    assert run.diff_json is not None and run.diff_json["conteos"]["nuevas"] == 1
    assert len(correos) == 1 and "OK" in correos[0][1]


def test_on_run_finished_dead_letter_notifica_fallo(db, correos):
    run = _run("r2", [], trigger_source="continuous", status=STATUS_DEAD_LETTER,
               error_trace="boom")
    db.add(run)
    db.commit()
    C.on_run_finished(db, run, to=["auditor@firma.ec"])
    assert len(correos) == 1 and "FALLO" in correos[0][1]


def test_corrida_manual_no_notifica(db, correos):
    run = _run("r3", [E1], trigger_source="manual", status=STATUS_SUCCEEDED)
    db.add(run)
    db.commit()
    C.on_run_finished(db, run, to=["auditor@firma.ec"])
    assert correos == []
