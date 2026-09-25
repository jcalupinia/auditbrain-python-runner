"""Papel de trabajo (Excel con fórmulas, HTML autónomo, Word y PowerPoint) de una prueba con procesador.

El exportador del sitio arma el papel de las pruebas declarativas en el
navegador; el de un procesador lo arma aquí el servidor con las cédulas que el
propio procesador calculó (``run["hojas"]``), más carátula, programa, fuentes,
conclusión y bitácora del registro.
"""
from __future__ import annotations

import html as _html
import io
import re
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import column_index_from_string, get_column_letter
from openpyxl.worksheet.properties import PageSetupProperties

from backend.app.aud.niif.procesadores import estilo_ejecutivo as est

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


def _paneles_analiticos(reg: dict) -> list[dict]:
    """Cédulas opcionales con el enriquecimiento del ciclo (evidence/risk):
    "15_Riesgo" (scoring de anomalías) y "16_Evidencia" (cobertura de
    requerimientos ↔ archivos). Solo se agregan cuando el registro trae los
    datos (``riskScoring``/``evidenceMatrix`` que puebla ``ciclo.insights``);
    si no, no aparecen — así una prueba sin scoring no gana hojas vacías."""
    paneles: list[dict] = []

    rs = reg.get("riskScoring") or {}
    anomalias = rs.get("anomalias") or []
    if anomalias or (rs.get("resumen") or {}).get("total"):
        res = rs.get("resumen") or {}
        filas = [
            [a.get("indice"), a.get("score"), a.get("nivel"),
             "; ".join(f"{f.get('variable')} (z={f.get('z')})"
                       for f in (a.get("factores") or [])[:3])]
            for a in anomalias
        ] or [["—", "—", "sin filas marcadas", f"revisadas {res.get('total', 0)}"]]
        paneles.append({
            "name": "15_Riesgo", "label": "Scoring de riesgo", "total": None,
            "cols": [["Fila", "i"], ["Score (0-100)", "n"], ["Nivel", "t"], ["Factores (top 3)", "t"]],
            "rows": filas,
        })

    em = reg.get("evidenceMatrix") or {}
    entradas = em.get("entradas") or []
    if entradas:
        filas = [
            [e.get("requerimiento"), e.get("documento"), e.get("fuentes"),
             "Sí" if e.get("corroborado") else "No", e.get("estado")]
            for e in entradas
        ]
        paneles.append({
            "name": "16_Evidencia", "label": "Cobertura de evidencia", "total": None,
            "cols": [["Requerimiento", "t"], ["Documento", "t"], ["Fuentes", "i"],
                     ["Corroborado (≥2)", "t"], ["Estado", "t"]],
            "rows": filas,
        })

    return paneles


