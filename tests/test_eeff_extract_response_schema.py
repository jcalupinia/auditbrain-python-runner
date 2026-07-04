"""Regresión: ExtractResponse NO debe filtrar las comparaciones.

El endpoint /extract usa `response_model=ExtractResponse`. FastAPI serializa la
respuesta a través de ese modelo y DESCARTA cualquier clave no declarada. Si el
schema no incluye `comparaciones`/`periodos_esf`/`periodos_eri`, el extractor las
devuelve pero nunca llegan al dashboard (bug detectado en verificación E2E).
"""
from backend.app.tax.planificacion_utilidades.schemas import ExtractResponse
from backend.app.tax.planificacion_utilidades.parsers.balance_interno import (
    extract_balance_interno,
)
from tests.fixtures.eeff_sintetico import libro_resumido_nombre


def test_extract_response_declara_comparaciones_y_periodos():
    campos = ExtractResponse.model_fields
    assert "comparaciones" in campos
    assert "periodos_esf" in campos
    assert "periodos_eri" in campos


def test_pipeline_extractor_a_response_conserva_comparaciones():
    result = extract_balance_interno(libro_resumido_nombre())
    # Debe traer comparaciones antes de pasar por el schema.
    assert result.get("comparaciones", {}).get("esf")
    # Al serializar por el response_model, NO se deben perder.
    dumped = ExtractResponse(**result).model_dump()
    assert dumped["comparaciones"]["esf"], "response_model filtró las comparaciones"
    assert dumped["comparaciones"]["eri"]
    assert dumped["periodos_esf"] and dumped["periodos_eri"]
