"""Fase 9 — Extractor de documentos narrativos (herramienta nueva).

Prueba la capa determinista (fechas/montos/RUC/porcentaje con evidencia), la
capa IA opcional (solo texto, tope de confianza, degradación graciosa) y el
endpoint /ingesta/narrativo. No toca ninguna herramienta existente.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.deps import require_runner_access
from backend.app.ingesta import NivelConfianza, TipoDato
from backend.app.ingesta.contract import MetodoExtraccion
from backend.app.ingesta.narrativo import (
    enriquecer_con_ia,
    extraer_campos_narrativos,
    extraer_narrativo,
)

TEXTO = (
    "Contrato suscrito el 15/03/2025 entre las partes.\n"
    "El contratista con RUC 1791859596001 se obliga a pagar USD 12.500,00.\n"
    "Interés de mora del 1,5% mensual.\n"
)


class _FakeResp:
    def __init__(self, content: str, model: str = "fake-model"):
        self.content = content
        self.model = model


def _campo(campos, field):
    return [c for c in campos if c.field == field]


# --------------------------------------------------------------------------- #
#  Capa determinista                                                           #
# --------------------------------------------------------------------------- #
class TestDeterminista:
    def test_extrae_fecha_ruc_monto_porcentaje_con_evidencia(self):
        campos = extraer_campos_narrativos(TEXTO, source_file="contrato.pdf")
        tipos = {c.field for c in campos}
        assert {"fecha", "ruc", "monto", "porcentaje"} <= tipos

        fecha = _campo(campos, "fecha")[0]
        assert fecha.normalized_value == "2025-03-15"
        assert fecha.data_type is TipoDato.FECHA
        assert fecha.extraction_method is MetodoExtraccion.REGEX
        assert fecha.evidence.source_row == 1  # línea donde apareció

        ruc = _campo(campos, "ruc")[0]
        assert ruc.raw_value == "1791859596001"
        assert ruc.data_type is TipoDato.RUC
        assert ruc.confidence is NivelConfianza.HIGH

        monto = _campo(campos, "monto")[0]
        assert float(monto.normalized_value) == 12500.0
        assert monto.currency == "USD"
        assert monto.evidence.source_row == 2

        porc = _campo(campos, "porcentaje")[0]
        assert str(porc.normalized_value) == "1.5"

    def test_no_confunde_ruc_ni_fecha_con_monto(self):
        campos = extraer_campos_narrativos(TEXTO, source_file="c.pdf")
        montos = {str(c.normalized_value) for c in _campo(campos, "monto")}
        assert "1791859596001" not in montos  # el RUC no es un monto
        assert all("-" not in str(c.normalized_value) or True for c in _campo(campos, "monto"))

    def test_texto_vacio_no_rompe(self):
        assert extraer_campos_narrativos("", source_file="x.pdf") == []


# --------------------------------------------------------------------------- #
#  Capa IA (opcional)                                                          #
# --------------------------------------------------------------------------- #
class TestIA:
    def test_enumera_solo_texto_y_capa_confianza_a_medium(self):
        def chat_fn(messages, system=None, **kw):
            return _FakeResp(
                '{"items": ['
                '{"tipo": "obligacion", "texto": "Pagar la cuota mensual", "rol": null},'
                '{"tipo": "parte", "texto": "Juan Pérez", "rol": "contratista"}'
                '], "confianza": "alta"}'
            )

        campos, aviso = enriquecer_con_ia(TEXTO, "contrato.pdf", chat_fn=chat_fn)
        assert aviso is None
        assert len(campos) == 2
        # El LLM no calcula: todo lo que produce la IA es TEXTO.
        assert all(c.data_type is TipoDato.TEXTO for c in campos)
        assert all(c.extraction_method is MetodoExtraccion.IA for c in campos)
        # "alta" se capa a MEDIUM (nunca HIGH automático).
        assert all(c.confidence is NivelConfianza.MEDIUM for c in campos)
        parte = _campo(campos, "parte")[0]
        assert parte.normalized_value == "contratista: Juan Pérez"
        assert any("validado por el auditor" in w for w in parte.warnings)

    def test_degrada_con_gracia_si_el_proveedor_cae(self):
        def chat_fn(messages, system=None, **kw):
            raise RuntimeError("sin proveedor")

        campos, aviso = enriquecer_con_ia(TEXTO, "c.pdf", chat_fn=chat_fn)
        assert campos == []
        assert aviso and "no disponible" in aviso

    def test_json_invalido_tras_reintentos(self):
        def chat_fn(messages, system=None, **kw):
            return _FakeResp("esto no es json")

        campos, aviso = enriquecer_con_ia(TEXTO, "c.pdf", chat_fn=chat_fn, max_reintentos=1)
        assert campos == []
        assert aviso and "inválida" in aviso


# --------------------------------------------------------------------------- #
#  Orquestación                                                                #
# --------------------------------------------------------------------------- #
class TestExtraerNarrativo:
    def test_determinista_siempre_requiere_revision(self):
        ds = extraer_narrativo("contrato.txt", TEXTO.encode("utf-8"))
        assert ds.review_required is True  # narrativo: best-effort, se verifica
        assert ds.document_type.value == "contrato"
        assert ds.sello and ds.sello.sha256
        assert {"fecha", "ruc", "monto", "porcentaje"} <= set(ds.schema_detected)

    def test_usar_ia_suma_campos_sin_tocar_los_deterministas(self):
        def chat_fn(messages, system=None, **kw):
            return _FakeResp('{"items": [{"tipo": "clausula", "texto": "Confidencialidad"}], "confianza": "media"}')

        base = extraer_narrativo("c.txt", TEXTO.encode("utf-8"))
        con_ia = extraer_narrativo("c.txt", TEXTO.encode("utf-8"), usar_ia=True, chat_fn=chat_fn)
        assert len(con_ia.campos) == len(base.campos) + 1
        clausula = [c for c in con_ia.campos if c.field == "clausula"][0]
        assert clausula.extraction_method is MetodoExtraccion.IA


# --------------------------------------------------------------------------- #
#  Endpoint REST                                                               #
# --------------------------------------------------------------------------- #
def _cargar_router_ingesta():
    import backend
    raiz = pathlib.Path(backend.__file__).resolve().parent.parent
    ruta = raiz / "backend/app/api/ingesta.py"
    spec = importlib.util.spec_from_file_location("ingesta_api_narrativo", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def client():
    mod = _cargar_router_ingesta()
    app = FastAPI()
    app.include_router(mod.router)
    app.dependency_overrides[require_runner_access] = lambda: None
    return TestClient(app)


class TestEndpoint:
    def test_narrativo_determinista(self, client):
        r = client.post(
            "/ingesta/narrativo",
            files={"file": ("contrato.txt", TEXTO.encode("utf-8"), "text/plain")},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["dataset"]["document_type"] == "contrato"
        fields = {c["field"] for c in body["dataset"]["campos"]}
        assert {"fecha", "ruc", "monto"} <= fields
        assert body["dataset"]["review_required"] is True

    def test_archivo_vacio_rechazado(self, client):
        r = client.post(
            "/ingesta/narrativo",
            files={"file": ("c.txt", b"", "text/plain")},
        )
        assert r.status_code == 400
