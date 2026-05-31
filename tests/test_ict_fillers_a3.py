"""Tests for A3 Costos y Gastos filler (9 bloques de límites)."""

from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a3_costos_gastos import A3Filler


def _session_data():
    return {
        "razon_social": "X Corp S.A.",
        "ruc": "1234567890001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def test_a3_filler_writes_header():
    wb = load_template()
    filler = A3Filler()
    result = filler.fill(wb, _session_data(), {})
    ws = wb["COSTOS  GASTOS A3"]
    assert ws["B3"].value == "X Corp S.A."
    assert ws["B4"].value == "1234567890001"
    assert ws["B5"].value == "2025"
    assert result["filled_cells"] >= 3


def test_a3_filler_writes_casilleros_from_f101():
    wb = load_template()
    filler = A3Filler()
    f101 = {
        # Bloque 1: Gastos gestión
        "7992": 1531596.16,
        "7185": 25337.71,
        "7186": 0.0,
        # Bloque 2: Gastos viaje
        "6999": 18379679.21,
        "804": 0.0,
        "805": 0.0,
        "812": 0.0,
        "1116": 0.0,
        "828": 0.0,
        "834": 0.0,
        "1117": 0.0,
        "829": 0.0,
        "835": 0.0,
        "7182": 8468.7,
        "7183": 0.0,
        # Bloque 4: Promoción publicidad
        "7173": 7923.67,
        "7174": 0.0,
        # Bloque 7b: Deterioro gasto
        "7113": 5.0,
        "7114": 0.0,
    }
    result = filler.fill(wb, _session_data(), {"f101": f101})
    ws = wb["COSTOS  GASTOS A3"]

    # Bloque gastos gestión
    assert ws["F15"].value == 1531596.16   # 7992 → row 15
    assert ws["F16"].value == 25337.71     # 7185 → row 16
    assert ws["F21"].value == 25337.71     # 7185 again → row 21
    assert ws["F22"].value == 0.0          # 7186 → row 22

    # Bloque gastos viaje
    assert ws["F32"].value == 18379679.21  # 6999 → row 32
    assert ws["F46"].value == 8468.7       # 7182 → row 46

    # Bloque promoción publicidad
    assert ws["F86"].value == 7923.67      # 7173 → row 86

    # Bloque deterioro gasto (col G)
    assert ws["G151"].value == 5.0         # 7113 → row 151 col G

    assert result["filled_cells"] > 3


def test_a3_filler_compound_casilleros():
    wb = load_template()
    filler = A3Filler()
    f101 = {
        "7205": 100000.0,
        "7206": 50000.0,  # compound 7205+7206 = 150000
        "7207": 10000.0,
    }
    result = filler.fill(wb, _session_data(), {"f101": f101})
    ws = wb["COSTOS  GASTOS A3"]
    # Bloque indirectos: row 57, col F = 7205+7206
    assert ws["F57"].value == 150000.0
    # row 62, col F = 7205+7206 again
    assert ws["F62"].value == 150000.0
    # row 63, col F = 7207
    assert ws["F63"].value == 10000.0


def test_a3_filler_warns_for_missing_casilleros():
    wb = load_template()
    filler = A3Filler()
    result = filler.fill(wb, _session_data(), {"f101": {}})
    # All non-manual casilleros should generate warnings
    assert len(result["warnings"]) > 0
    # Should still write header
    assert result["filled_cells"] >= 3


def test_a3_filler_skips_manual_cells():
    wb = load_template()
    filler = A3Filler()
    # MANUAL_ keys should not generate warnings nor attempt writes
    result = filler.fill(wb, _session_data(), {"f101": {"6999": 1000.0}})
    # None of the warnings should mention MANUAL_ keys
    for w in result["warnings"]:
        assert "MANUAL_" not in w


def test_a3_filler_no_crash_with_empty_data():
    wb = load_template()
    filler = A3Filler()
    result = filler.fill(wb, _session_data(), {})
    assert "filled_cells" in result
    assert "warnings" in result
    assert isinstance(result["warnings"], list)
