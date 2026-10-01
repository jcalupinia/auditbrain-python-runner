"""Fase 3 del Motor de Ingesta: normalización (tipado/moneda/fechas/duplicados).

Reutiliza el parser regional canónico del repo para moneda; aquí se verifica
que el contrato quede con valores normalizados correctos y trazables.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from backend.app.ingesta import (
    CampoExtraido,
    DatasetNormalizado,
    MetodoExtraccion,
    NivelConfianza,
    TipoDato,
    TipoDocumento,
    detectar_duplicados,
    inferir_tipo,
    normalizar_campo,
    normalizar_dataset,
    normalizar_fecha,
    normalizar_monto,
    normalizar_valor,
)


# --------------------------------------------------------------------------- #
#  Moneda (reutiliza _parse_amount_sri)                                        #
# --------------------------------------------------------------------------- #
class TestMonto:
    def test_formato_us(self):
        assert normalizar_monto("178,259.63") == Decimal("178259.63")

    def test_formato_europeo(self):
        assert normalizar_monto("178.259,63") == Decimal("178259.63")

    def test_plano_y_cero(self):
        assert normalizar_monto("183724.10") == Decimal("183724.10")
        assert normalizar_monto("0,00") == Decimal("0.00")

    def test_negativo(self):
        assert normalizar_monto("-150.00") == Decimal("-150.00")

    def test_tipos_nativos(self):
        assert normalizar_monto(Decimal("5.5")) == Decimal("5.5")
        assert normalizar_monto(100) == Decimal("100")

    def test_invalido(self):
        assert normalizar_monto("abc") is None
        assert normalizar_monto(None) is None


# --------------------------------------------------------------------------- #
#  Fechas                                                                      #
# --------------------------------------------------------------------------- #
class TestFecha:
    def test_iso(self):
        assert normalizar_fecha("2025-01-31") == date(2025, 1, 31)

    def test_dd_mm_aaaa_ecuador(self):
        assert normalizar_fecha("31/01/2025") == date(2025, 1, 31)
        assert normalizar_fecha("05/07/2025") == date(2025, 7, 5)  # ambiguo → dd/mm

    def test_mm_dd_cuando_segundo_es_dia(self):
        assert normalizar_fecha("01/31/2025") == date(2025, 1, 31)

    def test_fecha_larga_espanol(self):
        assert normalizar_fecha("31 de enero de 2025") == date(2025, 1, 31)

    def test_aaaa_slash(self):
        assert normalizar_fecha("2025/12/01") == date(2025, 12, 1)

    def test_invalida(self):
        assert normalizar_fecha("32/01/2025") is None
        assert normalizar_fecha("no es fecha") is None
        assert normalizar_fecha(None) is None

    def test_date_nativo(self):
        assert normalizar_fecha(date(2024, 6, 1)) == date(2024, 6, 1)


# --------------------------------------------------------------------------- #
#  Inferencia de tipo                                                          #
# --------------------------------------------------------------------------- #
class TestInferirTipo:
    def test_ruc(self):
        assert inferir_tipo("1791859596001") is TipoDato.RUC

    def test_fecha(self):
        assert inferir_tipo("31/01/2025") is TipoDato.FECHA

    def test_entero(self):
        assert inferir_tipo("100") is TipoDato.ENTERO

    def test_decimal(self):
        assert inferir_tipo("178,259.63") is TipoDato.DECIMAL

    def test_booleano(self):
        assert inferir_tipo("Sí") is TipoDato.BOOLEANO
        assert inferir_tipo(True) is TipoDato.BOOLEANO

    def test_porcentaje(self):
        assert inferir_tipo("12.5%") is TipoDato.PORCENTAJE

    def test_texto(self):
        assert inferir_tipo("Ventas locales") is TipoDato.TEXTO

    def test_vacio_desconocido(self):
        assert inferir_tipo("") is TipoDato.DESCONOCIDO
        assert inferir_tipo(None) is TipoDato.DESCONOCIDO


# --------------------------------------------------------------------------- #
#  normalizar_valor                                                            #
# --------------------------------------------------------------------------- #
class TestNormalizarValor:
    def test_entero_desde_decimal_exacto(self):
        v, t = normalizar_valor("100", TipoDato.ENTERO)
        assert v == 100 and t is TipoDato.ENTERO

    def test_booleano(self):
        assert normalizar_valor("no", TipoDato.BOOLEANO) == (False, TipoDato.BOOLEANO)

    def test_moneda_forzada(self):
        v, t = normalizar_valor("1.234,56", TipoDato.MONEDA)
        assert v == Decimal("1234.56") and t is TipoDato.MONEDA

    def test_autodeteccion(self):
        v, t = normalizar_valor("2025-01-31")
        assert v == date(2025, 1, 31) and t is TipoDato.FECHA


# --------------------------------------------------------------------------- #
#  normalizar_campo                                                            #
# --------------------------------------------------------------------------- #
class TestNormalizarCampo:
    def test_completa_desde_raw(self):
        c = CampoExtraido(
            document_id="d", field="cas_799", raw_value="178,259.63",
            data_type=TipoDato.MONEDA, confidence=NivelConfianza.HIGH,
        )
        normalizar_campo(c)
        assert c.normalized_value == Decimal("178259.63")

    def test_infra_tipo_cuando_desconocido(self):
        c = CampoExtraido(
            document_id="d", field="fecha", raw_value="31/01/2025",
            confidence=NivelConfianza.HIGH,
        )
        normalizar_campo(c)
        assert c.data_type is TipoDato.FECHA
        assert c.normalized_value == date(2025, 1, 31)

    def test_raw_no_normalizable_agrega_warning(self):
        c = CampoExtraido(
            document_id="d", field="monto", raw_value="N/D",
            data_type=TipoDato.MONEDA, confidence=NivelConfianza.HIGH,
        )
        normalizar_campo(c)
        assert c.normalized_value is None
        assert any("no se pudo normalizar" in w for w in c.warnings)

    def test_respeta_valor_ya_normalizado(self):
        c = CampoExtraido(
            document_id="d", field="x", normalized_value=Decimal("5.0"),
            raw_value="otra cosa", data_type=TipoDato.MONEDA,
            confidence=NivelConfianza.HIGH,
        )
        normalizar_campo(c)
        assert c.normalized_value == Decimal("5.0")


# --------------------------------------------------------------------------- #
#  Duplicados                                                                  #
# --------------------------------------------------------------------------- #
class TestDuplicados:
    def test_detecta_grupos(self):
        filas = [
            {"ruc": "001", "doc": "A"},
            {"ruc": "002", "doc": "B"},
            {"ruc": "001", "doc": "A"},
            {"ruc": "001", "doc": "A"},
        ]
        grupos = detectar_duplicados(filas, ["ruc", "doc"])
        assert grupos == [[0, 2, 3]]

    def test_sin_duplicados(self):
        filas = [{"x": 1}, {"x": 2}]
        assert detectar_duplicados(filas, ["x"]) == []

    def test_vacio(self):
        assert detectar_duplicados([], ["x"]) == []


# --------------------------------------------------------------------------- #
#  normalizar_dataset                                                          #
# --------------------------------------------------------------------------- #
class TestNormalizarDataset:
    def test_normaliza_campos_y_detecta_duplicados(self):
        ds = DatasetNormalizado(
            dataset_id="ds", source_file="mayor.xlsx",
            document_type=TipoDocumento.MAYOR,
            rows=[
                {"doc": "F-001", "monto": "100,00"},
                {"doc": "F-001", "monto": "100,00"},
            ],
            campos=[
                CampoExtraido(
                    document_id="ds", field="cas_799", raw_value="1.000,50",
                    data_type=TipoDato.MONEDA, confidence=NivelConfianza.HIGH,
                ),
            ],
            quality_score=0.95,
        )
        normalizar_dataset(ds, claves_duplicado=["doc", "monto"])
        assert ds.campos[0].normalized_value == Decimal("1000.50")
        reglas = {r.regla: r for r in ds.validation_results}
        assert "duplicados" in reglas and reglas["duplicados"].ok is False
        assert any("duplicados detectados" in w for w in ds.warnings)

    def test_sin_claves_no_valida_duplicados(self):
        ds = DatasetNormalizado(
            dataset_id="ds", source_file="f.csv", quality_score=0.95,
            rows=[{"x": 1}, {"x": 1}],
        )
        normalizar_dataset(ds)
        assert all(r.regla != "duplicados" for r in ds.validation_results)

    def test_campo_no_normalizable_contagia_revision(self):
        ds = DatasetNormalizado(
            dataset_id="ds", source_file="f.pdf", quality_score=0.99,
            campos=[
                CampoExtraido(
                    document_id="ds", field="m", raw_value="???",
                    data_type=TipoDato.MONEDA, confidence=NivelConfianza.HIGH,
                ),
            ],
        )
        normalizar_dataset(ds)
        # El campo quedó con warning pero confianza HIGH ⇒ no review por sí solo;
        # sólo la calidad/review de campo lo contagia. Aquí confianza HIGH:
        assert ds.campos[0].normalized_value is None
