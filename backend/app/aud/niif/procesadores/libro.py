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
from openpyxl.utils import get_column_letter

NAVY, GOLD, BLANCO, CELESTE = "0A2342", "C7A83C", "FFFFFF", "DCE6F1"
_FINO = Side(style="thin", color="B7C0CC")
_DOBLE = Side(style="double", color="0A2342")
_BORDE = Border(left=_FINO, right=_FINO, top=_FINO, bottom=_FINO)
_BORDE_TOTAL = Border(left=_FINO, right=_FINO, top=_DOBLE, bottom=_DOBLE)
_FMT = {"n": "#,##0.00", "p": "0.00%", "i": "#,##0", "d": "yyyy-mm-dd"}


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
        ["Versión del papel", f"v{version}"], ["Estado", estado], ["Preparó", e.get("preparer")], ["Revisó", e.get("reviewer")],
        ["Aprobó", reg.get("approvedBy") or ""], ["Fecha de aprobación", (reg.get("approvedAt") or "")[:10]],
        ["Huella de la ejecución (SHA-256)", reg.get("runHash") or ""],
    ]
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
         "rows": [[(x.get("fecha") or "")[:19].replace("T", " "), x.get("accion"), x.get("estado_anterior"), x.get("estado_nuevo"),
                   x.get("actor"), x.get("comentario")] for x in eventos]},
    ]


