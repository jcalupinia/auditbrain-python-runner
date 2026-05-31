"""Tests for A1 Mapeo filler with dynamic row insertion."""
from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a1_mapeo import A1Filler


def test_a1_filler_writes_casillero_with_subaccounts():
    wb = load_template()
    filler = A1Filler()
    session_data = {
        "razon_social": "Test S.A.",
        "ruc": "1234567890001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "ABC-1",
    }
    anexo_data = {
        "f101": {"311": 5008023.09},
        "balance": {
            "1.1.01.01.01": {"nombre": "CAJA CHICA UIO", "saldo": 300.00},
            "1.1.01.01.02": {"nombre": "CAJA CHICA SSFD", "saldo": 1000.00},
            "1.1.01.02.01": {"nombre": "BANCO PICHINCHA", "saldo": 280330.14},
        },
    }
    result = filler.fill(wb, session_data, anexo_data)
    assert result["filled_cells"] > 0

    ws = wb["MAPEO DE LA DECLARACIÓN A1"]
    found_row = None
    for r in range(10, 30):
        if ws[f"A{r}"].value == "311":
            found_row = r
            break
    assert found_row is not None, "Casillero 311 not written"
    assert ws[f"D{found_row}"].value == "1.1.01.01.01"
    assert ws[f"F{found_row}"].value == 300.00


def test_a1_filler_warns_for_casillero_without_balance_match():
    wb = load_template()
    filler = A1Filler()
    session_data = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    anexo_data = {
        "f101": {"311": 1000.0},
        "balance": {},
    }
    result = filler.fill(wb, session_data, anexo_data)
    assert any("subcuentas" in w.lower() or "balance" in w.lower() for w in result["warnings"])
