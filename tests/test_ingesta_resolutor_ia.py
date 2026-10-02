"""Fase 6 del Motor de Ingesta: AI Semantic Resolver.

Se prueba con una función de chat FALSA (imita chat.providers.chat_complete): sin
red ni proveedor real. Verifica que la IA solo actúe sobre texto ambiguo (nunca
cifras), que no suba la confianza a HIGH y que degrade con gracia.
"""
from __future__ import annotations

import json
from decimal import Decimal

from backend.app.ingesta import (
    CampoExtraido,
    DatasetNormalizado,
    MetodoExtraccion,
    NivelConfianza,
    ResolucionSemantica,
    TipoDato,
    TipoDocumento,
    resoluble,
    resolver_campo,
    resolver_dataset,
)


class _Resp:
    def __init__(self, content, model="modelo-falso"):
        self.content = content
        self.model = model
        self.tokens_in = None
        self.tokens_out = None


def _chat(payload: dict, model="modelo-falso"):
    def chat(messages, system=None, **kw):
        return _Resp(json.dumps(payload), model=model)
    return chat


def _campo_texto(review=True, raw="Vta. loc.", tipo=TipoDato.TEXTO):
    return CampoExtraido(
        document_id="d", field="concepto", raw_value=raw, data_type=tipo,
        confidence=NivelConfianza.REVIEW_REQUIRED if review else NivelConfianza.HIGH,
    )


# --------------------------------------------------------------------------- #
#  resoluble                                                                   #
# --------------------------------------------------------------------------- #
class TestResoluble:
    def test_texto_en_revision_es_resoluble(self):
        assert resoluble(_campo_texto()) is True

    def test_texto_confiable_no_es_resoluble(self):
        assert resoluble(_campo_texto(review=False)) is False

    def test_moneda_no_es_resoluble(self):
        c = CampoExtraido(document_id="d", field="m", data_type=TipoDato.MONEDA,
                          confidence=NivelConfianza.REVIEW_REQUIRED)
        assert resoluble(c) is False

    def test_fecha_no_es_resoluble(self):
        c = CampoExtraido(document_id="d", field="f", data_type=TipoDato.FECHA,
                          confidence=NivelConfianza.REVIEW_REQUIRED)
        assert resoluble(c) is False


# --------------------------------------------------------------------------- #
#  resolver_campo                                                              #
# --------------------------------------------------------------------------- #
class TestResolverCampo:
    def test_resuelve_texto_ambiguo(self):
        chat = _chat({"valor": "Ventas locales", "tipo": "texto",
                      "confianza": "alta", "razonamiento": "abreviatura común",
                      "requiere_revision_humana": False})
        c = resolver_campo(_campo_texto(), chat_fn=chat)
        assert c.normalized_value == "Ventas locales"
        assert c.extraction_method is MetodoExtraccion.IA
        # confianza "alta" del modelo se capa a MEDIUM (nunca HIGH automático)
        assert c.confidence is NivelConfianza.MEDIUM
        assert c.review_required is False
        assert any("resuelto por IA" in w for w in c.warnings)

    def test_confianza_nunca_sube_a_high(self):
        chat = _chat({"valor": "X", "tipo": "texto", "confianza": "alta",
                      "razonamiento": "", "requiere_revision_humana": False})
        c = resolver_campo(_campo_texto(), chat_fn=chat)
        assert c.confidence is not NivelConfianza.HIGH

    def test_modelo_inseguro_queda_en_revision(self):
        chat = _chat({"valor": "quizá ventas", "tipo": "texto", "confianza": "baja",
                      "razonamiento": "ambiguo", "requiere_revision_humana": True})
        c = resolver_campo(_campo_texto(), chat_fn=chat)
        assert c.confidence is NivelConfianza.REVIEW_REQUIRED
        assert c.review_required is True

    def test_no_toca_campo_no_resoluble(self):
        c = CampoExtraido(document_id="d", field="m", raw_value="100",
                          data_type=TipoDato.MONEDA,
                          confidence=NivelConfianza.REVIEW_REQUIRED)
        antes = c.model_copy(deep=True)
        out = resolver_campo(c, chat_fn=_chat({"valor": "9999", "confianza": "alta",
                                               "razonamiento": "", "requiere_revision_humana": False}))
        # No llamó al modelo ni cambió nada (el LLM no calcula cifras).
        assert out.normalized_value == antes.normalized_value
        assert out.extraction_method is antes.extraction_method

    def test_json_invalido_degrada_con_gracia(self):
        def chat(messages, system=None, **kw):
            return _Resp("esto no es json")
        c = resolver_campo(_campo_texto(), chat_fn=chat)
        assert c.extraction_method is not MetodoExtraccion.IA  # no se aplicó
        assert any("salida inválida" in w for w in c.warnings)

    def test_proveedor_caido_no_lanza(self):
        def chat(messages, system=None, **kw):
            raise RuntimeError("sin proveedor")
        c = resolver_campo(_campo_texto(), chat_fn=chat)
        assert any("no disponible" in w for w in c.warnings)
        assert c.review_required is True

    def test_acepta_json_con_cercos_markdown(self):
        payload = {"valor": "Ventas locales", "tipo": "texto", "confianza": "media",
                   "razonamiento": "ok", "requiere_revision_humana": False}
        def chat(messages, system=None, **kw):
            return _Resp("```json\n" + json.dumps(payload) + "\n```")
        c = resolver_campo(_campo_texto(), chat_fn=chat)
        assert c.normalized_value == "Ventas locales"


# --------------------------------------------------------------------------- #
#  resolver_dataset                                                           #
# --------------------------------------------------------------------------- #
class TestResolverDataset:
    def test_resuelve_solo_los_de_texto_dudosos(self):
        chat = _chat({"valor": "Ventas locales", "tipo": "texto", "confianza": "media",
                      "razonamiento": "ok", "requiere_revision_humana": False})
        ds = DatasetNormalizado(
            dataset_id="ds", source_file="f.pdf", document_type=TipoDocumento.F103,
            campos=[
                _campo_texto(),  # texto dudoso → se resuelve
                CampoExtraido(document_id="d", field="cas_302",
                              normalized_value=Decimal("100"), data_type=TipoDato.MONEDA,
                              confidence=NivelConfianza.REVIEW_REQUIRED),  # moneda → intacto
            ],
        )
        resolver_dataset(ds, chat_fn=chat)
        texto, moneda = ds.campos
        assert texto.extraction_method is MetodoExtraccion.IA
        assert moneda.extraction_method is not MetodoExtraccion.IA
        assert moneda.normalized_value == Decimal("100")


def test_esquema_resolucion_rechaza_confianza_invalida():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        ResolucionSemantica(confianza="altisima")
