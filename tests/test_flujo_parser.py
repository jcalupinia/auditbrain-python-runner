import io

from openpyxl import Workbook

from backend.app.client_portal.flujo import parser


def _wb_bytes(rows, headers=("Cod.Cuenta.Contable", "Descripción", "CODIFO SUPER CIAS",
                             "Códigos SRI", "Saldos 31 DIC")):
    wb = Workbook()
    ws = wb.active
    ws.append(list(headers))
    for r in rows:
        ws.append(list(r))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_parse_balanza_detecta_columnas_por_encabezado():
    data = _wb_bytes([
        ("1.01.01.01", "Caja", "1010101", "311", 1000.0),
        ("2.01.03.01", "Proveedores", "2010301", "413", -500.0),
    ])
    filas = parser.parse_balanza(data)
    assert len(filas) == 2
    assert filas[0] == {"cuenta": "1.01.01.01", "super_cias": "1010101",
                        "sri": "311", "saldo": 1000.0}
    assert filas[1]["saldo"] == -500.0


def test_parse_balanza_ignora_filas_sin_codigo_o_saldo():
    data = _wb_bytes([
        ("1.01.01.01", "Caja", "1010101", "311", 1000.0),
        ("", "Fila título", "", "", None),          # sin código ni saldo
        ("9.99", "Sin super cías", "", "", 5.0),     # sin super_cias → se ignora
    ])
    filas = parser.parse_balanza(data)
    assert len(filas) == 1
    assert filas[0]["super_cias"] == "1010101"


def test_parse_balanza_acepta_saldo_texto_con_separadores():
    data = _wb_bytes([
        ("1.01", "Caja", "1010101", "311", "1.234,56"),   # europeo
        ("1.02", "Bancos", "1010102", "311", "2,000.00"),  # us
    ])
    filas = parser.parse_balanza(data)
    assert filas[0]["saldo"] == 1234.56
    assert filas[1]["saldo"] == 2000.0
