"""Tests for Balance Mapeado parser."""
import io

import openpyxl

from backend.app.ict.parsers.balance_mapeado_excel import parse_balance_mapeado


def _make_excel(header_row: int, headers: list, data_rows: list) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    # Pad with empty rows to put headers at header_row
    for _ in range(header_row - 1):
        ws.append([])
    ws.append(headers)
    for r in data_rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_parse_balance_mapeado_real_structure():
    """Matches real BALANCE MAPEADO structure: headers at row 11, data from 13."""
    headers = ["Cod.Cuenta.Contable", "Descripción Cuenta Contable", "CODIFO SUPER CIAS",
               "Códigos SRI", "Saldos 31 DIC"]
    # Row 12 = blank (per real file), row 13+ = data
    data = [
        [],  # row 12 blank
        ["5BS.11101.002", "Caja Chica", "1010101", "311", 8500.0],
        ["5BS.11102.001", "Bco.Rumiñahui Cta. 80029773-04", "1010103", "311", 529181.54],
        ["5BS.11201.001", "CxC Clientes Nacionales", None, None, None],  # header
        [None, "Relacionados", "101020603", "312", 5069641.37],  # sub-row
        [None, "No Relacionados", "10102050201", "315", 218548.45],  # sub-row
    ]
    excel = _make_excel(header_row=11, headers=headers, data_rows=data)

    result = parse_balance_mapeado(excel)
    assert result["errores"] == []
    cuentas = result["cuentas"]
    assert len(cuentas) == 4  # 2 main + 2 sub (header skipped)

    # Verify casillero mapping
    assert cuentas[0]["casillero_sri"] == "311"
    assert cuentas[0]["codigo"] == "5BS.11101.002"
    assert cuentas[0]["descripcion"] == "Caja Chica"
    assert cuentas[0]["saldo"] == 8500.0

    # Sub-row inherits parent codigo
    assert cuentas[2]["casillero_sri"] == "312"
    assert cuentas[2]["codigo"] == "5BS.11201.001"  # inherited
    assert cuentas[2]["descripcion"] == "Relacionados"


def test_parse_skips_rows_without_saldo_or_casillero():
    headers = ["Cod.Cuenta.Contable", "Descripción Cuenta Contable", "CODIFO SUPER CIAS",
               "Códigos SRI", "Saldos 31 DIC"]
    data = [
        ["A1", "Header sin saldo", "X", None, None],
        ["A2", "Cuenta válida", "X", "311", 100.0],
        ["A3", "Sin casillero", "X", None, 200.0],
        ["A4", "Saldo inválido", "X", "312", "no_number"],
    ]
    excel = _make_excel(header_row=11, headers=headers, data_rows=data)
    result = parse_balance_mapeado(excel)
    # Only A2 should be valid
    assert len(result["cuentas"]) == 1
    assert result["cuentas"][0]["codigo"] == "A2"
    # A4 should generate an error
    assert any("Saldo inválido" in e for e in result["errores"])


def test_parse_returns_error_for_missing_headers():
    headers = ["foo", "bar"]
    excel = _make_excel(header_row=1, headers=headers, data_rows=[["x", "y"]])
    result = parse_balance_mapeado(excel)
    assert result["cuentas"] == []
    assert any("encabezado" in e.lower() for e in result["errores"])
