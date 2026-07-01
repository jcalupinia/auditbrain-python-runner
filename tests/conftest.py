"""Fixtures de test. Usa TestClient sobre la app legacy con la plataforma
v1 ya montada (app.py incluye el api_router)."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

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