def cedulas(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> list[dict]:
    antes, despues = _contexto(definicion, reg, eventos, version, estado)
    return (antes + ((reg.get("run") or {}).get("hojas") or [])
            + despues + _paneles_analiticos(reg))


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
        ws.column_dimensions[col].width = 22
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
        ws.row_dimensions[row].height = 22
    ws.print_options.horizontalCentered = True
    _print_setup(ws, e)


def _tarjeta_kpi(ws, col, row, etq, val, fmt, semaforo, S):
    c2 = chr(ord(col) + 0)
    ws[f"{col}{row}"].value = etq
    ws[f"{col}{row}"].font = S["kpi_etq"]
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


def _hoja_ejecutiva(ws, S, h, titulo_prueba, nav):
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
        c.border = S["borde"]
    filas = [(r, False) for r in h["rows"]] + ([(h["total"], True)] if h.get("total") else [])
    for i, (fila, total) in enumerate(filas, start=fila_enc + 1):
        for j, ((_, fmt), v) in enumerate(zip(h["cols"], fila), start=1):
            c = ws.cell(row=i, column=j, value=_excel(v, fmt))
            es_num = fmt in est.FMT or (fmt == "x" and isinstance(_valor(v), (int, float)))
            c.font = S["total"] if total else (S["cifra"] if es_num else S["dato"])
            c.border = S["borde_total"] if total else S["borde"]
            if total:
                c.fill = S["fill_total"]
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
    _bloque_como_se_calcula(ws, S, h, len(filas) + fila_enc + 2)
    _print_setup(ws, {})


def _bloque_como_se_calcula(ws, S, h, fila_inicio):
    """Escribe, debajo de la tabla, el bloque «ⓘ Cómo se calcula esta hoja» en
    lenguaje sencillo (una fila por columna con fórmula). No se imprime cortado:
    va en su propia banda con fondo claro y borde."""
    bloque = como_se_calcula(h)
    if not bloque:
        return
    r = fila_inicio
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
    t = ws.cell(row=r, column=1, value="ⓘ  Cómo se calcula esta hoja")
    t.font = S["subtitulo"]
    t.fill = S["fill_gold"]
    t.alignment = S["izq"]
    r += 1
    encabez = ["Columna", "Fórmula (Excel)", "Cómo se calcula (sencillo)", "Ejemplo (fila 1)", "De dónde viene", "Norma"]
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
    _panel_inicio(inicio, S, definicion, reg, titulos, hojas, estado, version)

    for idx, (h, t) in enumerate(zip(hojas, titulos)):
        ws = wb.create_sheet(t)
        nav = {"inicio": "00_Inicio",
               "anterior": titulos[idx - 1] if idx > 0 else None,
               "siguiente": titulos[idx + 1] if idx < len(titulos) - 1 else None}
        _hoja_ejecutiva(ws, S, h, titulo_prueba, nav)
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
_SOLO_ARITMETICA = re.compile(r"^[-+*/().\s0-9]*$")


def _fmt_num(v, fmt) -> str:
    return _celda(v, fmt if fmt in ("n", "p", "i", "a") else "n")


def _ejemplo_fila1(formula: str, h: dict, header_por_letra: dict, fmt: str) -> str:
    """Ejemplo con los números de la PRIMERA fila real. Si la fórmula es pura
    aritmética entre celdas de la misma hoja, sustituye cada celda por su valor
    («12.500,00 − 7.500,00 = 5.000,00»); si no, muestra el resultado de la fila 1."""
    filas = h["rows"]
    if not filas:
        return ""
    # Sustitución solo si no hay funciones (letras fuera de referencias) ni hojas externas.
    def sustituye(m):
        sheet, letra, num = m.group(1), m.group(2), int(m.group(3))
        if sheet:
            return m.group(0)
        idx_fila = num - 5           # los datos arrancan en la fila 5 de la hoja
        col = column_index_from_string(letra) - 1
        if 0 <= idx_fila < len(filas) and 0 <= col < len(filas[idx_fila]):
            return _fmt_num(_valor(filas[idx_fila][col]), fmt)
        return m.group(0)
    sin_refs = _REF.sub("X", formula)
    if _SOLO_ARITMETICA.match(sin_refs.replace("X", "")):
        return _REF.sub(sustituye, formula)
    return "resultado de la fila 1"


def como_se_calcula(h: dict) -> list[dict]:
    """Filas del bloque explicativo: una por columna CALCULADA (con fórmula).
    Cada una: columna, fórmula (texto), explicación sencilla, ejemplo de la fila 1,
    de dónde vienen los datos y la referencia normativa de la hoja."""
    filas = h.get("rows") or []
    if not filas:
        return []
    cols = [c[0] for c in h["cols"]]
    header_por_letra = {get_column_letter(j + 1): cols[j] for j in range(len(cols))}
    bloque = []
    for j, (nombre, fmt) in enumerate(h["cols"]):
        v0 = filas[0][j] if j < len(filas[0]) else None
        if not (isinstance(v0, dict) and "f" in v0):
            continue
        formula = v0["f"]
        refs = _REF.findall(formula)
        origen_cols, origen_hojas = [], []
        for sheet, letra, _num in refs:
            if sheet and sheet not in origen_hojas:
                origen_hojas.append(sheet)
            elif not sheet and letra in header_por_letra:
                col = header_por_letra[letra]
                if col not in origen_cols:
                    origen_cols.append(col)
        partes = []
        if origen_cols:
            partes.append("usa " + ", ".join(f"«{c}»" for c in origen_cols))
        if origen_hojas:
            partes.append(("y datos de " if partes else "usa datos de ") + ", ".join(origen_hojas))
        explic = f"«{nombre}» se obtiene con la fórmula indicada" + ((": " + " ".join(partes) + ".") if partes else ".")
        ejemplo_expr = _ejemplo_fila1(formula, h, header_por_letra, fmt)
        resultado = _fmt_num(_valor(v0), fmt)
        ejemplo = (f"Fila 1: {ejemplo_expr} = {resultado}" if ejemplo_expr and ejemplo_expr != "resultado de la fila 1"
                   else f"Resultado de la fila 1: {resultado}")
        destino = h.get("label", h["name"])
        origen = origen_cols + origen_hojas
        bloque.append({"columna": nombre, "formula": "=" + formula, "explicacion": explic, "ejemplo": ejemplo,
                       "origen": ", ".join(origen) if origen else "datos cargados del cliente",
                       "destino": destino, "norma": h.get("norma") or ""})
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
    for h in cedulas(definicion, reg, eventos, version, estado):
        bloque = como_se_calcula(h)
        if not bloque:
            continue
        doc.add_heading(h["label"], level=2)
        cols = ["Columna", "Fórmula", "Cómo se calcula", "Ejemplo (fila 1)", "De dónde viene"]
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
    for h in cedulas(definicion, reg, eventos, version, estado):
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
    """HTML autónomo: funciona sin internet (sin fuentes, scripts ni estilos
    externos) y trae dentro el Excel con fórmulas, el Word, el PowerPoint y el
    CSV para descargarlos. ``para_pdf=True`` devuelve una versión estática (todo
    visible, sin pestañas/descargas/JS) para renderizar el PDF en el servidor."""
    import base64

    hojas = cedulas(definicion, reg, eventos, version, estado)
    e = reg.get("engagement") or {}
    run = reg.get("run") or {}
    # Pestañas tipo botón + secciones
    tabs, secciones = [], []
    for idx, h in enumerate(hojas):
        act = " on" if idx == 0 else ""
        vis = "" if (para_pdf or idx == 0) else ' hidden'
        tabs.append(f'<button class="tab{act}" type="button" data-t="t{idx}">{_html.escape(h["label"])}</button>')
        cab = "".join(f"<th>{_html.escape(c[0])}</th>" for c in h["cols"])
        cuerpo = "".join(
            "<tr" + (' class="total"' if total else "") + ">"
            + "".join(f'<td class="{"num" if f in _FMT else ""}"'
                      + (f' title="={_html.escape(v["f"])}"' if isinstance(v, dict) else "")
                      + f">{_celda(v, f)}</td>" for (_, f), v in zip(h["cols"], fila))
            + "</tr>"
            for fila, total in _filas(h))
        bloque = como_se_calcula(h)
        calc = ""
        if bloque:
            filas_c = "".join(
                f"<tr><td>{_html.escape(b['columna'])}</td><td class='mono'>{_html.escape(b['formula'])}</td>"
                f"<td>{_html.escape(b['explicacion'])}</td><td>{_html.escape(b['ejemplo'])}</td>"
                f"<td>{_html.escape(b['origen'])}</td></tr>" for b in bloque)
            tabla_calc = ("<table class='calc'><thead><tr><th>Columna</th><th>Fórmula</th><th>Cómo se calcula</th>"
                          f"<th>Ejemplo (fila 1)</th><th>De dónde viene</th></tr></thead><tbody>{filas_c}</tbody></table>")
            if para_pdf:
                calc = f"<div class='calc'><p class='calctit'>ⓘ Cómo se calcula esta hoja</p>{tabla_calc}</div>"
            else:
                calc = f"<details class='calc'><summary>ⓘ Ver cálculo de esta hoja</summary>{tabla_calc}</details>"
        secciones.append(f'<section id="t{idx}"{vis}><h2>{_html.escape(h["label"])}</h2>{calc}'
                         f'<div class="scroll"><table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></div></section>')
    # Tarjetas KPI
    totales, etiquetas, prim = run.get("totals") or {}, run.get("labels") or {}, run.get("primary")
    n_prob = len(run.get("exceptions") or [])
    kpi_items = []
    if prim in totales:
        kpi_items.append((etiquetas.get(prim, prim), _celda({"v": totales[prim]}, "n"), est.NAVY))
    for k in ("perdida", "cartera", "provReg"):
        if k in totales and k != prim:
            kpi_items.append((etiquetas.get(k, k), _celda({"v": totales[k]}, "n"), est.NAVY))
    kpi_items.append(("Problemas encontrados", str(n_prob), est.color_semaforo(n_prob)))
    kpis = "".join(f'<div class="kpi"><small>{_html.escape(etq)}</small><strong style="color:#{col}">{val}</strong></div>'
                   for etq, val, col in kpi_items[:5])
    base = re.sub(r"[^\w-]+", "_", definicion.get("name", "papel"))[:60] + f"_v{version}"
    adjuntos = (
        ("xlsx", "Excel con fórmulas", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xlsx),
        ("docx", "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx),
        ("pptx", "PowerPoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation", pptx),
        ("zip", "CSV (ZIP)", "application/zip", csv_zip),
    )
    botones = "".join(
        f'<a class="btn" download="{base}.{ext}" href="data:{mime};base64,'
        f'{base64.b64encode(fn(definicion, reg, eventos, version, estado)).decode()}">⬇ {etiqueta}</a>'
        for ext, etiqueta, mime, fn in adjuntos
    ) + '<button class="btn" type="button" onclick="window.print()">⬇ PDF (Guardar como PDF)</button>'
    css = (
        f"body{{font-family:'Segoe UI',Calibri,Arial,sans-serif;margin:0;color:#{est.NAVY};background:#{est.LIGHT}}}"
        f".wrap{{max-width:1200px;margin:0 auto;padding:20px}}"
        f".marca{{background:#{est.NAVY};color:#fff;padding:14px 20px;border-radius:10px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}}"
        ".marca b{font-size:16px}.marca span{font-size:12px;opacity:.85}"
        ".kpis{display:flex;flex-wrap:wrap;gap:10px;margin:16px 0}"
        f".kpi{{background:#fff;border:1px solid #{est.LINE};border-radius:10px;padding:10px 14px;min-width:150px}}"
        f".kpi small{{display:block;color:#{est.TURQUOISE};font-weight:700;font-size:11px}}.kpi strong{{font-size:20px}}"
        ".descargas{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}"
        f".btn{{background:#{est.TURQUOISE};color:#fff;border:0;border-radius:6px;padding:8px 14px;font:inherit;text-decoration:none;cursor:pointer}}"
        f".btn:hover{{background:#{est.GOLD};color:#{est.DEEP_BLUE}}}"
        ".tabs{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 6px}"
        f".tab{{background:#fff;border:1px solid #{est.LINE};border-radius:999px;padding:5px 12px;font:inherit;cursor:pointer;font-size:13px}}"
        f".tab.on{{background:#{est.NAVY};color:#fff;border-color:#{est.NAVY};font-weight:700}}"
        f"h2{{font-size:15px;border-bottom:2px solid #{est.GOLD};padding-bottom:4px}}"
        ".scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px;background:#fff}"
        f"th{{background:#{est.NAVY};color:#fff;padding:5px 6px}}"
        f"td{{border:1px solid #{est.LINE};padding:3px 6px;vertical-align:top}}td.num{{text-align:right;white-space:nowrap;font-family:Consolas,monospace}}"
        f"tr.total td{{font-weight:700;background:#{est.CELESTE};border-top:3px double #{est.NAVY};border-bottom:3px double #{est.NAVY}}}"
        f"details.calc,div.calc{{margin:8px 0;background:#fff;border:1px solid #{est.LINE};border-radius:8px;padding:6px 10px}}"
        f"details.calc summary,.calctit{{cursor:pointer;font-weight:700;color:#{est.TURQUOISE};margin:0}}"
        "table.calc td.mono,td.mono{font-family:Consolas,monospace;font-size:11px}"
        f".nota{{color:#555;font-size:12px}}"
        "@media print{.descargas,.tabs,.nota,.btn{display:none}section[hidden]{display:block!important}"
        "details.calc{display:none}body{background:#fff}.wrap{max-width:none;padding:0}"
        "section{break-inside:avoid}"
        "th{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{size:A4 landscape;margin:12mm}}"
    )
    js = ("" if para_pdf else
          "<script>document.querySelectorAll('.tab').forEach(function(b){b.onclick=function(){"
          "document.querySelectorAll('.tab').forEach(function(x){x.classList.remove('on')});b.classList.add('on');"
          "document.querySelectorAll('section').forEach(function(s){s.hidden=(s.id!==b.dataset.t)});};});</script>")
    chrome = "" if para_pdf else (
        f'<div class="descargas">{botones}</div>'
        '<p class="nota">Funciona sin conexión. Pase el cursor sobre un importe para ver su fórmula; use «ⓘ Ver cálculo» para la explicación de cada hoja. En el Excel las fórmulas son editables y trazables.</p>'
        f'<div class="tabs">{"".join(tabs)}</div>')
    doc = (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_html.escape(definicion.get('name', ''))}</title><style>{css}</style></head><body><div class=\"wrap\">"
        f'<div class="marca"><b>AuditConsulting Auditores Cía. Ltda. · AUDIT-IA</b>'
        f'<span>{_html.escape(str(e.get("client","")))} · RUC {_html.escape(str(e.get("ruc","")))} · corte {_html.escape(str(e.get("cutoff","")))} · v{version} · {_html.escape(est.estado_es(estado))}</span></div>'
        f'<h1>{_html.escape(definicion.get("name",""))}</h1>'
        f'<div class="kpis">{kpis}</div>'
        + chrome
        + "".join(secciones) + js + "</div></body></html>"
    )
    return doc.encode("utf-8")


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
