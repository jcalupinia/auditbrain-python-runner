"""Generador de Excel interactivo a partir de una Declaracion Patrimonial (XML del SRI).

Lee un archivo XML de Declaracion Patrimonial y produce un libro .xlsx con:
  - Una hoja por cada grupo de bienes (Dinero, Vehiculos, Bienes Inmuebles, Pasivo).
  - Columna con el valor declarado del anio del XML (ej. 2025).
  - Columna EDITABLE para el anio siguiente (ej. 2026).
  - Columnas de variacion (absoluta y %) calculadas con formulas que se
    actualizan solas al escribir los valores del anio 2026.
  - Una hoja "Dashboard" con totales por grupo, variaciones y graficos.

Uso:
    python tools/declaracion_patrimonial_excel.py ENTRADA.xml [SALIDA.xlsx]
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# --- Estilos -----------------------------------------------------------------

AZUL = "1F4E78"
AZUL_CLARO = "D9E1F2"
GRIS = "F2F2F2"
VERDE = "E2EFDA"
AMARILLO_EDIT = "FFF2CC"
NARANJA = "C55A11"

FONT_TITULO = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
FONT_NORMAL = Font(name="Calibri", size=11)
FONT_BOLD = Font(name="Calibri", size=11, bold=True)

FILL_TITULO = PatternFill("solid", fgColor=AZUL)
FILL_HEADER = PatternFill("solid", fgColor=AZUL)
FILL_EDIT = PatternFill("solid", fgColor=AMARILLO_EDIT)
FILL_TOTAL = PatternFill("solid", fgColor=AZUL_CLARO)

_THIN = Side(style="thin", color="BFBFBF")
BORDE = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT = Alignment(horizontal="left", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center")

MONEDA = '#,##0.00'
PORCENT = '0.0%'

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


# --- Construccion del Excel --------------------------------------------------

def _titulo(ws, texto, ncols):
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws.cell(row=1, column=1, value=texto)
    c.font = FONT_TITULO
    c.fill = FILL_TITULO
    c.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 26


def _set_headers(ws, row, headers):
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=row, column=j, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = CENTER
        c.border = BORDE
    ws.row_dimensions[row].height = 30


def _grupo_sheet(wb, nombre, titulo, anio, headers_desc, filas, signo_deuda=False):
    """Crea una hoja de grupo. `filas` es lista de (lista_descripciones, valor).

    Columnas: descripciones... | Valor {anio} | Valor {anio+1} (editable) |
              Variacion absoluta | Variacion %
    """
    ws = wb.create_sheet(nombre)
    ncols = len(headers_desc) + 4
    _titulo(ws, titulo, ncols)

    hdr_row = 3
    headers = list(headers_desc) + [
        f"Valor {anio}",
        f"Valor {anio + 1}  (editable)",
        "Variacion",
        "Variacion %",
    ]
    _set_headers(ws, hdr_row, headers)

    nd = len(headers_desc)
    col_2025 = nd + 1
    col_2026 = nd + 2
    col_var = nd + 3
    col_pct = nd + 4
    L25 = get_column_letter(col_2025)
    L26 = get_column_letter(col_2026)

    first = hdr_row + 1
    r = first
    for descs, valor in filas:
        for j, d in enumerate(descs, start=1):
            c = ws.cell(row=r, column=j, value=d)
            c.font = FONT_NORMAL
            c.alignment = LEFT
            c.border = BORDE
        c25 = ws.cell(row=r, column=col_2025, value=valor)
        c25.number_format = MONEDA
        c25.font = FONT_NORMAL
        c25.border = BORDE
        c25.alignment = RIGHT

        c26 = ws.cell(row=r, column=col_2026, value=valor)
        c26.number_format = MONEDA
        c26.font = FONT_NORMAL
        c26.fill = FILL_EDIT
        c26.border = BORDE
        c26.alignment = RIGHT

        cv = ws.cell(row=r, column=col_var, value=f"={L26}{r}-{L25}{r}")
        cv.number_format = MONEDA
        cv.font = FONT_NORMAL
        cv.border = BORDE
        cv.alignment = RIGHT

        cp = ws.cell(row=r, column=col_pct,
                     value=f'=IF({L25}{r}=0,"",({L26}{r}-{L25}{r})/{L25}{r})')
        cp.number_format = PORCENT
        cp.font = FONT_NORMAL
        cp.border = BORDE
        cp.alignment = RIGHT
        r += 1

    last = r - 1
    # Fila de totales
    tcell = ws.cell(row=r, column=1, value="TOTAL")
    tcell.font = FONT_BOLD
    for j in range(1, nd + 1):
        ws.cell(row=r, column=j).fill = FILL_TOTAL
        ws.cell(row=r, column=j).border = BORDE
    if last >= first:
        sum25 = f"=SUM({L25}{first}:{L25}{last})"
        sum26 = f"=SUM({L26}{first}:{L26}{last})"
    else:
        sum25 = sum26 = 0
    for col, formula in ((col_2025, sum25), (col_2026, sum26)):
        c = ws.cell(row=r, column=col, value=formula)
        c.number_format = MONEDA
        c.font = FONT_BOLD
        c.fill = FILL_TOTAL
        c.border = BORDE
        c.alignment = RIGHT
    Lv = get_column_letter(col_2025)
    Lw = get_column_letter(col_2026)
    cvt = ws.cell(row=r, column=col_var, value=f"={Lw}{r}-{Lv}{r}")
    cvt.number_format = MONEDA
    cvt.font = FONT_BOLD
    cvt.fill = FILL_TOTAL
    cvt.border = BORDE
    cvt.alignment = RIGHT
    cpt = ws.cell(row=r, column=col_pct,
                  value=f'=IF({Lv}{r}=0,"",({Lw}{r}-{Lv}{r})/{Lv}{r})')
    cpt.number_format = PORCENT
    cpt.font = FONT_BOLD
    cpt.fill = FILL_TOTAL
    cpt.border = BORDE
    cpt.alignment = RIGHT
    ws.row_dimensions[r].height = 20

    # Anchos de columna
    for j in range(1, nd + 1):
        ws.column_dimensions[get_column_letter(j)].width = 26
    for j in range(nd + 1, ncols + 1):
        ws.column_dimensions[get_column_letter(j)].width = 18

    ws.freeze_panes = ws.cell(row=first, column=1)
    ws.sheet_view.showGridLines = False

    return {"hoja": nombre, "total_row": r, "col_2025": col_2025,
            "col_2026": col_2026, "col_var": col_var, "col_pct": col_pct}


def build_workbook(data: dict, salida: Path):
    anio = data["encabezado"]["anio"] or 2025
    wb = Workbook()
    wb.remove(wb.active)

    # --- Hojas de grupo ---
    grupos = []

    grupos.append(("Dinero", _grupo_sheet(
        wb, "Dinero", "DINERO E INVERSIONES", anio,
        ["Ubicacion", "Tipo", "Institucion / detalle", "Moneda"],
        [([d["dineroEn"] + " / " + d["ubicacion"], d["tipoInversion"],
           d["ifi"], d["moneda"]], d["valor"]) for d in data["dinero"]],
    )))

    grupos.append(("Vehiculos", _grupo_sheet(
        wb, "Vehiculos", "VEHICULOS", anio,
        ["Tipo de vehiculo", "Placa", "Ubicacion"],
        [([d["tipoVehiculo"], d["placa"], d["ubicacion"]], d["valor"])
         for d in data["vehiculos"]],
    )))

    grupos.append(("Bienes Inmuebles", _grupo_sheet(
        wb, "Bienes Inmuebles", "BIENES INMUEBLES", anio,
        ["Tipo de inmueble", "Ubicacion", "Clave catastral", "Inscripcion"],
        [([d["tipoInmueble"], d["ubicacion"], d["claveCat"],
           d["fechaInscripcion"]], d["valor"]) for d in data["inmuebles"]],
    )))

    grupos.append(("Pasivo", _grupo_sheet(
        wb, "Pasivo", "PASIVOS / DEUDAS", anio,
        ["Tipo de acreedor", "Acreedor", "Domicilio", "Identificacion"],
        [([d["tipoAcreedor"], d["nombreAcreedor"], d["domicilio"],
           d["identAcreedor"]], d["valor"]) for d in data["pasivo"]],
    )))

    _build_dashboard(wb, data, grupos, anio)
    _build_info(wb, data, anio)

    # Orden de hojas: Dashboard primero
    wb.move_sheet("Dashboard", offset=-wb.sheetnames.index("Dashboard"))
    wb.active = 0

    salida.parent.mkdir(parents=True, exist_ok=True)
    wb.save(salida)


def _build_dashboard(wb, data, grupos, anio):
    ws = wb.create_sheet("Dashboard")
    ws.sheet_view.showGridLines = False
    _titulo(ws, f"DASHBOARD - DECLARACION PATRIMONIAL {anio} vs {anio + 1}", 7)

    enc = data["encabezado"]
    ws.cell(row=2, column=1, value=f"Declarante: {enc['nombre']}  |  "
            f"{enc['tipoIdent']}: {enc['numIdent']}  |  {enc['tipoDec']}").font = FONT_BOLD

    # Tabla resumen por grupo
    hdr = 4
    headers = ["Grupo", f"Total {anio}", f"Total {anio + 1}",
               "Variacion", "Variacion %"]
    _set_headers(ws, hdr, headers)

    r = hdr + 1
    primera_fila_datos = r
    activos_rows = []
    for nombre, info in grupos:
        tr = info["total_row"]
        L25 = get_column_letter(info["col_2025"])
        L26 = get_column_letter(info["col_2026"])
        hoja = f"'{info['hoja']}'"
        ws.cell(row=r, column=1, value=nombre).font = FONT_NORMAL
        c25 = ws.cell(row=r, column=2, value=f"={hoja}!{L25}{tr}")
        c26 = ws.cell(row=r, column=3, value=f"={hoja}!{L26}{tr}")
        cv = ws.cell(row=r, column=4, value=f"=C{r}-B{r}")
        cp = ws.cell(row=r, column=5, value=f'=IF(B{r}=0,"",(C{r}-B{r})/B{r})')
        for c in (c25, c26, cv):
            c.number_format = MONEDA
        cp.number_format = PORCENT
        for col in range(1, 6):
            cc = ws.cell(row=r, column=col)
            cc.border = BORDE
            cc.font = FONT_NORMAL
            if col >= 2:
                cc.alignment = RIGHT
        if nombre != "Pasivo":
            activos_rows.append(r)
        r += 1

    ultima_fila_grupos = r - 1
    pasivo_row = ultima_fila_grupos  # Pasivo es el ultimo grupo

    # Fila Total Activos
    a0, a1 = activos_rows[0], activos_rows[-1]
    ws.cell(row=r, column=1, value="TOTAL ACTIVOS").font = FONT_BOLD
    for col, letra in ((2, "B"), (3, "C"), (4, "D")):
        c = ws.cell(row=r, column=col,
                    value=f"=SUM({letra}{a0}:{letra}{a1})")
        c.number_format = MONEDA
        c.font = FONT_BOLD
    cp = ws.cell(row=r, column=5, value=f'=IF(B{r}=0,"",(C{r}-B{r})/B{r})')
    cp.number_format = PORCENT
    cp.font = FONT_BOLD
    for col in range(1, 6):
        ws.cell(row=r, column=col).fill = FILL_TOTAL
        ws.cell(row=r, column=col).border = BORDE
    total_activos_row = r
    r += 1

    # Fila Patrimonio Neto = Activos - Pasivo
    ws.cell(row=r, column=1, value="PATRIMONIO NETO (Activos - Pasivo)").font = FONT_BOLD
    for col, letra in ((2, "B"), (3, "C"), (4, "D")):
        c = ws.cell(row=r, column=col,
                    value=f"={letra}{total_activos_row}-{letra}{pasivo_row}")
        c.number_format = MONEDA
        c.font = FONT_BOLD
    cp = ws.cell(row=r, column=5, value=f'=IF(B{r}=0,"",(C{r}-B{r})/B{r})')
    cp.number_format = PORCENT
    cp.font = FONT_BOLD
    fill_neto = PatternFill("solid", fgColor=VERDE)
    for col in range(1, 6):
        ws.cell(row=r, column=col).fill = fill_neto
        ws.cell(row=r, column=col).border = BORDE
    patrimonio_neto_row = r
    r += 1

    # KPIs / tarjetas
    r += 1
    ws.cell(row=r, column=1, value="INDICADORES CLAVE").font = Font(
        bold=True, size=12, color=AZUL)
    r += 1
    kpis = [
        (f"Patrimonio declarado {anio}", f"=B{patrimonio_neto_row}", MONEDA),
        (f"Patrimonio declarado (XML) {anio}",
         data["patrimonio"]["totalDeclarado"], MONEDA),
        (f"Patrimonio anio anterior", data["patrimonio"]["anioAnterior"], MONEDA),
        (f"Crecimiento patrimonial (XML)",
         data["patrimonio"]["crecimientoPat"], MONEDA),
        (f"Variacion proyectada {anio}->{anio + 1}",
         f"=D{patrimonio_neto_row}", MONEDA),
        (f"Variacion % proyectada {anio}->{anio + 1}",
         f"=E{patrimonio_neto_row}", PORCENT),
    ]
    for nombre, valor, fmt in kpis:
        ws.cell(row=r, column=1, value=nombre).font = FONT_NORMAL
        c = ws.cell(row=r, column=2, value=valor)
        c.number_format = fmt
        c.font = FONT_BOLD
        c.alignment = RIGHT
        for col in (1, 2):
            ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor=GRIS)
            ws.cell(row=r, column=col).border = BORDE
        r += 1

    # Anchos
    ws.column_dimensions["A"].width = 38
    for col in "BCDE":
        ws.column_dimensions[col].width = 18
    ws.column_dimensions["F"].width = 4

    # --- Graficos ---
    # Grafico de barras: total por grupo 2025 vs 2026
    bar = BarChart()
    bar.type = "col"
    bar.title = f"Total por grupo: {anio} vs {anio + 1}"
    bar.style = 10
    datos = Reference(ws, min_col=2, max_col=3,
                      min_row=hdr, max_row=ultima_fila_grupos)
    cats = Reference(ws, min_col=1, min_row=primera_fila_datos,
                     max_row=ultima_fila_grupos)
    bar.add_data(datos, titles_from_data=True)
    bar.set_categories(cats)
    bar.height = 9
    bar.width = 16
    ws.add_chart(bar, "H4")

    # Grafico de pastel: composicion de activos 2025
    pie = PieChart()
    pie.title = f"Composicion de activos {anio}"
    pdatos = Reference(ws, min_col=2, min_row=primera_fila_datos,
                       max_row=ultima_fila_grupos - 1)
    pcats = Reference(ws, min_col=1, min_row=primera_fila_datos,
                      max_row=ultima_fila_grupos - 1)
    pie.add_data(pdatos, titles_from_data=False)
    pie.set_categories(pcats)
    pie.height = 9
    pie.width = 14
    ws.add_chart(pie, "H22")

    # Grafico de barras: variacion por grupo
    barv = BarChart()
    barv.type = "col"
    barv.title = f"Variacion proyectada por grupo ({anio}->{anio + 1})"
    barv.style = 12
    vdatos = Reference(ws, min_col=4, max_col=4,
                       min_row=hdr, max_row=ultima_fila_grupos)
    barv.add_data(vdatos, titles_from_data=True)
    barv.set_categories(cats)
    barv.height = 9
    barv.width = 16
    ws.add_chart(barv, "H39")

    ws.cell(row=hdr - 1, column=1,
            value="Edite la columna amarilla en cada hoja de grupo; "
                  "los totales, variaciones y graficos se actualizan solos.").font = Font(
        italic=True, size=9, color="808080")


def _build_info(wb, data, anio):
    ws = wb.create_sheet("Datos del XML")
    ws.sheet_view.showGridLines = False
    _titulo(ws, "DATOS GENERALES DE LA DECLARACION", 4)

    enc = data["encabezado"]
    pat = data["patrimonio"]
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
    r = 3
    for nombre, valor in filas:
        ws.cell(row=r, column=1, value=nombre).font = FONT_BOLD
        c = ws.cell(row=r, column=2, value=valor)
        if isinstance(valor, float):
            c.number_format = MONEDA
        c.font = FONT_NORMAL
        for col in (1, 2):
            ws.cell(row=r, column=col).border = BORDE
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Justificacion de la variacion patrimonial").font = Font(
        bold=True, size=12, color=AZUL)
    r += 1
    for j in data["justificacion"]:
        ws.cell(row=r, column=1, value="- " + j).font = FONT_NORMAL
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Nota: las descripciones de codigos son de "
            "referencia; verificar contra el catalogo oficial del SRI.").font = Font(
        italic=True, size=9, color="808080")

    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 44


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
