import io
import pandas as pd
from backend.app.tax.planificacion_utilidades.parsers.layout import detect_layout
from tests.fixtures.eeff_sintetico import libro_resumido_nombre


def _df(bytes_):
    xls = pd.ExcelFile(io.BytesIO(bytes_), engine="openpyxl")
    return xls.parse(xls.sheet_names[0], header=None)


def test_detecta_resumido_nombre():
    assert detect_layout(_df(libro_resumido_nombre())) == "resumido_nombre"


def test_detecta_codificado():
    import openpyxl
    wb = openpyxl.Workbook(); ws = wb.active
    ws.append(["Cuenta", 2024, 2025])
    ws.append(["1", "ACTIVO", 100, 110])
    ws.append(["1.1.01", "Caja", 100, 110])
    buf = io.BytesIO(); wb.save(buf)
    assert detect_layout(_df(buf.getvalue())) == "codificado"
