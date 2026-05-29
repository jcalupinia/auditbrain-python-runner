"""Exportador a Excel con FÓRMULAS NATIVAS interactivas.

Replica la lógica de frontend/src/tax/engine.js como fórmulas de Excel, de modo
que el archivo descargado recalcula en vivo al editar inputs (celdas azules) o
parámetros. No se "hornean" resultados: todo lo derivado es fórmula.

Hojas:
  Datos       parámetros editables (%, fechas) + tabla de tramos de tarifa.
  ESF         estado de situación: inputs azules + totales por fórmula.
  ER          estado de resultados: inputs azules + subtotales por fórmula.
  Índices     ratios financieros por fórmula (referencian ESF/ER).
  Proyección  motor tributario (computeER + computeModel) por fórmula, con
              columna comparativa "sin acción".
  Resumen     KPIs (pago actual vs. sin acción, devolución, costo muerto).

IMPORTANTE: la lógica tributaria no se altera; solo se traduce a fórmulas.
"""

from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.app.tax.planificacion_utilidades import schema
from backend.app.tax.planificacion_utilidades.mapping import (
    PLANTILLA_KEY_HEADER,
    PLANTILLA_LABEL_HEADER,
    PLANTILLA_SHEET,
)

# Paleta (marca AuditBrain Tax): Deep Blue / Navy / Gold.
NAVY = "0A2342"
GOLD = "C7A83C"
INPUT_FILL = PatternFill("solid", fgColor="DCE9F7")   # celdas editables (azul)
HEAD_FILL = PatternFill("solid", fgColor=NAVY)
TOTAL_FILL = PatternFill("solid", fgColor="EEF1F5")
WHITE = Font(color="FFFFFF", bold=True)
BOLD = Font(bold=True)
GOLD_FONT = Font(color=GOLD, bold=True, size=14)
THIN = Side(style="thin", color="C9D2DC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
MONEY = "#,##0"
PCT = "0.00%"
YEAR_COLS = ["C", "D", "E"]  # 2023, 2024, 2025

# Agrupaciones de totales (espejo de engine.js tAC/tPC/...).
_AC_KEYS = ["efectivo", "inversiones", "cxc", "cxcRel", "impRec", "otrasCxc",
            "inventario"]
_ANC_KEYS = ["ppe", "actImpDif"]
_PC_KEYS = ["cxp", "impPagar", "benef", "anticipos", "provisiones", "otrasCxp"]
_PNC_KEYS = ["benefPost", "cxpRel", "pasImpDif"]
_PAT_KEYS = ["capital", "reservas", "ori", "resAcum"]


def build_workbook(data: dict, ctrl: list[dict], params: dict) -> bytes:
    """Arma el libro interactivo y devuelve los bytes .xlsx."""
    wb = Workbook()
    wb.remove(wb.active)

    datos_ref = _sheet_datos(wb, params)
    esf_rows = _sheet_esf(wb, data)
    er_rows = _sheet_er(wb, data)
    _sheet_indices(wb, esf_rows, er_rows)
    _sheet_proyeccion(wb, ctrl, esf_rows, er_rows, datos_ref)
    _sheet_resumen(wb, params)

    wb.move_sheet("Resumen", -(len(wb.sheetnames) - 1))  # Resumen primero
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _g(key: str, val) -> float:
    return 0.0 if val is None else float(val)


# ----------------------------------------------------------------- Datos
def _sheet_datos(wb: Workbook, params: dict) -> dict:
    ws = wb.create_sheet("Datos")
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 28
    ws["A1"] = "Datos del cliente y parámetros"
    ws["A1"].font = GOLD_FONT

    txt = [
        ("Empresa / razón social", params.get("empresa", "")),
        ("RUC", params.get("ruc", "")),
        ("Representante legal", params.get("repLegal", "")),
        ("Fecha de corte", params.get("fechaCorte", "")),
        ("Fecha del análisis", params.get("fechaAnalisis", "")),
    ]
    r = 3
    for label, value in txt:
        ws[f"A{r}"] = label
        ws[f"A{r}"].font = BOLD
        ws[f"B{r}"] = value
        ws[f"B{r}"].fill = INPUT_FILL
        r += 1

    ws[f"A{r+1}"] = "Parámetros (editables · validación humana)"
    ws[f"A{r+1}"].font = BOLD
    pr = r + 2
    pcells = {}
    for label, key, default in [
        ("Costo / ventas (%)", "costoR", 60.6),
        ("Gastos op. / ventas (%)", "gastoR", 34.6),
        ("Tasa Impuesto a la Renta (%)", "irR", 25),
        ("Retención dividendos (%)", "retDiv", 10),
    ]:
        ws[f"A{pr}"] = label
        ws[f"B{pr}"] = _g(key, params.get(key, default))
        ws[f"B{pr}"].fill = INPUT_FILL
        ws[f"B{pr}"].number_format = "0.0"
        pcells[key] = f"Datos!$B${pr}"
        pr += 1

    # Tabla de tramos de tarifa (editable). límite superior | tarifa.
    th = pr + 1
    ws[f"A{th}"] = "Tramos de tarifa única (editable)"
    ws[f"A{th}"].font = BOLD
    ws[f"A{th+1}"] = "Límite superior de base"
    ws[f"B{th+1}"] = "Tarifa"
    ws[f"A{th+1}"].font = WHITE
    ws[f"B{th+1}"].font = WHITE
    ws[f"A{th+1}"].fill = HEAD_FILL
    ws[f"B{th+1}"].fill = HEAD_FILL
    brackets = [
        (100000, 0.0), (1000000, 0.0075), (10000000, 0.0125),
        (100000000, 0.0175), (500000000, 0.0225), (1000000000000, 0.025),
    ]
    first = th + 2
    for i, (lim, tar) in enumerate(brackets):
        ws[f"A{first+i}"] = lim
        ws[f"A{first+i}"].number_format = MONEY
        ws[f"A{first+i}"].fill = INPUT_FILL
        ws[f"B{first+i}"] = tar
        ws[f"B{first+i}"].number_format = PCT
        ws[f"B{first+i}"].fill = INPUT_FILL
    limit_cells = [f"Datos!$A${first+i}" for i in range(6)]
    rate_cells = [f"Datos!$B${first+i}" for i in range(6)]

    return {**pcells, "limit_cells": limit_cells, "rate_cells": rate_cells}


def _tarifa_formula(base_addr: str, datos: dict) -> str:
    """IF anidado que replica tarifa(base): primer tramo cuyo límite >= base."""
    L = datos["limit_cells"]
    T = datos["rate_cells"]
    return (
        f"=IF({base_addr}<={L[0]},{T[0]},"
        f"IF({base_addr}<={L[1]},{T[1]},"
        f"IF({base_addr}<={L[2]},{T[2]},"
        f"IF({base_addr}<={L[3]},{T[3]},"
        f"IF({base_addr}<={L[4]},{T[4]},{T[5]})))))"
    )


# ------------------------------------------------------------------- ESF
def _sheet_esf(wb: Workbook, data: dict) -> dict:
    ws = wb.create_sheet("ESF")
    _two_col_header(ws, "Estado de Situación Financiera")
    rowmap: dict[str, int] = {}
    r = 3
    for row in schema.ESF_SCHEMA:
        kind = row[0]
        if kind == "sec":
            ws[f"A{r}"] = row[1]
            ws[f"A{r}"].font = WHITE
            for c in ("A", "B", "C", "D", "E"):
                ws[f"{c}{r}"].fill = HEAD_FILL
            r += 1
            continue
        key, label = row[1], row[2]
        ws[f"A{r}"] = key
        ws[f"B{r}"] = label
        rowmap[key] = r
        if kind == "in":
            vals = data.get(key) or [0, 0, 0]
            for i, col in enumerate(YEAR_COLS):
                cell = ws[f"{col}{r}"]
                cell.value = _g(key, vals[i] if i < len(vals) else 0)
                cell.fill = INPUT_FILL
                cell.number_format = MONEY
                cell.border = BORDER
        else:  # sub / tot -> fórmula
            ws[f"B{r}"].font = BOLD
            for col in YEAR_COLS:
                ws[f"{col}{r}"].font = BOLD
                ws[f"{col}{r}"].number_format = MONEY
                if kind == "tot":
                    ws[f"{col}{r}"].fill = TOTAL_FILL
        r += 1

    # Fórmulas de totales (tras conocer todas las filas).
    def s(keys, col):
        return "+".join(f"{col}{rowmap[k]}" for k in keys)

    for col in YEAR_COLS:
        ws[f"{col}{rowmap['totalAC']}"] = f"={s(_AC_KEYS, col)}"
        ws[f"{col}{rowmap['totalANC']}"] = f"={s(_ANC_KEYS, col)}"
        ws[f"{col}{rowmap['totalActivo']}"] = (
            f"={col}{rowmap['totalAC']}+{col}{rowmap['totalANC']}")
        ws[f"{col}{rowmap['totalPC']}"] = f"={s(_PC_KEYS, col)}"
        ws[f"{col}{rowmap['totalPNC']}"] = f"={s(_PNC_KEYS, col)}"
        ws[f"{col}{rowmap['totalPasivo']}"] = (
            f"={col}{rowmap['totalPC']}+{col}{rowmap['totalPNC']}")
        ws[f"{col}{rowmap['totalPat']}"] = f"={s(_PAT_KEYS, col)}"
    return rowmap


# -------------------------------------------------------------------- ER
def _sheet_er(wb: Workbook, data: dict) -> dict:
    ws = wb.create_sheet("ER")
    _two_col_header(ws, "Estado de Resultados")
    rowmap: dict[str, int] = {}
    r = 3
    for row in schema.ER_SCHEMA:
        kind, key, label = row[0], row[1], row[2]
        ws[f"A{r}"] = key
        ws[f"B{r}"] = label
        rowmap[key] = r
        if kind == "in":
            vals = data.get(key) or [0, 0, 0]
            for i, col in enumerate(YEAR_COLS):
                cell = ws[f"{col}{r}"]
                cell.value = _g(key, vals[i] if i < len(vals) else 0)
                cell.fill = INPUT_FILL
                cell.number_format = MONEY
                cell.border = BORDER
        else:
            ws[f"B{r}"].font = BOLD
            for col in YEAR_COLS:
                ws[f"{col}{r}"].font = BOLD
                ws[f"{col}{r}"].number_format = MONEY
                ws[f"{col}{r}"].fill = TOTAL_FILL
        r += 1

    for col in YEAR_COLS:
        ws[f"{col}{rowmap['ub']}"] = (
            f"={col}{rowmap['ventas']}+{col}{rowmap['otrosIng']}"
            f"+{col}{rowmap['otrosIngFin']}-{col}{rowmap['costo']}")
        ws[f"{col}{rowmap['ebit']}"] = f"={col}{rowmap['ub']}-{col}{rowmap['gAdmin']}"
        ws[f"{col}{rowmap['uai']}"] = f"={col}{rowmap['ebit']}-{col}{rowmap['gFin']}"
        ws[f"{col}{rowmap['neta']}"] = (
            f"={col}{rowmap['uai']}-{col}{rowmap['partTrab']}"
            f"-{col}{rowmap['irCausado']}-{col}{rowmap['impDif']}")
    return rowmap


# --------------------------------------------------------------- Índices
def _sheet_indices(wb: Workbook, esf: dict, er: dict) -> None:
    ws = wb.create_sheet("Índices")
    ws.column_dimensions["A"].width = 34
    ws["A1"] = "Índices financieros"
    ws["A1"].font = GOLD_FONT
    hdr = ["Indicador", "2023", "2024", "2025"]
    for ci, h in enumerate(hdr):
        c = ws.cell(row=2, column=ci + 1, value=h)
        c.fill = HEAD_FILL
        c.font = WHITE

    E = lambda k, col: f"ESF!{col}{esf[k]}"   # noqa: E731
    R = lambda k, col: f"ER!{col}{er[k]}"     # noqa: E731

    def ratio(col, expr):
        return f"=IFERROR({expr},\"\")"

    defs = [
        ("Liquidez corriente", lambda c: f"{E('totalAC',c)}/{E('totalPC',c)}", "0.00"),
        ("Prueba ácida",
         lambda c: f"({E('totalAC',c)}-{E('inventario',c)})/{E('totalPC',c)}", "0.00"),
        ("Capital de trabajo", lambda c: f"{E('totalAC',c)}-{E('totalPC',c)}", MONEY),
        ("Endeudamiento", lambda c: f"{E('totalPasivo',c)}/{E('totalActivo',c)}", PCT),
        ("Apalancamiento", lambda c: f"{E('totalActivo',c)}/{E('totalPat',c)}", "0.00"),
        ("Margen bruto", lambda c: f"{R('ub',c)}/{R('ventas',c)}", PCT),
        ("Margen operativo", lambda c: f"{R('ebit',c)}/{R('ventas',c)}", PCT),
        ("Margen neto", lambda c: f"{R('neta',c)}/{R('ventas',c)}", PCT),
        ("ROE", lambda c: f"{R('neta',c)}/{E('totalPat',c)}", PCT),
        ("ROA", lambda c: f"{R('neta',c)}/{E('totalActivo',c)}", PCT),
        ("Rotación de activos", lambda c: f"{R('ventas',c)}/{E('totalActivo',c)}", "0.00"),
        ("Días de cartera", lambda c: f"{E('cxc',c)}/{R('ventas',c)}*365", "0"),
        ("Días de inventario", lambda c: f"{E('inventario',c)}/{R('costo',c)}*365", "0"),
        ("Días de proveedores", lambda c: f"{E('cxp',c)}/{R('costo',c)}*365", "0"),
    ]
    rr = 3
    for name, fn, fmt in defs:
        ws[f"A{rr}"] = name
        for ci, col in enumerate(YEAR_COLS):
            cell = ws.cell(row=rr, column=ci + 2)
            cell.value = ratio(col, fn(col))
            cell.number_format = fmt
        rr += 1


# ------------------------------------------------------------ Proyección
# Columnas del motor.
_PCOLS = ["Año", "g (%)", "Dividendos", "Capitalización", "Ventas", "Otros ing.",
          "Costo", "Utilidad bruta", "Gastos op.", "EBIT", "UAI", "Particip. 15%",
          "IR causado", "Resultado neto", "Res. acum. inicial", "Base imponible",
          "Tarifa", "Pago a cuenta", "Retención div.", "Crédito vs. retención",
          "Crédito vs. IR", "Devolución", "En riesgo (costo muerto)", "IR a pagar",
          "Res. acum. final", "Pago SIN acción", "Res. acum. SIN acción"]


def _sheet_proyeccion(wb, ctrl, esf, er, datos) -> None:
    ws = wb.create_sheet("Proyección")
    ws["A1"] = "Proyección y motor tributario (2026–2028)"
    ws["A1"].font = GOLD_FONT
    ws["A2"] = ("Inputs azules: crecimiento, dividendos, capitalización. Todo lo "
                "demás recalcula por fórmula al editar ESF/ER/Datos.")
    for ci, h in enumerate(_PCOLS):
        c = ws.cell(row=3, column=ci + 1, value=h)
        c.fill = HEAD_FILL
        c.font = WHITE
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(ci + 1)].width = 13

    cR, gR, irR, rd = datos["costoR"], datos["gastoR"], datos["irR"], datos["retDiv"]
    # Refs al año base 2025 (columna E).
    v25 = f"ER!E{er['ventas']}"
    oi25 = f"ER!E{er['otrosIng']}"
    of25 = f"ER!E{er['otrosIngFin']}"
    ra25 = f"ESF!E{esf['resAcum']}"

    first = 4
    proj_years = [2026, 2027, 2028]
    L = get_column_letter  # alias
    # Índices de columna (1-based) por nombre.
    col = {name: i + 1 for i, name in enumerate(_PCOLS)}

    def cell(r, name):
        return f"{L(col[name])}{r}"

    for i, year in enumerate(proj_years):
        r = first + i
        c = ctrl[i] if i < len(ctrl) else {"g": 0, "div": 0, "cap": 0}
        prev_ventas = v25 if i == 0 else cell(r - 1, "Ventas")
        prev_resacum = ra25 if i == 0 else cell(r - 1, "Res. acum. final")

        # Inputs (azules).
        ws[cell(r, "Año")] = year
        for nm, val in [("g (%)", c.get("g", 0)), ("Dividendos", c.get("div", 0)),
                        ("Capitalización", c.get("cap", 0))]:
            cc = ws[cell(r, nm)]
            cc.value = val
            cc.fill = INPUT_FILL
            cc.number_format = "0.0" if nm == "g (%)" else MONEY

        # computeER.
        ws[cell(r, "Ventas")] = f"={prev_ventas}*(1+{cell(r,'g (%)')}/100)"
        ws[cell(r, "Otros ing.")] = f"={oi25}+{of25}"
        ws[cell(r, "Costo")] = f"={cell(r,'Ventas')}*{cR}/100"
        ws[cell(r, "Utilidad bruta")] = (
            f"={cell(r,'Ventas')}+{cell(r,'Otros ing.')}-{cell(r,'Costo')}")
        ws[cell(r, "Gastos op.")] = f"={cell(r,'Ventas')}*{gR}/100"
        ws[cell(r, "EBIT")] = f"={cell(r,'Utilidad bruta')}-{cell(r,'Gastos op.')}"
        ws[cell(r, "UAI")] = f"={cell(r,'EBIT')}"
        ws[cell(r, "Particip. 15%")] = f"={cell(r,'UAI')}*0.15"
        ws[cell(r, "IR causado")] = (
            f"=MAX(0,({cell(r,'UAI')}-{cell(r,'Particip. 15%')})*{irR}/100)")
        ws[cell(r, "Resultado neto")] = (
            f"={cell(r,'UAI')}-{cell(r,'Particip. 15%')}-{cell(r,'IR causado')}")

        # computeModel.
        ws[cell(r, "Res. acum. inicial")] = f"={prev_resacum}"
        ws[cell(r, "Base imponible")] = (
            f"=MAX(0,{cell(r,'Res. acum. inicial')}-{cell(r,'Dividendos')}"
            f"-{cell(r,'Capitalización')})")
        ws[cell(r, "Tarifa")] = _tarifa_formula(cell(r, "Base imponible"), datos)
        ws[cell(r, "Pago a cuenta")] = f"={cell(r,'Base imponible')}*{cell(r,'Tarifa')}"
        ws[cell(r, "Retención div.")] = f"={cell(r,'Dividendos')}*{rd}/100"
        ws[cell(r, "Crédito vs. retención")] = (
            f"=MIN({cell(r,'Pago a cuenta')},{cell(r,'Retención div.')})")
        ws[cell(r, "Crédito vs. IR")] = (
            f"=MIN({cell(r,'Pago a cuenta')}-{cell(r,'Crédito vs. retención')},"
            f"{cell(r,'IR causado')})")
        ws[cell(r, "Devolución")] = (
            f"=IF(OR({cell(r,'Dividendos')}>0,{cell(r,'Capitalización')}>0),"
            f"{cell(r,'Pago a cuenta')}-{cell(r,'Crédito vs. retención')}"
            f"-{cell(r,'Crédito vs. IR')},0)")
        ws[cell(r, "En riesgo (costo muerto)")] = (
            f"=IF(AND({cell(r,'Dividendos')}<=0,{cell(r,'Capitalización')}<=0),"
            f"{cell(r,'Pago a cuenta')},0)")
        ws[cell(r, "IR a pagar")] = (
            f"={cell(r,'IR causado')}-{cell(r,'Crédito vs. IR')}")
        ws[cell(r, "Res. acum. final")] = (
            f"={cell(r,'Res. acum. inicial')}+{cell(r,'Resultado neto')}"
            f"-{cell(r,'Dividendos')}-{cell(r,'Capitalización')}")

        # Comparativo SIN acción (div=cap=0): la base de cada año es el res.
        # acum. acumulado al INICIO del año (= inicio previo + neta previa).
        ws[cell(r, "Res. acum. SIN acción")] = (
            f"={ra25}" if i == 0 else
            f"={cell(r-1,'Res. acum. SIN acción')}+{cell(r-1,'Resultado neto')}")
        base_sin = f"MAX(0,{cell(r,'Res. acum. SIN acción')})"
        ws[cell(r, "Pago SIN acción")] = (
            f"={base_sin}*" + _tarifa_formula(f"({base_sin})", datos)[1:])

        for nm in _PCOLS[4:]:
            cc = ws[cell(r, nm)]
            if nm != "Tarifa":
                cc.number_format = MONEY
            else:
                cc.number_format = PCT

    # Totales.
    tr = first + len(proj_years)
    ws[cell(tr, "Año")] = "TOTAL"
    ws[cell(tr, "Año")].font = BOLD
    for nm in ["Pago a cuenta", "Devolución", "En riesgo (costo muerto)",
               "IR a pagar", "Pago SIN acción"]:
        cl = L(col[nm])
        c = ws[f"{cl}{tr}"]
        c.value = f"=SUM({cl}{first}:{cl}{tr-1})"
        c.number_format = MONEY
        c.font = BOLD
        c.fill = TOTAL_FILL


