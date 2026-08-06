"""Fixtures de test. Usa TestClient sobre la app legacy con la plataforma
v1 ya montada (app.py incluye el api_router)."""

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = Path(__file__).resolve().parents[1]

# --- Base de datos de la suite (ANTES de importar la app) ---------------
#
# ``backend/app/db/session.py`` resuelve ``DATABASE_URL`` **en tiempo de
# import** y su default es ``sqlite:///./auditbrain.db``: exactamente la
# misma base que usa ``uvicorn app:app`` en local. Sin este override,
# ``pytest`` escribe en la base de desarrollo del programador y:
#
#  - la ensucia (se midieron 1.957 clientes y ~700 usuarios basura), y
#  - a partir de la SEGUNDA corrida fallan los tests que insertan filas con
#    nombre fijo contra el índice único ``clients(organization_id, name)``.
#
# En CI no se notaba porque el checkout es limpio y la base nace vacía.
# Se borra el archivo al arrancar para que cada corrida sea reproducible;
# no se borra al terminar, para poder inspeccionarlo tras un fallo.
# ``TEST_DATABASE_URL`` permite apuntar la suite a otro motor (p. ej. el
# Postgres de un entorno de pruebas) sin tocar código.
_TEST_DB = _REPO_ROOT / "auditbrain_tests.db"
_EXPLICITA = os.getenv("TEST_DATABASE_URL", "").strip()
if _EXPLICITA:
    os.environ["DATABASE_URL"] = _EXPLICITA
else:
    _TEST_DB.unlink(missing_ok=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

sys.path.insert(0, str(_REPO_ROOT))

import app as legacy_app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _ensure_schema():
    """Garantiza que el esquema exista antes de CUALQUIER test.

    Muchos tests del repo usan ``SessionLocal()`` directo (sin el fixture
    ``client``), por lo que dependían de que algún otro test con ``client``
    disparara ``init_db()`` (vía el startup de la app) antes en el orden
    alfabético de recolección. Eso hacía frágiles las corridas aisladas o con
    ``-k``/reordenamiento. ``init_db()`` es idempotente (``create_all`` +
    migraciones aditivas), así que llamarlo una vez al inicio de la sesión de
    tests hace herméticos a todos los módulos sin acoplarlos al orden.
    """
    from backend.app.db.session import init_db
    init_db()
    yield


@pytest.fixture()
def client():
    with TestClient(legacy_app.app) as c:
        yield c
