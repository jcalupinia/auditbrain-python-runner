"""Hoja de VERIFICACIÓN para el ICT 2025 — dashboard interactivo.

Diseño:
  - KPI Cards arriba (4 cuadros grandes con cifras clave + estado global)
  - Tabla 1: Cuadratura por bloque del EEFF con formato condicional
  - Tabla 2: Cuadratura Estado de Resultados
  - Tabla 3: Casilleros del F-101 omitidos del A1 (con autofilter)
  - Tabla 4: Casilleros del Balance fuera del A1 (con autofilter)
  - Hipervínculos a la hoja A1 para ir al casillero específico
  - Freeze panes para que los headers siempre estén visibles
  - Formato condicional: verde (cuadra), rojo (difiere)

Pensado como artefacto auditable: el auditor abre la hoja y en 5 segundos
sabe si todo cuadra o dónde están las diferencias.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

from backend.app.ict.cell_maps.a1 import A1_CASILLEROS_ORDERED, A1_SHEET


SHEET_NAME = "VERIFICACIÓN A1"

# ---------------- Estilos reutilizables ----------------
THIN = Side(border_style="thin", color="A0A0A0")
MEDIUM = Side(border_style="medium", color="2D5F8B")
BORDER_DATA = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BORDER_KPI = Border(left=MEDIUM, right=MEDIUM, top=MEDIUM, bottom=MEDIUM)

FONT_TITLE = Font(name="Calibri", size=18, bold=True, color="FFFFFF")
FONT_SUBTITLE = Font(name="Calibri", size=11, bold=True, color="2D5F8B")
FONT_KPI_LABEL = Font(name="Calibri", size=10, bold=True, color="5A6575")
FONT_KPI_VALUE = Font(name="Calibri", size=20, bold=True, color="2D5F8B")
FONT_KPI_VALUE_OK = Font(name="Calibri", size=20, bold=True, color="2E7D32")
FONT_KPI_VALUE_BAD = Font(name="Calibri", size=20, bold=True, color="C62828")
FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
FONT_DATA = Font(name="Calibri", size=10)
FONT_DATA_OK = Font(name="Calibri", size=10, color="2E7D32", bold=True)
FONT_DATA_BAD = Font(name="Calibri", size=10, color="C62828", bold=True)
FONT_SECTION = Font(name="Calibri", size=12, bold=True, color="FFFFFF")

FILL_TITLE = PatternFill("solid", fgColor="1F3A5F")
FILL_SECTION = PatternFill("solid", fgColor="2D5F8B")
FILL_HEADER = PatternFill("solid", fgColor="4A7BA8")
FILL_KPI_BG = PatternFill("solid", fgColor="F4F7FB")
FILL_OK = PatternFill("solid", fgColor="C8E6C9")
FILL_WARN = PatternFill("solid", fgColor="FFE0B2")
FILL_BAD = PatternFill("solid", fgColor="FFCDD2")

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")


def _kpi_card(ws, row: int, col: int, *, label: str, value, color: str = "default") -> None:
    """Dibuja una tarjeta KPI ocupando 3 columnas (col..col+2) y 3 filas (row..row+2)."""
    # Label
    cell_label = ws.cell(row, col, value=label)
    cell_label.font = FONT_KPI_LABEL
    cell_label.fill = FILL_KPI_BG
    cell_label.alignment = ALIGN_CENTER
    ws.merge_cells(start_row=row, start_column=col, end_row=row, end_column=col+2)

    # Value
    cell_val = ws.cell(row+1, col, value=value)
    if color == "ok":
        cell_val.font = FONT_KPI_VALUE_OK
    elif color == "bad":
        cell_val.font = FONT_KPI_VALUE_BAD
    else:
        cell_val.font = FONT_KPI_VALUE
    cell_val.fill = FILL_KPI_BG
    cell_val.alignment = ALIGN_CENTER
    ws.merge_cells(start_row=row+1, start_column=col, end_row=row+2, end_column=col+2)

    # Aplicar borde KPI a todo el cuadro
    for r in (row, row+1, row+2):
        for c in range(col, col+3):
            ws.cell(r, c).border = BORDER_KPI


def _section_header(ws, row: int, *, title: str, span_cols: int = 6) -> int:
    """Inserta un header de sección de fondo azul. Devuelve la siguiente fila."""
    cell = ws.cell(row, 1, value=title)
    cell.font = FONT_SECTION
    cell.fill = FILL_SECTION
    cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span_cols)
    ws.row_dimensions[row].height = 24
    return row + 1


def _table_header(ws, row: int, headers: list[str]) -> int:
    """Escribe la fila de headers con estilo. Devuelve la siguiente fila."""
    for i, h in enumerate(headers, start=1):
        c = ws.cell(row, i, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = ALIGN_CENTER
        c.border = BORDER_DATA
    ws.row_dimensions[row].height = 30
    return row + 1


def build_verification_sheet(
    workbook: Workbook,
    *,
    f101: dict,
    balance_mapeado: list[dict],
    session_data: dict,
    f103_monthly: dict | None = None,
    f104_monthly: dict | None = None,
    trace_log: list[dict] | None = None,
) -> None:
    if SHEET_NAME in workbook.sheetnames:
        del workbook[SHEET_NAME]
    ws = workbook.create_sheet(SHEET_NAME)

    casilleros_a1_set = {c for c, _ in A1_CASILLEROS_ORDERED}
    casilleros_a1_names = dict(A1_CASILLEROS_ORDERED)

    # Agrupar balance por casillero
    by_cas: dict[str, list[dict]] = {}
    for b in balance_mapeado:
        cas = str(b.get("casillero_sri", "")).strip()
        if cas:
            by_cas.setdefault(cas, []).append(b)

    # ============================================================
    # SECCIÓN 0 — TÍTULO + EMPRESA
    # ============================================================
    ws.merge_cells("A1:F2")
    tcell = ws.cell(1, 1, value="🔍 VERIFICACIÓN A1 · Dashboard de Cuadratura")
    tcell.font = FONT_TITLE
    tcell.fill = FILL_TITLE
    tcell.alignment = Alignment(horizontal="left", vertical="center", indent=2)
    ws.row_dimensions[1].height = 22
    ws.row_dimensions[2].height = 22

    info_label_style = Font(name="Calibri", size=10, bold=True, color="5A6575")
    info_value_style = Font(name="Calibri", size=10, color="1F3A5F")
    info_rows = [
        ("Contribuyente", session_data.get("razon_social", "")),
        ("RUC", session_data.get("ruc", "")),
        ("Ejercicio fiscal", session_data.get("ejercicio_fiscal", "")),
    ]
    for i, (k, v) in enumerate(info_rows, start=3):
        ck = ws.cell(i, 1, value=k); ck.font = info_label_style
        cv = ws.cell(i, 2, value=v); cv.font = info_value_style

    # ============================================================
    # SECCIÓN 1 — KPI Cards (4 tarjetas)
    # ============================================================
    # Pre-calc para los KPIs.
    # Prioridad para Pasivo+Patrimonio: usar cas 699 (TOTAL PASIVO Y PATRIMONIO)
    # que el F-101 declara directamente; sólo caer a 599+698 si 699 no se
    # parseó. Sin esta prioridad, cuando el parser falla en 599/698 el KPI
    # mostraba la diferencia = activo total (~ 21M) en vez de 0.
    activo_f101 = f101.get("499") or 0
    if f101.get("699") not in (None, 0, 0.0):
        pp_f101 = f101.get("699")
    else:
        pp_f101 = (f101.get("599") or 0) + (f101.get("698") or 0)
    cuadre_f101 = round(abs(activo_f101 - pp_f101), 2)
    activo_bal = _sum_balance_range(by_cas, [(311, 499)])
    pp_bal = _sum_balance_range(by_cas, [(511, 599), (601, 697)], take_abs=True)
    cuadre_bal = round(abs(activo_bal - pp_bal), 2)

    casilleros_with_value = sum(1 for k, v in f101.items() if v not in (None, 0, 0.0))
    casilleros_en_a1 = sum(1 for k in f101.keys() if k in casilleros_a1_set)
    cuentas_total = len(balance_mapeado)
    cuentas_con_cas = sum(1 for b in balance_mapeado if str(b.get("casillero_sri", "")).strip())

    # Estado global
    if cuadre_f101 <= 0.5 and cuadre_bal <= 0.5:
        estado_global = "✓ CUADRA"
        color_global = "ok"
    elif cuadre_f101 <= 0.5:
        estado_global = "⚠ REVISAR"
        color_global = "default"
    else:
        estado_global = "✗ NO CUADRA"
        color_global = "bad"

    # Layout: 4 cards x (3 cols cada una) — desde fila 7
    kpi_row = 7
    _kpi_card(ws, kpi_row, 1, label="ESTADO GENERAL", value=estado_global, color=color_global)
    _kpi_card(ws, kpi_row, 4, label="DIFERENCIA F-101 (A=P+Pa)",
              value=f"{cuadre_f101:,.2f}",
              color=("ok" if cuadre_f101 <= 0.5 else "bad"))
    _kpi_card(ws, kpi_row+4, 1, label="DIFERENCIA BALANCE (A=P+Pa)",
              value=f"{cuadre_bal:,.2f}",
              color=("ok" if cuadre_bal <= 0.5 else "bad"))
    _kpi_card(ws, kpi_row+4, 4, label="TOTAL DEL ACTIVO",
              value=f"{activo_f101:,.2f}")

    # Segunda fila de KPIs
    kpi_row2 = kpi_row + 8
    _kpi_card(ws, kpi_row2, 1, label="CASILLEROS F-101 CON VALOR",
              value=f"{casilleros_with_value}")
    _kpi_card(ws, kpi_row2, 4, label="CASILLEROS QUE LLEGAN AL A1",
              value=f"{casilleros_en_a1}")
    _kpi_card(ws, kpi_row2+4, 1, label="CUENTAS EN BALANCE MAPEADO",
              value=f"{cuentas_total}")
    _kpi_card(ws, kpi_row2+4, 4, label="CUENTAS CON CASILLERO SRI",
              value=f"{cuentas_con_cas}",
              color=("ok" if cuentas_con_cas == cuentas_total else "bad"))

    row = kpi_row2 + 9

    # ============================================================
    # SECCIÓN 2 — CUADRATURA Estado Situación Financiera
    # ============================================================
    row = _section_header(ws, row, title="📊 CUADRATURA · ESTADO DE SITUACIÓN FINANCIERA")
    headers = ["Bloque", "Casillero", "F-101 declarado", "Balance contable",
               "Diferencia", "Estado"]
    row = _table_header(ws, row, headers)
    table_eeff_start = row

    BLOQUES_EEFF = [
        ("TOTAL ACTIVOS CORRIENTES",      "361", [(311, 360)],            False),
        ("TOTAL ACTIVOS NO CORRIENTES",   "449", [(362, 449)],            False),
        ("TOTAL DEL ACTIVO",              "499", [(311, 499)],            False),
        ("TOTAL PASIVOS CORRIENTES",      "550", [(511, 549)],            True),
        ("TOTAL PASIVOS NO CORRIENTES",   "589", [(553, 588)],            True),
        ("TOTAL DEL PASIVO",              "599", [(511, 599)],            True),
        ("TOTAL DEL PATRIMONIO",          "698", [(601, 697)],            True),
        ("TOTAL PASIVO + PATRIMONIO",     "699", [(511, 599), (601, 697)], True),
    ]
    for nombre, cas, ranges, abs_flag in BLOQUES_EEFF:
        # decl_raw es None si el F-101 NO declaró ese casillero (ej. cas
        # 550/589/698 cuando el parser falló o el PDF no los tenía).
        # Mostrarlo como "n/d" en lugar de 0 evita la confusión "diferencia
        # = total balance" que sugiere bug cuando en realidad es ausencia
        # de dato declarado.
        decl_raw = f101.get(cas)
        decl = round(decl_raw, 2) if decl_raw is not None else None
        bal = round(_sum_balance_range(by_cas, ranges, take_abs=abs_flag), 2)
        if decl is None:
            diff = None
            estado = "⚠ F-101 NO DECLARÓ"
        else:
            diff = round(bal - decl, 2)
            estado = "✓ CUADRA" if abs(diff) <= 0.5 else "✗ DIFIERE"

        ws.cell(row, 1, value=nombre).font = FONT_DATA
        ws.cell(row, 2, value=cas).font = FONT_DATA
        ws.cell(row, 3, value=decl if decl is not None else "n/d").font = FONT_DATA
        ws.cell(row, 4, value=bal).font = FONT_DATA
        diff_cell = ws.cell(row, 5, value=diff if diff is not None else "—")
        est_cell = ws.cell(row, 6, value=estado)
        # Coloreado: si diff es None (F-101 no declaró), usar color warning;
        # si no, verde cuando cuadra y rojo cuando difiere.
        if diff is None:
            diff_cell.font = FONT_DATA_BAD
            est_cell.font = FONT_DATA_BAD
            est_cell.fill = FILL_BAD
        elif abs(diff) <= 0.5:
            diff_cell.font = FONT_DATA_OK
            est_cell.font = FONT_DATA_OK
            est_cell.fill = FILL_OK
        else:
            diff_cell.font = FONT_DATA_BAD
            est_cell.font = FONT_DATA_BAD
            est_cell.fill = FILL_BAD

        # Formato números + bordes + alineación
        for c in range(1, 7):
            cell = ws.cell(row, c)
            cell.border = BORDER_DATA
            if c in (3, 4, 5):
                cell.number_format = '#,##0.00;-#,##0.00;"—"'
                cell.alignment = ALIGN_RIGHT
            elif c == 2 or c == 6:
                cell.alignment = ALIGN_CENTER
            else:
                cell.alignment = ALIGN_LEFT
        row += 1

    table_eeff_end = row - 1
    # AutoFilter sobre la tabla
    ws.auto_filter.ref = f"A{table_eeff_start - 1}:F{table_eeff_end}"
    row += 1

    # ============================================================
    # SECCIÓN 3 — CUADRATURA Estado de Resultados
    # ============================================================
    row = _section_header(ws, row, title="📈 CUADRATURA · ESTADO DE RESULTADOS")
    row = _table_header(ws, row, headers)

    BLOQUES_RESULTADOS = [
        ("TOTAL INGRESOS DE ACTIVIDADES ORDINARIAS", "1005", [(6001, 6018)], False),
        ("TOTAL INGRESOS",                           "6999", [(6001, 6999)], False),
        ("TOTAL COSTOS Y GASTOS",                    "7999", [(7001, 7999)], False),
    ]
    for nombre, cas, ranges, abs_flag in BLOQUES_RESULTADOS:
        decl_raw = f101.get(cas)
        decl = round(decl_raw, 2) if decl_raw is not None else None
        bal = round(_sum_balance_range(by_cas, ranges, take_abs=abs_flag), 2)
        if decl is None:
            diff = None
            estado = "⚠ F-101 NO DECLARÓ"
        else:
            diff = round(bal - decl, 2)
            estado = "✓ CUADRA" if abs(diff) <= 0.5 else "✗ DIFIERE"

        ws.cell(row, 1, value=nombre).font = FONT_DATA
        ws.cell(row, 2, value=cas).font = FONT_DATA
        ws.cell(row, 3, value=decl if decl is not None else "n/d").font = FONT_DATA
        ws.cell(row, 4, value=bal).font = FONT_DATA
        diff_cell = ws.cell(row, 5, value=diff if diff is not None else "—")
        est_cell = ws.cell(row, 6, value=estado)
        # Coloreado: si diff es None (F-101 no declaró), usar color warning;
        # si no, verde cuando cuadra y rojo cuando difiere.
        if diff is None:
            diff_cell.font = FONT_DATA_BAD
            est_cell.font = FONT_DATA_BAD
            est_cell.fill = FILL_BAD
        elif abs(diff) <= 0.5:
            diff_cell.font = FONT_DATA_OK
            est_cell.font = FONT_DATA_OK
            est_cell.fill = FILL_OK
        else:
            diff_cell.font = FONT_DATA_BAD
            est_cell.font = FONT_DATA_BAD
            est_cell.fill = FILL_BAD
        for c in range(1, 7):
            cell = ws.cell(row, c)
            cell.border = BORDER_DATA
            if c in (3, 4, 5):
                cell.number_format = '#,##0.00;-#,##0.00;"—"'
                cell.alignment = ALIGN_RIGHT
            elif c == 2 or c == 6:
                cell.alignment = ALIGN_CENTER
            else:
                cell.alignment = ALIGN_LEFT
        row += 1
    row += 1

    # ============================================================
    # SECCIÓN 4 — Utilidad del ejercicio
    # ============================================================
    row = _section_header(ws, row, title="💰 UTILIDAD DEL EJERCICIO")
    ingresos = round(f101.get("6999") or 0, 2)
    cyg = round(f101.get("7999") or 0, 2)
    util_calc = round(ingresos - cyg, 2)
    util_decl = round(f101.get("801") or 0, 2)
    diff_util = round(util_calc - util_decl, 2)

    util_rows = [
        ("F-101: Ingresos (6999) menos Costos y Gastos (7999)", util_calc),
        ("F-101: Utilidad declarada (cas 801)", util_decl),
        ("Diferencia (debe ser 0)", diff_util),
    ]
    for label, val in util_rows:
        ws.cell(row, 1, value=label).font = FONT_DATA
        cell_v = ws.cell(row, 3, value=val)
        cell_v.font = FONT_DATA_OK if abs(diff_util) <= 0.5 else FONT_DATA_BAD
        cell_v.number_format = '#,##0.00;-#,##0.00;"—"'
        cell_v.alignment = ALIGN_RIGHT
        for c in range(1, 7):
            ws.cell(row, c).border = BORDER_DATA
        row += 1
    est_util = "✓ UTILIDAD CUADRA" if abs(diff_util) <= 0.5 else "✗ UTILIDAD NO CUADRA"
    est_cell = ws.cell(row, 1, value=est_util)
    est_cell.font = FONT_DATA_OK if abs(diff_util) <= 0.5 else FONT_DATA_BAD
    est_cell.fill = FILL_OK if abs(diff_util) <= 0.5 else FILL_BAD
    est_cell.alignment = Alignment(horizontal="center", vertical="center", indent=1)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
    ws.row_dimensions[row].height = 22
    row += 2

    # ============================================================
    # SECCIÓN 5 — Casilleros del F-101 con valor !=0 OMITIDOS del A1
    # ============================================================
    casilleros_no_cero = {k: v for k, v in f101.items() if v not in (None, 0, 0.0)}
    casilleros_omitidos = sorted(
        [k for k in casilleros_no_cero if k not in casilleros_a1_set],
        key=lambda x: int(x) if x.isdigit() else 9999,
    )

    row = _section_header(ws, row, title=f"⚠ CASILLEROS F-101 CON VALOR FUERA DEL A1 ({len(casilleros_omitidos)})")
    if casilleros_omitidos:
        row = _table_header(ws, row, ["Casillero", "Valor F-101", "Anexo destino sugerido", "", "", ""])
        for cas in casilleros_omitidos:
            ws.cell(row, 1, value=cas).font = FONT_DATA
            ws.cell(row, 2, value=casilleros_no_cero[cas]).font = FONT_DATA
            destino = _sugerir_anexo(cas)
            cell_d = ws.cell(row, 3, value=destino)
            cell_d.font = FONT_DATA
            if "A3" in destino or "A5" in destino:
                cell_d.fill = FILL_WARN
            for c in range(1, 7):
                cell = ws.cell(row, c)
                cell.border = BORDER_DATA
                if c == 2:
                    cell.number_format = '#,##0.00;-#,##0.00;"—"'
                    cell.alignment = ALIGN_RIGHT
                elif c == 1:
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
            row += 1
    else:
        msg = ws.cell(row, 1, value="✓ Todos los casilleros del F-101 con valor están cubiertos por el A1")
        msg.font = FONT_DATA_OK
        msg.fill = FILL_OK
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1
    row += 1

    # ============================================================
    # SECCIÓN 6 — Casilleros del Balance fuera del A1
    # ============================================================
    cas_fuera = sorted(set(by_cas.keys()) - casilleros_a1_set,
                       key=lambda x: int(x) if x.isdigit() else 9999)
    row = _section_header(ws, row, title=f"📋 CASILLEROS DEL BALANCE FUERA DEL A1 ({len(cas_fuera)})")
    if cas_fuera:
        row = _table_header(ws, row, ["Casillero", "# Cuentas", "Suma saldos", "Anexo destino", "", ""])
        for cas in cas_fuera:
            items = by_cas[cas]
            total = sum((it.get("saldo") or 0) for it in items)
            destino = _sugerir_anexo(cas)
            ws.cell(row, 1, value=cas).font = FONT_DATA
            ws.cell(row, 2, value=len(items)).font = FONT_DATA
            ws.cell(row, 3, value=total).font = FONT_DATA
            ws.cell(row, 4, value=destino).font = FONT_DATA
            for c in range(1, 7):
                cell = ws.cell(row, c)
                cell.border = BORDER_DATA
                if c == 3:
                    cell.number_format = '#,##0.00;-#,##0.00;"—"'
                    cell.alignment = ALIGN_RIGHT
                elif c in (1, 2):
                    cell.alignment = ALIGN_CENTER
                else:
                    cell.alignment = ALIGN_LEFT
            row += 1

    # ============================================================
    # SECCIÓN 7 — COBERTURA DE CASILLEROS POR FORMULARIO
    # ============================================================
    # Reporta qué casilleros de F-101, F-103, F-104 NO fueron usados
    # (no se generó ninguna fórmula que los referencie). Esto detecta
    # datos del cliente que se PARSEAN pero quedan SIN llegar a los anexos.
    row += 1
    row = _section_header(ws, row,
                          title="🔎 COBERTURA · Casilleros parseados vs referenciados")

    # Set de casilleros que aparecen en el trace log (= fueron escritos)
    trace_log = trace_log or []
    casilleros_referenciados: set[str] = set()
    for entry in trace_log:
        cas = str(entry.get("casillero", "")).strip()
        if cas:
            casilleros_referenciados.add(cas)
    # También agregar los casilleros que el A1 cubre por cell_map
    # (aunque no aparezcan con casillero explícito en el trace)
    casilleros_referenciados |= casilleros_a1_set

    def _reportar_formulario(label: str, casilleros_disponibles: set[str], total_parseados: int):
        nonlocal row
        usados = sum(1 for c in casilleros_disponibles if c in casilleros_referenciados)
        no_usados_con_valor = sorted(
            [c for c in casilleros_disponibles if c not in casilleros_referenciados],
            key=lambda x: int(x) if x.isdigit() else 9999,
        )
        # Header subtítulo
        c = ws.cell(row, 1, value=label)
        c.font = Font(name="Calibri", size=11, bold=True, color="2D5F8B")
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        row += 1

        ws.cell(row, 1, value="Casilleros parseados:").font = FONT_DATA
        ws.cell(row, 2, value=total_parseados).font = FONT_DATA
        ws.cell(row, 4, value="Casilleros usados en anexos:").font = FONT_DATA
        c_used = ws.cell(row, 5, value=usados)
        c_used.font = FONT_DATA_OK if usados > 0 else FONT_DATA
        row += 1
        ws.cell(row, 1, value="Casilleros con valor SIN usar:").font = FONT_DATA
        c_un = ws.cell(row, 2, value=len(no_usados_con_valor))
        c_un.font = FONT_DATA_BAD if len(no_usados_con_valor) > 0 else FONT_DATA_OK
        row += 1

        if no_usados_con_valor:
            # Listar primeros 50
            ws.cell(row, 1, value="Casilleros NO usados (primeros 50):").font = FONT_DATA
            row += 1
            for cas in no_usados_con_valor[:50]:
                ws.cell(row, 1, value=cas).font = FONT_DATA
                ws.cell(row, 1).alignment = ALIGN_CENTER
                ws.cell(row, 2, value="(revisar si debe estar en algún anexo)").font = FONT_DATA
                ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=6)
                row += 1
            if len(no_usados_con_valor) > 50:
                ws.cell(row, 1, value=f"... y {len(no_usados_con_valor)-50} más").font = FONT_DATA
                row += 1
        else:
            ok = ws.cell(row, 1, value="✓ Todos los casilleros parseados fueron referenciados en algún anexo")
            ok.font = FONT_DATA_OK
            ok.fill = FILL_OK
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
            row += 1
        row += 1

    # F-101
    f101_caslleros_con_valor = {k for k, v in f101.items() if v not in (None, 0, 0.0)}
    _reportar_formulario("📄 F-101 · Declaración Anual IR Sociedades",
                          f101_caslleros_con_valor, len(f101))

    # F-103
    if f103_monthly:
        all_f103: set[str] = set()
        for periodo in f103_monthly:
            casilleros = (f103_monthly[periodo].get("casilleros") if isinstance(f103_monthly.get(periodo), dict) else {}) or {}
            for cas, val in casilleros.items():
                if val not in (None, 0, 0.0):
                    all_f103.add(cas)
        _reportar_formulario("📋 F-103 · Retenciones IR mensuales",
                              all_f103, len(all_f103))

    # F-104
    if f104_monthly:
        all_f104: set[str] = set()
        for periodo in f104_monthly:
            d = f104_monthly.get(periodo) or {}
            casilleros = d.get("casilleros") if isinstance(d, dict) else None
            if casilleros:
                for cas, val in casilleros.items():
                    if val not in (None, 0, 0.0):
                        all_f104.add(cas)
        _reportar_formulario("📑 F-104 · IVA mensual",
                              all_f104, len(all_f104))

    # ============================================================
    # FORMATO FINAL
    # ============================================================
    widths = {"A": 50, "B": 14, "C": 18, "D": 24, "E": 18, "F": 18}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    # Freeze panes: dejar el título y el bloque KPI siempre visible
    ws.freeze_panes = "A7"


# ----------------------------------------------------------------------
# Helpers de suma
# ----------------------------------------------------------------------
def _sum_balance_range(
    by_cas: dict[str, list[dict]],
    ranges: list[tuple[int, int]],
    *,
    take_abs: bool = False,
) -> float:
    total = 0.0
    for cas, items in by_cas.items():
        try:
            n = int(cas)
        except (ValueError, TypeError):
            continue
        for lo, hi in ranges:
            if lo <= n <= hi:
                for it in items:
                    val = it.get("saldo") or 0
                    total += abs(val) if take_abs else val
                break
    return total


def _sugerir_anexo(casillero: str) -> str:
    try:
        n = int(casillero)
    except (ValueError, TypeError):
        return "—"
    if 6001 <= n <= 6149: return "A2 (Ingresos)"
    if 6150 <= n <= 6152: return "A4 (Conciliación Ingresos)"
    if 7001 <= n <= 7999: return "A3 / A5 (Costos / Gastos)"
    if 800 <= n <= 999:   return "A6 / A7 (Beneficios / Crédito)"
    if 402 <= n <= 433:   return "A8 (Comercio Exterior)"
    return "—"
