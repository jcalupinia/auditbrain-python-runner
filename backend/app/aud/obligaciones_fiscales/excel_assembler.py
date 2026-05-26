"""Carga la plantilla baked-in DM Obligaciones Fiscales y la puebla con datos.

Para M1:
- DM6 IVA: columnas C, D, E (casilleros F-104 415, 413, 417) por mes
- DM7 Retenciones: columnas H, I, J, K, L, M (casilleros 721, 723, 725,
  729, 731, 727) por mes
- Encabezado: cliente, periodo en todas las pestañas relevantes

El resto de pestañas (DM, DM1, DM2, DM3, DM4, DM5, DM8, DM9, DM10) quedan
con su contenido original de plantilla. Se completan en M2.
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path

from openpyxl import load_workbook

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dm_obligaciones_fiscales.xlsx"

DM6_SHEET = "DM6 IVA"
DM7_SHEET = "DM7 Retenciones x pagar"
DM6_FIRST_ROW = 20  # Enero
DM7_FIRST_ROW = 21  # Enero

# Mapeo columna del Excel DM6 -> clave del row_data
DM6_COL_MAP = {
    3: "c415",   # C: Ventas tarifa 0% (c/ derecho)
    4: "c413",   # D: Ventas tarifa 0% (s/ derecho)
    5: "c417",   # E: Exportaciones
}

# Mapeo columna del Excel DM7 -> clave del row_data
# Orden según plantilla: H=10%, I=20%, J=30%, K=70%, L=100%, M=50%
DM7_COL_MAP = {
    8: "c721",   # H: 10%
    9: "c723",   # I: 20%
    10: "c725",  # J: 30%
    11: "c729",  # K: 70%
    12: "c731",  # L: 100%
    13: "c727",  # M: 50%
}

# Hojas que muestran encabezado de cliente/período en celdas conocidas
HEADER_SHEETS = [
    "DM  Programa de Auditoria",
    "DM1 Cuestionario de Auditoria ",
    "DM4 Compras ",
    "DM5 Ventas ",
    DM6_SHEET,
    DM7_SHEET,
    "DM9 Límite costos y gastos",
]


def assemble(
    *,
    cliente_name: str,
    period_label: str,
    period_end: datetime.date | None,
    prepared_by_name: str | None,
    reviewed_by_name: str | None,
    dm6_data: dict,
    dm7_data: dict,
) -> bytes:
    """Carga plantilla, escribe encabezados + DM6 + DM7, devuelve bytes."""
    wb = load_workbook(TEMPLATE_PATH)

    for name in HEADER_SHEETS:
        if name in wb.sheetnames:
            _write_header(wb[name], cliente_name, period_end,
                          prepared_by_name, reviewed_by_name)

    if DM7_SHEET in wb.sheetnames:
        _populate_monthly_grid(
            wb[DM7_SHEET], DM7_FIRST_ROW, DM7_COL_MAP, dm7_data.get("rows", [])
        )
    if DM6_SHEET in wb.sheetnames:
        _populate_monthly_grid(
            wb[DM6_SHEET], DM6_FIRST_ROW, DM6_COL_MAP, dm6_data.get("rows", [])
        )

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _write_header(
    ws,
    cliente_name: str,
    period_end: datetime.date | None,
    prepared_by_name: str | None,
    reviewed_by_name: str | None,
) -> None:
    """Escribe celdas comunes del encabezado de cada cédula."""
    # La plantilla pone cliente en A5 ó B5 según la hoja. Probamos ambas
    # — openpyxl no falla si la celda está vacía, simplemente la sobreescribe.
    _try_write(ws, "A5", cliente_name)
    _try_write(ws, "B5", cliente_name)
    if period_end:
        _try_write(ws, "D5", period_end)
    if prepared_by_name:
        _try_write(ws, "A7", prepared_by_name)
    if reviewed_by_name:
        _try_write(ws, "A9", reviewed_by_name)


def _populate_monthly_grid(
    ws,
    first_row: int,
    col_map: dict[int, str],
    rows: list[dict],
) -> None:
    """Escribe cada fila mensual en su row del Excel.

    rows: lista de 12 dicts (Enero..Diciembre).
    col_map: {col_index: key_in_row_dict}.
    Solo escribe celdas cuando el valor NO es None (para no romper formulas
    o sobreescribir hardcoded zeros).
    """
    for i, row_data in enumerate(rows):
        excel_row = first_row + i
        for col, key in col_map.items():
            v = row_data.get(key)
            if v is not None:
                ws.cell(row=excel_row, column=col, value=v)


def _try_write(ws, coord: str, value) -> None:
    try:
        ws[coord] = value
    except Exception:
        pass
