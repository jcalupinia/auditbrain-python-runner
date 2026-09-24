"""Encadenado real de la bitácora vía servicio._evento (P2-G, ENG-020)."""
import types

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.ciclo.models import PruebaEvento
from backend.app.aud.niif.ciclo.gobernanza import GENESIS, CadenaCorrupta


@pytest.fixture
def db():
    eng = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import backend.app.aud.niif.ciclo.models  # noqa: F401
    import backend.app.auth.models  # noqa: F401
    import backend.app.context.models  # noqa: F401
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _p(estado="PRUEBA_SELECCIONADA"):
    # _evento solo lee p.id / p.revision / p.estado (FK no se fuerza en SQLite).
    return types.SimpleNamespace(id=1, revision=1, estado=estado)


def test_cadena_de_una_prueba_verifica(db):
    p = _p()
    servicio._evento(db, p, "create", None, "a@x.ec")
    p.estado = "PROGRAMA_PROPUESTO"
    servicio._evento(db, p, "generate_program", "PRUEBA_SELECCIONADA", "a@x.ec")
    p.estado = "APROBADO"
    servicio._evento(db, p, "approve", "EN_REVISION", "socio@x.ec", rol="SOCIO")
    db.commit()

    filas = servicio.verificar_bitacora(db, 1)  # no lanza
    assert [f.seq for f in filas] == [1, 2, 3]
    assert filas[0].prev_hash == GENESIS
    assert filas[1].prev_hash == filas[0].hash and filas[2].prev_hash == filas[1].hash
    assert all(len(f.hash) == 64 for f in filas)


def test_dos_eventos_seguidos_no_colisionan_en_seq(db):
    p = _p()
    servicio._evento(db, p, "a", None, "u")
    servicio._evento(db, p, "b", "PRUEBA_SELECCIONADA", "u")  # sin commit intermedio
    db.commit()
    assert sorted(f.seq for f in db.query(PruebaEvento).all()) == [1, 2]


def test_manipular_un_evento_rompe_la_verificacion(db):
    p = _p()
    servicio._evento(db, p, "create", None, "a@x.ec")
    p.estado = "X"
    servicio._evento(db, p, "b", "PRUEBA_SELECCIONADA", "a@x.ec")
    db.commit()

    ev = db.query(PruebaEvento).filter(PruebaEvento.seq == 1).first()
    ev.estado_nuevo = "HACKEADO"  # altera el contenido sin recomputar el hash
    db.flush()
    with pytest.raises(CadenaCorrupta):
        servicio.verificar_bitacora(db, 1)
