"""Generador de la presentación ejecutiva (.pptx) — estilo PoC AuditBrain.

Replica la estética aprobada (ver docs/CANVA_ESTILO_PoC.md): tema oscuro premium,
tipografía DM Sans, KPIs grandes, acentos Gold. Deck 16:9 para gerencia/accionistas,
alimentado por el `content` que arma el frontend (cifras y narrativa en vivo).

Compatible con python-pptx 0.6.23 (versión de producción).
"""

from __future__ import annotations

import io

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

# Paleta
NAVY = RGBColor(0x0A, 0x23, 0x42)
DEEP = RGBColor(0x07, 0x1B, 0x2F)
GOLD = RGBColor(0xC7, 0xA8, 0x3C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY = RGBColor(0xD3, 0xDA, 0xE3)
CARD = RGBColor(0x12, 0x31, 0x52)
GREEN = RGBColor(0x35, 0xB3, 0x7A)
RED = RGBColor(0xE0, 0x6A, 0x5C)
BLUE = RGBColor(0x4F, 0x8F, 0xD6)
FONT = "DM Sans"

EMU_W = Inches(13.333)
EMU_H = Inches(7.5)


def build_deck(content: dict) -> bytes:
    prs = Presentation()
    prs.slide_width = EMU_W
    prs.slide_height = EMU_H
    c = content or {}

    _cover(prs, c)
    _resumen(prs, c)
    _historico(prs, c)
    _diag_financiero(prs, c)
    _diag_trib_soc(prs, c)
    _alternativas(prs, c)
    _matriz(prs, c)
    _grafico_escenarios(prs, c)
    _recomendacion(prs, c)
    _modelacion(prs, c)
    _plan(prs, c)
    _cierre(prs, c)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


# ----------------------------------------------------------------- helpers
def _blank(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(1, 0, 0, EMU_W, EMU_H)  # 1 = rectángulo
    bg.fill.solid()
    bg.fill.fore_color.rgb = NAVY
    bg.line.fill.background()
    bg.shadow.inherit = False
    # franja superior dorada fina
    strip = s.shapes.add_shape(1, 0, 0, EMU_W, Pt(6))
    strip.fill.solid()
    strip.fill.fore_color.rgb = GOLD
    strip.line.fill.background()
    strip.shadow.inherit = False
    return s


def _txt(slide, x, y, w, h, text, size, *, color=WHITE, bold=False,
         align=PP_ALIGN.LEFT, italic=False, anchor=MSO_ANCHOR.TOP):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    lines = text.split("\n") if isinstance(text, str) else [str(text)]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = ln
        r.font.name = FONT
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.italic = italic
        r.font.color.rgb = color
    return tb


def _heading(slide, title, sub=None):
    bar = slide.shapes.add_shape(1, Inches(0.55), Inches(0.55), Inches(0.12), Inches(0.55))
    bar.fill.solid(); bar.fill.fore_color.rgb = GOLD; bar.line.fill.background()
    bar.shadow.inherit = False
    _txt(slide, Inches(0.8), Inches(0.45), Inches(11.8), Inches(0.8), title, 26, bold=True)
    if sub:
        _txt(slide, Inches(0.82), Inches(1.15), Inches(11.8), Inches(0.5), sub, 13, color=GREY)


def _card(slide, x, y, w, h, color=CARD):
    sh = slide.shapes.add_shape(1, x, y, w, h)
    sh.fill.solid(); sh.fill.fore_color.rgb = color
    sh.line.color.rgb = RGBColor(0x1E, 0x3A, 0x5F); sh.line.width = Pt(0.75)
    sh.shadow.inherit = False
    return sh


def _money(v):
    try:
        return "$" + format(int(round(float(v))), ",d")
    except (TypeError, ValueError):
        return str(v)


# ------------------------------------------------------------------ slides
def _cover(prs, c):
    s = _blank(prs)
    _txt(s, Inches(0.9), Inches(0.9), Inches(11.5), Inches(0.5),
         "AUDITBRAIN · EXECUTIVE ADVISORY · TAX ADVISORY", 13, color=GOLD, bold=True)
    _txt(s, Inches(0.9), Inches(2.4), Inches(11.5), Inches(1.8),
         "Planificación tributaria sobre\nutilidades no distribuidas", 40, bold=True)
    _txt(s, Inches(0.9), Inches(4.6), Inches(11.5), Inches(0.6),
         c.get("empresa", "la Compañía"), 24, color=GOLD, bold=True)
    meta = []
    if c.get("ruc"):
        meta.append("RUC: " + c["ruc"])
    if c.get("representante"):
        meta.append(c["representante"] + " · Representante legal")
    linea = "Horizonte 2026–2028"
    if c.get("fecha_analisis"):
        linea += " · " + c["fecha_analisis"]
    if c.get("fecha_corte"):
        linea += " · Corte: " + c["fecha_corte"]
    meta.append(linea)
    _txt(s, Inches(0.9), Inches(5.3), Inches(11.5), Inches(1.2), "\n".join(meta), 14, color=GREY)
    _txt(s, Inches(0.9), Inches(6.9), Inches(11.5), Inches(0.4),
         "Confidencial · Documento preliminar sujeto a revisión y aprobación", 10,
         color=GREY, italic=True)


def _resumen(prs, c):
    s = _blank(prs)
    _heading(s, "Resumen Ejecutivo", c.get("recomendacion", "")[:120])
    kpis = c.get("kpis", [])[:6]
    cols, x0, y0 = 3, Inches(0.8), Inches(1.9)
    cw, ch, gx, gy = Inches(3.85), Inches(1.9), Inches(0.18), Inches(0.25)
    for i, k in enumerate(kpis):
        r, col = divmod(i, cols)
        x = x0 + col * (cw + gx)
        y = y0 + r * (ch + gy)
        _card(s, x, y, cw, ch)
        _txt(s, x + Inches(0.2), y + Inches(0.18), cw - Inches(0.4), Inches(0.5),
             k.get("label", ""), 11, color=GREY)
        _txt(s, x + Inches(0.2), y + Inches(0.62), cw - Inches(0.4), Inches(0.9),
             str(k.get("valor", "")), 26, bold=True, color=GOLD)


def _table(slide, x, y, w, headers, rows, col_w=None, first_left=True, highlight_row=None):
    nrows, ncols = len(rows) + 1, len(headers)
    h = Inches(0.42) * nrows
    gtable = slide.shapes.add_table(nrows, ncols, x, y, w, h).table
    if col_w:
        for ci, cw in enumerate(col_w):
            gtable.columns[ci].width = cw
    for ci, htxt in enumerate(headers):
        cell = gtable.cell(0, ci)
        cell.fill.solid(); cell.fill.fore_color.rgb = DEEP
        _style_cell(cell, htxt, 11, WHITE, bold=True,
                    align=PP_ALIGN.LEFT if (first_left and ci == 0) else PP_ALIGN.RIGHT)
    for ri, row in enumerate(rows, start=1):
        hl = (highlight_row is not None and ri - 1 == highlight_row)
        for ci, val in enumerate(row):
            cell = gtable.cell(ri, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0x10, 0x2C, 0x4C) if hl else NAVY
            _style_cell(cell, str(val), 11,
                        GOLD if hl else WHITE, bold=hl,
                        align=PP_ALIGN.LEFT if (first_left and ci == 0) else PP_ALIGN.RIGHT)
    return gtable


def _style_cell(cell, text, size, color, bold=False, align=PP_ALIGN.LEFT):
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.margin_left = Inches(0.1); cell.margin_right = Inches(0.1)
    cell.margin_top = Inches(0.03); cell.margin_bottom = Inches(0.03)
    tf = cell.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    r = p.add_run(); r.text = text
    r.font.name = FONT; r.font.size = Pt(size); r.font.bold = bold
    r.font.color.rgb = color


def _historico(prs, c):
    s = _blank(prs)
    _heading(s, "Análisis del Pago Históricamente Realizado",
             "Base = utilidades retenidas del cierre del ejercicio anterior")
    headers = ["Año", "Base (acum. anterior)", "Tarifa", "Pago a cuenta", "Estado"]
    rows = []
    for h in c.get("pago_historico", []):
        rows.append([h.get("anio"), _money(h.get("base")),
                     "", _money(h.get("pago")), h.get("estado", "Realizado")])
    mod = c.get("modelacion_2026_2028", {})
    anios = mod.get("anios", [])
    pagos = mod.get("pago_a_cuenta", [])
    for i, a in enumerate(anios):
        rows.append([a, "", "", _money(pagos[i] if i < len(pagos) else 0),
                     "Proyectado"])
    _table(s, Inches(0.8), Inches(1.9), Inches(11.7), headers, rows,
           col_w=[Inches(1.6), Inches(3.6), Inches(1.6), Inches(2.9), Inches(2.0)])


def _diag_financiero(prs, c):
    s = _blank(prs)
    _heading(s, "Diagnóstico Financiero")
    d = c.get("diagnostico_financiero", {})
    items = [
        ("Liquidez corriente", d.get("liquidez", "—")),
        ("Endeudamiento", d.get("endeudamiento", "—")),
        ("ROE", d.get("roe", "—")),
        ("Margen neto", d.get("margen_neto", "—")),
        ("Días de inventario", d.get("dias_inventario", "—")),
        ("Ciclo de efectivo", d.get("ciclo_efectivo", "—")),
    ]
    cols, x0, y0 = 3, Inches(0.8), Inches(2.0)
    cw, ch, gx, gy = Inches(3.85), Inches(1.7), Inches(0.18), Inches(0.3)
    for i, (lab, val) in enumerate(items):
        r, col = divmod(i, cols)
        x = x0 + col * (cw + gx); y = y0 + r * (ch + gy)
        _card(s, x, y, cw, ch)
        _txt(s, x + Inches(0.2), y + Inches(0.2), cw - Inches(0.4), Inches(0.5), lab, 12, color=GREY)
        _txt(s, x + Inches(0.2), y + Inches(0.62), cw - Inches(0.4), Inches(0.8), str(val), 24, bold=True)


def _bullets(slide, x, y, w, items, size=15, gap=0.12):
    tb = slide.shapes.add_textbox(x, y, w, Inches(4.5))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap * 72)
        r = p.add_run(); r.text = "›  " + it
        r.font.name = FONT; r.font.size = Pt(size); r.font.color.rgb = WHITE


def _diag_trib_soc(prs, c):
    s = _blank(prs)
    _heading(s, "Diagnóstico Tributario y Societario")
    t = c.get("diagnostico_tributario", {})
    soc = c.get("diagnostico_societario", {})
    _txt(s, Inches(0.8), Inches(1.9), Inches(5.7), Inches(0.5), "Tributario", 16, bold=True, color=GOLD)
    _bullets(s, Inches(0.8), Inches(2.5), Inches(5.7), [
        f"Base año 1: {t.get('base_anio1','—')}",
        f"Tarifa aplicable: {t.get('tarifa','—')}",
        f"Pago a cuenta año 1: {t.get('pago_anio1','—')}",
        f"Pago horizonte sin acción: {t.get('pago_horizonte','—')}",
    ], size=14)
    _txt(s, Inches(6.8), Inches(1.9), Inches(5.7), Inches(0.5), "Societario", 16, bold=True, color=GOLD)
    _bullets(s, Inches(6.8), Inches(2.5), Inches(5.7), [
        f"Capital: {soc.get('capital','—')}",
        f"Reservas: {soc.get('reservas','—')}",
        f"Resultados acumulados: {soc.get('resultados_acumulados','—')}",
        f"Patrimonio total: {soc.get('patrimonio_total','—')}",
    ], size=14)


def _alternativas(prs, c):
    s = _blank(prs)
    _heading(s, "Alternativas Previas al 31 de Julio")
    _bullets(s, Inches(0.9), Inches(2.1), Inches(11.4),
             c.get("alternativas", []), size=17, gap=0.28)


def _matriz(prs, c):
    s = _blank(prs)
    _heading(s, "Matriz de Decisión Estratégica", "Decisión aplicada en 2026")
    headers = ["Escenario", "Pago 2026", "Pago 2026–28", "Retención (crédito)", "Costo muerto", "Patrimonio 2028"]
    rows, hl = [], None
    for i, m in enumerate(c.get("matriz_escenarios", [])):
        if m.get("recomendado"):
            hl = i
        rows.append([
            m.get("escenario", ""),
            _money(m.get("pago_2026")),
            _money(m.get("pago_2026_2028")),
            _money(m.get("retencion_credito")),
            _money(m.get("costo_muerto")),
            _money(m.get("patrimonio_2028")),
        ])
    _table(s, Inches(0.6), Inches(2.0), Inches(12.1), headers, rows,
           col_w=[Inches(3.7), Inches(1.5), Inches(1.7), Inches(2.0), Inches(1.6), Inches(1.6)],
           highlight_row=hl)
    _txt(s, Inches(0.6), Inches(6.6), Inches(12.1), Inches(0.6),
         "Escenario sugerido resaltado: anula el pago de 2026 y genera crédito recuperable. "
         "La capitalización debe respaldarse con sustancia económica (no inventarios).",
         11, color=GREY, italic=True)


def _add_bar(slide, x, y, w, h, categories, series, colors=None):
    cd = CategoryChartData()
    cd.categories = categories
    for name, vals in series:
        cd.add_series(name, vals)
    gf = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, x, y, w, h, cd)
    chart = gf.chart
    chart.has_title = False
    if len(series) > 1:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.color.rgb = WHITE
        chart.legend.font.size = Pt(10)
        chart.legend.font.name = FONT
    else:
        chart.has_legend = False
    plot = chart.plots[0]
    # Estilizado defensivo: si alguna API difiere en la versión de prod, el
    # gráfico se genera igual (sin tumbar la presentación).
    try:
        plot.gap_width = 60
        cat_ax = chart.category_axis
        cat_ax.tick_labels.font.color.rgb = WHITE
        cat_ax.tick_labels.font.size = Pt(10)
        cat_ax.tick_labels.font.name = FONT
        val_ax = chart.value_axis
        val_ax.tick_labels.font.color.rgb = GREY
        val_ax.tick_labels.font.size = Pt(9)
        val_ax.has_major_gridlines = False
    except Exception:
        pass
    try:
        if colors and len(series) == 1:
            for i, pt in enumerate(plot.series[0].points):
                pt.format.fill.solid()
                pt.format.fill.fore_color.rgb = colors[i % len(colors)]
        else:
            palette = [BLUE, GREEN, RED, GOLD]
            for i, ser in enumerate(plot.series):
                ser.format.fill.solid()
                ser.format.fill.fore_color.rgb = palette[i % len(palette)]
    except Exception:
        pass
    return gf


