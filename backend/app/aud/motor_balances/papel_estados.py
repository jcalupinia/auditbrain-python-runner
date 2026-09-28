"""Papel de trabajo del análisis de estados financieros (NIA 315 / NIA 520).

Arma el `.xlsx` desde la salida de ``analisis.analizar``: hojas ESF y ERI con
los valores homologados (datos) y las columnas Variación, Var % y Vertical %
como **fórmulas**; hoja Ratios cuyos valores son fórmulas que remiten a las
celdas del ESF/ERI; y hoja «NIA 520» con la expectativa, la diferencia (fórmula)
y la marca de lo que supera el umbral. Escapa texto que parece fórmula.
"""
from __future__ import annotations

import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_AZUL = "0A2342"
_BLANCO = "FFFFFF"
_FONDO_TOTAL = "E8EEF6"
_F_TITULO = Font(name="Calibri", size=14, bold=True, color=_AZUL)
_F_SUB = Font(name="Calibri", size=9, italic=True, color="6B7280")
_F_ENCAB = Font(name="Calibri", size=10, bold=True, color=_BLANCO)
_F_DATO = Font(name="Calibri", size=9)
_F_TOTAL = Font(name="Calibri", size=10, bold=True, color=_AZUL)
_RELLENO_ENCAB = PatternFill("solid", fgColor=_AZUL)
_RELLENO_ALERTA = PatternFill("solid", fgColor="F6E0E0")
_THIN = Side(style="thin", color="B8C4D0")
_BORDE = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_DER = Alignment(horizontal="right")
_IZQ = Alignment(horizontal="left", vertical="top", wrap_text=True)
_CEN = Alignment(horizontal="center")
_FMT_MONEDA = '#,##0.00'
_FMT_PCT = '0.00%'
_FMT_VECES = '0.00'
_FILA0 = 4  # fila de datos (encabezados en la fila 3)


def _seguro(v) -> str:
    s = "" if v is None else str(v)
    return " " + s if s[:1] in ("=", "+", "-", "@") else s


def _encabezados(ws, fila, titulos):
    for c, t in enumerate(titulos, start=1):
        cel = ws.cell(row=fila, column=c, value=t)
        cel.font = _F_ENCAB
        cel.fill = _RELLENO_ENCAB
        cel.border = _BORDE
        cel.alignment = _CEN


def _hoja_estado(wb, titulo_hoja, titulo, estado, es_activa=False):
    """Escribe una hoja de estado y devuelve (ws, {codigo: fila_excel}, col_ultimo_periodo)."""
    ws = wb.active if es_activa else wb.create_sheet(titulo_hoja)
    if es_activa:
        ws.title = titulo_hoja
    ws.sheet_view.showGridLines = False
    periodos = estado.get("periodos", [])
    lineas = estado.get("lineas", [])
    n = len(periodos)
    ws["A1"] = titulo
    ws["A1"].font = _F_TITULO
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 46
    # Columnas: A Código, B Rubro, C.. períodos, Variación, Var %, Vertical %
    cols = ["Código", "Rubro"] + list(periodos) + ["Variación", "Var %", "Vertical %"]
    _encabezados(ws, _FILA0 - 1, cols)
    for idx in range(3, 3 + n + 3):
        ws.column_dimensions[get_column_letter(idx)].width = 15
    col_p0 = 3                      # primera columna de período
    col_pu = col_p0 + n - 1         # última columna de período
    col_var = col_pu + 1
    col_pct = col_var + 1
    col_ver = col_pct + 1
    L = get_column_letter
    base_codigo = estado.get("base_codigo")
    filas_por_codigo = {l["codigo"]: (_FILA0 + i) for i, l in enumerate(lineas)}
    fila_base = filas_por_codigo.get(base_codigo)

    for i, l in enumerate(lineas):
        r = _FILA0 + i
        es_total = len(str(l["codigo"])) <= 1
        ws.cell(row=r, column=1, value=_seguro(l["codigo"])).font = _F_DATO
        cel_rub = ws.cell(row=r, column=2, value=_seguro(l["etiqueta"]))
        cel_rub.font = _F_TOTAL if es_total else _F_DATO
        cel_rub.alignment = _IZQ
        for j in range(n):
            cel = ws.cell(row=r, column=col_p0 + j, value=round(float(l["valores"][j]), 2))
            cel.number_format = _FMT_MONEDA
            cel.alignment = _DER
            cel.font = _F_DATO
        if n >= 2:
            cprev, cact = L(col_pu - 1), L(col_pu)
            cv = ws.cell(row=r, column=col_var, value=f"={cact}{r}-{cprev}{r}")
            cv.number_format = _FMT_MONEDA; cv.alignment = _DER; cv.font = _F_DATO
            cp = ws.cell(row=r, column=col_pct,
                         value=f"=IF({cprev}{r}=0,\"\",({cact}{r}-{cprev}{r})/{cprev}{r})")
            cp.number_format = _FMT_PCT; cp.alignment = _DER; cp.font = _F_DATO
        if fila_base:
            cu = L(col_pu)
            cver = ws.cell(row=r, column=col_ver,
                           value=f"=IF({cu}${fila_base}=0,\"\",{cu}{r}/{cu}${fila_base})")
            cver.number_format = _FMT_PCT; cver.alignment = _DER; cver.font = _F_DATO
        for c in range(1, col_ver + 1):
            ws.cell(row=r, column=c).border = _BORDE
    ws.freeze_panes = f"A{_FILA0}"
    return ws, filas_por_codigo, col_pu


