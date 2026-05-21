"""Generador de Excel ejecutivo a partir de una Declaracion Patrimonial (XML del SRI).

Lee un archivo XML de Declaracion Patrimonial y produce un libro .xlsx con
formato premium que incluye:
  - Una hoja por cada grupo de bienes (Dinero, Vehiculos, Bienes Inmuebles,
    Pasivo) con columna editable para el anio siguiente y variaciones.
  - Una hoja "Dashboard" ejecutiva con tarjetas KPI y el resumen separado en
    tres bloques: ACTIVOS, PASIVOS y PATRIMONIO NETO, con graficos.

Uso:
    python tools/declaracion_patrimonial_excel.py ENTRADA.xml [SALIDA.xlsx]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# --- Paleta ejecutiva --------------------------------------------------------

NAVY = "10243E"          # banner principal
NAVY_SOFT = "1F3B5C"     # encabezados de tabla
GOLD = "C8A24B"          # linea de acento
INK = "1A1A1A"           # texto de cifras
GRIS_TXT = "7A7A7A"

ACT = "1E6B52"           # activos (verde)
ACT_L = "E6F0EB"
PAS = "A23B3B"           # pasivos (rojo)
PAS_L = "F4E6E6"
PAT = "20507D"           # patrimonio (azul)
PAT_L = "E2EAF2"

EDIT = "FCEFC9"          # celdas editables
GRIS = "F3F4F6"

FONT_NORMAL = Font(name="Calibri", size=11, color=INK)
FONT_BOLD = Font(name="Calibri", size=11, bold=True, color=INK)
FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")

_THIN = Side(style="thin", color="D0D3D8")
BORDE = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")

MONEDA = '"$"#,##0.00'
PORCENT = '+0.0%;-0.0%;0.0%'

# --- Catalogos de codigos del SRI --------------------------------------------
# Descripciones de referencia para hacer legible el XML. Verificar contra el
# catalogo oficial del SRI si se requiere precision formal.

CAT_TIPO_DEC = {"SOC": "Sociedad conyugal", "IND": "Individual"}
CAT_TIPO_IDENT = {"R": "RUC", "C": "Cedula", "P": "Pasaporte"}
CAT_UBICACION = {"ECU": "Ecuador", "EXT": "Exterior"}
CAT_DINERO_EN = {"IFI": "Institucion financiera", "CAJ": "Caja / efectivo"}
CAT_TIPO_INVERSION = {
    "1": "Cuenta de ahorros",
    "2": "Cuenta corriente",
    "3": "Inversion / poliza",
    "4": "Deposito a plazo",
}
CAT_TIPO_VEHICULO = {
    "1": "Vehiculo terrestre",
    "2": "Aeronave",
    "3": "Embarcacion",
}
CAT_TIPO_INMUEBLE = {
    "1": "Edificacion / casa",
    "2": "Departamento",
    "3": "Terreno",
}
CAT_TIPO_ACREEDOR = {
    "IFI": "Institucion financiera",
    "PER": "Persona natural",
    "EMP": "Empresa",
}
CAT_JUSTIFICACION = {
    "1": "Ingresos por trabajo en relacion de dependencia",
    "2": "Ingresos por actividad empresarial / profesional",
    "3": "Rendimientos financieros",
    "4": "Herencias, legados y donaciones",
    "5": "Loterias, rifas y similares",
    "6": "Otros ingresos / variaciones de mercado",
}


def _txt(node, tag, default=""):
    el = node.find(tag)
    return el.text.strip() if el is not None and el.text else default


def _num(node, tag, default=0.0):
    try:
        return float(_txt(node, tag, "0") or "0")
    except ValueError:
        return default


def _label(catalogo, code):
    code = (code or "").strip()
    return f"{code} - {catalogo[code]}" if code in catalogo else (code or "-")


# --- Parseo del XML ----------------------------------------------------------

def parse_xml(path: Path) -> dict:
    root = ET.parse(path).getroot()
    anio = int(_txt(root, "anio", "0") or 0)

    encabezado = {
        "anio": anio,
        "tipoDec": _label(CAT_TIPO_DEC, _txt(root, "tipoDec")),
        "tipoIdent": _label(CAT_TIPO_IDENT, _txt(root, "tipoIdent")),
        "numIdent": _txt(root, "numIdent"),
        "nombre": _txt(root, "nombre"),
        "tipoIdentCony": _label(CAT_TIPO_IDENT, _txt(root, "tipoIdentCony")),
        "numIdentCony": _txt(root, "numIdentCony"),
        "nombreCony": _txt(root, "nombreCony"),
        "totalCreditos": _num(root, "totalCreditos"),
    }

    pat = root.find("patrimonio")
    patrimonio = {
        "totalDeclarado": _num(pat, "totalDeclarado"),
        "atribuibleHijos": _num(pat, "atribuibleHijos"),
        "sociedadConyugal": _num(pat, "sociedadConyugal"),
        "individual": _num(pat, "individual"),
        "anioAnterior": _num(pat, "anioAnterior"),
        "crecimientoPat": _num(pat, "crecimientoPat"),
    }
    justif = []
    for d in root.iter("detalleJustificacion"):
        justif.append(_label(CAT_JUSTIFICACION, _txt(d, "justificVariacion")))

    dinero = []
    for d in root.iter("detalleDinero"):
        ifi = _txt(d, "nombreIfiExterior") or _txt(d, "ifiEcuador")
        dinero.append({
            "dineroEn": _label(CAT_DINERO_EN, _txt(d, "dineroEn")),
            "tipoInversion": _label(CAT_TIPO_INVERSION, _txt(d, "tipoInversion")),
            "ubicacion": _label(CAT_UBICACION, _txt(d, "ubicacion")),
            "ifi": ifi,
            "moneda": _txt(d, "tipoMoneda"),
            "valor": _num(d, "saldo"),
        })

    vehiculos = []
    for d in root.iter("detalleVehiculos"):
        vehiculos.append({
            "tipoVehiculo": _label(CAT_TIPO_VEHICULO, _txt(d, "tipoVehiculo")),
            "placa": _txt(d, "placa"),
            "ubicacion": _label(CAT_UBICACION, _txt(d, "ubicacion")),
            "valor": _num(d, "valor"),
        })

    inmuebles = []
    for d in root.iter("detalleBienesInmuebles"):
        inmuebles.append({
            "tipoInmueble": _label(CAT_TIPO_INMUEBLE, _txt(d, "tipoInmueble")),
            "ubicacion": _label(CAT_UBICACION, _txt(d, "ubicacion")),
            "claveCat": _txt(d, "claveCat"),
            "fechaInscripcion": _txt(d, "fechaInscripcion"),
            "valor": _num(d, "valor"),
        })

    pasivo = []
    for d in root.iter("detallePasivo"):
        pasivo.append({
            "tipoAcreedor": _label(CAT_TIPO_ACREEDOR, _txt(d, "tipoAcreedor")),
            "nombreAcreedor": _txt(d, "nombreAcreedor"),
            "domicilio": _label(CAT_UBICACION, _txt(d, "domicilioAcreedor")),
            "identAcreedor": _txt(d, "numeroIdentificacionAcreedor"),
            "valor": _num(d, "valorDeuda"),
        })

    return {
        "encabezado": encabezado,
        "patrimonio": patrimonio,
        "justificacion": justif,
        "dinero": dinero,
        "vehiculos": vehiculos,
        "inmuebles": inmuebles,
        "pasivo": pasivo,
    }


# --- Hojas de grupo ----------------------------------------------------------

def _banner(ws, ncols, titulo, subtitulo=""):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=titulo)
    c.font = Font(name="Calibri", size=15, bold=True, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=NAVY)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 30
    if subtitulo:
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=ncols)
        s = ws.cell(row=2, column=1, value=subtitulo)
        s.font = Font(size=10, italic=True, color=GRIS_TXT)
        s.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    # linea de acento dorada
    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=ncols)
    ws.cell(row=3, column=1).fill = PatternFill("solid", fgColor=GOLD)
    ws.row_dimensions[3].height = 5


def _grupo_sheet(wb, nombre, titulo, anio, headers_desc, filas, accent, light):
    ws = wb.create_sheet(nombre)
    ws.sheet_view.showGridLines = False
    ncols = len(headers_desc) + 4
    _banner(ws, ncols, titulo, f"Declaracion {anio}  -  columna {anio + 1} editable")

    hdr_row = 5
    headers = list(headers_desc) + [
        f"Valor {anio}",
        f"Valor {anio + 1}",
        "Variacion",
        "Variacion %",
    ]
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=hdr_row, column=j, value=h)
        c.font = FONT_HEADER
        c.fill = PatternFill("solid", fgColor=NAVY_SOFT)
        c.alignment = CENTER
        c.border = BORDE
    ws.row_dimensions[hdr_row].height = 30

    nd = len(headers_desc)
    col_2025, col_2026, col_var, col_pct = nd + 1, nd + 2, nd + 3, nd + 4
    L25, L26 = get_column_letter(col_2025), get_column_letter(col_2026)

    first = hdr_row + 1
    r = first
    for idx, (descs, valor) in enumerate(filas):
        zebra = PatternFill("solid", fgColor=GRIS) if idx % 2 else None
        for j, d in enumerate(descs, start=1):
            c = ws.cell(row=r, column=j, value=d)
            c.font = FONT_NORMAL
            c.alignment = LEFT
            c.border = BORDE
            if zebra:
                c.fill = zebra
        c25 = ws.cell(row=r, column=col_2025, value=valor)
        c26 = ws.cell(row=r, column=col_2026, value=valor)
        cv = ws.cell(row=r, column=col_var, value=f"={L26}{r}-{L25}{r}")
        cp = ws.cell(row=r, column=col_pct,
                     value=f'=IF({L25}{r}=0,"",({L26}{r}-{L25}{r})/{L25}{r})')
        for c, fmt in ((c25, MONEDA), (c26, MONEDA), (cv, MONEDA), (cp, PORCENT)):
            c.number_format = fmt
            c.font = FONT_NORMAL
            c.border = BORDE
            c.alignment = RIGHT
        if zebra:
            c25.fill = zebra
            cv.fill = zebra
            cp.fill = zebra
        c26.fill = PatternFill("solid", fgColor=EDIT)
        r += 1

    last = r - 1
    for j in range(1, nd + 1):
        cc = ws.cell(row=r, column=j, value="TOTAL" if j == 1 else None)
        cc.font = FONT_HEADER
        cc.fill = PatternFill("solid", fgColor=accent)
        cc.border = BORDE
        cc.alignment = LEFT
    rng = (first, last) if last >= first else (first, first)
    tot25 = ws.cell(row=r, column=col_2025,
                    value=f"=SUM({L25}{rng[0]}:{L25}{rng[1]})")
    tot26 = ws.cell(row=r, column=col_2026,
                    value=f"=SUM({L26}{rng[0]}:{L26}{rng[1]})")
    totv = ws.cell(row=r, column=col_var, value=f"={L26}{r}-{L25}{r}")
    totp = ws.cell(row=r, column=col_pct,
                   value=f'=IF({L25}{r}=0,"",({L26}{r}-{L25}{r})/{L25}{r})')
    for c, fmt in ((tot25, MONEDA), (tot26, MONEDA), (totv, MONEDA), (totp, PORCENT)):
        c.number_format = fmt
        c.font = Font(bold=True, size=11, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=accent)
        c.border = BORDE
        c.alignment = RIGHT
    ws.row_dimensions[r].height = 22

    for j in range(1, nd + 1):
        ws.column_dimensions[get_column_letter(j)].width = 25
    for j in range(nd + 1, ncols + 1):
        ws.column_dimensions[get_column_letter(j)].width = 17

    ws.freeze_panes = ws.cell(row=first, column=1)
    return {"hoja": nombre, "total_row": r,
            "L25": L25, "L26": L26,
            "Lv": get_column_letter(col_var),
            "Lp": get_column_letter(col_pct)}


# --- Dashboard ---------------------------------------------------------------

def _kpi_card(ws, r, c1, c2, label, value_formula, pct_formula, accent, light):
    L1, L2 = get_column_letter(c1), get_column_letter(c2)
    ws.merge_cells(f"{L1}{r}:{L2}{r}")
    ws.cell(row=r, column=c1).fill = PatternFill("solid", fgColor=accent)
    ws.row_dimensions[r].height = 6

    ws.merge_cells(f"{L1}{r + 1}:{L2}{r + 1}")
    lc = ws.cell(row=r + 1, column=c1, value=label)
    lc.font = Font(bold=True, size=10, color=accent)
    lc.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    ws.merge_cells(f"{L1}{r + 2}:{L2}{r + 2}")
    vc = ws.cell(row=r + 2, column=c1, value=value_formula)
    vc.font = Font(bold=True, size=18, color=INK)
    vc.number_format = MONEDA
    vc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[r + 2].height = 30

    cap = ws.cell(row=r + 3, column=c1, value="Var. proyectada")
    cap.font = Font(size=8, color=GRIS_TXT)
    cap.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    pc = ws.cell(row=r + 3, column=c2, value=pct_formula)
    pc.font = Font(bold=True, size=10, color=accent)
    pc.number_format = PORCENT
    pc.alignment = Alignment(horizontal="right", vertical="center", indent=1)

    for rr in range(r + 1, r + 4):
        for c in (c1, c2):
            ws.cell(row=rr, column=c).fill = PatternFill("solid", fgColor=light)
    for rr in range(r, r + 4):
        for c in (c1, c2):
            ws.cell(row=rr, column=c).border = BORDE


def _sec_header(ws, row, texto, accent):
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=7)
    c = ws.cell(row=row, column=2, value=texto)
    c.font = Font(bold=True, size=12, color="FFFFFF")
    c.fill = PatternFill("solid", fgColor=accent)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[row].height = 22


def _col_headers(ws, row, anio):
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
    textos = ["Concepto", None, f"Total {anio}", f"Total {anio + 1}",
              "Variacion", "Variacion %"]
    for j, t in enumerate(textos, start=2):
        c = ws.cell(row=row, column=j, value=t)
        c.font = FONT_HEADER
        c.fill = PatternFill("solid", fgColor=NAVY_SOFT)
        c.alignment = CENTER if j > 3 else LEFT
        if j == 2:
            c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        c.border = BORDE
    ws.row_dimensions[row].height = 24


def _data_row(ws, row, concepto, v2025, v2026, light, *, bold=False,
              total=False, accent=None):
    ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
    cc = ws.cell(row=row, column=2, value=concepto)
    fill = None
    txtcolor = "FFFFFF" if total else INK
    if total:
        fill = PatternFill("solid", fgColor=accent)
    elif light:
        fill = PatternFill("solid", fgColor=light)
    cc.font = Font(bold=bold or total, size=11, color=txtcolor)
    cc.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    c25 = ws.cell(row=row, column=4, value=v2025)
    c26 = ws.cell(row=row, column=5, value=v2026)
    cv = ws.cell(row=row, column=6, value=f"=E{row}-D{row}")
    cp = ws.cell(row=row, column=7,
                 value=f'=IF(D{row}=0,"",(E{row}-D{row})/D{row})')
    for c, fmt in ((c25, MONEDA), (c26, MONEDA), (cv, MONEDA), (cp, PORCENT)):
        c.number_format = fmt
        c.font = Font(bold=bold or total, size=11, color=txtcolor)
        c.alignment = RIGHT
    for c in (cc, c25, c26, cv, cp):
        c.border = BORDE
        if fill:
            c.fill = fill
    ws.row_dimensions[row].height = 20 if not total else 22


def _build_dashboard(wb, data, grupos, anio):
    ws = wb.create_sheet("Dashboard")
    ws.sheet_view.showGridLines = False
    enc = data["encabezado"]
    pat = data["patrimonio"]

    _banner(ws, 8,
            "DECLARACION PATRIMONIAL  -  TABLERO EJECUTIVO",
            f"{enc['nombre']}   |   {enc['tipoIdent']}: {enc['numIdent']}   "
            f"|   {enc['tipoDec']}   |   Comparativo {anio} vs {anio + 1}")

    g = {name: info for name, info in grupos}

    def link(name, attr):
        info = g[name]
        return f"='{info['hoja']}'!{info[attr]}{info['total_row']}"

    # --- Tarjetas KPI (rows 5-8): Activos / Pasivos / Patrimonio ---
    _kpi_card(ws, 5, 2, 3, "TOTAL ACTIVOS", "=D17", "=G17", ACT, ACT_L)
    _kpi_card(ws, 5, 4, 5, "TOTAL PASIVOS", "=D22", "=G22", PAS, PAS_L)
    _kpi_card(ws, 5, 6, 7, "PATRIMONIO NETO", "=D28", "=G28", PAT, PAT_L)

    # --- Seccion ACTIVOS (header 11, datos 13-15, total 16... ajustamos) ---
    _sec_header(ws, 11, "ACTIVOS", ACT)
    _col_headers(ws, 12, anio)
    _data_row(ws, 13, "Dinero e inversiones",
              link("Dinero", "L25"), link("Dinero", "L26"), ACT_L)
    _data_row(ws, 14, "Vehiculos",
              link("Vehiculos", "L25"), link("Vehiculos", "L26"), ACT_L)
    _data_row(ws, 15, "Bienes inmuebles",
              link("Bienes Inmuebles", "L25"),
              link("Bienes Inmuebles", "L26"), ACT_L)
    _data_row(ws, 16, "Total bruto de activos",
              "=SUM(D13:D15)", "=SUM(E13:E15)", ACT_L)
    _data_row(ws, 17, "TOTAL ACTIVOS", "=D16", "=E16", None,
              total=True, accent=ACT)

    # --- Seccion PASIVOS ---
    _sec_header(ws, 19, "PASIVOS", PAS)
    _col_headers(ws, 20, anio)
    _data_row(ws, 21, "Deudas y obligaciones",
              link("Pasivo", "L25"), link("Pasivo", "L26"), PAS_L)
    _data_row(ws, 22, "TOTAL PASIVOS", "=D21", "=E21", None,
              total=True, accent=PAS)

    # --- Seccion PATRIMONIO NETO ---
    _sec_header(ws, 24, "PATRIMONIO NETO", PAT)
    _col_headers(ws, 25, anio)
    _data_row(ws, 26, "(+) Total activos", "=D17", "=E17", PAT_L)
    _data_row(ws, 27, "(-) Total pasivos", "=D22", "=E22", PAT_L)
    _data_row(ws, 28, "(=) PATRIMONIO NETO", "=D26-D27", "=E26-E27", None,
              total=True, accent=PAT)

    # filas informativas (solo control, sin variacion)
    for off, (txt, val) in enumerate([
        (f"Patrimonio declarado en el XML ({anio})", pat["totalDeclarado"]),
        ("Patrimonio neto del anio anterior", pat["anioAnterior"]),
        ("Crecimiento patrimonial declarado (XML)", pat["crecimientoPat"]),
    ]):
        row = 29 + off
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
        cc = ws.cell(row=row, column=2, value=txt)
        cc.font = Font(size=9, italic=True, color=GRIS_TXT)
        cc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        cv = ws.cell(row=row, column=4, value=val)
        cv.number_format = MONEDA
        cv.font = Font(size=9, italic=True, color=GRIS_TXT)
        cv.alignment = RIGHT
        for c in range(2, 8):
            ws.cell(row=row, column=c).border = BORDE
        ws.row_dimensions[row].height = 16

    # --- Bloque consolidado para graficos ---
    _sec_header(ws, 34, "CONSOLIDADO", NAVY_SOFT)
    _col_headers(ws, 35, anio)
    _data_row(ws, 36, "Activos", "=D17", "=E17", ACT_L, bold=True)
    _data_row(ws, 37, "Pasivos", "=D22", "=E22", PAS_L, bold=True)
    _data_row(ws, 38, "Patrimonio neto", "=D28", "=E28", PAT_L, bold=True)

    # --- Graficos ---
    bar = BarChart()
    bar.type = "col"
    bar.grouping = "clustered"
    bar.title = f"Activos / Pasivos / Patrimonio: {anio} vs {anio + 1}"
    bar.style = 10
    bar.add_data(Reference(ws, min_col=4, max_col=5, min_row=35, max_row=38),
                 titles_from_data=True)
    bar.set_categories(Reference(ws, min_col=2, min_row=36, max_row=38))
    bar.height, bar.width = 8.5, 15
    ws.add_chart(bar, "I5")

    pie = PieChart()
    pie.title = f"Composicion de activos {anio}"
    pie.add_data(Reference(ws, min_col=4, min_row=13, max_row=15),
                 titles_from_data=False)
    pie.set_categories(Reference(ws, min_col=2, min_row=13, max_row=15))
    pie.dataLabels = DataLabelList()
    pie.dataLabels.showPercent = True
    pie.height, pie.width = 8.5, 14
    ws.add_chart(pie, "I22")

    barv = BarChart()
    barv.type = "col"
    barv.title = f"Variacion proyectada ({anio} -> {anio + 1})"
    barv.style = 12
    barv.add_data(Reference(ws, min_col=6, max_col=6, min_row=35, max_row=38),
                  titles_from_data=True)
    barv.set_categories(Reference(ws, min_col=2, min_row=36, max_row=38))
    barv.height, barv.width = 8.5, 15
    ws.add_chart(barv, "I39")

    # nota
    nota = ws.cell(row=40, column=2,
                   value="Edite la columna amarilla en las hojas de cada grupo; "
                         "las tarjetas, secciones y graficos se recalculan solos.")
    nota.font = Font(italic=True, size=9, color=GRIS_TXT)

    # anchos
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 14
    for col in ("D", "E", "F", "G"):
        ws.column_dimensions[col].width = 16
    ws.column_dimensions["H"].width = 3


def _build_info(wb, data, anio):
    ws = wb.create_sheet("Datos del XML")
    ws.sheet_view.showGridLines = False
    _banner(ws, 2, "DATOS GENERALES DE LA DECLARACION")

    enc, pat = data["encabezado"], data["patrimonio"]
    filas = [
        ("Anio de la declaracion", enc["anio"]),
        ("Tipo de declaracion", enc["tipoDec"]),
        ("Tipo de identificacion", enc["tipoIdent"]),
        ("Numero de identificacion", enc["numIdent"]),
        ("Nombre del declarante", enc["nombre"]),
        ("Identificacion del conyuge", enc["tipoIdentCony"]),
        ("Numero ident. conyuge", enc["numIdentCony"]),
        ("Nombre del conyuge", enc["nombreCony"]),
        ("Total creditos", enc["totalCreditos"]),
        ("", ""),
        ("Patrimonio total declarado", pat["totalDeclarado"]),
        ("Atribuible a hijos", pat["atribuibleHijos"]),
        ("Sociedad conyugal", pat["sociedadConyugal"]),
        ("Individual", pat["individual"]),
        ("Patrimonio anio anterior", pat["anioAnterior"]),
        ("Crecimiento patrimonial", pat["crecimientoPat"]),
    ]
    r = 5
    for nombre, valor in filas:
        cc = ws.cell(row=r, column=1, value=nombre)
        cc.font = FONT_BOLD
        c = ws.cell(row=r, column=2, value=valor)
        if isinstance(valor, float):
            c.number_format = MONEDA
        c.font = FONT_NORMAL
        if nombre:
            for col in (1, 2):
                ws.cell(row=r, column=col).border = BORDE
        r += 1

    r += 1
    h = ws.cell(row=r, column=1, value="Justificacion de la variacion patrimonial")
    h.font = Font(bold=True, size=12, color=NAVY)
    r += 1
    for j in data["justificacion"]:
        ws.cell(row=r, column=1, value="- " + j).font = FONT_NORMAL
        r += 1

    r += 1
    ws.cell(row=r, column=1,
            value="Nota: las descripciones de codigos son de referencia; "
                  "verificar contra el catalogo oficial del SRI.").font = Font(
        italic=True, size=9, color=GRIS_TXT)

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 46


def build_workbook(data: dict, salida: Path):
    anio = data["encabezado"]["anio"] or 2025
    wb = Workbook()
    wb.remove(wb.active)

    grupos = [
        ("Dinero", _grupo_sheet(
            wb, "Dinero", "DINERO E INVERSIONES", anio,
            ["Ubicacion", "Tipo", "Institucion / detalle", "Moneda"],
            [([d["dineroEn"] + " / " + d["ubicacion"], d["tipoInversion"],
               d["ifi"], d["moneda"]], d["valor"]) for d in data["dinero"]],
            ACT, ACT_L)),
        ("Vehiculos", _grupo_sheet(
            wb, "Vehiculos", "VEHICULOS", anio,
            ["Tipo de vehiculo", "Placa", "Ubicacion"],
            [([d["tipoVehiculo"], d["placa"], d["ubicacion"]], d["valor"])
             for d in data["vehiculos"]],
            ACT, ACT_L)),
        ("Bienes Inmuebles", _grupo_sheet(
            wb, "Bienes Inmuebles", "BIENES INMUEBLES", anio,
            ["Tipo de inmueble", "Ubicacion", "Clave catastral", "Inscripcion"],
            [([d["tipoInmueble"], d["ubicacion"], d["claveCat"],
               d["fechaInscripcion"]], d["valor"]) for d in data["inmuebles"]],
            ACT, ACT_L)),
        ("Pasivo", _grupo_sheet(
            wb, "Pasivo", "PASIVOS / DEUDAS", anio,
            ["Tipo de acreedor", "Acreedor", "Domicilio", "Identificacion"],
            [([d["tipoAcreedor"], d["nombreAcreedor"], d["domicilio"],
               d["identAcreedor"]], d["valor"]) for d in data["pasivo"]],
            PAS, PAS_L)),
    ]

    _build_dashboard(wb, data, grupos, anio)
    _build_info(wb, data, anio)

    wb.move_sheet("Dashboard", offset=-wb.sheetnames.index("Dashboard"))
    wb.active = 0

    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    entrada = Path(argv[1])
    if not entrada.exists():
        print(f"No existe el archivo: {entrada}")
        return 1
    salida = Path(argv[2]) if len(argv) > 2 else entrada.with_suffix(".xlsx")
    data = parse_xml(entrada)
    build_workbook(data, salida)
    print(f"Excel generado: {salida}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
