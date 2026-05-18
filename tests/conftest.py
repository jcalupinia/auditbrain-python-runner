"""Fixtures de test. Usa TestClient sobre la app legacy con la plataforma
v1 ya montada (app.py incluye el api_router)."""

import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as legacy_app  # noqa: E402


@pytest.fixture()
def client():
    with TestClient(legacy_app.app) as c:
        yield c
