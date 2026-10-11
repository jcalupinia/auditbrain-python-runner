"""Fase B de la Capa de Mapeo Universal: endpoints HTTP del flujo en dos tiempos.

Monta una app FastAPI mínima solo con el router de ingesta (sin DB ni conftest
pesado) y sobreescribe la dependencia de acceso, igual que test_ingesta_api.py.
El flujo es SIN estado: el cliente reenvía el archivo en «aplicar».

Datos ficticios (M14/M35): ninguna cifra de cliente entra al repo.
"""
from __future__ import annotations

import importlib.util
import io
import json
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_runner_access


def _cargar_router_ingesta():
    """Carga backend/app/api/ingesta.py SIN disparar backend.app.api.__init__."""
    import backend
    raiz = pathlib.Path(backend.__file__).resolve().parent.parent
    ruta = raiz / "backend/app/api/ingesta.py"
    spec = importlib.util.spec_from_file_location("ingesta_api_mapeo_standalone", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ingesta_api = _cargar_router_ingesta()


def _xlsx(filas) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(list(fila))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


MAYOR_OK = [
    ["Cuenta", "Fecha", "Debe", "Haber"],
    ["1.1.01.001", "2025-01-05", "100.00", "0"],
    ["4.1.01.001", "2025-01-05", "0", "100.00"],
    ["1.1.02.001", "2025-02-10", "250.50", "0"],
]

# Sinónimo-frase ("Movimiento Deudor"/"Movimiento Acreedor") → pista débil → cola.
MAYOR_FRASE = [
    ["Cuenta", "Fecha", "Movimiento Deudor", "Movimiento Acreedor"],
    ["1.1.01.001", "2025-01-05", "100.00", "0"],
    ["4.1.01.001", "2025-01-05", "0", "100.00"],
]

# Un obligatorio (haber) con celda vacía → M22: None, nunca cero.
MAYOR_VACIO = [
    ["Cuenta", "Fecha", "Debe", "Haber"],
    ["1.1.01.001", "2025-01-05", "100.00", ""],
]


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ingesta_api.router)
    app.dependency_overrides[require_runner_access] = lambda: None
    return TestClient(app)


def _files(contenido: bytes, nombre="mayor.xlsx"):
    return {"file": (nombre, contenido,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}


# --------------------------------------------------------------------------- #
#  /mapeo/preparar                                                             #
# --------------------------------------------------------------------------- #
class TestPreparar:
    def test_propuesta_high_sin_cola(self, client):
        r = client.post("/ingesta/mapeo/preparar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "mayor"})
        assert r.status_code == 200
        body = r.json()
        assert body["perfil"]["fila_encabezado"] == 0
        assert body["propuesta"]["tipo_documento"] == "mayor"
        assert body["propuesta"]["review_required"] is False
        assert body["cola_revision"] == []
        # El esquema expone TODOS los campos canónicos (para poblar dropdowns).
        nombres = {c["nombre"] for c in body["esquema"]}
        assert {"cuenta", "fecha", "debe", "haber"} <= nombres
        # Debe/Haber se proponen HIGH (sinónimo de una palabra).
        prop = {p["campo_canonico"]: p for p in body["propuesta"]["propuestas"]}
        assert prop["debe"]["confianza"] == "HIGH"

    def test_frase_sinonima_va_a_la_cola(self, client):
        r = client.post("/ingesta/mapeo/preparar",
                        files=_files(_xlsx(MAYOR_FRASE)),
                        data={"tipo_documento": "mayor"})
        assert r.status_code == 200
        body = r.json()
        assert body["propuesta"]["review_required"] is True
        campos_en_cola = {i["field"] for i in body["cola_revision"]}
        assert "debe" in campos_en_cola and "haber" in campos_en_cola

    def test_tipo_invalido_400(self, client):
        r = client.post("/ingesta/mapeo/preparar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "f103"})
        assert r.status_code == 400

    def test_tipo_ausente_400(self, client):
        r = client.post("/ingesta/mapeo/preparar", files=_files(_xlsx(MAYOR_OK)))
        assert r.status_code == 400


# --------------------------------------------------------------------------- #
#  /mapeo/aplicar                                                              #
# --------------------------------------------------------------------------- #
class TestAplicar:
    def _preparar(self, client, filas, tipo="mayor"):
        r = client.post("/ingesta/mapeo/preparar",
                        files=_files(_xlsx(filas)), data={"tipo_documento": tipo})
        assert r.status_code == 200
        return r.json()

    def test_aplicar_mapeo_confirmado(self, client):
        prep = self._preparar(client, MAYOR_OK)
        confirmado = {p["campo_canonico"]: p["columna_indice"]
                      for p in prep["propuesta"]["propuestas"]}
        r = client.post("/ingesta/mapeo/aplicar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "mayor",
                              "mapeo_confirmado": json.dumps(confirmado)})
        assert r.status_code == 200
        body = r.json()
        ds = body["dataset"]
        assert ds["document_type"] == "mayor"
        assert ds["sello"]["sha256"]
        assert ds["row_count"] == 3
        assert float(ds["rows"][0]["debe"]) == 100.0
        assert body["cola_revision"] == []

    def test_m22_celda_vacia_no_asume_cero(self, client):
        confirmado = {"cuenta": 0, "fecha": 1, "debe": 2, "haber": 3}
        r = client.post("/ingesta/mapeo/aplicar",
                        files=_files(_xlsx(MAYOR_VACIO)),
                        data={"tipo_documento": "mayor",
                              "mapeo_confirmado": json.dumps(confirmado)})
        assert r.status_code == 200
        body = r.json()
        # M22: el obligatorio vacío queda None (NUNCA 0) y va a revisión.
        assert body["dataset"]["rows"][0]["haber"] is None
        assert any(i["field"] == "haber" for i in body["cola_revision"]) or \
            body["dataset"]["review_required"] is True

    def test_json_invalido_400(self, client):
        r = client.post("/ingesta/mapeo/aplicar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "mayor", "mapeo_confirmado": "{no-json"})
        assert r.status_code == 400

    def test_campo_desconocido_400(self, client):
        r = client.post("/ingesta/mapeo/aplicar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "mayor",
                              "mapeo_confirmado": json.dumps({"inexistente": 0})})
        assert r.status_code == 400

    def test_indice_fuera_de_rango_400(self, client):
        r = client.post("/ingesta/mapeo/aplicar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "mayor",
                              "mapeo_confirmado": json.dumps({"debe": 99})})
        assert r.status_code == 400

    def test_mapeo_vacio_400(self, client):
        r = client.post("/ingesta/mapeo/aplicar",
                        files=_files(_xlsx(MAYOR_OK)),
                        data={"tipo_documento": "mayor", "mapeo_confirmado": "{}"})
        assert r.status_code == 400
