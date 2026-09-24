"""Endpoints del motor de evidencia: conciliación asistida y confianza."""
import types

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_staff
from backend.app.evidence.router import router


@pytest.fixture
def c():
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_staff] = lambda: types.SimpleNamespace(
        id=1, email="a@x.ec", role="admin", organization_id=None
    )
    return TestClient(app)


def test_conciliar_empareja_por_texto_y_monto(c):
    body = {
        "izquierda": [
            {"ref": "F-001", "monto": "100.00"},
            {"ref": "F-002", "monto": "250.50"},
            {"ref": "F-999", "monto": "9.99"},  # sin par
        ],
        "derecha": [
            {"ref": "F-002", "monto": "250.51"},  # 1 centavo de diferencia
            {"ref": "F-001", "monto": "100.00"},
        ],
        "criterio": {
            "umbral": 0.8,
            "campos": [
                {"nombre": "ref", "tipo": "texto", "modo": "normalizado", "peso": 1},
                {"nombre": "monto", "tipo": "numero", "modo": "normalizado", "peso": 1,
                 "tolerancia_absoluta": "0.02"},
            ],
        },
    }
    r = c.post("/evidence/conciliar", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["resumen"]["conciliadas"] == 2
    assert data["resumen"]["izquierda_sin_conciliar"] == 1
    assert data["resumen"]["derecha_sin_conciliar"] == 0
    # F-001 y F-002 conciliadas; F-999 sin coincidencia
    estados = {f["indice_izquierda"]: f["estado"] for f in data["filas"]}
    assert estados[0] == "unica" and estados[1] == "unica" and estados[2] == "sin_coincidencia"


def test_conciliar_sin_campos_da_400(c):
    r = c.post("/evidence/conciliar", json={"izquierda": [], "derecha": [], "criterio": {"campos": []}})
    assert r.status_code == 400


def test_conciliar_modo_semantico_rechazado(c):
    body = {"izquierda": [{"x": "a"}], "derecha": [{"x": "a"}],
            "criterio": {"campos": [{"nombre": "x", "modo": "semantico"}]}}
    assert c.post("/evidence/conciliar", json=body).status_code == 400


def test_confianza_extraccion(c):
    r = c.post("/evidence/confianza", json={"tipo": "extraccion", "metodo": "excel"})
    assert r.status_code == 200
    assert r.json()["nivel"] == "alta" and r.json()["score"] >= 0.9


def test_confianza_ocr_penaliza(c):
    r = c.post("/evidence/confianza",
               json={"tipo": "extraccion", "metodo": "ocr", "ocr_word_confidence": 0.5})
    assert r.status_code == 200 and r.json()["score"] < 0.6  # 0.70 * 0.5 = 0.35


def test_confianza_tipo_invalido_da_400(c):
    assert c.post("/evidence/confianza", json={"tipo": "otro"}).status_code == 400
