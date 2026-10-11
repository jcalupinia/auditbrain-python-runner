"""Cierre de huecos del grupo Motor de Datos y Evidencia (BLOQUE 1).

Contiene:
- Regresión del bug del adaptador ATS (`adapters.py::extraer_ats`): antes leía la
  clave `compras` que `parse_ats` nunca produce → el dataset ATS salía con 0 filas.
- Pruebas de MUTACIÓN (M20) **rotuladas** para los motores que no tenían una:
  umbrales de `confidence.py`, el tope de confianza del extractor narrativo y del
  resolutor semántico, y la restricción «la IA no toca cifras». Cada mutación debe
  **cambiar el veredicto**; si no lo cambia, el control no está realmente puesto.

Datos ficticios (M14/M35): ningún dato real de cliente entra al repo.
"""
from __future__ import annotations

import pytest

from backend.app.ingesta import confidence
from backend.app.ingesta.confidence import NivelConfianza, clasificar_confianza
from backend.app.ingesta.contract import TipoDato


# --------------------------------------------------------------------------- #
#  Regresión — bug del adaptador ATS (Hueco/bug detectado en la verificación)  #
# --------------------------------------------------------------------------- #
_ATS_XML = (
    b"<ats><IdInformante>1790012345001</IdInformante>"
    b"<razonSocial>EMPRESA FICTICIA SA</razonSocial>"
    b"<Anio>2025</Anio><Mes>03</Mes>"
    b"<pagoExterior><pagoLocExt>02</pagoLocExt><tipoRegi>01</tipoRegi>"
    b"<paisEfecPago>249</paisEfecPago></pagoExterior>"
    b"</ats>"
)


class TestRegresionAts:
    def test_extraer_ats_lee_pagos_exterior_no_cero_filas(self):
        from backend.app.ingesta.adapters import extraer_ats

        ds = extraer_ats(_ATS_XML, "ats_marzo.xml")
        # Antes del fix: row_count == 0 (leía la clave inexistente "compras").
        assert ds.row_count == 1, "el adaptador ATS debe trasladar los pagos al exterior"
        assert "pago_loc_ext" in ds.rows[0]
        # El metadato de cabecera sigue presente como campo.
        assert any(c.field == "ruc_informante" for c in ds.campos)

    def test_ats_vacio_no_rompe(self):
        from backend.app.ingesta.adapters import extraer_ats

        ds = extraer_ats(b"<ats></ats>", "vacio.xml")
        assert ds.row_count == 0  # sin pagos al exterior, pero sin reventar


# --------------------------------------------------------------------------- #
#  M20 — umbrales de confidence.py                                             #
# --------------------------------------------------------------------------- #
class TestMutacionConfianzaM20:
    def test_umbral_alta_importa(self, monkeypatch):
        # Línea base: 0.90 es HIGH con el umbral vigente (0.90).
        assert clasificar_confianza(0.90) is NivelConfianza.HIGH
        # MUTACIÓN: subir UMBRAL_ALTA por encima de 0.90 debe degradar ese score.
        monkeypatch.setattr(confidence, "UMBRAL_ALTA", 0.95)
        assert clasificar_confianza(0.90) is not NivelConfianza.HIGH

    def test_umbral_media_importa(self, monkeypatch):
        assert clasificar_confianza(0.70) is NivelConfianza.MEDIUM
        monkeypatch.setattr(confidence, "UMBRAL_MEDIA", 0.80)
        assert clasificar_confianza(0.70) is not NivelConfianza.MEDIUM


# --------------------------------------------------------------------------- #
#  M20 — extractor narrativo                                                   #
# --------------------------------------------------------------------------- #
_TEXTO = (
    "Contrato del 15/03/2025 con RUC 1791859596001 por USD 12.500,00.\n"
    "Interés de mora del 1,5% mensual.\n"
)


class TestMutacionNarrativoM20:
    def test_tope_confianza_ia_es_medium(self):
        from backend.app.ingesta.narrativo import enriquecer_con_ia

        class _Resp:
            content = '{"items": [{"tipo": "parte", "texto": "Juan", "rol": null}], "confianza": "alta"}'
            model = "fake"

        campos, _ = enriquecer_con_ia(_TEXTO, "c.pdf", chat_fn=lambda *a, **k: _Resp())
        # Línea base: "alta" se capa a MEDIUM (la IA nunca sube a HIGH automático).
        assert campos and all(c.confidence is NivelConfianza.MEDIUM for c in campos)

    def test_mutacion_tope_ia_rompe(self, monkeypatch):
        from backend.app.ingesta import narrativo

        class _Resp:
            content = '{"items": [{"tipo": "parte", "texto": "Juan", "rol": null}], "confianza": "alta"}'
            model = "fake"

        # MUTACIÓN: si "alta" dejara de caparse a MEDIUM (p.ej. subiera a HIGH),
        # la salida ya NO sería MEDIUM. Prueba de que el tope está puesto.
        mut = dict(narrativo._IA_MAP_CONFIANZA)
        mut["alta"] = NivelConfianza.HIGH
        monkeypatch.setattr(narrativo, "_IA_MAP_CONFIANZA", mut)
        campos, _ = narrativo.enriquecer_con_ia(_TEXTO, "c.pdf", chat_fn=lambda *a, **k: _Resp())
        assert campos and all(c.confidence is NivelConfianza.HIGH for c in campos)

    def test_mutacion_umbral_afecta_al_ruc_determinista(self, monkeypatch):
        from backend.app.ingesta.narrativo import extraer_campos_narrativos

        base = [c for c in extraer_campos_narrativos(_TEXTO, source_file="c.pdf") if c.field == "ruc"][0]
        assert base.confidence is NivelConfianza.HIGH  # RUC score 0.92 >= 0.90
        # MUTACIÓN del umbral: el mismo RUC deja de ser HIGH.
        monkeypatch.setattr(confidence, "UMBRAL_ALTA", 0.95)
        mut = [c for c in extraer_campos_narrativos(_TEXTO, source_file="c.pdf") if c.field == "ruc"][0]
        assert mut.confidence is not NivelConfianza.HIGH


