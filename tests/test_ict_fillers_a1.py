"""Tests for A1 Mapeo filler using Balance Mapeado (casillero pre-asignado)."""
from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.a1_mapeo import A1Filler


def test_a1_filler_writes_casillero_with_balance_mapeado_items():
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
        "balance_mapeado": [
            {"casillero_sri": "311", "codigo": "5BS.11101.002", "descripcion": "CAJA CHICA UIO", "saldo": 300.00},
            {"casillero_sri": "311", "codigo": "5BS.11102.001", "descripcion": "BANCO RUMINAHUI", "saldo": 529181.54},
            {"casillero_sri": "315", "codigo": "5BS.11201.001", "descripcion": "CLIENTES NO RELACIONADOS", "saldo": 218548.45},
        ],
    }
    result = filler.fill(wb, session_data, anexo_data)
    assert result["filled_cells"] > 0

    ws = wb["MAPEO DE LA DECLARACIÓN A1"]
    found_311 = None
    for r in range(10, 30):
        if ws[f"A{r}"].value == "311":
            found_311 = r
            break
    assert found_311 is not None
    assert ws[f"D{found_311}"].value == "5BS.11101.002"
    assert ws[f"F{found_311}"].value == 300.00


def test_a1_filler_warns_when_casillero_has_no_balance_items():
    wb = load_template()
    filler = A1Filler()
    sess = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    data = {"f101": {"311": 1000.0}, "balance_mapeado": []}
    result = filler.fill(wb, sess, data)
    assert any("balance mapeado" in w.lower() or "balance" in w.lower() for w in result["warnings"])


def test_a1_filler_notes_extra_casilleros_not_in_a1():
    wb = load_template()
    filler = A1Filler()
    sess = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    # 999 is not in A1_CASILLEROS_ORDERED
    data = {
        "f101": {},
        "balance_mapeado": [
            {"casillero_sri": "999", "codigo": "X", "descripcion": "Test", "saldo": 100.0},
        ],
    }
    result = filler.fill(wb, sess, data)
    assert any(
        "no mapean al a1" in w.lower()
        or "no se mapean" in w.lower()
        or "se trasladan a" in w.lower()
        or "otros anexos" in w.lower()
        for w in result["warnings"]
    )
