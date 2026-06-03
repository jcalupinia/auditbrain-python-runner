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
def build_f101_sheet(
    wb: Workbook,
    f101: dict,
    casillero_names: dict[str, str] | None = None,
) -> dict[str, int]:
    """Crea hoja DATOS F-101 con TODOS los casilleros canónicos del F-101 SRI.

    REGLA del proyecto (CLAUDE.md / pedido del usuario):
        "verificar que se trasladen TODOS los casilleros con sus códigos,
        nombres, valores — no importa que estén en cero, con la finalidad
        de que no haya saldos de líneas [vacías]"

    Estrategia:
      1. La lista CANÓNICA viene de backend/app/ict/catalogo_f101.py
         (F101_CASILLERO_NAMES). El test estático garantiza que cubre
         todos los casilleros del parser.
      2. Para cada casillero de la lista canónica se escribe SIEMPRE:
            · Columna A — número del casillero
            · Columna B — nombre oficial SRI (NUNCA vacío)
            · Columna C — valor declarado (0.00 si el PDF no lo trae)
            · Columna D — observación (vacío para edición manual)
      3. Si el F-101 trae casilleros EXTRAS no contemplados en el catálogo
         (caso edge: PDF con formato no estándar), también se escriben al
         final con el nombre del legacy lookup como fallback.
      4. Runtime check: si algún casillero del PDF no tiene nombre en el
         catálogo, se emite un warning vía logging (regla runtime).

    Args:
        f101: dict casillero_str → valor (extraído por parse_f101).
        casillero_names: legacy, opcional. Ya no se usa como fuente
            primaria — solo fallback para casilleros extras del PDF.

    Returns:
        casillero_to_row: {"311": 4, "315": 5, ...} para usar en fórmulas.
    """
    from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES

    if SHEET_F101 in wb.sheetnames:
        del wb[SHEET_F101]
    ws = wb.create_sheet(SHEET_F101)

    _write_title(ws, "📄 DATOS F-101 · Declaración Anual del Impuesto a la Renta")
    _write_header(ws, 3, ["Casillero", "Nombre del Casillero", "Valor Declarado", "Observación"])

    # === REGLA: la lista canónica define qué casilleros aparecen ===
    canonical_cas = sorted(
        F101_CASILLERO_NAMES.keys(),
        key=lambda x: int(x) if x.isdigit() else 99999,
    )
    # Detectar casilleros del PDF que NO están en el catálogo (caso edge).
    legacy_names = casillero_names or {}
    extras_in_pdf = sorted(
        set(f101.keys()) - set(F101_CASILLERO_NAMES.keys()),
        key=lambda x: int(x) if x.isdigit() else 99999,
    )
    if extras_in_pdf:
        import logging
        logging.warning(
            "DATOS F-101: %d casilleros del PDF NO están en el catálogo canónico: %s. "
            "Agregar a backend/app/ict/catalogo_f101.py para que tengan nombre.",
            len(extras_in_pdf), extras_in_pdf[:20],
        )

    casillero_to_row: dict[str, int] = {}
    row = 4

    # Paso 1: TODOS los casilleros canónicos (con valor 0.00 si el PDF no trae)
    for cas in canonical_cas:
        val = f101.get(cas, 0)
        if val is None:
            val = 0
        nombre = F101_CASILLERO_NAMES[cas]
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

    # Paso 2: extras del PDF que no estaban en el catálogo, al final
    for cas in extras_in_pdf:
        val = f101.get(cas) or 0
        nombre = legacy_names.get(cas, "(no catalogado — actualizar catalogo_f101.py)")
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
        ws.cell(row, 4, value="⚠ no catalogado").border = BORDER
        casillero_to_row[cas] = row
        row += 1

    # === REGLA runtime: verificar que NO haya filas con nombre vacío ===
    # Si algún row.B quedó vacío, es bug — emitir warning para alertar.
    for r in range(4, row):
        b_val = ws.cell(r, 2).value
        if b_val is None or str(b_val).strip() == "":
            cas_r = ws.cell(r, 1).value
            import logging
            logging.warning(
                "DATOS F-101 fila %d (cas %s): NOMBRE VACÍO. Regresión de regla.",
                r, cas_r,
            )

    # Anchos
    widths = {"A": 14, "B": 60, "C": 18, "D": 32}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    ws.freeze_panes = "A4"
    ws.auto_filter.ref = f"A3:D{row-1}"
    return casillero_to_row