# --------------------------------------------------------------------------- #
#  M20 — resolutor semántico                                                   #
# --------------------------------------------------------------------------- #
class TestMutacionResolutorM20:
    def _campo_texto_dudoso(self):
        from backend.app.ingesta.contract import CampoExtraido, MetodoExtraccion

        return CampoExtraido(
            document_id="d", field="concepto", raw_value="SFE",
            data_type=TipoDato.TEXTO, confidence=NivelConfianza.REVIEW_REQUIRED,
            extraction_method=MetodoExtraccion.REGEX, review_required=True,
        )

    def test_tope_confianza_resolutor_es_medium(self):
        from backend.app.ingesta.semantic_resolver import resolver_campo

        class _Resp:
            content = '{"valor": "Servicio Financiero Externo", "tipo": "texto", "confianza": "alta", "razonamiento": "x", "requiere_revision_humana": false}'
            model = "fake"

        c = resolver_campo(self._campo_texto_dudoso(), chat_fn=lambda *a, **k: _Resp())
        assert c.confidence is NivelConfianza.MEDIUM  # "alta" se capa a MEDIUM

    def test_mutacion_tope_resolutor_rompe(self, monkeypatch):
        from backend.app.ingesta import semantic_resolver as sr

        class _Resp:
            content = '{"valor": "X", "tipo": "texto", "confianza": "alta", "razonamiento": "x", "requiere_revision_humana": false}'
            model = "fake"

        mut = dict(sr._MAP_CONFIANZA)
        mut["alta"] = NivelConfianza.HIGH
        monkeypatch.setattr(sr, "_MAP_CONFIANZA", mut)
        c = sr.resolver_campo(self._campo_texto_dudoso(), chat_fn=lambda *a, **k: _Resp())
        assert c.confidence is NivelConfianza.HIGH

    def test_mutacion_resoluble_tipos_la_ia_no_toca_cifras(self, monkeypatch):
        from backend.app.ingesta import semantic_resolver as sr
        from backend.app.ingesta.contract import CampoExtraido, MetodoExtraccion

        monto = CampoExtraido(
            document_id="d", field="monto", raw_value="100",
            data_type=TipoDato.MONEDA, confidence=NivelConfianza.REVIEW_REQUIRED,
            extraction_method=MetodoExtraccion.REGEX, review_required=True,
        )
        # Línea base: un monto NO es resoluble por IA (la IA no calcula cifras).
        assert sr.resoluble(monto) is False
        # MUTACIÓN: si se permitiera MONEDA entre los tipos resolubles, pasaría a True
        # → la prueba demuestra que la restricción es la que impide que la IA toque cifras.
        monkeypatch.setattr(sr, "_RESOLUBLE_TIPOS", frozenset({TipoDato.TEXTO, TipoDato.MONEDA}))
        assert sr.resoluble(monto) is True


# --------------------------------------------------------------------------- #
#  Hueco 2 — hook `ingerir_o_pendiente` enganchado al pipeline                 #
# --------------------------------------------------------------------------- #
class TestHookPendienteDeMapeo:
    def _ds(self, *, con_datos: bool):
        from backend.app.ingesta.contract import CampoExtraido, DatasetNormalizado, TipoDocumento

        campos = []
        if con_datos:
            campos = [CampoExtraido(document_id="d", field="cas_1", confidence=NivelConfianza.HIGH)]
        return DatasetNormalizado(
            dataset_id="d", source_file="d", document_type=TipoDocumento.DESCONOCIDO, campos=campos,
        )

    def test_camino_feliz_intacto(self):
        from backend.app.ingesta.mapeo import PENDIENTE_DE_MAPEO, ingerir_o_pendiente

        ds = ingerir_o_pendiente("x.pdf", b"...", ingerir_fn=lambda *a, **k: self._ds(con_datos=True))
        assert PENDIENTE_DE_MAPEO not in ds.warnings  # no se reencauza si hay datos

    def test_dataset_vacio_se_marca_pendiente(self):
        from backend.app.ingesta.mapeo import PENDIENTE_DE_MAPEO, ingerir_o_pendiente

        ds = ingerir_o_pendiente("x.pdf", b"...", ingerir_fn=lambda *a, **k: self._ds(con_datos=False))
        assert ds.review_required is True
        assert PENDIENTE_DE_MAPEO in ds.warnings

    def test_reenvia_parametros_a_la_ingesta(self):
        from backend.app.ingesta.mapeo import ingerir_o_pendiente

        visto = {}

        def fake(filename, contenido, *, tipo_declarado=None, **kw):
            visto.update(kw)
            return self._ds(con_datos=True)

        ingerir_o_pendiente("x.pdf", b"...", ingerir_fn=fake, ocr=False, consolidar=False)
        assert visto == {"ocr": False, "consolidar": False}
