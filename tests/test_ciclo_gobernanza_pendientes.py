"""Pendientes de P2-G (ENG-020): trigger append-only, sellado histórico,
checkpoint IA y toggle de segregación de funciones."""
import types

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.ciclo.models import PruebaEvento
from backend.app.aud.niif.ciclo.gobernanza import GENESIS, CadenaCorrupta, compute_hash_evento


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import backend.app.aud.niif.ciclo.models  # noqa: F401
    import backend.app.auth.models  # noqa: F401
    import backend.app.context.models  # noqa: F401
    Base.metadata.create_all(eng)
    return eng


@pytest.fixture
def db(engine):
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


# --- Trigger append-only: bloquea UPDATE, permite DELETE --------------------

def _crea_trigger_sqlite(engine):
    """Aplica el mismo DDL que ``_ensure_bitacora_append_only_trigger`` en un
    engine de test (la función real usa el engine global del módulo)."""
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TRIGGER IF NOT EXISTS aud_prueba_eventos_no_update "
            "BEFORE UPDATE ON aud_prueba_eventos BEGIN "
            "SELECT RAISE(ABORT, 'aud_prueba_eventos es append-only: los eventos no se modifican'); END;"
        ))


def test_ensure_trigger_del_modulo_es_el_mismo_ddl(monkeypatch, engine):
    """La función real crea el trigger si se apunta al engine de test."""
    from backend.app.db import session as sess
    monkeypatch.setattr(sess, "engine", engine)
    sess._ensure_bitacora_append_only_trigger()  # no debe lanzar
    with engine.connect() as conn:
        nombres = [r[0] for r in conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='trigger'"
        )).all()]
    assert "aud_prueba_eventos_no_update" in nombres


def test_update_de_un_evento_esta_bloqueado_a_nivel_de_motor(db, engine):
    servicio._evento(db, types.SimpleNamespace(id=1, revision=1, estado="X"),
                     "create", None, "a@x.ec")
    db.commit()
    _crea_trigger_sqlite(engine)
    ev = db.query(PruebaEvento).first()
    ev.estado_nuevo = "HACKEADO"
    with pytest.raises(DatabaseError):
        db.commit()  # el trigger aborta el UPDATE
    db.rollback()


def test_delete_de_eventos_sigue_permitido(db, engine):
    """encerar/eliminar borran eventos: el trigger (solo UPDATE) no lo impide."""
    p = types.SimpleNamespace(id=1, revision=1, estado="X")
    servicio._evento(db, p, "create", None, "a@x.ec")
    servicio._evento(db, p, "b", "X", "a@x.ec")
    db.commit()
    _crea_trigger_sqlite(engine)
    for e in db.query(PruebaEvento).all():
        db.delete(e)
    db.commit()  # no lanza
    assert db.query(PruebaEvento).count() == 0


# --- Sellado histórico ------------------------------------------------------

def _evento_sin_sellar(db, pid, accion, anterior, nuevo, actor="a@x.ec"):
    """Inserta un evento como los previos a P2-G: sin seq/prev_hash/hash."""
    ev = PruebaEvento(prueba_id=pid, revision=1, accion=accion,
                      estado_anterior=anterior, estado_nuevo=nuevo, actor=actor)
    db.add(ev)
    db.flush()
    return ev


def test_sellar_bitacora_historica_encadena_y_verifica(db):
    _evento_sin_sellar(db, 1, "create", None, "PRUEBA_SELECCIONADA")
    _evento_sin_sellar(db, 1, "generate_program", "PRUEBA_SELECCIONADA", "PROGRAMA_PROPUESTO")
    _evento_sin_sellar(db, 2, "create", None, "PRUEBA_SELECCIONADA")  # otra prueba
    db.commit()

    n = servicio.sellar_bitacora_historica(db)
    db.commit()
    assert n == 3
    # ambas cadenas quedan íntegras y arrancan en GENESIS/seq=1
    f1 = servicio.verificar_bitacora(db, 1)
    f2 = servicio.verificar_bitacora(db, 2)
    assert [f.seq for f in f1] == [1, 2] and f1[0].prev_hash == GENESIS
    assert [f.seq for f in f2] == [1] and f2[0].prev_hash == GENESIS


def test_sellar_es_idempotente(db):
    _evento_sin_sellar(db, 1, "create", None, "PRUEBA_SELECCIONADA")
    db.commit()
    assert servicio.sellar_bitacora_historica(db) == 1
    db.commit()
    assert servicio.sellar_bitacora_historica(db) == 0  # ya no hay nada sin sellar


# --- Checkpoint IA ----------------------------------------------------------

def test_registrar_checkpoint_ia_deja_content_hash_y_cadena_valida(db):
    p = types.SimpleNamespace(id=7, revision=2, estado="RESULTADOS_ANALIZADOS")
    servicio._evento(db, p, "analyze", "PRUEBA_EJECUTADA", "a@x.ec")
    db.commit()
    ev = servicio.registrar_checkpoint_ia(db, p, "ia@x.ec", "deadbeef" * 8,
                                          comentario="Interpretación A1", rol="PREPARADOR")
    assert ev.accion == "checkpoint_ia"
    assert ev.content_hash == "deadbeef" * 8 and ev.rol == "PREPARADOR"
    assert ev.estado_anterior == "RESULTADOS_ANALIZADOS" and ev.estado_nuevo == "RESULTADOS_ANALIZADOS"
    filas = servicio.verificar_bitacora(db, 7)  # el content_hash entra al hash firmado
    assert [f.seq for f in filas] == [1, 2]


# --- Toggle de segregación --------------------------------------------------

def test_segregacion_desactivada_por_defecto(monkeypatch):
    monkeypatch.delenv("CICLO_SEGREGACION_ENABLED", raising=False)
    assert servicio._segregacion_activa() is False


@pytest.mark.parametrize("valor", ["true", "1", "on", "YES", "True"])
def test_segregacion_se_activa_con_env(monkeypatch, valor):
    monkeypatch.setenv("CICLO_SEGREGACION_ENABLED", valor)
    assert servicio._segregacion_activa() is True


def test_rol_no_aprobador_es_rechazado_por_reglas_cuando_hay_segregacion():
    """La transición con el rol real rechaza a quien no puede aprobar (ENG-005)."""
    from backend.app.aud.niif.ciclo import reglas
    t = {"state": "EN_REVISION", "run": True, "analysis": "x", "conclusion": "y",
         "conclusionReviewed": True, "validation": {"ok": True},
         "reconciliation": {"resolved": True}, "notes": []}
    # ADMIN aprueba; PREPARADOR no.
    assert reglas.transicion(t, "approve", "ADMIN") == "APROBADO"
    with pytest.raises(reglas.ReglaIncumplida):
        reglas.transicion(t, "approve", "PREPARADOR")
