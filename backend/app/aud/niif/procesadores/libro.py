"""Papel de trabajo (Excel y HTML) de una prueba con procesador.

El exportador del sitio arma el papel de las pruebas declarativas en el
navegador; el de un procesador lo arma aquí el servidor con las cédulas que el
propio procesador calculó (``run["hojas"]``), más carátula, programa, fuentes,
conclusión y bitácora del registro.
"""
from __future__ import annotations

import html as _html
import io

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

NAVY, GOLD, BLANCO, CELESTE = "0A2342", "C7A83C", "FFFFFF", "DCE6F1"
_FINO = Side(style="thin", color="B7C0CC")
_DOBLE = Side(style="double", color="0A2342")
_BORDE = Border(left=_FINO, right=_FINO, top=_FINO, bottom=_FINO)
_BORDE_TOTAL = Border(left=_FINO, right=_FINO, top=_DOBLE, bottom=_DOBLE)
_FMT = {"n": "#,##0.00", "p": "0.00%", "i": "#,##0"}


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
                c = ws.cell(row=i, column=j, value=_seguro(v))
                c.font = Font(name="Calibri", size=10 if total else 9, bold=total)
                c.border = _BORDE_TOTAL if total else _BORDE
                if total:
                    c.fill = PatternFill("solid", fgColor=CELESTE)
                if fmt in _FMT:
                    c.number_format = _FMT[fmt]
                    c.alignment = Alignment(horizontal="right")
                else:
                    c.alignment = Alignment(horizontal="left", wrap_text=True, vertical="top")
                anchos[j - 1] = max(anchos[j - 1], min(60, len(str(v if v is not None else "")) + 2))
        for j, w in enumerate(anchos, start=1):
            ws.column_dimensions[get_column_letter(j)].width = max(12, min(60, w))
        ws.freeze_panes = "A5"
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def _celda(v, fmt) -> str:
    if v is None or v == "":
        return ""
    if fmt == "n":
        return f"{float(v):,.2f}"
    if fmt == "p":
        return f"{float(v) * 100:,.2f} %"
    if fmt == "i":
        return f"{int(v):,}"
    return _html.escape(str(v))


def html(definicion: dict, reg: dict, eventos: list, version: int, estado: str) -> bytes:
    partes = []
    for h in cedulas(definicion, reg, eventos, version, estado):
        cab = "".join(f"<th>{_html.escape(c[0])}</th>" for c in h["cols"])
        cuerpo = "".join(
            "<tr" + (' class="total"' if total else "") + ">"
            + "".join(f'<td class="{"num" if f in _FMT else ""}">{_celda(v, f)}</td>' for (_, f), v in zip(h["cols"], fila))
            + "</tr>"
            for fila, total in [(r, False) for r in h["rows"]] + ([(h["total"], True)] if h.get("total") else []))
        partes.append(f"<section><h2>{_html.escape(h['label'])}</h2><table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></section>")
    e = reg.get("engagement") or {}
    doc = (
        "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
        f"<title>{_html.escape(definicion.get('name', ''))}</title><style>"
        "body{font-family:'DM Sans',Calibri,sans-serif;margin:24px;color:#0A2342}h1{font-size:20px}h2{font-size:15px;margin-top:28px;border-bottom:2px solid #C7A83C}"
        "table{border-collapse:collapse;width:100%;font-size:12px}th{background:#0A2342;color:#fff;padding:4px 6px}"
        "td{border:1px solid #B7C0CC;padding:3px 6px;vertical-align:top}td.num{text-align:right;white-space:nowrap}"
        "tr.total td{font-weight:700;background:#DCE6F1;border-top:3px double #0A2342;border-bottom:3px double #0A2342}"
        "</style></head><body>"
        f"<h1>{_html.escape(definicion.get('name', ''))}</h1>"
        f"<p>{_html.escape(str(e.get('client', '')))} · corte {_html.escape(str(e.get('cutoff', '')))} · v{version} · {_html.escape(estado)}</p>"
        + "".join(partes) + "</body></html>"
    )
    return doc.encode("utf-8")
