"""Tests for A4 Conciliación Ingresos filler (2 cuadros)."""

import uuid

from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a4_conciliacion_ingresos import A4Filler


def _session_data():
    return {
        "razon_social": f"Empresa Test {uuid.uuid4().hex[:6]}",
        "ruc": "1799999990001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def test_a4_filler_writes_header():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    ws = wb["CONCILIACIÓN INGRESOS A4"]
    assert ws["C3"].value == sess["razon_social"]
    assert ws["C4"].value == sess["ruc"]
    assert ws["C5"].value == sess["ejercicio_fiscal"]
    assert result["filled_cells"] >= 3


def test_a4_filler_writes_casilleros():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    data = {
        "f101": {
            "804": 5000.0,
            "805": 1200.0,
            "812": 0.0,
            "1112": 3500.0,
        }
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # Cuadro 2: casillero → row mapping
    assert ws["G32"].value == 5000.0    # 804 → row 32
    assert ws["G33"].value == 1200.0   # 805 → row 33
    assert ws["G34"].value == 0.0      # 812 → row 34
    assert ws["G35"].value == 3500.0   # 1112 → row 35
    assert result["filled_cells"] > 3


def test_a4_filler_writes_mayor_detail():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    movimientos = [
        {"codigo": "510101", "nombre": "Dividendos recibidos exentos", "saldo": 18000.0, "debe": 0.0, "haber": 18000.0, "tipo": ""},
        {"codigo": "510201", "nombre": "Renta exenta inversiones", "saldo": 5500.0, "debe": 0.0, "haber": 5500.0, "tipo": ""},
    ]
    data = {
        "f101": {"804": 18000.0, "805": 5500.0, "812": 0.0, "1112": 0.0},
        "mayor_exentos": movimientos,
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # Cuadro 1: first movimiento at row 16
    assert ws["G16"].value == 18000.0     # valor/saldo primera cuenta
    assert ws["C16"].value == "510101"    # código primera cuenta
    assert ws["G17"].value == 5500.0      # segunda cuenta
    assert result["filled_cells"] > 5


def test_a4_filler_truncates_mayor_at_10_rows():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    # 12 cuentas → se truncan en 10
    movimientos = [
        {"codigo": f"51{i:04d}", "nombre": f"Cuenta {i}", "saldo": float(i * 100), "debe": 0.0, "haber": 0.0, "tipo": ""}
        for i in range(12)
    ]
    data = {"mayor_exentos": movimientos}
    result = filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # Row 25 (index 9) should be filled; row 26 is the SUM formula
    assert ws["G25"].value is not None   # última fila permitida (fila 25 = start_row + 9)
    assert any("truncaron" in w for w in result["warnings"])


def test_a4_filler_no_crash_with_empty_data():
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    assert "filled_cells" in result
    assert isinstance(result["warnings"], list)
    # Should warn about missing data
    assert any("mayor_exentos" in w or "F-101" in w for w in result["warnings"])


def test_a4_filler_preserves_formula_rows():
    """Formula rows (G26 =SUM, G36 =SUM, G37 =diferencia) must NOT be overwritten."""
    wb = load_template()
    filler = A4Filler()
    sess = _session_data()
    data = {
        "f101": {"804": 1000.0, "805": 2000.0, "812": 500.0, "1112": 0.0},
        "mayor_exentos": [
            {"codigo": "510101", "nombre": "Cuenta exenta", "saldo": 3500.0, "debe": 0.0, "haber": 3500.0, "tipo": ""}
        ],
    }
    filler.fill(wb, sess, data)
    ws = wb["CONCILIACIÓN INGRESOS A4"]

    # G26 should still have the SUM formula
    assert ws["G26"].value is not None
    val = ws["G26"].value
    assert isinstance(val, str) and val.startswith("="), (
        f"G26 formula was overwritten: {val!r}"
    )
    # G36 should still have the SUM formula
    assert ws["G36"].value is not None
    val36 = ws["G36"].value
    assert isinstance(val36, str) and val36.startswith("="), (
        f"G36 formula was overwritten: {val36!r}"
    )
