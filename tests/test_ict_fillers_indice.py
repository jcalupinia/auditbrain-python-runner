"""Tests for ÍNDICE filler."""
from backend.app.ict.fillers.base import load_template
from backend.app.ict.fillers.indice import IndiceFiller


def test_indice_filler_writes_cliente_data():
    wb = load_template()
    filler = IndiceFiller()
    session_data = {
        "razon_social": "Test S.A.",
        "ruc": "1234567890001",
        "ejercicio_fiscal": "2025",
        "numero_adhesivo": "ABC-12345",
    }
    anexo_data = {"aplica": {"A1": "SI", "A2": "NO", "A9": "SI"}}
    result = filler.fill(wb, session_data, anexo_data)
    assert result["filled_cells"] >= 4

    ws = wb["INDICE"]
    assert ws["C3"].value == "Test S.A."
    assert ws["C4"].value == "1234567890001"


def test_indice_marks_si_for_ready_anexos():
    wb = load_template()
    filler = IndiceFiller()
    session_data = {"razon_social": "X", "ruc": "1", "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    anexo_data = {"aplica": {"A1": "SI", "A9": "SI"}}
    filler.fill(wb, session_data, anexo_data)
    ws = wb["INDICE"]
    # row 10 = A1, row 35 = A9, column J
    assert ws["J10"].value == "SI"
    assert ws["J35"].value == "SI"
    # row 16 = A3 not in aplica → NO
    assert ws["J16"].value == "NO"