# ---------------- F-103 ----------------
def build_f103_sheet(wb: Workbook, f103_monthly: dict) -> dict[tuple[str, str], str]:
    """Crea hoja DATOS F-103 con TODOS los casilleros canónicos del F-103 SRI.

    REGLA del proyecto (pedido del usuario):
        "se trasladen TODOS los casilleros con sus códigos, nombres, valores,
        no importa que estén en cero, con la finalidad de que no haya saldos
        de líneas [vacías]"

    Estrategia (igual que F-101):
      · Lista canónica viene de catalogo_f103.py (F103_CASILLERO_NAMES).
      · SIEMPRE escribe todos los casilleros canónicos, aunque tengan 0.
      · Si el cliente no subió F-103, igual se muestra la matriz vacía
        para que el auditor sepa qué iba a esperar.
      · Casilleros extras del PDF que no están en el catálogo se agregan
        al final con observación "⚠ no catalogado".

    Returns:
        lookup: {(periodo, casillero) → "addr"} ej. ("2025-01", "302") → "C5"
                + lookup ("ANUAL", cas) → addr de la columna TOTAL ANUAL.
    """
    from backend.app.ict.catalogo_f103 import F103_CASILLERO_NAMES

    if SHEET_F103 in wb.sheetnames:
        del wb[SHEET_F103]
    ws = wb.create_sheet(SHEET_F103)

    _write_title(ws, "📋 DATOS F-103 · Declaraciones Mensuales de Retenciones IR")

    # Meses presentes (si no hay datos, generar matriz vacía con 12 meses
    # placeholder para visualizar la estructura completa).
    meses = sorted(f103_monthly.keys()) if f103_monthly else [
        f"2025-{m:02d}" for m in range(1, 13)
    ]

    # Casilleros: todos los canónicos + extras del PDF
    canonical_cas = list(F103_CASILLERO_NAMES.keys())
    extras_pdf: set[str] = set()
    for periodo in meses:
        if periodo not in f103_monthly:
            continue
        pdf_cas = set((f103_monthly[periodo].get("casilleros") or {}).keys())
        extras_pdf.update(pdf_cas - set(F103_CASILLERO_NAMES.keys()))
    extras_pdf_sorted = sorted(extras_pdf, key=lambda x: int(x) if x.isdigit() else 99999)
    sorted_cas = sorted(canonical_cas, key=lambda x: int(x) if x.isdigit() else 99999) + extras_pdf_sorted

    if extras_pdf:
        import logging
        logging.warning(
            "DATOS F-103: %d casilleros del PDF NO están en catalogo_f103.py: %s",
            len(extras_pdf), extras_pdf_sorted[:20],
        )

    # Header: Casillero | Nombre | mes1..mesN | TOTAL ANUAL
    headers = ["Casillero", "Nombre del Casillero"] + list(meses) + ["TOTAL ANUAL"]
    _write_header(ws, 3, headers)

    n_meses = len(meses)
    first_data_col = 3                              # mes 1 = col C
    last_data_col_idx = 2 + n_meses                 # último mes
    total_col_idx = 3 + n_meses                     # columna TOTAL ANUAL

    lookup: dict[tuple[str, str], str] = {}
    row = 4

    for cas in sorted_cas:
        # Columna A — casillero
        ws.cell(row, 1, value=cas).font = FONT_DATA
        ws.cell(row, 1).alignment = Alignment(horizontal="center")
        ws.cell(row, 1).border = BORDER

        # Columna B — nombre del catálogo (NUNCA vacío si está en canónicos)
        nombre = F103_CASILLERO_NAMES.get(cas, "(no catalogado — actualizar catalogo_f103.py)")
        ws.cell(row, 2, value=nombre).font = FONT_DATA
        ws.cell(row, 2).border = BORDER
        ws.cell(row, 2).alignment = Alignment(horizontal="left", wrap_text=True)

        # Columnas de cada mes — valor o 0 si no se declaró
        for j, periodo in enumerate(meses, start=first_data_col):
            mes_data = f103_monthly.get(periodo) or {}
            val = (mes_data.get("casilleros") or {}).get(cas, 0)
            if val is None:
                val = 0
            c = ws.cell(row, j, value=val)
            c.font = FONT_DATA
            c.number_format = '#,##0.00;-#,##0.00;0.00'
            c.alignment = Alignment(horizontal="right")
            c.border = BORDER
            lookup[(periodo, cas)] = f"{get_column_letter(j)}{row}"

        # Columna TOTAL ANUAL = SUM de los meses
        first_col_letter = get_column_letter(first_data_col)
        last_col_letter = get_column_letter(last_data_col_idx)
        total_col_letter = get_column_letter(total_col_idx)
        c_total = ws.cell(row, total_col_idx,
                          value=f"=SUM({first_col_letter}{row}:{last_col_letter}{row})")
        c_total.font = Font(name="Calibri", size=9, bold=True)
        c_total.number_format = '#,##0.00;-#,##0.00;0.00'
        c_total.alignment = Alignment(horizontal="right")
        c_total.border = BORDER
        lookup[("ANUAL", cas)] = f"{total_col_letter}{row}"
        row += 1

    # REGLA runtime: ninguna fila debe quedar sin nombre
    for r in range(4, row):
        b_val = ws.cell(r, 2).value
        if b_val is None or str(b_val).strip() == "":
            cas_r = ws.cell(r, 1).value
            import logging
            logging.warning(
                "DATOS F-103 fila %d (cas %s): NOMBRE VACÍO. Regresión de regla.",
                r, cas_r,
            )

    # Anchos: A=14 (cas), B=55 (nombre largo), meses=13, total=15
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 55
    for j in range(first_data_col, last_data_col_idx + 1):
        ws.column_dimensions[get_column_letter(j)].width = 13
    ws.column_dimensions[get_column_letter(total_col_idx)].width = 15

    ws.freeze_panes = "C4"
    ws.auto_filter.ref = f"A3:{get_column_letter(total_col_idx)}{row-1}"
    return lookup


