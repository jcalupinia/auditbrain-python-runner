"""Tests de la cédula DM6 IVA (extractor F-104 sección IVA)."""

from pathlib import Path

from backend.app.aud.obligaciones_fiscales.cedulas import dm6_iva

FIXTURES = Path(__file__).parent / "fixtures" / "obligaciones_fiscales"


def test_compute_dm6_one_month():
    month_data = {
        "01": {"casilleros": {"411": 704667.18, "419": 717710.66,
                              "421": 105700.08, "429": 107656.60,
                              "480": 717710.66, "499": 107656.60,
                              "529": 87403.98}}
    }
    result = dm6_iva.compute_from_months(month_data)
    assert len(result["rows"]) == 12
    enero = result["rows"][0]
    assert enero["mes"] == "Enero"
    assert enero["c419"] == 717710.66
    assert enero["c429"] == 107656.60
    assert enero["has_data"] is True


def test_compute_dm6_with_real_pdf():
    f104 = FIXTURES / "f104_enero.pdf"
    result = dm6_iva.compute(inputs={"f104": [f104]})
    assert result["total_months_with_data"] == 1
    enero = result["rows"][0]
    # Valores reales del fixture (NEGOCIOS MORACOSTA enero 2025)
    assert enero["c411"] == 704667.18
    assert enero["c419"] == 717710.66
    assert enero["c429"] == 107656.60
    assert enero["c499"] == 107656.60
