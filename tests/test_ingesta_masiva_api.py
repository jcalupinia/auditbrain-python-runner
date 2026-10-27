"""Pruebas aisladas de API masiva: sin SharePoint ni base productiva."""
import csv
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.ingesta.masiva_router import router


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("INGESTA_MASIVA_SQLITE_PATH", str(tmp_path / "ingesta.sqlite"))
    app = FastAPI()
    app.include_router(router, prefix="/ingesta")
    return TestClient(app)


def _cargar(client, n=7):
    import io
    buffer = io.StringIO()
    w = csv.writer(buffer)
    w.writerow(["cuenta", "fecha", "debe", "haber"])
    for i in range(n):
        w.writerow(["110101", "2026-10-26", "1.25", "0.25"])
    return client.post("/ingesta/masiva/cargar",
        files={"file": ("mayor.csv", buffer.getvalue().encode(), "text/csv")},
        data={"cliente_id": "clienteA", "encargo_id": "2026", "periodo": "2026",
              "tipo_documento": "mayor",
              "mapeo_confirmado": json.dumps({"cuenta": 0, "fecha": 1, "debe": 2, "haber": 3})})


def test_carga_paginada_y_aislamiento(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = _cargar(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_filas"] == 7
    assert body["filas_revision"] == 0
    ruta = "/ingesta/masiva/" + body["dataset_id"] + "/filas"
    ok = client.get(ruta, params={"cliente_id": "clienteA", "encargo_id": "2026", "limite": 3})
    assert ok.status_code == 200 and len(ok.json()["filas"]) == 3
    denied = client.get(ruta, params={"cliente_id": "otro", "encargo_id": "2026"})
    assert denied.status_code == 404


def test_desactivada_sin_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("INGESTA_MASIVA_SQLITE_PATH", raising=False)
    app = FastAPI()
    app.include_router(router, prefix="/ingesta")
    resp = TestClient(app).get("/ingesta/masiva/123/filas",
        params={"cliente_id": "a", "encargo_id": "b"})
    assert resp.status_code == 503


def test_rechaza_archivo_no_tabular(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/ingesta/masiva/cargar",
        files={"file": ("documento.pdf", b"PDF", "application/pdf")},
        data={"cliente_id": "a", "encargo_id": "b", "periodo": "2026",
              "tipo_documento": "mayor", "mapeo_confirmado": "{}"})
    assert r.status_code == 400
