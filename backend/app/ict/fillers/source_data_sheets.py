"""Hojas de DATOS FUENTE para el ICT 2025.

Genera al final del workbook 4 hojas con TODOS los datos parseados de
los formularios SRI + Balance Mapeado del cliente. Cada anexo (A1..A9)
escribe FÓRMULAS que referencian estas hojas en lugar de valores
literales, de modo que:

  1. El auditor puede hacer doble-click en cualquier valor del anexo y
     ver desde QUÉ casillero/cuenta proviene.
  2. Si se actualiza un valor en la hoja DATOS (cambio manual del
     auditor), todos los anexos se recalculan automáticamente.
  3. Es trivial verificar qué casilleros del F-101/F-103/F-104 quedaron
     sin usar (la hoja DATOS los muestra TODOS, y la hoja
     VERIFICACIÓN reporta cuáles no se referenciaron).

Hojas generadas (al final, antes de VERIFICACIÓN y TRAZABILIDAD):
  · DATOS F-101            — un casillero por fila (anual)
  · DATOS F-103            — pivot mes×casillero (12 meses retenciones)
  · DATOS F-104            — pivot mes×casillero (12 meses IVA)
  · DATOS BALANCE MAPEADO — todas las cuentas con su casillero+saldo
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


SHEET_F101 = "DATOS F-101"
SHEET_F103 = "DATOS F-103"
SHEET_F104 = "DATOS F-104"
SHEET_BALANCE = "DATOS BALANCE"


# ---- Estilos compartidos ----
THIN = Side(border_style="thin", color="A0A0A0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_DATA = Font(name="Calibri", size=9)
FILL_TITLE = PatternFill("solid", fgColor="1F3A5F")
FILL_HEADER = PatternFill("solid", fgColor="4A7BA8")


def _write_title(ws, title: str, span_cols: int = 4) -> None:
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span_cols)
    c = ws.cell(1, 1, value=title)
    c.font = FONT_TITLE
    c.fill = FILL_TITLE
    c.alignment = Alignment(horizontal="left", vertical="center", indent=2)
    ws.row_dimensions[1].height = 26


def _write_header(ws, row: int, headers: list[str]) -> None:
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row, i, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDER
    ws.row_dimensions[row].height = 24


# ---------------- F-101 ----------------
def build_f101_sheet(wb: Workbook, f101: dict, casillero_names: dict[str, str]) -> dict[str, int]:
    """Crea hoja DATOS F-101. Retorna lookup {casillero → row} para que
    los fillers puedan generar fórmulas tipo ='DATOS F-101'!C<row>.

    Args:
        f101: dict casillero_str → valor (extraído por parse_f101).
        casillero_names: dict casillero_str → nombre del casillero
            (típicamente de A1_CASILLEROS_ORDERED y ampliaciones).

    Returns:
        casillero_to_row: {"311": 4, "315": 5, ...} para usar en fórmulas.
    """
    if SHEET_F101 in wb.sheetnames:
        del wb[SHEET_F101]
    ws = wb.create_sheet(SHEET_F101)

    _write_title(ws, "📄 DATOS F-101 · Declaración Anual del Impuesto a la Renta")
    _write_header(ws, 3, ["Casillero", "Nombre del Casillero", "Valor Declarado", "Observación"])

    # Ordenar casilleros numéricamente
    sorted_cas = sorted(f101.keys(), key=lambda x: int(x) if x.isdigit() else 99999)
    casillero_to_row: dict[str, int] = {}
    row = 4
    for cas in sorted_cas:
        val = f101.get(cas)
        nombre = casillero_names.get(cas, "")
        ws.cell(row, 1, value=cas).font = FONT_DATA
        ws.cell(row, 1).alignment = Alignment(horizontal="center")
        ws.cell(row, 1).border = BORDER
        ws.cell(row, 2, value=nombre).font = FONT_DATA
        ws.cell(row, 2).border = BORDER
        c_val = ws.cell(row, 3, value=val)
        c_val.font = FONT_DATA
        c_val.number_format = '#,##0.00;-#,##0.00;0.00'
        c_val.alignment = Alignment(horizontal="right")
        c_val.border = BORDER
        ws.cell(row, 4, value="").border = BORDER
        casillero_to_row[cas] = row
        row += 1

    # Anchos
    widths = {"A": 14, "B": 60, "C": 18, "D": 32}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:D{row-1}"
    return casillero_to_row


# ---------------- F-103 ----------------
def build_f103_sheet(wb: Workbook, f103_monthly: dict) -> dict[tuple[str, str], str]:
    """Crea hoja DATOS F-103. f103_monthly es {'YYYY-MM': {casilleros: {cas: val}}, ...}

    Returns:
        lookup: {(periodo, casillero) → "addr"} ej. ("2025-01", "302") → "C4"
                para construir fórmulas ='DATOS F-103'!<addr>
    """
    if SHEET_F103 in wb.sheetnames:
        del wb[SHEET_F103]
    ws = wb.create_sheet(SHEET_F103)

    _write_title(ws, "📋 DATOS F-103 · Declaraciones Mensuales de Retenciones IR")

    if not f103_monthly:
        ws.cell(3, 1, value="(no se subieron declaraciones F-103)").font = FONT_DATA
        ws.column_dimensions["A"].width = 50
        return {}

    # Pivot: filas = casilleros, cols = meses
    meses = sorted(f103_monthly.keys())
    all_casilleros: set[str] = set()
    for periodo in meses:
        all_casilleros.update((f103_monthly[periodo].get("casilleros") or {}).keys())
    sorted_cas = sorted(all_casilleros, key=lambda x: int(x) if x.isdigit() else 99999)

    headers = ["Casillero"] + meses + ["TOTAL ANUAL"]
    _write_header(ws, 3, headers)

    lookup: dict[tuple[str, str], str] = {}
    row = 4
    for cas in sorted_cas:
        ws.cell(row, 1, value=cas).font = FONT_DATA
        ws.cell(row, 1).alignment = Alignment(horizontal="center")
        ws.cell(row, 1).border = BORDER

        for j, periodo in enumerate(meses, start=2):
            val = (f103_monthly[periodo].get("casilleros") or {}).get(cas, 0)
            c = ws.cell(row, j, value=val)
            c.font = FONT_DATA
            c.number_format = '#,##0.00;-#,##0.00;0.00'
            c.alignment = Alignment(horizontal="right")
            c.border = BORDER
            lookup[(periodo, cas)] = f"{get_column_letter(j)}{row}"

        # TOTAL ANUAL = SUM de los meses
        last_col = get_column_letter(len(meses) + 1)
        total_col = get_column_letter(len(meses) + 2)
        c_total = ws.cell(row, len(meses) + 2,
                          value=f"=SUM(B{row}:{last_col}{row})")
        c_total.font = Font(name="Calibri", size=9, bold=True)
        c_total.number_format = '#,##0.00;-#,##0.00;0.00'
        c_total.alignment = Alignment(horizontal="right")
        c_total.border = BORDER
        # Lookup especial: "ANUAL" → celda total
        lookup[("ANUAL", cas)] = f"{total_col}{row}"
        row += 1

    widths = {"A": 14}
    for col_letter in [get_column_letter(i) for i in range(2, len(meses) + 3)]:
        widths[col_letter] = 13
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "B4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(meses)+2)}{row-1}"
    return lookup


# ---------------- F-104 ----------------
def build_f104_sheet(wb: Workbook, f104_monthly: dict) -> dict[tuple[str, str], str]:
    """Crea hoja DATOS F-104. f104_monthly es {'mm': {'casilleros': {cas:val}, ...}, ...}

    El parser de F-104 usa claves de mes que pueden venir como "01", "01/2025", etc.
    Normalizamos a YYYY-MM mejor posible.
    """
    if SHEET_F104 in wb.sheetnames:
        del wb[SHEET_F104]
    ws = wb.create_sheet(SHEET_F104)

    _write_title(ws, "📑 DATOS F-104 · Declaraciones Mensuales de IVA")

    if not f104_monthly:
        ws.cell(3, 1, value="(no se subieron declaraciones F-104)").font = FONT_DATA
        ws.column_dimensions["A"].width = 50
        return {}

    meses = sorted(f104_monthly.keys())
    all_casilleros: set[str] = set()
    for m in meses:
        d = f104_monthly[m]
        casilleros = d.get("casilleros") if isinstance(d, dict) else None
        if casilleros:
            all_casilleros.update(casilleros.keys())
    sorted_cas = sorted(all_casilleros, key=lambda x: int(x) if x.isdigit() else 99999)

    headers = ["Casillero"] + list(meses) + ["TOTAL ANUAL"]
    _write_header(ws, 3, headers)

    lookup: dict[tuple[str, str], str] = {}
    row = 4
    for cas in sorted_cas:
        ws.cell(row, 1, value=cas).font = FONT_DATA
        ws.cell(row, 1).alignment = Alignment(horizontal="center")
        ws.cell(row, 1).border = BORDER

        for j, periodo in enumerate(meses, start=2):
            d = f104_monthly.get(periodo) or {}
            casilleros = d.get("casilleros") if isinstance(d, dict) else None
            val = (casilleros or {}).get(cas, 0)
            c = ws.cell(row, j, value=val)
            c.font = FONT_DATA
            c.number_format = '#,##0.00;-#,##0.00;0.00'
            c.alignment = Alignment(horizontal="right")
            c.border = BORDER
            lookup[(periodo, cas)] = f"{get_column_letter(j)}{row}"

        last_col = get_column_letter(len(meses) + 1)
        total_col = get_column_letter(len(meses) + 2)
        c_total = ws.cell(row, len(meses) + 2,
                          value=f"=SUM(B{row}:{last_col}{row})")
        c_total.font = Font(name="Calibri", size=9, bold=True)
        c_total.number_format = '#,##0.00;-#,##0.00;0.00'
        c_total.alignment = Alignment(horizontal="right")
        c_total.border = BORDER
        lookup[("ANUAL", cas)] = f"{total_col}{row}"
        row += 1

    widths = {"A": 14}
    for col_letter in [get_column_letter(i) for i in range(2, len(meses) + 3)]:
        widths[col_letter] = 13
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "B4"
    ws.auto_filter.ref = f"A3:{get_column_letter(len(meses)+2)}{row-1}"
    return lookup


# ---------------- BALANCE MAPEADO ----------------
def build_balance_sheet(wb: Workbook, balance: list[dict]) -> list[int]:
    """Crea hoja DATOS BALANCE con TODAS las cuentas del balance mapeado.

    Returns:
        item_to_row: lista del mismo largo que balance, donde item_to_row[i]
            es la fila en DATOS BALANCE donde se escribió la cuenta i de la lista
            original. Permite a A1 generar fórmulas tipo
            ='DATOS BALANCE'!D<row_idx>.
    """
    if SHEET_BALANCE in wb.sheetnames:
        del wb[SHEET_BALANCE]
    ws = wb.create_sheet(SHEET_BALANCE)

    _write_title(ws, "📊 DATOS BALANCE MAPEADO · Cuentas y saldos del cliente",
                 span_cols=5)
    _write_header(ws, 3, ["Casillero SRI", "Código Contable", "Nombre Cuenta",
                          "Saldo 31-dic", "Origen"])

    item_to_row: list[int] = []
    row = 4
    for item in balance:
        cas = str(item.get("casillero_sri", "")).strip()
        codigo = item.get("codigo", "")
        desc = item.get("descripcion", "")
        saldo = item.get("saldo", 0)

        ws.cell(row, 1, value=cas).font = FONT_DATA
        ws.cell(row, 1).alignment = Alignment(horizontal="center")
        ws.cell(row, 1).border = BORDER
        ws.cell(row, 2, value=codigo).font = FONT_DATA
        ws.cell(row, 2).border = BORDER
        ws.cell(row, 3, value=desc).font = FONT_DATA
        ws.cell(row, 3).border = BORDER
        c_saldo = ws.cell(row, 4, value=saldo)
        c_saldo.font = FONT_DATA
        c_saldo.number_format = '#,##0.00;-#,##0.00;0.00'
        c_saldo.alignment = Alignment(horizontal="right")
        c_saldo.border = BORDER
        ws.cell(row, 5, value="Balance Mapeado del cliente").font = FONT_DATA
        ws.cell(row, 5).border = BORDER

        item_to_row.append(row)
        row += 1

    widths = {"A": 14, "B": 22, "C": 50, "D": 18, "E": 30}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:E{row-1}"
    return item_to_row
