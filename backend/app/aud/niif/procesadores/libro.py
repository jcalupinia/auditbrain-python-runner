"""Papel de trabajo (Excel con fórmulas, HTML autónomo, Word y PowerPoint) de una prueba con procesador.

El exportador del sitio arma el papel de las pruebas declarativas en el
navegador; el de un procesador lo arma aquí el servidor con las cédulas que el
propio procesador calculó (``run["hojas"]``), más carátula, programa, fuentes,
conclusión y bitácora del registro.
"""
from __future__ import annotations

import html as _html
import io
import math
import re
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from backend.app.aud.niif.procesadores import estilo_ejecutivo as est
from backend.app.aud.niif.procesadores import graficos

NAVY, GOLD, BLANCO, CELESTE = "0A2342", "C7A83C", "FFFFFF", "DCE6F1"
_FINO = Side(style="thin", color="B7C0CC")
_DOBLE = Side(style="double", color="0A2342")
_BORDE = Border(left=_FINO, right=_FINO, top=_FINO, bottom=_FINO)
_BORDE_TOTAL = Border(left=_FINO, right=_FINO, top=_DOBLE, bottom=_DOBLE)
_FMT = {"n": "#,##0.00", "p": "0.00%", "i": "#,##0", "a": "0", "d": "yyyy-mm-dd"}


_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _excel(v, fmt):
    """Valor que se escribe en la celda: la fórmula (editable y trazable) si la
    hay; las fechas ISO como fecha de Excel, para que las fórmulas operen con ellas."""
    if isinstance(v, dict):
        return "=" + v["f"]
    if fmt in ("d", "x") and isinstance(v, str) and _ISO.match(v):
        return date.fromisoformat(v)
    return _seguro(v)


def _valor(v):
    return v.get("v") if isinstance(v, dict) else v


