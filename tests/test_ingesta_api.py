"""Fase 7 del Motor de Ingesta: API v1 y target del master_router.

Monta una app FastAPI mínima solo con el router de ingesta (sin DB ni conftest
pesado) y sobreescribe la dependencia de acceso. El registro de extractores se
monkeypatchea para no depender de pdfplumber/openpyxl.
"""
from __future__ import annotations

import asyncio
import base64
import importlib.util
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_runner_access
from backend.app.ingesta import DatasetNormalizado, NivelConfianza, TipoDocumento
from backend.app.ingesta import orchestrator as orch
from backend.app.ingesta.contract import CampoExtraido
from backend.app.router_engine import master_router


def _cargar_router_ingesta():
    """Carga backend/app/api/ingesta.py SIN disparar backend.app.api.__init__
    (que importaría toda la API: ICT, Forge, chat, etc.)."""
    import backend
    raiz = pathlib.Path(backend.__file__).resolve().parent.parent
    ruta = raiz / "backend/app/api/ingesta.py"
    spec = importlib.util.spec_from_file_location("ingesta_api_standalone", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ingesta_api = _cargar_router_ingesta()


def _fake_extractor(contenido: bytes, filename: str) -> DatasetNormalizado:
    return DatasetNormalizado(
        dataset_id=filename, source_file=filename, document_type=TipoDocumento.F103,
        quality_score=0.95,
        campos=[CampoExtraido(document_id=filename, field="cas_302",
                              confidence=NivelConfianza.HIGH)],
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(ingesta_api.router)
    app.dependency_overrides[require_runner_access] = lambda: None
    return TestClient(app)


@pytest.fixture(autouse=True)
def _registro_fake(monkeypatch):
    monkeypatch.setattr(
        orch, "extractores_por_defecto",
        lambda: {TipoDocumento.F103: _fake_extractor},
    )


# --------------------------------------------------------------------------- #
#  API REST                                                                    #
# --------------------------------------------------------------------------- #
class TestApi:
    def test_tipos(self, client):
        r = client.get("/ingesta/tipos")
        assert r.status_code == 200
        body = r.json()
        assert "f103" in body["tipos"] and "mayor" in body["tipos"]

    def test_clasificar(self, client):
        r = client.post(
            "/ingesta/clasificar",
            files={"file": ("F103_enero.pdf", b"contenido", "application/pdf")},
        )
        assert r.status_code == 200
        assert r.json()["tipo"] == "f103"

    def test_clasificar_tipo_declarado_manda(self, client):
        r = client.post(
            "/ingesta/clasificar",
            files={"file": ("x.bin", b"...", "application/octet-stream")},
            data={"tipo_declarado": "mayor"},
        )
        assert r.json()["tipo"] == "mayor"

    def test_ingerir(self, client):
        r = client.post(
            "/ingesta/ingerir",
            files={"file": ("f103.pdf", b"contenido", "application/pdf")},
            data={"tipo_declarado": "f103"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["dataset"]["document_type"] == "f103"
        assert body["dataset"]["sello"]["sha256"]
        # un campo HIGH, calidad alta ⇒ sin revisión ⇒ cola vacía
        assert body["cola_revision"] == []

    def test_archivo_vacio_rechazado(self, client):
        r = client.post(
            "/ingesta/ingerir",
            files={"file": ("f103.pdf", b"", "application/pdf")},
        )
        assert r.status_code == 400


# --------------------------------------------------------------------------- #
#  master_router: target ingestion_engine                                      #
# --------------------------------------------------------------------------- #
class TestMasterRouter:
    def test_ingestion_engine_es_operativo(self):
        assert "ingestion_engine" in master_router.OPERATIONAL_TARGETS
        assert "ingestion_engine" not in master_router.FUTURE_TARGETS

    def test_route_ingestion_engine(self):
        payload = {
            "target": "ingestion_engine",
            "payload": {
                "filename": "f103.pdf",
                "contenido_base64": base64.b64encode(b"contenido").decode(),
                "tipo_declarado": "f103",
            },
        }
        res = asyncio.run(master_router.route(payload))
        assert res["status"] == "ok"
        assert res["result"]["document_type"] == "f103"

    def test_route_base64_invalido(self):
        payload = {"target": "ingestion_engine",
                   "payload": {"filename": "f.pdf", "contenido_base64": "!!!no-b64"}}
        with pytest.raises(master_router.RouterError) as e:
            asyncio.run(master_router.route(payload))
        assert e.value.status_code == 400

    def test_route_sin_contenido(self):
        payload = {"target": "ingestion_engine", "payload": {"filename": "f.pdf"}}
        with pytest.raises(master_router.RouterError) as e:
            asyncio.run(master_router.route(payload))
        assert e.value.status_code == 400
