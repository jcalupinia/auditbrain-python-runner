"""Tests de la cédula DM7 Retenciones (extractor F-104 sección agente)."""

from pathlib import Path

import pytest

from backend.app.aud.obligaciones_fiscales.cedulas import dm7_retenciones, f104_extractor

FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


def test_extract_f104_returns_periodo_and_casilleros():
    pdf_path = FIXTURES / "f104_enero.pdf"
    assert pdf_path.exists(), "fixture missing"
    data = f104_extractor.extract_f104(pdf_path.read_bytes())
    assert data is not None
    assert data["periodo"] == "01/2025"
    # Casilleros de retención IVA del fixture real:
    cas = data["casilleros"]
    assert cas["721"] == 8594.74
    assert cas["723"] == 25.41
    assert cas["725"] == 304.62
    assert cas["727"] == 0.00
    assert cas["729"] == 997.30
    assert cas["731"] == 37.50
    assert cas["799"] == 9959.57


def test_compute_dm7_one_month():
    month_data = {
        "01": {"casilleros": {"721": 8594.74, "723": 25.41, "725": 304.62,
                              "727": 0.00, "729": 997.30, "731": 37.50, "799": 9959.57}}
    }
    result = dm7_retenciones.compute_from_months(month_data)
    assert len(result["rows"]) == 12
    enero = result["rows"][0]
    assert enero["mes"] == "Enero"
    assert enero["c721"] == 8594.74
    assert enero["has_data"] is True
    febrero = result["rows"][1]
    assert febrero["c721"] is None
    assert febrero["has_data"] is False
    assert result["total_months_with_data"] == 1


def test_compute_dm7_with_real_pdf():
    f104 = FIXTURES / "f104_enero.pdf"
    result = dm7_retenciones.compute(inputs={"f104": [f104]})
    assert result["total_months_with_data"] == 1
    enero = result["rows"][0]
    assert enero["c721"] == 8594.74
    assert enero["c799"] == 9959.57


def test_extract_f104_returns_none_on_invalid_bytes():
    assert f104_extractor.extract_f104(b"not a pdf") is None