# ---------------------------------------------------------------- Resumen
def _sheet_resumen(wb, params) -> None:
    ws = wb.create_sheet("Resumen")
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 22
    ws["A1"] = "Planificación tributaria · utilidades no distribuidas"
    ws["A1"].font = GOLD_FONT
    ws["A2"] = params.get("empresa", "")
    ws["A2"].font = BOLD
    if params.get("ruc"):
        ws["A3"] = f"RUC: {params['ruc']}"

    P = "Proyección"
    # Total = última fila de proyección (4 años base + fila total = fila 7).
    items = [
        ("Pago a cuenta (escenario actual)", f"='{P}'!R7"),
        ("Pago a cuenta (SIN acción)", f"='{P}'!Z7"),
        ("Ahorro / diferimiento", f"='{P}'!Z7-'{P}'!R7"),
        ("Devolución acumulada", f"='{P}'!V7"),
        ("En riesgo de costo muerto", f"='{P}'!W7"),
    ]
    r = 5
    for label, formula in items:
        ws[f"A{r}"] = label
        ws[f"A{r}"].font = BOLD
        c = ws[f"B{r}"]
        c.value = formula
        c.number_format = MONEY
        c.font = Font(bold=True, color=NAVY)
        r += 1
    ws[f"A{r+1}"] = ("Parámetros normativos editables — requieren validación "
                     "humana antes de presentar cifras.")
    ws[f"A{r+1}"].font = Font(italic=True, size=9, color="888888")