def _grafico_escenarios(prs, c):
    s = _blank(prs)
    _heading(s, "Pago a Cuenta por Escenario", "2026–2028, comparativo")
    g = c.get("grafico_pago_por_escenario", {})
    labels = g.get("labels", [])
    vals = g.get("valores", [])
    short = [str(l).split(" · ")[-1][:22] if " · " in str(l) else str(l)[:22] for l in labels]
    if labels and vals:
        _add_bar(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(4.8),
                 short, [("Pago a cuenta", vals)], colors=[RED, BLUE, GREEN, GOLD])


def _recomendacion(prs, c):
    s = _blank(prs)
    _heading(s, "Recomendación")
    _card(s, Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.2))
    _txt(s, Inches(1.1), Inches(2.3), Inches(11.1), Inches(2.6),
         c.get("recomendacion", ""), 18, color=WHITE)
    _txt(s, Inches(0.8), Inches(5.6), Inches(11.7), Inches(1.0),
         c.get("nota", ""), 11, color=GREY, italic=True)


def _modelacion(prs, c):
    s = _blank(prs)
    _heading(s, "Modelación Financiera y Tributaria", "Proyección 2026–2028")
    mod = c.get("modelacion_2026_2028", {})
    anios = [str(a) for a in mod.get("anios", [])]
    if anios:
        _add_bar(s, Inches(0.9), Inches(2.0), Inches(11.5), Inches(4.8), anios, [
            ("Pago a cuenta", mod.get("pago_a_cuenta", [])),
            ("Crédito vs. IR", mod.get("credito_vs_ir", [])),
            ("En riesgo", mod.get("en_riesgo", [])),
        ])