# ---------------- F-104 ----------------
def build_f104_sheet(wb: Workbook, f104_monthly: dict) -> dict[tuple[str, str], str]:
    """Crea hoja DATOS F-104 con TODOS los casilleros canónicos del F-104 SRI.

    REGLA del proyecto (pedido del usuario):
        "se trasladen TODOS los casilleros con sus códigos, nombres, valores,
        no importa que estén en cero, con la finalidad de que no haya saldos
        de líneas [vacías]"

    Estrategia idéntica a F-103: catálogo canónico
    (backend/app/ict/catalogo_f104.py) define las 22+ filas. Si el cliente
    sube F-104 con valores 0 para ciertos casilleros, igual aparecen.
    Si no sube F-104, se muestra matriz vacía con la estructura completa.

    Returns:
        lookup: {(periodo, casillero) → "addr"} + ("ANUAL", cas) → total.
    """
    from backend.app.ict.catalogo_f104 import F104_CASILLERO_NAMES

    if SHEET_F104 in wb.sheetnames:
        del wb[SHEET_F104]
    ws = wb.create_sheet(SHEET_F104)

    _write_title(ws, "📑 DATOS F-104 · Declaraciones Mensuales de IVA")

    # Meses presentes (si no hay datos, 12 meses placeholder)
    meses = sorted(f104_monthly.keys()) if f104_monthly else [
        f"2025-{m:02d}" for m in range(1, 13)
    ]

    # Casilleros: todos los canónicos + extras del PDF
    canonical_cas = list(F104_CASILLERO_NAMES.keys())
    extras_pdf: set[str] = set()
    for periodo in meses:
        if periodo not in f104_monthly:
            continue
        d = f104_monthly.get(periodo) or {}
        cas_dict = d.get("casilleros") if isinstance(d, dict) else None
        if cas_dict:
            extras_pdf.update(set(cas_dict.keys()) - set(F104_CASILLERO_NAMES.keys()))
    extras_pdf_sorted = sorted(extras_pdf, key=lambda x: int(x) if x.isdigit() else 99999)
    sorted_cas = sorted(canonical_cas, key=lambda x: int(x) if x.isdigit() else 99999) + extras_pdf_sorted

    if extras_pdf:
        import logging
        logging.warning(
            "DATOS F-104: %d casilleros del PDF NO están en catalogo_f104.py: %s",
            len(extras_pdf), extras_pdf_sorted[:20],
        )

    # Header: Casillero | Nombre | mes1..mesN | TOTAL ANUAL
    headers = ["Casillero", "Nombre del Casillero"] + list(meses) + ["TOTAL ANUAL"]
    _write_header(ws, 3, headers)

    n_meses = len(meses)
    first_data_col = 3
    last_data_col_idx = 2 + n_meses
    total_col_idx = 3 + n_meses

    lookup: dict[tuple[str, str], str] = {}
    row = 4

    for cas in sorted_cas:
        ws.cell(row, 1, value=cas).font = FONT_DATA
        ws.cell(row, 1).alignment = Alignment(horizontal="center")
        ws.cell(row, 1).border = BORDER

        nombre = F104_CASILLERO_NAMES.get(cas, "(no catalogado — actualizar catalogo_f104.py)")
        ws.cell(row, 2, value=nombre).font = FONT_DATA
        ws.cell(row, 2).border = BORDER
        ws.cell(row, 2).alignment = Alignment(horizontal="left", wrap_text=True)

        for j, periodo in enumerate(meses, start=first_data_col):
            d = f104_monthly.get(periodo) or {}
            cas_dict = d.get("casilleros") if isinstance(d, dict) else None
            val = (cas_dict or {}).get(cas, 0)
            if val is None:
                val = 0
            c = ws.cell(row, j, value=val)
            c.font = FONT_DATA
            c.number_format = '#,##0.00;-#,##0.00;0.00'
            c.alignment = Alignment(horizontal="right")
            c.border = BORDER
            lookup[(periodo, cas)] = f"{get_column_letter(j)}{row}"

        first_col_letter = get_column_letter(first_data_col)
        last_col_letter = get_column_letter(last_data_col_idx)
        total_col_letter = get_column_letter(total_col_idx)
        c_total = ws.cell(row, total_col_idx,
                          value=f"=SUM({first_col_letter}{row}:{last_col_letter}{row})")
        c_total.font = Font(name="Calibri", size=9, bold=True)
        c_total.number_format = '#,##0.00;-#,##0.00;0.00'
        c_total.alignment = Alignment(horizontal="right")
        c_total.border = BORDER
        lookup[("ANUAL", cas)] = f"{total_col_letter}{row}"
        row += 1

    # REGLA runtime: ninguna fila sin nombre
    for r in range(4, row):
        b_val = ws.cell(r, 2).value
        if b_val is None or str(b_val).strip() == "":
            cas_r = ws.cell(r, 1).value
            import logging
            logging.warning(
                "DATOS F-104 fila %d (cas %s): NOMBRE VACÍO. Regresión de regla.",
                r, cas_r,
            )

    # Anchos
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 55
    for j in range(first_data_col, last_data_col_idx + 1):
        ws.column_dimensions[get_column_letter(j)].width = 13
    ws.column_dimensions[get_column_letter(total_col_idx)].width = 15

    ws.freeze_panes = "C4"
    ws.auto_filter.ref = f"A3:{get_column_letter(total_col_idx)}{row-1}"
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
