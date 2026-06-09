"""Tests for A7 Crédito Tributario filler (2 matrices multi-año)."""

import uuid

from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a7_credito import A7Filler


def _session_data():
    return {
        "razon_social": f"Empresa Test {uuid.uuid4().hex[:6]}",
        "ruc": "1799999990001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "",
    }


def test_a7_filler_writes_header():
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    ws = wb["CRÉDITO TRIBUTARIO A7"]
    assert ws["C3"].value == sess["razon_social"]
    assert ws["C4"].value == sess["ruc"]
    assert ws["C5"].value == sess["ejercicio_fiscal"]
    assert result["filled_cells"] >= 3


def test_a7_filler_writes_ir_credit_by_year():
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    data = {
        "f101_multiyear": {
            "2022": {"valor_generado": 10000.0},
            "2023": {"valor_generado": 15000.0},
            "2024": {"valor_generado": 8000.0},
        }
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CRÉDITO TRIBUTARIO A7"]

    # Matriz IR: years → rows 15, 16, 17, col D = valor_generado
    assert ws["D15"].value == 10000.0   # 2022 → row 15
    assert ws["D16"].value == 15000.0   # 2023 → row 16
    assert ws["D17"].value == 8000.0    # 2024 → row 17
    assert result["filled_cells"] > 3


def test_a7_filler_accepts_casillero_857_alias():
    """'857' (retenciones en la fuente) es el crédito tributario generado.
    NO el 850 (IR causado). Validado contra ICT_14."""
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    data = {
        "f101_multiyear": {
            "2022": {"857": 7500.0},
        }
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CRÉDITO TRIBUTARIO A7"]
    assert ws["D15"].value == 7500.0
    assert result["filled_cells"] > 0


def test_a7_filler_writes_isd_by_year():
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    data = {
        "f108_multiyear": {
            "2021": {"total_isd_pagado": 3000.0},
            "2022": {"total_isd_pagado": 4500.0},
            "2023": {"total_isd_pagado": 2200.0},
            "2024": {"total_isd_pagado": 1800.0},
            "2025": {"total_isd_pagado": 500.0},
        }
    }
    result = filler.fill(wb, sess, data)
    ws = wb["CRÉDITO TRIBUTARIO A7"]

    # Matriz ISD: years → rows 28-32, col B = total_isd_pagado
    assert ws["B28"].value == 3000.0   # 2021 → row 28
    assert ws["B29"].value == 4500.0   # 2022 → row 29
    assert ws["B30"].value == 2200.0   # 2023 → row 30
    assert ws["B31"].value == 1800.0   # 2024 → row 31
    assert ws["B32"].value == 500.0    # 2025 → row 32
    assert result["filled_cells"] > 3


def test_a7_filler_accepts_999_alias_for_isd():
    """'999' key should map to total_isd_pagado."""
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    data = {
        "f108_multiyear": {
            "2023": {"999": 9999.0},
        }
    }
    filler.fill(wb, sess, data)
    ws = wb["CRÉDITO TRIBUTARIO A7"]
    assert ws["B30"].value == 9999.0   # 2023 → row 30


def test_a7_filler_warns_with_no_multiyear_data():
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    assert any("multi-año" in w for w in result["warnings"])
    assert any("IR" in w or "f101_multiyear" in w for w in result["warnings"])
    assert any("ISD" in w or "f108_multiyear" in w for w in result["warnings"])


def test_a7_filler_preserves_formula_columns():
    """Formula columns (H, Q, S for IR; H, N, U for ISD) must NOT be overwritten."""
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    data = {
        "f101_multiyear": {
            "2022": {"valor_generado": 5000.0},
        },
        "f108_multiyear": {
            "2021": {"total_isd_pagado": 2000.0},
        },
    }
    filler.fill(wb, sess, data)
    ws = wb["CRÉDITO TRIBUTARIO A7"]

    # H15 = =SUM(E15:G15) — must still be a formula
    h15_val = ws["H15"].value
    assert h15_val is not None
    assert isinstance(h15_val, str) and h15_val.startswith("="), (
        f"H15 formula overwritten: {h15_val!r}"
    )
    # H28 = formula for ISD row 2021
    h28_val = ws["H28"].value
    assert h28_val is not None
    assert isinstance(h28_val, str) and h28_val.startswith("="), (
        f"H28 formula overwritten: {h28_val!r}"
    )


def test_a7_filler_no_crash_with_empty_data():
    wb = load_template()
    filler = A7Filler()
    sess = _session_data()
    result = filler.fill(wb, sess, {})
    assert "filled_cells" in result
    assert isinstance(result["warnings"], list)
