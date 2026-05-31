"""Tests for A9 Inventarios filler."""
from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a9_inventarios import A9Filler


def test_a9_filler_writes_9_casilleros():
    wb = load_template()
    filler = A9Filler()
    session_data = {
        "razon_social": "Test S.A.",
        "ruc": "1234567890001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "ABC-12345",
    }
    anexo_data = {
        "f101": {
            "7001": 3649643.24,
            "7010": 6004284.22,
            "7013": 0.0, "7022": 0.0, "7025": 0.0,
            "7028": 0.0, "7031": 0.0, "7034": 0.0, "7037": 0.0,
        },
        "kardex_items": [],
    }
    result = filler.fill(wb, session_data, anexo_data)
    assert result["filled_cells"] >= 9

    ws = wb["INVENTARIOS A9"]
    assert ws["C18"].value == 3649643.24
    assert ws["C19"].value == 6004284.22


def test_a9_filler_warns_when_kardex_missing_and_valor_exists():
    wb = load_template()
    filler = A9Filler()
    session_data = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    anexo_data = {
        "f101": {"7001": 5000.0, "7010": 0.0, "7013": 0.0, "7022": 0.0,
                 "7025": 0.0, "7028": 0.0, "7031": 0.0, "7034": 0.0, "7037": 0.0},
        "kardex_items": [],
    }
    result = filler.fill(wb, session_data, anexo_data)
    assert any("Kardex" in w for w in result["warnings"])