def cedulas(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> list[dict]:
    antes, despues = _contexto(definicion, reg, eventos, version, estado)
    return antes + ((reg.get("run") or {}).get("hojas") or []) + despues


def xlsx(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    titulo = f"{definicion.get('name', '')} · {(reg.get('engagement') or {}).get('client', '')} · corte {(reg.get('engagement') or {}).get('cutoff', '')}"
    for h in cedulas(definicion, reg, eventos, version, estado):
        ws = wb.create_sheet(h["name"][:31])
        ws.cell(row=1, column=1, value=_seguro(h["label"])).font = Font(name="Calibri", size=11, bold=True, color=NAVY)
        ws.cell(row=2, column=1, value=_seguro(titulo)).font = Font(name="Calibri", size=9, italic=True, color=GOLD)
        anchos = [len(c[0]) + 2 for c in h["cols"]]
        for j, (nombre, _) in enumerate(h["cols"], start=1):
            c = ws.cell(row=4, column=j, value=nombre)
            c.font = Font(name="Calibri", size=10, bold=True, color=BLANCO)
            c.fill = PatternFill("solid", fgColor=NAVY)
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = _BORDE
        filas = [(r, False) for r in h["rows"]] + ([(h["total"], True)] if h.get("total") else [])
        for i, (fila, total) in enumerate(filas, start=5):
            for j, ((_, fmt), v) in enumerate(zip(h["cols"], fila), start=1):
                c = ws.cell(row=i, column=j, value=_excel(v, fmt))
                c.font = Font(name="Calibri", size=10 if total else 9, bold=total)
                c.border = _BORDE_TOTAL if total else _BORDE
                if total:
                    c.fill = PatternFill("solid", fgColor=CELESTE)
                if isinstance(c.value, date):
                    c.number_format = "yyyy-mm-dd"
                    c.alignment = Alignment(horizontal="center")
                elif fmt in _FMT:
                    c.number_format = _FMT[fmt]
                    c.alignment = Alignment(horizontal="right")
                elif fmt == "x" and isinstance(_valor(v), (int, float)):
                    c.alignment = Alignment(horizontal="right")
                else:
                    c.alignment = Alignment(horizontal="left", wrap_text=True, vertical="top")
                vista = _valor(v)
                anchos[j - 1] = max(anchos[j - 1], min(60, len(str(vista if vista is not None else "")) + 2))
        for j, w in enumerate(anchos, start=1):
            ws.column_dimensions[get_column_letter(j)].width = max(12, min(60, w))
        ws.freeze_panes = "A5"
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _celda(v, fmt) -> str:
    v = _valor(v)
    if v is None or v == "":
        return ""
    if fmt == "n" or (fmt == "x" and isinstance(v, (int, float))):
        return f"{float(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if fmt == "p":
        return f"{float(v) * 100:.2f} %".replace(".", ",")
    if fmt == "i":
        return f"{int(v):,}".replace(",", ".")
    return _html.escape(str(v))


def _filas(h):
    return [(r, False) for r in h["rows"]] + ([(h["total"], True)] if h.get("total") else [])


# Cédulas que van a la presentación (PowerPoint): las de lectura ejecutiva.
_EN_PPT = ("01_Resumen", "04_Matriz_deterioro", "05_Por_cliente", "08_Fiscal", "10_Asientos", "12_Problemas", "13_Conclusion")
_MAX_FILAS_PPT = 14


def docx(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """Word del papel: carátula y cada cédula como tabla (valores ya calculados)."""
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.shared import Pt, RGBColor

    doc = Document()
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = sec.page_height, sec.page_width
    estilo = doc.styles["Normal"]
    estilo.font.name = "Calibri"
    estilo.font.size = Pt(9)
    e = reg.get("engagement") or {}
    t = doc.add_heading(definicion.get("name", ""), level=0)
    t.runs[0].font.color.rgb = RGBColor(0x0A, 0x23, 0x42)
    doc.add_paragraph(f"{e.get('client', '')} · corte {e.get('cutoff', '')} · v{version} · {estado}")
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
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = definicion.get("name", "")
    s.placeholders[1].text = f"{e.get('client', '')} · corte {e.get('cutoff', '')} · v{version} · {estado}\nAuditConsulting Auditores Cía. Ltda."
    for h in cedulas(definicion, reg, eventos, version, estado):
        if h["name"] not in _EN_PPT:
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


def html(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    """HTML autónomo: funciona sin internet (sin fuentes, scripts ni estilos
    externos) y trae dentro el Excel con fórmulas, el Word y el PowerPoint para
    descargarlos; el PDF se guarda desde la impresión del navegador."""
    import base64

    partes = []
    for h in cedulas(definicion, reg, eventos, version, estado):
        cab = "".join(f"<th>{_html.escape(c[0])}</th>" for c in h["cols"])
        cuerpo = "".join(
            "<tr" + (' class="total"' if total else "") + ">"
            + "".join(f'<td class="{"num" if f in _FMT else ""}"'
                      + (f' title="={_html.escape(v["f"])}"' if isinstance(v, dict) else "")
                      + f">{_celda(v, f)}</td>" for (_, f), v in zip(h["cols"], fila))
            + "</tr>"
            for fila, total in _filas(h))
        partes.append(f"<section><h2>{_html.escape(h['label'])}</h2><table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></section>")
    e = reg.get("engagement") or {}
    base = re.sub(r"[^\w-]+", "_", definicion.get("name", "papel"))[:60] + f"_v{version}"
    adjuntos = (
        ("xlsx", "Excel con fórmulas", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", xlsx),
        ("docx", "Word", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", docx),
        ("pptx", "PowerPoint", "application/vnd.openxmlformats-officedocument.presentationml.presentation", pptx),
    )
    botones = "".join(
        f'<a class="btn" download="{base}.{ext}" href="data:{mime};base64,'
        f'{base64.b64encode(fn(definicion, reg, eventos, version, estado)).decode()}">⬇ {etiqueta}</a>'
        for ext, etiqueta, mime, fn in adjuntos
    ) + '<button class="btn" type="button" onclick="window.print()">⬇ PDF (Guardar como PDF)</button>'
    doc = (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{_html.escape(definicion.get('name', ''))}</title><style>"
        "body{font-family:'DM Sans',Calibri,Arial,sans-serif;margin:24px;color:#0A2342;background:#fff}h1{font-size:20px}"
        "h2{font-size:15px;margin-top:28px;border-bottom:2px solid #C7A83C}"
        ".descargas{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 20px}"
        ".btn{background:#0A2342;color:#fff;border:0;border-radius:6px;padding:8px 14px;font:inherit;text-decoration:none;cursor:pointer}"
        ".btn:hover{background:#C7A83C;color:#071B2F}.nota{color:#555;font-size:12px}"
        "section{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th{background:#0A2342;color:#fff;padding:4px 6px}"
        "td{border:1px solid #B7C0CC;padding:3px 6px;vertical-align:top}td.num{text-align:right;white-space:nowrap}"
        "tr.total td{font-weight:700;background:#DCE6F1;border-top:3px double #0A2342;border-bottom:3px double #0A2342}"
        "@media print{.descargas,.nota{display:none}body{margin:0}section{break-inside:auto;overflow:visible}"
        "th{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{size:A4 landscape;margin:12mm}}"
        "</style></head><body>"
        f"<h1>{_html.escape(definicion.get('name', ''))}</h1>"
        f"<p>{_html.escape(str(e.get('client', '')))} · corte {_html.escape(str(e.get('cutoff', '')))} · v{version} · {_html.escape(estado)}</p>"
        f'<div class="descargas">{botones}</div>'
        '<p class="nota">Este archivo funciona sin conexión a internet. Pase el cursor sobre un importe para ver su fórmula; '
        "en el Excel las fórmulas son editables y remiten a Parámetros, Detalle por factura y Matriz de deterioro.</p>"
        + "".join(partes) + "</body></html>"
    )
    return doc.encode("utf-8")
