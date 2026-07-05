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

from openpyxl import Workbook, load_workbook
from openpyxl.chart import AreaChart, BarChart, LineChart, Reference
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
TOTAL_FILL = PatternFill("solid", fgColor="BDD7EE")  # azul claro visible (totales)
DET_FONT = Font(name="Calibri", size=9, italic=True, color="555555")
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
    _verif_utilidad(wb, esf_rows, er_rows)
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
        ("Retención dividendos (%)", "retDiv", 12),
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
        elif kind == "det":  # subcuenta de desglose (valor leído, solo lectura)
            ws[f"B{r}"].font = DET_FONT
            vals = data.get(key) or [0, 0, 0]
            for i, col in enumerate(YEAR_COLS):
                cell = ws[f"{col}{r}"]
                cell.value = _g(key, vals[i] if i < len(vals) else 0)
                cell.number_format = MONEY
                cell.font = DET_FONT
        elif kind == "chk":  # línea de verificación de cuadre (texto)
            ws[f"B{r}"].font = BOLD
            for col in YEAR_COLS:
                ws[f"{col}{r}"].font = BOLD
                ws[f"{col}{r}"].alignment = Alignment(horizontal="center")
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
        # Pasivo + Patrimonio y verificación de cuadre (A = P + Patrimonio).
        ws[f"{col}{rowmap['totalPasPat']}"] = (
            f"={col}{rowmap['totalPasivo']}+{col}{rowmap['totalPat']}")
        act = f"{col}{rowmap['totalActivo']}"
        pp = f"{col}{rowmap['totalPasPat']}"
        ws[f"{col}{rowmap['cuadre']}"] = (
            f'=IF(ABS({act}-{pp})<1,"✓ Cuadra",'
            f'"✗ No cuadra (Δ "&TEXT({act}-{pp},"#,##0")&")")')
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


# ------------------------------------- Verificación utilidad del ejercicio
def _verif_utilidad(wb: Workbook, esf: dict, er: dict) -> None:
    """En la hoja ESF, valida que la 'Utilidad del ejercicio' (patrimonio,
    casillero 615) cuadre con el 'Resultado Neto' del Estado de Resultados.
    Fórmula cruzada ESF↔ER (se escribe tras construir ambas hojas)."""
    if "verUtil" not in esf or "utilEjercicio" not in esf or "neta" not in er:
        return
    ws = wb["ESF"]
    for col in YEAR_COLS:
        ue = f"{col}{esf['utilEjercicio']}"
        nt = f"ER!{col}{er['neta']}"
        ws[f"{col}{esf['verUtil']}"] = (
            f'=IF({ue}=0,"—",IF(ABS({ue}-{nt})<1,"✓ Cuadra",'
            f'"✗ Δ "&TEXT({ue}-{nt},"#,##0")))')


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


# =========================================================================
# Dashboard con GRÁFICOS NATIVOS de Excel (openpyxl.chart)
# =========================================================================
#
# Genera un .xlsx con una hoja "Datos" (tidy, apta para Power BI) y una hoja
# "Dashboard" con gráficos NATIVOS ligados por `Reference` a las celdas de la
# hoja "Datos". Al editar los números en Excel, los gráficos se recalculan
# solos (no se hornean imágenes ni valores estáticos en el gráfico).
#
# Regla suprema (CLAUDE.md): el archivo NO puede levantar el cuadro "Excel
# pudo abrir el archivo reparando…". Al final se recarga con openpyxl para
# validar que el libro es íntegro antes de devolver los bytes.

_HEAD_FONT = Font(name="Calibri", color=GOLD, bold=True, size=11)
_TITLE_FONT = Font(name="Calibri", color=GOLD, bold=True, size=14)
_BLOCK_FONT = Font(name="Calibri", color="FFFFFF", bold=True, size=11)


def _dseries(data: dict, key: str) -> list[float]:
    """Serie de valores por período de una clave del modelo D."""
    vals = data.get(key) or []
    return [0.0 if v is None else float(v) for v in vals]


def _dabs(data: dict, key: str) -> list[float]:
    """Serie en valor absoluto (pasivos/costos pueden venir positivos)."""
    return [abs(v) for v in _dseries(data, key)]


def _at(seq: list[float], i: int) -> float:
    return seq[i] if i < len(seq) else 0.0


