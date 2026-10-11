"""Endpoint del Validador de coherencia SRI (portal cliente, Fase 9).

Monta una app FastAPI mínima solo con el router del validador (sin DB ni
conftest pesado) y sobreescribe la dependencia de acceso del cliente. Los
extractores del motor se monkeypatchean para no depender de pdfplumber: el
contenido del archivo lleva una spec "cas=valor;..." que el fake parsea.
"""
from __future__ import annotations

import importlib.util
import pathlib
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_client_with_device
from backend.app.ingesta import DatasetNormalizado, TipoDocumento
from backend.app.ingesta import orchestrator as orch
from backend.app.ingesta.contract import CampoExtraido


def _cargar_router():
    """Carga client_portal/validador_sri.py SIN disparar backend.app.api.__init__."""
    import backend
    raiz = pathlib.Path(backend.__file__).resolve().parent.parent
    ruta = raiz / "backend/app/client_portal/validador_sri.py"
    spec = importlib.util.spec_from_file_location("validador_sri_standalone", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _spec(contenido: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    for par in contenido.decode("utf-8", "ignore").split(";"):
        if "=" in par:
            k, v = par.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _mk(tipo, contenido, filename):
    cas = _spec(contenido)
    campos = [
        CampoExtraido(document_id=filename, document_type=tipo, field=f"cas_{n}",
                      raw_value=v, normalized_value=Decimal(v))
        for n, v in cas.items()
    ]
    return DatasetNormalizado(dataset_id=filename, source_file=filename,
                              document_type=tipo, campos=campos)


@pytest.fixture(autouse=True)
def _registro_fake(monkeypatch):
    monkeypatch.setattr(orch, "extractores_por_defecto", lambda: {
        TipoDocumento.F101: lambda c, f: _mk(TipoDocumento.F101, c, f),
        TipoDocumento.F103: lambda c, f: _mk(TipoDocumento.F103, c, f),
        TipoDocumento.F104: lambda c, f: _mk(TipoDocumento.F104, c, f),
    })


@pytest.fixture
def client():
    mod = _cargar_router()
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[require_client_with_device] = lambda: None
    return TestClient(app)


def _f104_files(valor_mensual: str, meses: int):
    return [("f104", (f"F104_{m:02d}.pdf", f"411={valor_mensual}".encode(), "application/pdf"))
            for m in range(1, meses + 1)]


def _f103_files(meses: int):
    return [("f103", (f"F103_{m:02d}.pdf", b"402=0;433=0", "application/pdf"))
            for m in range(1, meses + 1)]


class TestEndpoint:
    def test_cuadra(self, client):
        files = [("f101", ("F101.pdf", b"6001=100000;6005=50000", "application/pdf"))]
        files += _f104_files("12500", 12)  # Σ411 = 150000 = ventas IR
        files += _f103_files(12)           # 12 meses, sin pagos al exterior
        r = client.post("/client/validador-sri/coherencia", files=files)
        assert r.status_code == 200
        body = r.json()
        assert body["f101"] == 1 and body["f104"] == 12 and body["f103"] == 12
        ch = {c["codigo"]: c for c in body["chequeos"]}
        assert ch["VENTAS_IR_IVA"]["estado"] == "ok"
        assert ch["F104_COMPLETO"]["estado"] == "ok"
        assert ch["F103_COMPLETO"]["estado"] == "ok"
        assert ch["PAGOS_EXTERIOR"]["estado"] == "ok"
        assert body["review_required"] is False

    def test_diferencia_y_faltan_meses(self, client):
        files = [("f101", ("F101.pdf", b"6001=100000;6005=50000", "application/pdf"))]
        files += _f104_files("12000", 6)  # Σ = 72000 ≠ 150000, y solo 6 meses
        r = client.post("/client/validador-sri/coherencia", files=files)
        assert r.status_code == 200
        body = r.json()
        ch = {c["codigo"]: c for c in body["chequeos"]}
        assert ch["VENTAS_IR_IVA"]["estado"] == "diferencia"
        assert ch["F104_COMPLETO"]["estado"] == "faltante"
        assert body["review_required"] is True

    def test_f101_obligatorio(self, client):
        # sin f101 → 422 (File(...) requerido)
        r = client.post("/client/validador-sri/coherencia", files=_f104_files("1", 1))
        assert r.status_code == 422

    def test_archivo_vacio_rechazado(self, client):
        files = [("f101", ("F101.pdf", b"", "application/pdf"))]
        r = client.post("/client/validador-sri/coherencia", files=files)
        assert r.status_code == 400

    def test_tope_mensuales(self, client):
        files = [("f101", ("F101.pdf", b"6001=1;6005=0", "application/pdf"))]
        files += _f104_files("1", 12) + [("f104", ("extra.pdf", b"411=1", "application/pdf"))]
        r = client.post("/client/validador-sri/coherencia", files=files)
        assert r.status_code == 400
