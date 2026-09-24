"""Endpoints del motor de riesgo: detección de anomalías explicable."""
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_staff
from backend.app.risk.router import router


@pytest.fixture
def c():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_staff] = lambda: types.SimpleNamespace(
        id=1, email="a@x.ec", role="admin", organization_id=None
    )
    return TestClient(app)


def _datos():
    # Una serie con un outlier claro en 'monto'.
    base = [{"monto": v} for v in (100, 101, 99, 102, 98, 100, 101, 99)]
    return base + [{"monto": 100000}]  # atípico


def test_anomalias_estadistico_marca_el_outlier(c):
    r = c.post("/risk/anomalias", json={"registros": _datos(), "campos": ["monto"],
                                        "metodo": "estadistico"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["resumen"]["total"] == 9
    assert data["resumen"]["alto"] >= 1
    # el outlier (índice 8) sale con nivel alto y con factores que lo explican
    top = data["anomalias"][0]
    assert top["indice"] == 8 and top["nivel"] == "alto"
    assert top["factores"] and top["factores"][0]["variable"] == "monto"


def test_solo_marcados_omite_los_bajos(c):
    r = c.post("/risk/anomalias", json={"registros": _datos(), "campos": ["monto"],
                                        "metodo": "estadistico", "solo_marcados": True})
    filas = r.json()["anomalias"]
    assert all(f["nivel"] != "bajo" for f in filas)


def test_sin_campos_da_400(c):
    r = c.post("/risk/anomalias", json={"registros": [{"a": 1}], "campos": []})
    assert r.status_code == 400


def test_metodo_invalido_da_400(c):
    r = c.post("/risk/anomalias", json={"registros": [{"a": 1}], "campos": ["a"], "metodo": "magico"})
    assert r.status_code == 400


def test_ml_endpoint(c):
    r = c.get("/risk/ml")
    assert r.status_code == 200 and isinstance(r.json()["disponible"], bool)


def test_ensemble_sin_ml_degrada(c):
    # usar_ml pero sin sklearn → degrada a estadístico sin romper
    r = c.post("/risk/anomalias", json={"registros": _datos(), "campos": ["monto"],
                                        "metodo": "ensemble", "usar_ml": False})
    assert r.status_code == 200 and r.json()["metodo"] == "ensemble"
