"""Resolución semántica por IA (Fase 6) expuesta como endpoint /ingesta/resolver.

App FastAPI mínima con el router de ingesta; se sobreescribe el acceso y se
monkeypatchean los extractores (para no depender de pdfplumber) y el proveedor
de chat compartido (para no salir a la red). Verifica que la IA solo toca el
TEXTO dudoso, con tope de confianza MEDIUM, y que si no hay nada que resolver
no llama al modelo.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_runner_access
from backend.app.ingesta import DatasetNormalizado, NivelConfianza, TipoDocumento
from backend.app.ingesta import orchestrator as orch
from backend.app.ingesta.contract import CampoExtraido, MetodoExtraccion, TipoDato
import backend.app.chat.providers as providers


def _cargar_router_ingesta():
    import backend
    raiz = pathlib.Path(backend.__file__).resolve().parent.parent
    ruta = raiz / "backend/app/api/ingesta.py"
    spec = importlib.util.spec_from_file_location("ingesta_api_resolver", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeResp:
    def __init__(self, content, model="fake-model"):
        self.content = content
        self.model = model


def _ds_texto_dudoso(contenido, filename):
    """Extractor fake: un campo de TEXTO en revisión (resoluble por IA)."""
    campo = CampoExtraido(
        document_id=filename, document_type=TipoDocumento.F103, field="descripcion",
        raw_value="hon. prof.", data_type=TipoDato.TEXTO,
        confidence=NivelConfianza.REVIEW_REQUIRED,
    )
    return DatasetNormalizado(dataset_id=filename, source_file=filename,
                             document_type=TipoDocumento.F103, campos=[campo])


def _ds_numerico(contenido, filename):
    """Extractor fake: un campo MONEDA confiable (NO resoluble por IA)."""
    campo = CampoExtraido(
        document_id=filename, document_type=TipoDocumento.F104, field="cas_411",
        normalized_value=None, data_type=TipoDato.MONEDA, confidence=NivelConfianza.HIGH,
    )
    return DatasetNormalizado(dataset_id=filename, source_file=filename,
                             document_type=TipoDocumento.F104, campos=[campo])


@pytest.fixture
def client():
    mod = _cargar_router_ingesta()
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[require_runner_access] = lambda: None
    return TestClient(app)


class TestResolver:
    def test_resuelve_texto_dudoso_con_ia(self, client, monkeypatch):
        monkeypatch.setattr(orch, "extractores_por_defecto",
                            lambda: {TipoDocumento.F103: _ds_texto_dudoso})

        def fake_chat(messages, system=None, **kw):
            return _FakeResp('{"valor": "Honorarios profesionales", "tipo": "texto", '
                             '"confianza": "alta", "razonamiento": "sigla expandida", '
                             '"requiere_revision_humana": false}')
        monkeypatch.setattr(providers, "chat_complete", fake_chat)

        r = client.post("/ingesta/resolver",
                        files={"file": ("f103.pdf", b"x", "application/pdf")},
                        data={"tipo_declarado": "f103"})
        assert r.status_code == 200
        body = r.json()
        assert body["resolubles"] == 1
        assert body["resueltos"] == 1
        campo = body["dataset"]["campos"][0]
        assert campo["extraction_method"] == "ia"
        assert campo["normalized_value"] == "Honorarios profesionales"
        # Tope MEDIUM: la IA nunca sube a HIGH automático.
        assert campo["confidence"] == "MEDIUM"

    def test_sin_texto_dudoso_no_llama_al_modelo(self, client, monkeypatch):
        monkeypatch.setattr(orch, "extractores_por_defecto",
                            lambda: {TipoDocumento.F104: _ds_numerico})

        def boom(*a, **k):
            raise AssertionError("no debió llamarse al modelo")
        monkeypatch.setattr(providers, "chat_complete", boom)

        r = client.post("/ingesta/resolver",
                        files={"file": ("f104.pdf", b"x", "application/pdf")},
                        data={"tipo_declarado": "f104"})
        assert r.status_code == 200
        body = r.json()
        assert body["resolubles"] == 0
        assert body["resueltos"] == 0

    def test_degrada_con_gracia_si_el_proveedor_cae(self, client, monkeypatch):
        monkeypatch.setattr(orch, "extractores_por_defecto",
                            lambda: {TipoDocumento.F103: _ds_texto_dudoso})

        def caido(*a, **k):
            raise RuntimeError("sin proveedor")
        monkeypatch.setattr(providers, "chat_complete", caido)

        r = client.post("/ingesta/resolver",
                        files={"file": ("f103.pdf", b"x", "application/pdf")},
                        data={"tipo_declarado": "f103"})
        assert r.status_code == 200
        body = r.json()
        assert body["resolubles"] == 1
        assert body["resueltos"] == 0  # no se resolvió, pero no crashea
        campo = body["dataset"]["campos"][0]
        assert any("no disponible" in w for w in campo["warnings"])

    def test_archivo_vacio_rechazado(self, client):
        r = client.post("/ingesta/resolver",
                        files={"file": ("f103.pdf", b"", "application/pdf")})
        assert r.status_code == 400
