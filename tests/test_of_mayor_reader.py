"""El constructor de fixtures debe producir un xlsx legible por openpyxl."""

from io import BytesIO

from openpyxl import load_workbook

from tests._mayor_fixtures import ENCABEZADO_REAL, mayor_xlsx


def test_construye_un_xlsx_con_el_encabezado_en_la_fila_indicada():
    data = mayor_xlsx(
        [["1.1.5.1.1", "IVA sobre Compras", None, "COM 1", "", "", "", "", "", 10, 0, 10]],
        fila_encabezado=3,
    )
    ws = load_workbook(BytesIO(data)).active
    assert [c.value for c in ws[3]] == list(ENCABEZADO_REAL)
    assert ws.cell(4, 1).value == "1.1.5.1.1"
