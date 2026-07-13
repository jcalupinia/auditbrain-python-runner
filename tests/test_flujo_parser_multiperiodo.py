import io
from datetime import datetime

from openpyxl import Workbook

from backend.app.client_portal.flujo import parser


def _wb(headers, rows):
    wb = Workbook(); ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    bio = io.BytesIO(); wb.save(bio)
    return bio.getvalue()


def test_multiperiodo_detecta_periodos_fecha_y_anio():
    data = _wb(
        ["Código", "Cuenta", datetime(2023, 12, 31), datetime(2024, 12, 31), datetime(2026, 5, 31)],
        [("1.01.01.02.001", "Produbanco Quito", 341440.43, 144362.32, 89723.89)],
    )
    res = parser.parse_balanza_multiperiodo(data)
    assert res["periodos"] == ["31-dic-2023", "31-dic-2024", "31-may-2026"]
    assert res["estado"] == "esf"
    fila = res["filas"][0]
    assert fila["cuenta"] == "1.01.01.02.001"
    assert fila["nombre"] == "Produbanco Quito"
    assert fila["saldos"] == [341440.43, 144362.32, 89723.89]


def test_multiperiodo_clasifica_eri_por_codigo_dominante():
    data = _wb(
        ["Código", "Cuenta", 2024, 2025],
        [("4.01.01", "Ventas", -100.0, -120.0),
         ("5.1.01", "Costo de ventas", 60.0, 70.0)],
    )
    res = parser.parse_balanza_multiperiodo(data)
    assert res["estado"] == "eri"
    assert res["periodos"] == ["2024", "2025"]


def test_multiperiodo_ignora_filas_de_grupo_y_saldo_texto_regional():
    data = _wb(
        ["Código", "Cuenta", 2024],
        [("1.01.01.02.", "BANCOS", ""),
         ("1.01.01.02.001", "Produbanco", "1.234,56")],
    )
    res = parser.parse_balanza_multiperiodo(data)
    fila_leaf = [f for f in res["filas"] if f["cuenta"] == "1.01.01.02.001"][0]
    assert fila_leaf["saldos"] == [1234.56]


def test_multiperiodo_ignora_fila_de_titulo_con_fecha():
    from datetime import datetime
    data = _wb(
        ["BALANCE AL", datetime(2024, 12, 31), None],   # fila de título con fecha
        [],
    )
    # segunda hoja de datos: reconstruimos un libro con título + header real + datos
    from openpyxl import Workbook
    import io as _io
    wb = Workbook(); ws = wb.active
    ws.append(["BALANCE GENERAL AL 31/12/2024", None, None])
    ws.append(["Código", "Cuenta", datetime(2024, 12, 31)])
    ws.append(["1.01", "Caja", 100.0])
    bio = _io.BytesIO(); wb.save(bio)
    res = parser.parse_balanza_multiperiodo(bio.getvalue())
    assert res["periodos"] == ["31-dic-2024"]
    assert res["filas"][0]["cuenta"] == "1.01"
    assert res["filas"][0]["saldos"] == [100.0]


def test_multiperiodo_detecta_fecha_texto():
    data = _wb(
        ["Código", "Cuenta", "31/12/2024", "2025-12-31"],
        [("1.01", "Caja", 10.0, 20.0)],
    )
    res = parser.parse_balanza_multiperiodo(data)
    assert res["periodos"] == ["31-dic-2024", "31-dic-2025"]
    assert res["filas"][0]["saldos"] == [10.0, 20.0]


def test_multiperiodo_anio_texto_con_sufijo_no_es_periodo():
    data = _wb(
        ["Código", "Cuenta", 2024, "2023 comparativo"],
        [("1.01", "Caja", 10.0, 20.0)],
    )
    res = parser.parse_balanza_multiperiodo(data)
    assert res["periodos"] == ["2024"]   # "2023 comparativo" NO es período