def build_dashboard_workbook(
    data: dict,
    labels: list[str],
    meses: list[int],
    empresa: str,
    chart_style: str = "combo",
) -> bytes:
    """Arma un libro con hoja de datos + gráficos NATIVOS y devuelve los bytes.

    Los gráficos referencian rangos de la hoja "Datos" mediante `Reference`,
    por lo que se actualizan solos al editar los datos en Excel.

    Args:
        data: modelo D (`data[clave]` = lista de valores por período).
        labels: etiquetas de cada período (columnas de datos / categorías).
        meses: meses por período (metadato, no altera los cálculos).
        empresa: razón social para el título.
        chart_style: 'barras' | 'lineas' | 'area' | 'combo' (default).
    """
    n = len(labels)
    if n == 0:
        n = len(_dseries(data, "ventas")) or 1
        labels = [str(i + 1) for i in range(n)]
    style = (chart_style or "combo").strip().lower()

    wb = Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Datos")
    ws_dash = wb.create_sheet("Dashboard")

    ws.column_dimensions["A"].width = 30
    for i in range(n):
        ws.column_dimensions[get_column_letter(2 + i)].width = 16

    last_col = get_column_letter(1 + n)

    ws["A1"] = f"AUDIT-IA · {empresa} · Datos del Dashboard"
    ws["A1"].font = _TITLE_FONT
    if n >= 1:
        ws.merge_cells(f"A1:{last_col}1")

    def _write_header(row: int, first_label: str) -> None:
        c = ws.cell(row=row, column=1, value=first_label)
        c.font = _HEAD_FONT
        c.fill = HEAD_FILL
        for i in range(n):
            hc = ws.cell(row=row, column=2 + i, value=labels[i])
            hc.font = Font(name="Calibri", color="FFFFFF", bold=True)
            hc.fill = HEAD_FILL
            hc.alignment = Alignment(horizontal="center")

    def _write_row(row: int, label: str, vals: list[float], fmt: str = MONEY) -> None:
        ws.cell(row=row, column=1, value=label).font = BOLD
        for i in range(n):
            cc = ws.cell(row=row, column=2 + i, value=round(_at(vals, i), 4))
            cc.number_format = fmt
            cc.border = BORDER

    def _block_title(row: int, text: str) -> None:
        c = ws.cell(row=row, column=1, value=text)
        c.font = _BLOCK_FONT
        for i in range(n + 1):
            ws.cell(row=row, column=1 + i).fill = HEAD_FILL

    # Series calculadas (todas por período).
    ventas = _dseries(data, "ventas")
    otros_ing = _dseries(data, "otrosIng")
    otros_ing_fin = _dseries(data, "otrosIngFin")
    costo = _dabs(data, "costo")
    g_admin = _dabs(data, "gAdmin")
    g_fin = _dabs(data, "gFin")
    part_trab = _dabs(data, "partTrab")
    ir_causado = _dabs(data, "irCausado")
    imp_dif = _dabs(data, "impDif")

    ub = [_at(ventas, i) - _at(costo, i) for i in range(n)]
    gastos_op = [_at(g_admin, i) + _at(g_fin, i) for i in range(n)]
    neta = [
        _at(ventas, i) - _at(costo, i) - _at(g_admin, i) - _at(g_fin, i)
        + _at(otros_ing, i) + _at(otros_ing_fin, i)
        - _at(part_trab, i) - _at(ir_causado, i) - _at(imp_dif, i)
        for i in range(n)
    ]

    # =============== Bloque ESTADO DE RESULTADOS ===============
    row = 3
    _block_title(row, "ESTADO DE RESULTADOS")
    row += 1
    er_head = row
    _write_header(row, "Concepto")
    row += 1
    er_ing_row = row
    _write_row(row, "Ingresos ordinarios", ventas)
    row += 1
    er_costo_row = row
    _write_row(row, "Costo de ventas", costo)
    row += 1
    _write_row(row, "Utilidad bruta", ub)
    row += 1
    _write_row(row, "Gastos operativos", gastos_op)
    row += 1
    er_neta_row = row
    _write_row(row, "Utilidad neta", neta)
    row += 2

    # =============== Bloque BALANCE ===============
    _block_title(row, "BALANCE")
    row += 1
    bal_head = row
    _write_header(row, "Cuenta")
    row += 1
    bal_first = row
    balance_rows = [
        ("Efectivo", _dabs(data, "efectivo")),
        ("Cuentas por cobrar", _dabs(data, "cxc")),
        ("Inventario", _dabs(data, "inventario")),
        ("Propiedad planta y equipo", _dabs(data, "ppe")),
        ("Capital", _dabs(data, "capital")),
        ("Resultados acumulados", _dabs(data, "resAcum")),
    ]
    for label, vals in balance_rows:
        _write_row(row, label, vals)
        row += 1
    # Filas de las 4 cuentas de composición (Efectivo/CxC/Inventario/PP&E).
    bal_comp_first = bal_first
    bal_comp_last = bal_first + 3
    row += 1

    # =============== Bloque MÁRGENES (%) ===============
    _block_title(row, "MÁRGENES (%)")
    row += 1
    mar_head = row
    _write_header(row, "Indicador")
    row += 1
    mb = [(_at(ub, i) / _at(ventas, i)) if _at(ventas, i) else 0.0 for i in range(n)]
    mn = [(_at(neta, i) / _at(ventas, i)) if _at(ventas, i) else 0.0 for i in range(n)]
    mar_bruto_row = row
    _write_row(row, "Margen bruto", mb, fmt="0.0%")
    row += 1
    mar_neto_row = row
    _write_row(row, "Margen neto", mn, fmt="0.0%")

    # ------------------------------------------------------------------
    # GRÁFICOS NATIVOS -> hoja "Dashboard", ligados por Reference a "Datos".
    # ------------------------------------------------------------------
    min_data_col, max_data_col = 2, 1 + n

    ws_dash["A1"] = f"AUDIT-IA · {empresa} · Dashboard"
    ws_dash["A1"].font = _TITLE_FONT

    cats = Reference(ws, min_col=min_data_col, max_col=max_data_col,
                     min_row=er_head, max_row=er_head)

    def _mk(cls: type):
        ch = cls()
        ch.style = 10
        ch.width = 18
        ch.height = 9
        ch.x_axis.title = "Período"
        ch.y_axis.title = "USD"
        return ch

    # --- (a) Resultados: Ingresos, Costo, Utilidad neta por período ---
    if style in ("barras", "lineas", "area"):
        cls_map = {"barras": BarChart, "lineas": LineChart, "area": AreaChart}
        chart_a = _mk(cls_map[style])
        if style == "barras":
            chart_a.type = "col"
        for rrow in (er_ing_row, er_costo_row, er_neta_row):
            data_ref = Reference(ws, min_col=1, max_col=max_data_col,
                                 min_row=rrow, max_row=rrow)
            chart_a.add_data(data_ref, titles_from_data=True, from_rows=True)
        chart_a.set_categories(cats)
    else:  # combo (default): barras (Ingresos, Costo) + línea (Utilidad neta)
        chart_a = _mk(BarChart)
        chart_a.type = "col"
        for rrow in (er_ing_row, er_costo_row):
            data_ref = Reference(ws, min_col=1, max_col=max_data_col,
                                 min_row=rrow, max_row=rrow)
            chart_a.add_data(data_ref, titles_from_data=True, from_rows=True)
        chart_a.set_categories(cats)
        line = _mk(LineChart)
        neta_ref = Reference(ws, min_col=1, max_col=max_data_col,
                             min_row=er_neta_row, max_row=er_neta_row)
        line.add_data(neta_ref, titles_from_data=True, from_rows=True)
        line.set_categories(cats)
        line.y_axis.axId = 200  # eje secundario para el combo
        chart_a += line
    chart_a.title = "Resultados por período"
    ws_dash.add_chart(chart_a, "A3")

    # --- (b) Composición del Balance: Efectivo/CxC/Inventario/PP&E ---
    chart_b = _mk(BarChart)
    chart_b.type = "col"
    chart_b.grouping = "clustered"
    chart_b.title = "Composición del Balance"
    cats_b = Reference(ws, min_col=min_data_col, max_col=max_data_col,
                       min_row=bal_head, max_row=bal_head)
    comp_ref = Reference(ws, min_col=1, max_col=max_data_col,
                         min_row=bal_comp_first, max_row=bal_comp_last)
    chart_b.add_data(comp_ref, titles_from_data=True, from_rows=True)
    chart_b.set_categories(cats_b)
    ws_dash.add_chart(chart_b, "A22")

    # --- (c) Tendencia de márgenes: Margen bruto y Margen neto ---
    chart_c = _mk(LineChart)
    chart_c.title = "Tendencia de márgenes"
    chart_c.y_axis.numFmt = "0.0%"
    chart_c.y_axis.title = "%"
    cats_c = Reference(ws, min_col=min_data_col, max_col=max_data_col,
                       min_row=mar_head, max_row=mar_head)
    mar_ref = Reference(ws, min_col=1, max_col=max_data_col,
                        min_row=mar_bruto_row, max_row=mar_neto_row)
    chart_c.add_data(mar_ref, titles_from_data=True, from_rows=True)
    chart_c.set_categories(cats_c)
    ws_dash.add_chart(chart_c, "A41")

    # --- Guardar + VALIDACIÓN OBLIGATORIA (regla suprema) ---
    buf = io.BytesIO()
    wb.save(buf)
    raw = buf.getvalue()
    load_workbook(io.BytesIO(raw))  # si estuviera corrupto, lanzaría
    return raw


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