def _seguro(v):
    """Texto que Excel no confunda con una fórmula (regla del proyecto)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@"):
        return "'" + v
    return v


def _contexto(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> list[dict]:
    e = reg.get("engagement") or {}
    run = reg.get("run") or {}
    caratula = [
        ["Firma", e.get("firm") or "AuditConsulting Auditores Cía. Ltda."], ["Cliente", e.get("client")], ["RUC", e.get("ruc")],
        ["Ejercicio", e.get("year")], ["Fecha de corte", e.get("cutoff")], ["Marco contable", e.get("framework")],
        ["Herramienta", definicion.get("name")], ["Rubro", definicion.get("area")], ["Motor", run.get("engine")],
        ["Versión del papel", f"v{version}"], ["Estado", est.estado_es(estado)], ["Preparó", e.get("preparer")], ["Revisó", e.get("reviewer")],
        ["Aprobó", reg.get("approvedBy") or ""], ["Fecha de aprobación", (reg.get("approvedAt") or "")[:10]],
        ["Huella de la ejecución (SHA-256)", reg.get("runHash") or ""],
    ]
    if reg.get("taxApplicable"):
        caratula.append(["Tratamiento tributario revisado", reg.get("taxScope") or ""])
        meta = reg.get("taxScopeMeta") or {}
        if meta:
            caratula.append(["Sustento tributario · revisión",
                             f"{meta.get('resumen', '')} · {meta.get('actor', '')} · {(meta.get('fecha') or '')[:19].replace('T', ' ')}"])
    fuentes = [[s.get("category"), s.get("document"), s.get("section"), s.get("url"), "Sí" if s.get("verified") else "No"]
               for s in reg.get("sources") or []]
    fuentes += [["NIA · " + x.get("document", ""), x.get("requirement", ""), x.get("section", ""), "", ""]
                for x in definicion.get("nia") or [] if isinstance(x, dict)]
    c = reg.get("reconciliation") or {}
    cierre = [
        ["Conciliación con el mayor", f"Población {c.get('total')} · mayor {c.get('ledger')} · diferencia {c.get('difference')}"
         + (f" · aceptación: {c.get('acceptance')}" if c.get("acceptance") and not c.get("within") else "")],
        ["Evaluación de excepciones", reg.get("exceptionReview") or ""],
        ["Análisis", reg.get("analysis") or ""], ["Conclusión", reg.get("conclusion") or ""],
    ]
    return [
        {"name": "00_Caratula", "label": "Carátula", "cols": [["Concepto", "t"], ["Detalle", "t"]], "rows": caratula, "total": None},
        {"name": "00_Programa", "label": "Programa", "total": None,
         "cols": [["Código", "t"], ["Objetivo", "t"], ["Afirmación", "t"], ["Procedimiento", "t"], ["Evidencia", "t"], ["Criterio", "t"], ["Referencia", "t"]],
         "rows": [[p.get("code"), p.get("objective"), p.get("assertion"), p.get("procedure"), p.get("evidence"), p.get("criterion"), p.get("reference")]
                  for p in reg.get("program") or []]},
        {"name": "00_Fuentes", "label": "Base técnica", "total": None,
         "cols": [["Categoría", "t"], ["Documento", "t"], ["Párrafos", "t"], ["URL", "t"], ["Verificada", "t"]], "rows": fuentes},
    ], [
        {"name": "13_Conclusion", "label": "Conclusión", "cols": [["Concepto", "t"], ["Detalle", "t"]], "rows": cierre, "total": None},
        {"name": "14_Control_Revision", "label": "Control de revisión", "total": None,
         "cols": [["Fecha", "t"], ["Acción", "t"], ["Estado anterior", "t"], ["Estado nuevo", "t"], ["Actor", "t"], ["Comentario", "t"]],
         "rows": [[(x.get("fecha") or "")[:19].replace("T", " "), est.accion_es(x.get("accion")),
                   est.estado_es(x.get("estado_anterior")), est.estado_es(x.get("estado_nuevo")),
                   x.get("actor"), x.get("comentario")] for x in eventos]},
    ]


def cedulas(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> list[dict]:
    antes, despues = _contexto(definicion, reg, eventos, version, estado)
    return antes + ((reg.get("run") or {}).get("hojas") or []) + despues


def _titulos_unicos(hojas: list[dict]) -> list[str]:
    """Nombres de hoja (≤31) únicos, en el orden de las cédulas."""
    titulos, vistos = [], set()
    for h in hojas:
        base = h["name"][:31]
        t, k = base, 1
        while t in vistos:
            k += 1
            t = f"{base[:28]}_{k}"
        vistos.add(t)
        titulos.append(t)
    return titulos


def _ref(hoja: str, celda: str = "A1") -> str:
    return f"#'{hoja}'!{celda}"


def _boton(ws, celda: str, texto: str, destino: str, S, nav=False):
    c = ws[celda]
    c.value = texto
    c.hyperlink = destino
    c.font = S["boton_nav"] if nav else S["boton"]
    c.fill = S["fill_boton_nav"] if nav else S["fill_boton"]
    c.alignment = S["centro"]
    c.border = S["borde"]


def _panel_inicio(ws, S, definicion, reg, titulos, hojas, estado, version):
    e = reg.get("engagement") or {}
    run = reg.get("run") or {}
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    for col in "BCDEF":
        ws.column_dimensions[col].width = 27  # botones con rótulos largos sin truncar
    # Banda de marca
    ws.merge_cells("B2:F3")
    b = ws["B2"]
    b.value = "AuditConsulting Auditores Cía. Ltda.  ·  AUDIT-IA"
    b.font = S["marca"]
    b.fill = S["fill_marca"]
    b.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    for r in (2, 3):
        for col in "BCDEF":
            ws[f"{col}{r}"].fill = S["fill_marca"]
    ws.merge_cells("B4:F4")
    ws["B4"].value = definicion.get("name", "")
    ws["B4"].font = S["titulo"]
    # Datos del encargo
    datos = [("Cliente", e.get("client")), ("RUC", e.get("ruc")), ("Marco contable", e.get("framework")),
             ("Fecha de corte", e.get("cutoff")), ("Preparó", e.get("preparer")), ("Revisó", e.get("reviewer"))]
    fila = 6
    for i, (etq, val) in enumerate(datos):
        col = "B" if i % 2 == 0 else "D"
        ecol, vcol = col, chr(ord(col) + 1)
        ws[f"{ecol}{fila}"].value = etq
        ws[f"{ecol}{fila}"].font = S["kpi_etq"]
        ws[f"{vcol}{fila}"].value = _seguro(val)
        ws[f"{vcol}{fila}"].font = S["dato"]
        if i % 2 == 1:
            fila += 1
    # Tarjetas KPI
    totales = run.get("totals") or {}
    etiquetas = run.get("labels") or {}
    prim = run.get("primary")
    n_prob = len(run.get("exceptions") or [])
    kpis = []
    if prim and prim in totales:
        kpis.append((etiquetas.get(prim, prim), totales.get(prim), "n", None))
    for k in ("perdida", "cartera", "provReg", "ajuste"):
        if k in totales and k != prim:
            kpis.append((etiquetas.get(k, k), totales.get(k), "n", None))
    kpis.append(("Problemas encontrados", n_prob, "i", est.color_semaforo(n_prob)))
    kfila = fila + 1
    ws[f"B{kfila}"].value = "INDICADORES CLAVE"
    ws[f"B{kfila}"].font = S["subtitulo"]
    kfila += 1
    for i, (etq, val, fmt, semaforo) in enumerate(kpis[:6]):
        col = "BCD"[i % 3] if i < 3 else "BCD"[i % 3]
        base_col = ["B", "C", "D"][i % 3]
        base_row = kfila + (i // 3) * 3
        _tarjeta_kpi(ws, base_col, base_row, etq, val, fmt, semaforo, S)
    ultima_kpi = kfila + ((len(kpis[:6]) - 1) // 3) * 3 + 2
    # Grilla de botones de navegación a cada cédula
    nav_row = ultima_kpi + 2
    ws[f"B{nav_row}"].value = "IR A LA CÉDULA"
    ws[f"B{nav_row}"].font = S["subtitulo"]
    nav_row += 1
    for i, (h, t) in enumerate(zip(hojas, titulos)):
        col = ["B", "C", "D", "E"][i % 4]
        row = nav_row + (i // 4)
        _boton(ws, f"{col}{row}", h.get("label", t), _ref(t), S)
        ws.row_dimensions[row].height = 32  # rótulos largos en dos líneas, sin truncar
    ws.print_options.horizontalCentered = True
    _print_setup(ws, e)
    return nav_row + max(0, (len(hojas) - 1) // 4)


def _tarjeta_kpi(ws, col, row, etq, val, fmt, semaforo, S):
    c2 = chr(ord(col) + 0)
    ws[f"{col}{row}"].value = etq
    ws[f"{col}{row}"].font = S["kpi_etq"]
    ws[f"{col}{row}"].alignment = Alignment(wrap_text=True, vertical="bottom")
    ws.row_dimensions[row].height = max(ws.row_dimensions[row].height or 0, 30)
    v = ws[f"{col}{row + 1}"]
    if fmt == "i":
        v.value = int(val) if isinstance(val, (int, float)) else val
        v.number_format = "#,##0"
    else:
        try:
            v.value = float(str(val).replace(",", "")) if val not in (None, "") else 0
            v.number_format = est.FMT["n"]
        except (ValueError, TypeError):
            v.value = _seguro(val)
    v.font = S["kpi_valor"]
    for r in (row, row + 1):
        ws[f"{col}{r}"].fill = S["fill_panel"]
        ws[f"{col}{r}"].border = S["borde"]
    if semaforo:
        from openpyxl.styles import Font as _F
        v.font = _F(name=est.FONT_CIFRA, size=18, bold=True, color=semaforo)


def _print_setup(ws, e):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    firma = e.get("firm") or "AuditConsulting Auditores Cía. Ltda."
    ws.oddFooter.left.text = firma
    ws.oddFooter.center.text = str(e.get("client") or "")
    ws.oddFooter.right.text = "Página &P de &N"


def _hoja_ejecutiva(ws, S, h, titulo_prueba, nav, hojas=None):
    ws.sheet_view.showGridLines = False
    # Encabezado: título, prueba/corte y botones de navegación
    ws.merge_cells("A1:F1")
    ws["A1"].value = _seguro(h["label"])
    ws["A1"].font = S["titulo"]
    ws.merge_cells("A2:F2")
    ws["A2"].value = _seguro(titulo_prueba)
    ws["A2"].font = S["subtitulo"]
    if nav.get("inicio"):
        _boton(ws, "H1", "⟵ Inicio", _ref(nav["inicio"]), S, nav=True)
    if nav.get("anterior"):
        _boton(ws, "I1", "◀ Anterior", _ref(nav["anterior"]), S, nav=True)
    if nav.get("siguiente"):
        _boton(ws, "J1", "Siguiente ▶", _ref(nav["siguiente"]), S, nav=True)
    # Cabecera de la tabla
    fila_enc = 4
    anchos = [len(c[0]) + 2 for c in h["cols"]]
    for j, (nombre, _) in enumerate(h["cols"], start=1):
        c = ws.cell(row=fila_enc, column=j, value=nombre)
        c.font = S["encabezado"]
        c.fill = S["fill_encabezado"]
        c.alignment = S["centro"]
        c.border = S["borde_enc"]
    ws.row_dimensions[fila_enc].height = 30
    # Subrayado dorado bajo el título de la cédula
    for j in range(1, max(6, len(h["cols"])) + 1):
        ws.cell(row=2, column=j).border = S["filete_oro"]
    filas = [(r, False) for r in h["rows"]] + ([(h["total"], True)] if h.get("total") else [])
    for i, (fila, total) in enumerate(filas, start=fila_enc + 1):
        for j, ((_, fmt), v) in enumerate(zip(h["cols"], fila), start=1):
            c = ws.cell(row=i, column=j, value=_excel(v, fmt))
            es_num = fmt in est.FMT or (fmt == "x" and isinstance(_valor(v), (int, float)))
            c.font = S["total"] if total else (S["cifra"] if es_num else S["dato"])
            c.border = S["borde_total"] if total else S["borde_fila"]
            if total:
                c.fill = S["fill_total"]
            elif (i - fila_enc) % 2 == 0:
                c.fill = S["fill_zebra"]   # filas alternas
            if isinstance(c.value, date):
                c.number_format = est.FMT["d"]
                c.alignment = S["centro"]
            elif fmt in est.FMT:
                c.number_format = est.FMT[fmt]
                c.alignment = S["der"]
            elif es_num:
                c.alignment = S["der"]
            else:
                c.alignment = S["izq"]
            vista = _valor(v)
            anchos[j - 1] = max(anchos[j - 1], min(60, len(str(vista if vista is not None else "")) + 2))
    for j, w in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(j)].width = max(12, min(60, w))
    ws.freeze_panes = f"A{fila_enc + 1}"
    _bloque_como_se_calcula(ws, S, h, len(filas) + fila_enc + 2, hojas)
    _print_setup(ws, {})



def _q(titulo: str) -> str:
    """Nombre de hoja citado para una fórmula: 'Hoja con espacios'!"""
    return "'" + titulo.replace("'", "''") + "'!"


def _barras_excel(ws, titulo, cat_ref, val_ref, alto_items, ancla):
    """Gráfico de barras nativo con el estilo del papel (una serie, sin cuadrícula,
    solo el valor como etiqueta, rótulos al borde para no pisar negativos)."""
    from openpyxl.chart import BarChart
    from openpyxl.chart.label import DataLabelList

    ch = BarChart()
    ch.type = "bar"
    ch.title = titulo
    ch.legend = None
    ch.gapWidth = 60
    ch.add_data(val_ref, titles_from_data=True)
    ch.set_categories(cat_ref)
    serie = ch.series[0]
    serie.graphicalProperties.solidFill = est.SERIE
    serie.graphicalProperties.line.noFill = True
    serie.invertIfNegative = False
    ch.x_axis.scaling.orientation = "maxMin"   # primer concepto arriba, como en la tabla
    ch.x_axis.tickLblPos = "low"               # rótulos al borde: no pisan barras negativas
    ch.x_axis.delete = False
    ch.y_axis.delete = False
    ch.y_axis.numFmt = "#,##0"
    ch.y_axis.majorGridlines = None
    ch.dataLabels = DataLabelList()
    ch.dataLabels.showVal = True
    # Explícitos: si faltan, algunos lectores (LibreOffice) añaden categoría y serie.
    ch.dataLabels.showCatName = False
    ch.dataLabels.showSerName = False
    ch.dataLabels.showLegendKey = False
    ch.dataLabels.showPercent = False
    ch.dataLabels.numFmt = "#,##0.00"
    ch.height = max(7.0, 0.72 * alto_items + 3.0)
    ch.width = 21.5  # ancho del panel (B:F): rótulos completos en una línea
    ws.add_chart(ch, ancla)
    return ch.height


def _graficos_dashboard(ws, S, hojas, titulos, fila):
    """Sección «PANORAMA» del panel 00_Inicio (el ÚNICO dashboard del libro).
    Los datos de cada gráfico son fórmulas a las cédulas (trazables y vivos):
    - Cifras del resumen: ='<Resumen>'!A5 / !B5 … (sin las tasas %, para no
      mezclar unidades en el eje de USD).
    - Hallazgos de mayor impacto: SUMIFS sobre la hoja de problemas por código
      (positivos − negativos = importe absoluto); el resto en «Otros»."""
    from openpyxl.chart import Reference

    ws[f"B{fila}"].value = "PANORAMA"
    ws[f"B{fila}"].font = S["subtitulo"]
    ancla_fila = fila + 2  # una fila de aire: el título no queda bajo el borde del gráfico
    col_a = 14  # N:O … bloque de datos de los gráficos (a la derecha del panel)
    ws.column_dimensions[get_column_letter(col_a)].width = 34
    ws.column_dimensions[get_column_letter(col_a + 1)].width = 16
    ws.cell(row=fila, column=col_a, value="Datos de los gráficos (fórmulas a las cédulas)").font = S["nota"]
    r = fila + 1
    fuente = Font(name=est.FONT_TEXTO, size=8, color="8A94A6")

    def bloque(titulo, filas_formula):
        nonlocal r
        cab = r
        ws.cell(row=cab, column=col_a, value=titulo).font = fuente
        ws.cell(row=cab, column=col_a + 1, value="Importe (USD)").font = fuente
        for etq, val in filas_formula:
            r += 1
            ws.cell(row=r, column=col_a, value=etq).font = fuente
            c = ws.cell(row=r, column=col_a + 1, value=val)
            c.font = fuente
            c.number_format = est.FMT["n"]
        ini, fin = cab + 1, r
        r += 2
        return (Reference(ws, min_col=col_a, min_row=ini, max_row=fin),
                Reference(ws, min_col=col_a + 1, min_row=cab, max_row=fin), fin - ini + 1)

    idx_res = next((i for i, h in enumerate(hojas) if [c[1] for c in h.get("cols", [])] == ["t", "n"]), None)
    if idx_res is not None:
        h, q = hojas[idx_res], _q(titulos[idx_res])
        filas = [(f"={q}A{5 + i}", f"={q}B{5 + i}") for i, f in enumerate(h.get("rows", []))
                 if len(f) > 1 and "%" not in str(f[0]) and isinstance(graficos._num(f[1]), float)]
        if filas:
            cats, vals, n = bloque("Cifras del resumen", filas)
            alto_cm = _barras_excel(ws, "Cifras del resumen (USD)", cats, vals, n, f"B{ancla_fila}")
            ancla_fila += math.ceil(alto_cm / 0.53) + 2  # filas de 15 pt ≈ 0,53 cm

    idx_p = next((i for i, h in enumerate(hojas) if [c[0] for c in h.get("cols", [])] == ["Código", "Descripción", "Importe"]), None)
    if idx_p is not None and hojas[idx_p].get("rows"):
        h, q = hojas[idx_p], _q(titulos[idx_p])
        n_rows = len(h["rows"])
        A, C = f"{q}$A$5:$A${4 + n_rows}", f"{q}$C$5:$C${4 + n_rows}"
        abs_de = lambda crit: f'SUMIFS({C},{A},{crit},{C},">0")-SUMIFS({C},{A},{crit},{C},"<0")'  # noqa: E731
        run_like = {"exceptions": [{"code": f[0], "amount": graficos._num(f[2])} for f in h["rows"]]}
        top = graficos.codigos_top(run_like)
        if top:
            filas = [(etq, "=" + abs_de(f'"{codigo}"')) for codigo, etq in top["top"]]
            if top["otros"]:
                total = f'SUMIF({C},">0")-SUMIF({C},"<0")'
                suma_top = "+".join(f"({abs_de(chr(34) + c + chr(34))})" for c, _ in top["top"])
                filas.append((top["otros"], f"={total}-({suma_top})"))
            cats, vals, n = bloque("Hallazgos de mayor impacto", filas)
            alto_cm = _barras_excel(ws, "Hallazgos de mayor impacto (USD)", cats, vals, n, f"B{ancla_fila}")
            ancla_fila += math.ceil(alto_cm / 0.53) + 2
    # Se imprime el panel (A:L); el bloque de datos de los gráficos (N:O) queda fuera.
    ws.print_area = f"A1:L{max(ancla_fila, r)}"

def _bloque_como_se_calcula(ws, S, h, fila_inicio, hojas=None):
    """Escribe, debajo de la tabla, el bloque «ⓘ Cómo se calcula esta hoja» en
    lenguaje sencillo (una fila por columna con fórmula). No se imprime cortado:
    va en su propia banda con fondo claro y borde."""
    bloque = como_se_calcula(h, hojas)
    if not bloque:
        return
    r = fila_inicio
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    t = ws.cell(row=r, column=1, value="ⓘ  Cómo se calcula esta hoja")
    t.font = S["subtitulo"]
    t.fill = S["fill_gold"]
    t.alignment = S["izq"]
    r += 1
    encabez = ["Columna", "Fórmula (Excel)", "Cómo se calcula (sencillo)", "Ejemplo con números reales", "De dónde viene", "Norma"]
    for j, txt in enumerate(encabez, start=1):
        c = ws.cell(row=r, column=j, value=txt)
        c.font = S["encabezado"]
        c.fill = S["fill_encabezado"]
        c.alignment = S["centro"]
        c.border = S["borde"]
    for b in bloque:
        r += 1
        celdas = [b["columna"], _seguro(b["formula"]), b["explicacion"], b["ejemplo"], b["origen"], b.get("norma") or "—"]
        for j, val in enumerate(celdas, start=1):
            c = ws.cell(row=r, column=j, value=val)
            c.font = S["cifra"] if j == 2 else S["dato"]
            c.fill = S["fill_panel"]
            c.alignment = S["izq"]
            c.border = S["borde"]
    ws.print_area = None


def xlsx(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """Papel de trabajo ejecutivo: panel 00_Inicio con marca, KPIs y navegación,
    y cada cédula como hoja «tipo software» (sin cuadrícula, botones de
    navegación, semáforo, impresión horizontal). Las celdas con fórmula se
    escriben como fórmula viva (trazable)."""
    S = est.estilos(Font, PatternFill, Border, Side, Alignment)
    wb = Workbook()
    wb.remove(wb.active)
    hojas = cedulas(definicion, reg, eventos, version, estado)
    titulos = _titulos_unicos(hojas)
    titulo_prueba = f"{definicion.get('name', '')} · {(reg.get('engagement') or {}).get('client', '')} · corte {(reg.get('engagement') or {}).get('cutoff', '')}"

    inicio = wb.create_sheet("00_Inicio")
    fin_panel = _panel_inicio(inicio, S, definicion, reg, titulos, hojas, estado, version)
    _graficos_dashboard(inicio, S, hojas, titulos, fin_panel + 2)

    for idx, (h, t) in enumerate(zip(hojas, titulos)):
        ws = wb.create_sheet(t)
        nav = {"inicio": "00_Inicio",
               "anterior": titulos[idx - 1] if idx > 0 else None,
               "siguiente": titulos[idx + 1] if idx < len(titulos) - 1 else None}
        _hoja_ejecutiva(ws, S, h, titulo_prueba, nav, hojas)
    wb.calculation.fullCalcOnLoad = True  # el gráfico y las fórmulas se calculan al abrir
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _celda(v, fmt) -> str:
    v = _valor(v)
    if v is None or v == "":
        return ""
    if fmt in ("n", "p", "i", "a") and not isinstance(v, (int, float)):
        return _html.escape(str(v))          # texto en una columna numérica («No aplica», «—»)
    if fmt == "n" or (fmt == "x" and isinstance(v, (int, float))):
        return f"{float(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if fmt == "p":
        return f"{float(v) * 100:.2f} %".replace(".", ",")
    if fmt == "i":
        return f"{int(v):,}".replace(",", ".")
    if fmt == "a":                               # año: 2025, nunca «2.025»
        return str(int(v))
    return _html.escape(str(v))


def _filas(h):
    return [(r, False) for r in h["rows"]] + ([(h["total"], True)] if h.get("total") else [])


# --- «Cómo se calcula esta hoja» ---------------------------------------------
# Se GENERA desde la misma definición de la cédula que produce las fórmulas
# (h["cols"]/h["rows"] con celdas {"f":…,"v":…}). Una sola fuente: si la fórmula
# cambia, la explicación cambia.
_REF = re.compile(r"(?:'([^']+)'!)?\$?([A-Z]{1,3})\$?(\d+)")
# Referencia a celda o a rango, con hoja opcional: 'Hoja'!$A$5:$A$24 · B5 · $B$8
_REF_RANGO = re.compile(r"(?:'([^']+)'!)?\$?([A-Z]{1,3})\$?(\d+)(?::\$?([A-Z]{1,3})\$?(\d+))?")
_TEXTO_FORMULA = re.compile(r'"[^"]*"')
_COLUMNA_COMPLETA = re.compile(r"(?:'([^']+)'!)?\$?([A-Z]{1,3}):\$?([A-Z]{1,3})(?![0-9A-Za-z])")
FILA_DATOS = 5  # los datos de toda cédula arrancan en la fila 5 (fila 4 = encabezado)

# Plantilla de respaldo cuando una columna calculada NO tiene explicación escrita en
# la definición de su cédula. Nunca debe llegar al papel: el test
# tests/test_aud_explicaciones_humanas.py falla si alguna la usa.
PLANTILLA_GENERICA = "se obtiene con la fórmula indicada"


def _fmt_num(v, fmt) -> str:
    return _celda(v, fmt if fmt in ("n", "p", "i", "a") else "n")


def _mapa_hojas(hojas) -> dict:
    return {h["name"]: h for h in (hojas or [])}


def _celda_de(h: dict, letra: str, num: int):
    """(valor, formato, encabezado) de la celda letra+num de la cédula h."""
    j = column_index_from_string(letra) - 1
    cols = h.get("cols") or []
    fmt = cols[j][1] if 0 <= j < len(cols) else "n"
    enc = cols[j][0] if 0 <= j < len(cols) else letra
    i = num - FILA_DATOS
    filas = h.get("rows") or []
    if 0 <= i < len(filas):
        fila = filas[i]
    elif i == len(filas) and h.get("total"):
        fila = h["total"]
    else:
        return None, fmt, enc
    return (_valor(fila[j]) if 0 <= j < len(fila) else None), fmt, enc


def _muestra(v, fmt) -> str:
    """Valor de una celda para leerlo dentro del ejemplo (texto entre comillas)."""
    if v is None or v == "":
        return "(vacío)"
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return _fmt_num(v, fmt)
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return f"«{_html.unescape(str(v))}»"


def _ejemplo_fila1(formula: str, h: dict, mapa: dict, fmt: str) -> str:
    """El cálculo de la FILA 1 con sus números reales: cada celda de la fórmula se
    reemplaza por su valor (de esta hoja o de la hoja citada) y cada rango por el
    nombre de la columna y la hoja de donde sale. Siempre devuelve el cálculo y el
    resultado; nunca queda vacío."""
    textos = []

    def guarda(m):  # protege los textos literales ("<=0", "Sí") de la sustitución
        textos.append(m.group(0))
        return f"\x00{len(textos) - 1}\x00"

    expr = _TEXTO_FORMULA.sub(guarda, formula)
    # Separador de argumentos «;» (como Excel en español): con decimales es-EC la
    # coma ya es parte de los números. Se hace ANTES de sustituir los valores.
    expr = expr.replace(",", "; ")

    def sustituye(m):
        hoja_ref, l1, n1, l2, n2_ = m.group(1), m.group(2), int(m.group(3)), m.group(4), m.group(5)
        destino = mapa.get(hoja_ref, h) if hoja_ref else h
        nombre_hoja = (destino.get("label") or hoja_ref) if hoja_ref else None
        if l2:  # rango → «Columna» de Hoja (n filas)
            _, _, enc = _celda_de(destino, l1, n1)
            n = int(n2_) - n1 + 1
            donde = f" de «{nombre_hoja}»" if nombre_hoja else ""
            return f"[«{enc}»{donde}, {n} fila{'s' if n != 1 else ''}]"
        v, f_cel, _ = _celda_de(destino, l1, n1)
        if v is None and hoja_ref and hoja_ref not in mapa:
            return m.group(0)
        return _muestra(v, f_cel)

    def columna_completa(m):  # 'Hoja'!$F:$F → [«Columna» de «Hoja», columna completa]
        hoja_ref, l1 = m.group(1), m.group(2)
        destino = mapa.get(hoja_ref, h) if hoja_ref else h
        _, _, enc = _celda_de(destino, l1, FILA_DATOS)
        donde = f" de «{destino.get('label') or hoja_ref}»" if hoja_ref else ""
        return f"[«{enc}»{donde}, columna completa]"

    expr = _COLUMNA_COMPLETA.sub(columna_completa, expr)
    expr = _REF_RANGO.sub(sustituye, expr)
    expr = re.sub("\x00(\\d+)\x00", lambda m: textos[int(m.group(1))], expr)
    return expr


def como_se_calcula(h: dict, hojas: list | None = None) -> list[dict]:
    """Filas del bloque «Cómo se calcula esta hoja»: una por columna CALCULADA.

    - ``explicacion``: la escrita por una persona en la definición de la cédula
      (``hoja(..., explica={...})``). Si falta, se usa la plantilla genérica, que
      los tests rechazan.
    - ``ejemplo``: el cálculo de la fila 1 con sus números reales y el resultado.
    - ``origen``: las columnas de ESTA hoja y las hojas de donde salen los datos
      (una referencia a otra hoja se nombra por esa hoja, no por una columna de
      esta, que era el error anterior).
    ``hojas`` (todas las cédulas del papel) permite leer valores de otras hojas."""
    filas = h.get("rows") or []
    if not filas:
        return []
    mapa = _mapa_hojas(hojas)
    mapa.setdefault(h["name"], h)
    cols = [c[0] for c in h["cols"]]
    header_por_letra = {get_column_letter(j + 1): cols[j] for j in range(len(cols))}
    escritas = h.get("explica") or {}
    bloque = []
    for j, (nombre, fmt) in enumerate(h["cols"]):
        # La primera fila donde la columna tiene fórmula (en casi todas es la fila 1;
        # en otras —p. ej. «Haber» de los asientos— la fila 1 es un dato).
        k = next((i for i, f in enumerate(filas) if j < len(f) and isinstance(f[j], dict) and "f" in f[j]), None)
        if k is None:
            continue
        v0 = filas[k][j]
        formula = v0["f"]
        origen_cols, origen_hojas = [], []
        for m in _REF_RANGO.finditer(_TEXTO_FORMULA.sub('""', formula)):
            hoja_ref, letra = m.group(1), m.group(2)
            if hoja_ref:
                etq = (mapa.get(hoja_ref) or {}).get("label") or hoja_ref
                if etq not in origen_hojas:
                    origen_hojas.append(etq)
            elif letra in header_por_letra and header_por_letra[letra] not in origen_cols:
                origen_cols.append(header_por_letra[letra])
        explic = escritas.get(nombre)
        if not explic:
            explic = f"«{nombre}» {PLANTILLA_GENERICA}."
        resultado = _valor(v0)
        if resultado in (None, ""):
            res_txt = "(en blanco)"
        elif isinstance(resultado, (int, float)) and not isinstance(resultado, bool):
            res_txt = _fmt_num(resultado, fmt)
        else:
            res_txt = _muestra(resultado, fmt).strip("«»")
        ejemplo = f"Fila {k + 1}: {_ejemplo_fila1(formula, h, mapa, fmt)} → {res_txt}"
        origen = [f"«{c}» (esta hoja)" for c in origen_cols] + [f"hoja «{x}»" for x in origen_hojas]
        bloque.append({"columna": nombre, "formula": "=" + formula, "explicacion": explic, "ejemplo": ejemplo,
                       "origen": ", ".join(origen) if origen else "datos cargados del cliente",
                       "destino": h.get("label", h["name"]), "norma": h.get("norma") or "",
                       "escrita": nombre in escritas})
    return bloque


# Cédulas que van a la presentación (PowerPoint): las de lectura ejecutiva. Se comparan por el nombre sin el número,
# porque una herramienta puede renumerar sus cédulas al insertar una nueva.
_EN_PPT = ("Resumen", "Matriz_deterioro", "Por_cliente", "Fiscal", "Asientos", "Problemas", "Conclusion")


def _en_ppt(nombre: str) -> bool:
    return nombre.split("_", 1)[-1] in _EN_PPT
_MAX_FILAS_PPT = 14


def _rgb(RGBColor, hex6):
    return RGBColor(int(hex6[0:2], 16), int(hex6[2:4], 16), int(hex6[4:6], 16))


def csv_zip(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """Un CSV por cédula dentro de un ZIP. UTF-8 con BOM y separador «;» para que
    Excel en español lo abra bien; solo datos limpios (valores, no fórmulas)."""
    import csv
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for h in cedulas(definicion, reg, eventos, version, estado):
            sio = io.StringIO()
            w = csv.writer(sio, delimiter=";")
            w.writerow([c[0] for c in h["cols"]])
            for fila, _total in _filas(h):
                w.writerow([_html.unescape(_celda(v, fmt)) for (_, fmt), v in zip(h["cols"], fila)])
            z.writestr(f"{h['name']}.csv", ("﻿" + sio.getvalue()).encode("utf-8"))
    return buf.getvalue()


def docx(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """Word ejecutivo del papel: portada, resumen ejecutivo con KPIs, cada cédula
    como tabla y un anexo «Cómo se calcula»."""
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    estilo = doc.styles["Normal"]
    estilo.font.name = est.FONT_TEXTO
    estilo.font.size = Pt(9)
    e = reg.get("engagement") or {}
    run = reg.get("run") or {}
    t = doc.add_heading(definicion.get("name", ""), level=0)
    t.runs[0].font.color.rgb = _rgb(RGBColor, est.NAVY)
    doc.add_paragraph(f"AuditConsulting Auditores Cía. Ltda.  ·  {e.get('client', '')} · RUC {e.get('ruc', '')}")
    doc.add_paragraph(f"Marco {e.get('framework', '')} · corte {e.get('cutoff', '')} · v{version} · {est.estado_es(estado)}")
    # Resumen ejecutivo con KPIs
    totales, etiquetas = run.get("totals") or {}, run.get("labels") or {}
    prim = run.get("primary")
    n_prob = len(run.get("exceptions") or [])
    doc.add_heading("Resumen ejecutivo", level=1)
    if prim in totales:
        doc.add_paragraph(f"{etiquetas.get(prim, prim)}: {_html.unescape(_celda({'v': totales[prim]}, 'n'))}")
    doc.add_paragraph(f"Problemas encontrados: {n_prob}")
    if reg.get("conclusion"):
        doc.add_paragraph("Conclusión: " + str(reg["conclusion"]))
    if reg.get("taxApplicable") and reg.get("taxScope"):
        doc.add_paragraph("Tratamiento tributario revisado: " + str(reg["taxScope"]))
    for h in cedulas(definicion, reg, eventos, version, estado):
        doc.add_heading(h["label"], level=1)
        filas = _filas(h)
        tabla = doc.add_table(rows=1 + len(filas), cols=len(h["cols"]))
        tabla.style = "Table Grid"
        for j, (nombre, _) in enumerate(h["cols"]):
            celda = tabla.rows[0].cells[j]
            celda.text = nombre
            celda.paragraphs[0].runs[0].font.bold = True
        for i, (fila, total) in enumerate(filas, start=1):
            for j, ((_, fmt), v) in enumerate(zip(h["cols"], fila)):
                celda = tabla.rows[i].cells[j]
                celda.text = _html.unescape(_celda(v, fmt))
                if total and celda.paragraphs[0].runs:
                    celda.paragraphs[0].runs[0].font.bold = True
    # Anexo «Cómo se calcula»
    doc.add_page_break()
    doc.add_heading("Anexo · Cómo se calcula cada hoja", level=1)
    hojas_doc = cedulas(definicion, reg, eventos, version, estado)
    for h in hojas_doc:
        bloque = como_se_calcula(h, hojas_doc)
        if not bloque:
            continue
        doc.add_heading(h["label"], level=2)
        cols = ["Columna", "Fórmula", "Cómo se calcula", "Ejemplo con números reales", "De dónde viene"]
        tabla = doc.add_table(rows=1 + len(bloque), cols=len(cols))
        tabla.style = "Table Grid"
        for j, nombre in enumerate(cols):
            r0 = tabla.rows[0].cells[j]
            r0.text = nombre
            r0.paragraphs[0].runs[0].font.bold = True
        for i, b in enumerate(bloque, start=1):
            for j, val in enumerate([b["columna"], b["formula"], b["explicacion"], b["ejemplo"], b["origen"]]):
                tabla.rows[i].cells[j].text = str(val)
    salida = io.BytesIO()
    doc.save(salida)
    return salida.getvalue()



_MAX_BARRAS_PPT = 14


def _diapositiva_grafico(prs, g: dict, navy):
    """Diapositiva con un gráfico de barras NATIVO (editable en PowerPoint)."""
    from pptx.chart.data import CategoryChartData
    from pptx.dml.color import RGBColor
    from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION
    from pptx.util import Inches, Pt

    items = g["items"]
    nota = ""
    if len(items) > _MAX_BARRAS_PPT:
        # Los de mayor importe absoluto, conservando el orden de la cédula.
        top = sorted(range(len(items)), key=lambda i: -abs(items[i][1]))[:_MAX_BARRAS_PPT]
        items = [items[i] for i in sorted(top)]
        nota = f" ({_MAX_BARRAS_PPT} conceptos de mayor importe; el resto en la tabla)"
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = g["titulo"] + nota
    tf = s.shapes.title.text_frame.paragraphs[0].runs[0].font
    tf.size, tf.color.rgb = Pt(26), navy
    datos = CategoryChartData()
    datos.categories = [graficos._recorta(e) for e, _ in items]
    datos.add_series("USD", [round(v, 2) for _, v in items])
    ch = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(0.5), Inches(1.35), Inches(12.3), Inches(5.6), datos).chart
    ch.has_legend = False
    ch.has_title = False  # el título de la diapositiva ya dice qué se grafica
    ch.font.size = Pt(10)
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = "#,##0.00", False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size = Pt(10)
    dl.font.color.rgb = RGBColor.from_string(est.TINTA_2)
    serie = plot.series[0]
    serie.invert_if_negative = False
    serie.format.fill.solid()
    serie.format.fill.fore_color.rgb = RGBColor.from_string(est.SERIE)
    ch.category_axis.reverse_order = True
    # Rótulos al borde izquierdo del área, no en el cero: así no pisan las barras negativas.
    ch.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    ch.category_axis.tick_labels.font.color.rgb = RGBColor.from_string(est.TINTA)
    ch.value_axis.has_major_gridlines = False
    ch.value_axis.visible = False
    pie = s.shapes.add_textbox(Inches(0.5), Inches(6.95), Inches(12.3), Inches(0.4)).text_frame
    pie.text = g["subtitulo"]
    pie.paragraphs[0].runs[0].font.size = Pt(10)
    pie.paragraphs[0].runs[0].font.color.rgb = RGBColor.from_string(est.TINTA_2)

def pptx(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """Presentación ejecutiva: portada y las cédulas de lectura (las largas, recortadas)."""
    from pptx import Presentation
    from pptx.dml.color import RGBColor
    from pptx.util import Inches, Pt

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    e = reg.get("engagement") or {}
    run = reg.get("run") or {}
    navy = _rgb(RGBColor, est.NAVY)
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = definicion.get("name", "")
    s.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = navy
    s.placeholders[1].text = (f"{e.get('client', '')} · corte {e.get('cutoff', '')} · v{version} · {est.estado_es(estado)}\n"
                              "AuditConsulting Auditores Cía. Ltda. · AUDIT-IA")
    # Diapositiva ejecutiva de cifras clave
    totales, etiquetas, prim = run.get("totals") or {}, run.get("labels") or {}, run.get("primary")
    n_prob = len(run.get("exceptions") or [])
    cifras = []
    if prim in totales:
        cifras.append((etiquetas.get(prim, prim), _html.unescape(_celda({"v": totales[prim]}, "n"))))
    for k in ("perdida", "cartera", "provReg"):
        if k in totales and k != prim:
            cifras.append((etiquetas.get(k, k), _html.unescape(_celda({"v": totales[k]}, "n"))))
    cifras.append(("Problemas encontrados", str(n_prob)))
    sk = prs.slides.add_slide(prs.slide_layouts[5])
    sk.shapes.title.text = "Cifras clave"
    sk.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = navy
    caja = sk.shapes.add_textbox(Inches(0.6), Inches(1.6), Inches(12), Inches(5)).text_frame
    caja.word_wrap = True
    for i, (etq, val) in enumerate(cifras[:5]):
        p = caja.paragraphs[0] if i == 0 else caja.add_paragraph()
        p.text = f"{etq}:  {val}"
        p.runs[0].font.size = Pt(20)
        p.runs[0].font.color.rgb = navy
    hojas_ppt = cedulas(definicion, reg, eventos, version, estado)
    for g in graficos.paneles(hojas_ppt, run):
        _diapositiva_grafico(prs, g, navy)
    for h in hojas_ppt:
        if not _en_ppt(h["name"]):
            continue
        filas = _filas(h)
        recorte = len(filas) > _MAX_FILAS_PPT
        if recorte:
            filas = filas[:_MAX_FILAS_PPT - 1] + ([f for f in filas if f[1]] or [])
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = h["label"] + (" (primeras filas; el detalle completo está en el Excel)" if recorte else "")
        s.shapes.title.text_frame.paragraphs[0].runs[0].font.size = Pt(24)
        forma = s.shapes.add_table(1 + len(filas), len(h["cols"]), Inches(0.4), Inches(1.4), Inches(12.5), Inches(0.3) * (1 + len(filas)))
        tabla = forma.table
        for j, (nombre, _) in enumerate(h["cols"]):
            tabla.cell(0, j).text = nombre
        for i, (fila, total) in enumerate(filas, start=1):
            for j, ((_, fmt), v) in enumerate(zip(h["cols"], fila)):
                tabla.cell(i, j).text = _html.unescape(_celda(v, fmt))
        for fila in tabla.rows:
            for c in fila.cells:
                for p in c.text_frame.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(10)
        for j in range(len(h["cols"])):
            tabla.cell(0, j).fill.solid()
            tabla.cell(0, j).fill.fore_color.rgb = RGBColor(0x0A, 0x23, 0x42)
    salida = io.BytesIO()
    prs.save(salida)
    return salida.getvalue()


def html(definicion: dict, reg: dict, eventos: list, version: int, estado: str, para_pdf: bool = False) -> bytes:
    """HTML autónomo con el dashboard ejecutivo (``html_ejecutivo``): funciona sin
    internet (sin fuentes, scripts ni estilos externos) y trae dentro el Excel con
    fórmulas, el Word, el PowerPoint y el CSV para descargarlos. ``para_pdf=True``
    devuelve la versión estática (tema Claro, todo visible, sin JS) para el PDF."""
    from backend.app.aud.niif.procesadores import html_ejecutivo

    hojas = cedulas(definicion, reg, eventos, version, estado)
    adjuntos = [] if para_pdf else [
        ("xlsx", "Excel con fórmulas", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         xlsx(definicion, reg, eventos, version, estado)),
        ("docx", "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         docx(definicion, reg, eventos, version, estado)),
        ("pptx", "PowerPoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation",
         pptx(definicion, reg, eventos, version, estado)),
        ("zip", "CSV (ZIP)", "application/zip", csv_zip(definicion, reg, eventos, version, estado)),
    ]
    return html_ejecutivo.render(definicion, reg, eventos, version, estado, hojas, adjuntos, _celda, como_se_calcula,
                                 para_pdf=para_pdf).encode("utf-8")


class PDFNoDisponible(ValueError):
    """WeasyPrint (o sus librerías nativas Pango/cairo) no está disponible en
    este entorno. El endpoint lo traduce a un aviso, no a un error 500."""


def pdf(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """PDF ejecutivo generado en el servidor (WeasyPrint) a partir del HTML
    estático: fiel a la vista, horizontal, con marca, KPIs, cédulas y el bloque
    «Cómo se calcula». No usa la impresión del navegador.

    En entornos sin las librerías nativas de WeasyPrint (p. ej. un servicio
    Render ``env: python``) degrada con ``PDFNoDisponible``; el papel sigue
    disponible en Excel/Word/HTML y el HTML trae «Guardar como PDF»."""
    try:
        import weasyprint  # requiere Pango/cairo/gdk-pixbuf nativos
    except Exception as e:  # ImportError o OSError al cargar las libs nativas
        raise PDFNoDisponible(
            "El PDF en el servidor no está disponible en este entorno (faltan las "
            "librerías nativas de WeasyPrint). Descargue el papel en Excel, Word o "
            "HTML, o use «Guardar como PDF» desde el HTML."
        ) from e
    contenido = html(definicion, reg, eventos, version, estado, para_pdf=True)
    return weasyprint.HTML(string=contenido.decode("utf-8")).write_pdf()
