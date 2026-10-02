"""Fase 1 del Motor de Ingesta y Normalización: contrato de datos + confianza.

Verifica el esquema común de salida (CampoExtraido / DatasetNormalizado), el
motor de confianza (umbrales HIGH/MEDIUM/LOW/REVIEW_REQUIRED) y la huella de
trazabilidad SHA-256. Todo es aditivo: no toca ningún flujo existente.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from backend.app.ingesta import (
    CONTRATO_VERSION,
    CampoExtraido,
    DatasetNormalizado,
    Evidencia,
    MetodoExtraccion,
    NivelConfianza,
    ResultadoValidacion,
    TipoDato,
    TipoDocumento,
    clasificar_confianza,
    huella,
    requiere_revision,
)
from backend.app.ingesta.confidence import (
    UMBRAL_ALTA,
    UMBRAL_BAJA,
    UMBRAL_MEDIA,
)


# --------------------------------------------------------------------------- #
#  Confidence Engine                                                           #
# --------------------------------------------------------------------------- #
class TestConfianza:
    def test_umbrales_clasifican_cada_nivel(self):
        assert clasificar_confianza(0.99) is NivelConfianza.HIGH
        assert clasificar_confianza(UMBRAL_ALTA) is NivelConfianza.HIGH
        assert clasificar_confianza(0.80) is NivelConfianza.MEDIUM
        assert clasificar_confianza(UMBRAL_MEDIA) is NivelConfianza.MEDIUM
        assert clasificar_confianza(0.60) is NivelConfianza.LOW
        assert clasificar_confianza(UMBRAL_BAJA) is NivelConfianza.LOW
        assert clasificar_confianza(0.10) is NivelConfianza.REVIEW_REQUIRED
        assert clasificar_confianza(0.0) is NivelConfianza.REVIEW_REQUIRED

    def test_score_fuera_de_rango_se_acota(self):
        assert clasificar_confianza(1.5) is NivelConfianza.HIGH
        assert clasificar_confianza(-3.0) is NivelConfianza.REVIEW_REQUIRED

    def test_nan_va_a_revision(self):
        assert clasificar_confianza(float("nan")) is NivelConfianza.REVIEW_REQUIRED

    def test_requiere_revision(self):
        assert requiere_revision(NivelConfianza.LOW)
        assert requiere_revision(NivelConfianza.REVIEW_REQUIRED)
        assert not requiere_revision(NivelConfianza.HIGH)
        assert not requiere_revision(NivelConfianza.MEDIUM)


# --------------------------------------------------------------------------- #
#  CampoExtraido                                                               #
# --------------------------------------------------------------------------- #
class TestCampoExtraido:
    def test_campo_minimo_valido(self):
        c = CampoExtraido(document_id="doc1", field="cas_799")
        assert c.document_type is TipoDocumento.DESCONOCIDO
        # Default REVIEW_REQUIRED ⇒ review_required forzado a True.
        assert c.confidence is NivelConfianza.REVIEW_REQUIRED
        assert c.review_required is True

    def test_confianza_baja_fuerza_revision(self):
        c = CampoExtraido(
            document_id="doc1", field="x", confidence=NivelConfianza.LOW
        )
        assert c.review_required is True

    def test_confianza_alta_no_fuerza_revision(self):
        c = CampoExtraido(
            document_id="doc1", field="x", confidence=NivelConfianza.HIGH
        )
        assert c.review_required is False

    def test_score_deriva_nivel_mas_conservador(self):
        # Nivel HIGH pero score bajo ⇒ se degrada a LOW (nunca sube la confianza).
        c = CampoExtraido(
            document_id="doc1",
            field="x",
            confidence=NivelConfianza.HIGH,
            confidence_score=0.55,
        )
        assert c.confidence is NivelConfianza.LOW
        assert c.review_required is True

    def test_score_no_sube_confianza_ya_conservadora(self):
        # Nivel REVIEW pero score alto ⇒ se respeta el nivel conservador.
        c = CampoExtraido(
            document_id="doc1",
            field="x",
            confidence=NivelConfianza.REVIEW_REQUIRED,
            confidence_score=0.99,
        )
        assert c.confidence is NivelConfianza.REVIEW_REQUIRED

    def test_desde_score_constructor(self):
        c = CampoExtraido.desde_score(
            document_id="doc1",
            field="cas_799",
            score=0.95,
            raw_value="1,234.56",
            normalized_value=Decimal("1234.56"),
            data_type=TipoDato.MONEDA,
            currency="USD",
            extraction_method=MetodoExtraccion.PARSER,
            document_type=TipoDocumento.F104,
        )
        assert c.confidence is NivelConfianza.HIGH
        assert c.review_required is False
        assert c.normalized_value == Decimal("1234.56")

    def test_evidencia_hasta_el_origen(self):
        c = CampoExtraido(
            document_id="doc1",
            field="saldo",
            confidence=NivelConfianza.HIGH,
            evidence=Evidencia(
                source_file="mayor_2025.xlsx",
                source_sheet="Hoja1",
                source_row=42,
                source_cell="D42",
            ),
        )
        assert c.evidence.source_file == "mayor_2025.xlsx"
        assert c.evidence.source_row == 42

    def test_document_id_vacio_rechazado(self):
        with pytest.raises(ValidationError):
            CampoExtraido(document_id="", field="x")

    def test_field_vacio_rechazado(self):
        with pytest.raises(ValidationError):
            CampoExtraido(document_id="doc1", field="")

    def test_score_fuera_de_rango_rechazado(self):
        with pytest.raises(ValidationError):
            CampoExtraido(document_id="d", field="f", confidence_score=1.5)


# --------------------------------------------------------------------------- #
#  DatasetNormalizado                                                          #
# --------------------------------------------------------------------------- #
class TestDataset:
    def test_dataset_minimo(self):
        d = DatasetNormalizado(dataset_id="ds1", source_file="f.pdf")
        assert d.row_count == 0
        assert d.document_type is TipoDocumento.DESCONOCIDO

    def test_row_count_se_deriva_de_filas(self):
        d = DatasetNormalizado(
            dataset_id="ds1",
            source_file="f.csv",
            rows=[{"a": 1}, {"a": 2}, {"a": 3}],
        )
        assert d.row_count == 3

    def test_calidad_baja_fuerza_revision(self):
        d = DatasetNormalizado(
            dataset_id="ds1", source_file="f.csv", quality_score=0.4
        )
        assert d.review_required is True

    def test_calidad_alta_no_fuerza_revision(self):
        d = DatasetNormalizado(
            dataset_id="ds1", source_file="f.csv", quality_score=0.98
        )
        assert d.review_required is False

    def test_campo_dudoso_contagia_revision_al_dataset(self):
        d = DatasetNormalizado(
            dataset_id="ds1",
            source_file="f.csv",
            quality_score=0.99,
            campos=[
                CampoExtraido(
                    document_id="doc1", field="x", confidence=NivelConfianza.LOW
                )
            ],
        )
        assert d.review_required is True

    def test_validation_results_y_mapping(self):
        d = DatasetNormalizado(
            dataset_id="ds1",
            source_file="mayor.xlsx",
            document_type=TipoDocumento.MAYOR,
            schema_detected=["Codigo", "Debe", "Haber"],
            schema_normalized=["codigo", "debe", "haber"],
            mapping={"Codigo": "codigo", "Debe": "debe", "Haber": "haber"},
            validation_results=[
                ResultadoValidacion(regla="columnas_minimas", ok=True),
                ResultadoValidacion(
                    regla="cuadre", ok=False, detalle="debe != haber en 3 filas"
                ),
            ],
            quality_score=0.95,
        )
        assert d.mapping["Codigo"] == "codigo"
        assert d.validation_results[1].ok is False


# --------------------------------------------------------------------------- #
#  Trazabilidad / sello                                                        #
# --------------------------------------------------------------------------- #
class TestHuellaYSello:
    def test_huella_reproducible_e_independiente_del_orden(self):
        a = {"x": 1, "y": 2, "z": Decimal("3.00")}
        b = {"z": Decimal("3.00"), "y": 2, "x": 1}
        assert huella(a) == huella(b)
        assert len(huella(a)) == 64

    def test_huella_cambia_con_el_dato(self):
        assert huella({"x": 1}) != huella({"x": 2})

    def test_sellar_dataset(self):
        d = DatasetNormalizado(
            dataset_id="ds1", source_file="f.csv", quality_score=0.95
        ).sellar()
        assert d.sello is not None
        assert len(d.sello.sha256) == 64
        assert d.sello.contrato_version == CONTRATO_VERSION

    def test_sello_estable_para_el_mismo_contenido(self):
        kw = dict(dataset_id="ds1", source_file="f.csv", quality_score=0.95)
        d1 = DatasetNormalizado(**kw).sellar()
        d2 = DatasetNormalizado(**kw).sellar()
        assert d1.sello.sha256 == d2.sello.sha256

    def test_huella_maneja_fecha_y_decimal(self):
        # No debe lanzar con tipos no triviales.
        valor = huella({"f": date(2025, 1, 31), "m": Decimal("10.5")})
        assert len(valor) == 64


def test_contrato_version_expuesta():
    assert CONTRATO_VERSION == "1.0.0"