# ------------------------------------------------------------- utilidades
def _two_col_header(ws, title: str) -> None:
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 34
    for c in ("C", "D", "E"):
        ws.column_dimensions[c].width = 15
    ws["A1"] = title
    ws["A1"].font = GOLD_FONT
    for ci, h in enumerate(["clave", "concepto", "2023", "2024", "2025"]):
        c = ws.cell(row=2, column=ci + 1, value=h)
        c.fill = HEAD_FILL
        c.font = WHITE


# ---------------------------------------------- plantilla balance resumido
def build_plantilla() -> bytes:
    """Genera la plantilla en blanco del 'balance resumido' (.xlsx).

    Una sola hoja con columnas clave|concepto|2023|2024|2025. El profesional
    llena las celdas de año; el parser las lee por encabezado.
    """
    wb = Workbook()
    ws = wb.active
    ws.title = PLANTILLA_SHEET
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 36
    for c in ("C", "D", "E"):
        ws.column_dimensions[c].width = 15

    ws["A1"] = "Balance resumido — informe de auditoría externa"
    ws["A1"].font = GOLD_FONT
    ws["A2"] = "Razón social"
    ws["B2"].fill = INPUT_FILL
    ws["A3"] = "RUC"
    ws["B3"].fill = INPUT_FILL

    hr = 5
    for ci, h in enumerate([PLANTILLA_KEY_HEADER, PLANTILLA_LABEL_HEADER,
                            *schema.ANIOS]):
        c = ws.cell(row=hr, column=ci + 1, value=h)
        c.fill = HEAD_FILL
        c.font = WHITE

    r = hr + 1
    for row in (*schema.ESF_SCHEMA, *schema.ER_SCHEMA):
        if row[0] == "sec":
            ws.cell(row=r, column=2, value=row[1]).font = BOLD
            r += 1
            continue
        if row[0] != "in":
            continue  # las líneas calculadas no se ingresan
        ws.cell(row=r, column=1, value=row[1])
        ws.cell(row=r, column=2, value=row[2])
        for ci in range(3, 6):
            cc = ws.cell(row=r, column=ci)
            cc.fill = INPUT_FILL
            cc.number_format = MONEY
        r += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