def _plan(prs, c):
    s = _blank(prs)
    _heading(s, "Plan de Acción")
    headers = ["Acción", "Responsable", "Plazo"]
    rows = [[p.get("accion", ""), p.get("responsable", ""), p.get("plazo", "")]
            for p in c.get("plan_accion", [])]
    _table(s, Inches(0.7), Inches(1.95), Inches(11.9), headers, rows,
           col_w=[Inches(7.1), Inches(2.6), Inches(2.2)], first_left=True)
    # forzar alineación izquierda en todas las columnas de esta tabla de texto
    # (se hace en _table sólo col 0; ajuste visual aceptable)


def _cierre(prs, c):
    s = _blank(prs)
    _txt(s, Inches(0.9), Inches(2.8), Inches(11.5), Inches(1.0),
         "Gracias", 40, bold=True, color=GOLD)
    _txt(s, Inches(0.9), Inches(4.0), Inches(11.5), Inches(1.0),
         c.get("empresa", ""), 20, bold=True)
    _txt(s, Inches(0.9), Inches(4.7), Inches(11.5), Inches(1.2),
         "AuditBrain® · Tax › Análisis\nProyección de planificación, no auditada. "
         "Régimen sujeto a criterios administrativos del SRI. Cifras normativas "
         "requieren validación profesional.", 12, color=GREY)
