"""Tests for A2 Ingresos filler (3 cuadros)."""

from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a2_ingresos import A2Filler


def _session_data(**overrides):
    base = {
        "razon_social": "Test S.A.",
        "ruc": "1234567890001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "ABC-1",
    }
    base.update(overrides)
    return base


def test_a2_filler_writes_header():
    wb = load_template()
    filler = A2Filler()
    result = filler.fill(wb, _session_data(), {})
    ws = wb["INGRESOS A2"]
    assert ws["C3"].value == "Test S.A."
    assert ws["C4"].value == "1234567890001"
    assert ws["C5"].value == "2025"
    assert result["filled_cells"] >= 3


def test_a2_filler_cuadro1_from_f101():
    wb = load_template()
    filler = A2Filler()
    session = _session_data()
    anexo_data = {
        "f101": {
            "6001": 13066588.05,   # ventas bienes tarifa dif 0% → row 14, col C
            "6011": 5313181.16,    # servicios tarifa dif 0%     → row 15, col C
            "6005": 2000000.0,     # exportaciones bienes        → row 17, col D
        }
    }
    result = filler.fill(wb, session, anexo_data)
    ws = wb["INGRESOS A2"]
    assert ws["C14"].value == 13066588.05
    assert ws["C15"].value == 5313181.16
    assert ws["D17"].value == 2000000.0
    assert result["filled_cells"] >= 6  # 3 header + 3 cuadro1


def test_a2_filler_cuadro2_from_f104_monthly():
    wb = load_template()
    filler = A2Filler()
    # Simulate 2 months of F-104 data
    f104_monthly = {
        "01": {"casilleros": {"411": 5000000.0, "416": 200000.0}, "periodo": "01/2025"},
        "02": {"casilleros": {"411": 4500000.0, "416": 180000.0}, "periodo": "02/2025"},
    }
    result = filler.fill(wb, _session_data(), {"f104_monthly": f104_monthly})
    ws = wb["INGRESOS A2"]
    # casillero 411 → ventas_locales_diff_iva row 35, col C
    assert ws["C35"].value == 9500000.0
    # casillero 416 → exportaciones_bienes row 41, col D
    assert ws["D41"].value == 380000.0
    assert "warnings" in result


def test_a2_filler_cuadro2_facturacion_total():
    wb = load_template()
    filler = A2Filler()
    facturacion = {
        "totales": {"emitidas": 10000000.0, "anuladas": 150000.0, "neto": 9850000.0},
        "meses": {},
    }
    result = filler.fill(wb, _session_data(), {"facturacion": facturacion})
    ws = wb["INGRESOS A2"]
    # Row 43 (total_ventas), col G = emitidas electrónicas
    assert ws["G43"].value == 10000000.0
    assert ws["H43"].value == 150000.0
    assert result["filled_cells"] > 0


def test_a2_filler_no_crash_with_empty_data():
    wb = load_template()
    filler = A2Filler()
    result = filler.fill(
        wb,
        {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""},
        {},
    )
    assert "filled_cells" in result
    assert "warnings" in result


def test_a2_filler_cuadro3_propagates_from_cuadro2():
    wb = load_template()
    filler = A2Filler()
    # Provide an IVA value for ventas_locales_diff_iva via F-104
    f104_monthly = {
        "01": {"casilleros": {"411": 8000000.0}, "periodo": "01/2025"},
    }
    result = filler.fill(wb, _session_data(), {"f104_monthly": f104_monthly})
    ws = wb["INGRESOS A2"]
    # Cuadro 3 row 51 (ventas_locales_diff) col B should have 8000000
    assert ws["B51"].value == 8000000.0
    assert result["filled_cells"] > 3