def _hoja_ratios(wb, ratios, filas_esf, filas_eri, col_pu):
    ws = wb.create_sheet("Ratios")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Ratios financieros de la firma"
    ws["A1"].font = _F_TITULO
    ws.column_dimensions["A"].width = 32
    periodos = ratios.get("periodos", [])
    n = len(periodos)
    _encabezados(ws, _FILA0 - 1, ["Ratio"] + list(periodos))
    for idx in range(2, 2 + n):
        ws.column_dimensions[get_column_letter(idx)].width = 16
    L = get_column_letter
    hoja = {"esf": ("ESF", filas_esf), "eri": ("ERI", filas_eri)}

    def _codigos(spec):
        return [spec[1], spec[2]] if isinstance(spec, (list, tuple)) else [spec]

    def _ref(origen, spec, j):
        """Referencia Excel al componente, o None si algún código no está en la
        hoja (línea en cero, filtrada): el ratio cae a valor literal."""
        nombre_hoja, filas = hoja[origen]
        col = L(3 + j)  # C = primer período en ESF/ERI
        if any(c not in filas for c in _codigos(spec)):
            return None
        if isinstance(spec, (list, tuple)):
            _, a, b = spec
            return f"('{nombre_hoja}'!{col}{filas[a]}-'{nombre_hoja}'!{col}{filas[b]})"
        return f"'{nombre_hoja}'!{col}{filas[spec]}"

    from backend.app.aud.motor_balances.analisis import RATIOS
    spec_por_nombre = {r[0]: r for r in RATIOS}
    for i, fila in enumerate(ratios.get("filas", [])):
        r = _FILA0 + i
        ws.cell(row=r, column=1, value=_seguro(fila["nombre"])).font = _F_TOTAL
        _, num_spec, den_spec, origen, fmt = spec_por_nombre[fila["nombre"]]
        for j in range(n):
            num = _ref(origen, num_spec, j)
            den = _ref(origen, den_spec, j)
            valor = fila["valores"][j] if j < len(fila["valores"]) else None
            if num is not None and den is not None:
                celda_val = f"=IF({den}=0,\"\",{num}/{den})"
            else:  # caso borde: algún componente en cero/ausente → valor calculado
                celda_val = round(valor, 6) if valor is not None else ""
            cel = ws.cell(row=r, column=2 + j, value=celda_val)
            cel.number_format = _FMT_PCT if fmt == "pct" else _FMT_VECES
            cel.alignment = _DER; cel.font = _F_DATO
        for c in range(1, 2 + n):
            ws.cell(row=r, column=c).border = _BORDE


def _hoja_nia520(wb, expectativa, titulo):
    ws = wb.create_sheet("NIA 520")
    ws.sheet_view.showGridLines = False
    ws["A1"] = "Expectativa vs. real (NIA 520)"
    ws["A1"].font = _F_TITULO
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 46
    for c in "CDEF":
        ws.column_dimensions[c].width = 15
    ws.column_dimensions["G"].width = 12
    if not expectativa.get("aplicable"):
        ws.cell(row=3, column=1, value="Se requieren al menos dos períodos para la expectativa NIA 520.").font = _F_SUB
        return
    umbral = expectativa.get("umbral_pct", 0.10)
    ws["A2"] = f"{titulo} · umbral de diferencia: {umbral:.0%}"
    ws["A2"].font = _F_SUB
    _encabezados(ws, _FILA0 - 1, ["Código", "Rubro", "Expectativa", "Real", "Diferencia", "Dif %", "¿Explicar?"])
    for i, l in enumerate(expectativa.get("lineas", [])):
        r = _FILA0 + i
        ws.cell(row=r, column=1, value=_seguro(l["codigo"])).font = _F_DATO
        cr = ws.cell(row=r, column=2, value=_seguro(l["etiqueta"])); cr.font = _F_DATO; cr.alignment = _IZQ
        ws.cell(row=r, column=3, value=round(l["expectativa"], 2)).number_format = _FMT_MONEDA
        ws.cell(row=r, column=4, value=round(l["real"], 2)).number_format = _FMT_MONEDA
        cd = ws.cell(row=r, column=5, value=f"=D{r}-C{r}"); cd.number_format = _FMT_MONEDA
        cp = ws.cell(row=r, column=6, value=f"=IF(C{r}=0,\"\",(D{r}-C{r})/C{r})"); cp.number_format = _FMT_PCT
        marca = "Explicar" if l["supera_umbral"] else ""
        cm = ws.cell(row=r, column=7, value=marca); cm.alignment = _CEN; cm.font = _F_TOTAL
        for c in range(1, 8):
            cel = ws.cell(row=r, column=c)
            cel.border = _BORDE
            if l["supera_umbral"]:
                cel.fill = _RELLENO_ALERTA


def generar_papel_estados(analisis: dict) -> bytes:
    """`.xlsx` del análisis de estados financieros."""
    wb = Workbook()
    ws_esf, filas_esf, col_pu = _hoja_estado(
        wb, "ESF", "Estado de Situación Financiera — análisis", analisis["esf"], es_activa=True)
    _hoja_estado(wb, "ERI", "Estado de Resultados Integral — análisis", analisis["eri"])
    filas_eri = {l["codigo"]: (_FILA0 + i) for i, l in enumerate(analisis["eri"]["lineas"])}
    _hoja_ratios(wb, analisis["ratios"], filas_esf, filas_eri, col_pu)
    _hoja_nia520(wb, analisis["expectativa_esf"], "Estado de Situación Financiera")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
