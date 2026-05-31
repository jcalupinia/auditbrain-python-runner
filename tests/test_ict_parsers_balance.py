"""Tests for Balance Excel parser."""
import io
import openpyxl

from backend.app.ict.parsers.balance_excel import parse_balance


def _make_balance_excel(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Código", "Nombre", "Saldo Final"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def test_parse_balance_extracts_accounts():
    data = _make_balance_excel([
        ("1.1.01.01.01", "CAJA CHICA UIO", 300.00),
        ("1.1.01.02.01", "BANCO PICHINCHA", 280330.14),
        ("1.1.02.05.01", "CLIENTES", 1718019.45),
    ])
    result = parse_balance(data)
    assert result["errores"] == []
    cuentas = result["cuentas"]
    assert "1.1.01.01.01" in cuentas
    assert cuentas["1.1.01.01.01"]["nombre"] == "CAJA CHICA UIO"
    assert cuentas["1.1.01.01.01"]["saldo"] == 300.00


def test_parse_balance_skips_empty_codes():
    data = _make_balance_excel([
        ("1.1.01.01.01", "CAJA", 100.0),
        (None, "Sub-total", 100.0),
        ("", "Header row", None),
    ])
    result = parse_balance(data)
    assert len(result["cuentas"]) == 1


def test_parse_balance_returns_error_for_missing_header():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["foo", "bar"])
    ws.append((1, 2))
    buf = io.BytesIO()
    wb.save(buf)
    result = parse_balance(buf.getvalue())
    assert "errores" in result and len(result["errores"]) > 0
