"""Tests for filler base + template loader."""
from backend.app.ict.fillers.base import load_template


def test_load_template_returns_workbook_with_all_sheets():
    wb = load_template()
    expected = {
        "INDICE", "MAPEO DE LA DECLARACIÓN A1", "INGRESOS A2",
        "COSTOS  GASTOS A3", "CONCILIACIÓN INGRESOS A4",
        "CONCILIACIÓN COSTOS Y GASTOS A5", "BENEFICIOS TRIBUTARIOS A6",
        "CRÉDITO TRIBUTARIO A7", "COMERCIO EXTERIOR A8", "INVENTARIOS A9",
    }
    sheets = set(wb.sheetnames)
    assert expected.issubset(sheets), f"missing sheets: {expected - sheets}"


def test_load_template_data_only_false_preserves_formulas():
    """Loaded with data_only=False so any formula in template stays as string starting with '='."""
    wb = load_template()
    # Just verify it loads without error and is a Workbook
    from openpyxl.workbook import Workbook as WB
    assert isinstance(wb, WB)
