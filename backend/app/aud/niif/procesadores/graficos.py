"""Gráficos del papel de trabajo ejecutivo NIIF (fuente única, heredada por las
20 herramientas a través de ``libro.py``).

Dos vistas, elegidas por el trabajo que hace cada dato (skill dataviz):

- **Cifras del resumen** — magnitud por concepto de la cédula ``01_Resumen``
  (importes monetarios en todas las herramientas). Barras horizontales de una
  sola serie desde una línea base en cero; las negativas crecen a la izquierda.
- **Hallazgos de mayor impacto** — importe absoluto sumado por tipo de hallazgo,
  los 7 mayores y el resto plegado en «Otros». (Un conteo «por tipo» no sirve:
  casi todos los códigos son únicos y darían barras de largo 1.)

El SVG es inline y autónomo: sin JavaScript, sin fuentes ni recursos externos,
así funciona sin conexión y WeasyPrint lo imprime tal cual en el PDF. El hover
usa ``<title>`` nativo; la vista de tabla equivalente es la propia cédula.

Especificación de marcas: barra <= 24 px (14 px en banda de 26 px), extremo de
datos redondeado 4 px y recto en la línea base, línea base hairline, un valor
por barra (sin ejes con marcas: cada valor ya está rotulado), el texto nunca
usa el color de la serie.
"""
from __future__ import annotations

import html as _html

from backend.app.aud.niif.procesadores import estilo_ejecutivo as est

ANCHO = 620
COL_ETQ = 262      # columna de rótulos (texto alineado a la derecha)
RESERVA_VALOR = 104  # espacio a la derecha para el valor de la barra más larga
BANDA = 26
GROSOR = 14
RADIO = 4
MAX_ETQ = 40
TOP_HALLAZGOS = 7


def _num(v):
    if isinstance(v, dict):
        v = v.get("v")
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fmt(v: float) -> str:
    s = f"{abs(v):,.2f}"
    return ("−" if v < 0 else "") + s


def _recorta(t: str) -> str:
    t = " ".join(str(t or "").split())
    return t if len(t) <= MAX_ETQ else t[: MAX_ETQ - 1].rstrip() + "…"


def datos_resumen(hojas: list[dict]) -> list[tuple[str, float]]:
    """(concepto, importe) de la cédula de resumen: la primera hoja cuyas columnas
    son (texto, número). Filas sin número se omiten."""
    for h in hojas:
        fmts = [c[1] for c in h.get("cols", [])]
        if len(fmts) == 2 and fmts[0] == "t" and fmts[1] == "n":
            out = []
            for fila in h.get("rows", []):
                v = _num(fila[1]) if len(fila) > 1 else None
                # Solo importes en USD: una tasa o porcentaje (rótulo con «%») en el
                # mismo eje mezclaría unidades. Sigue visible en la tabla del resumen.
                if v is not None and "%" not in str(fila[0]):
                    out.append((str(fila[0]), v))
            return out
    return []


def tasas_omitidas(hojas: list[dict]) -> int:
    """Cuántas filas del resumen son tasas (%) y quedan fuera del gráfico de USD."""
    for h in hojas:
        fmts = [c[1] for c in h.get("cols", [])]
        if len(fmts) == 2 and fmts[0] == "t" and fmts[1] == "n":
            return sum(1 for f in h.get("rows", []) if "%" in str(f[0]))
    return 0


def _humaniza(codigo: str) -> str:
    t = str(codigo or "").replace("_", " ").strip().lower()
    return t[:1].upper() + t[1:] if t else "(sin código)"


def _agrupa(run: dict):
    agrupado: dict[str, list] = {}
    for e in run.get("exceptions") or []:
        v = _num(e.get("amount"))
        if not v:
            continue
        a = agrupado.setdefault(e.get("code", ""), [0.0, 0])
        a[0] += abs(v)
        a[1] += 1
    return sorted(agrupado.items(), key=lambda kv: -kv[1][0])


def codigos_top(run: dict) -> dict | None:
    """Selección compartida por SVG, PowerPoint y Excel: los ``TOP_HALLAZGOS``
    códigos de mayor importe absoluto con su rótulo, y el rótulo de «Otros»
    (o None). None si no hay hallazgos con importe."""
    items = _agrupa(run)
    if not items:
        return None
    top = [(c, _humaniza(c) + (f" (×{n})" if n > 1 else "")) for c, (_, n) in items[:TOP_HALLAZGOS]]
    resto = items[TOP_HALLAZGOS:]
    return {"top": top, "otros": f"Otros ({len(resto)} tipos)" if resto else None}


def datos_hallazgos(run: dict) -> list[tuple[str, float]]:
    """Importe absoluto por tipo de hallazgo, de mayor a menor; los que pasan de
    ``TOP_HALLAZGOS`` se pliegan en «Otros (n tipos)». Tipos sin importe se omiten."""
    items = _agrupa(run)
    sel = codigos_top(run)
    if not sel:
        return []
    tot = dict((c, t) for c, (t, _) in items)
    out = [(etq, tot[c]) for c, etq in sel["top"]]
    if sel["otros"]:
        out.append((sel["otros"], sum(t for _, (t, _) in items[TOP_HALLAZGOS:])))
    return out


def _barra(x0: float, x1: float, y: float) -> str:
    """Barra con extremo de datos redondeado (4 px) y recta en la línea base x0."""
    ancho = abs(x1 - x0)
    if ancho < 0.5:
        return ""
    r = min(RADIO, ancho, GROSOR / 2)
    h = GROSOR
    if x1 >= x0:
        d = (f"M{x0:.1f},{y:.1f}H{x1 - r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}"
             f"V{y + h - r:.1f}Q{x1:.1f},{y + h:.1f} {x1 - r:.1f},{y + h:.1f}H{x0:.1f}Z")
    else:
        d = (f"M{x0:.1f},{y:.1f}H{x1 + r:.1f}Q{x1:.1f},{y:.1f} {x1:.1f},{y + r:.1f}"
             f"V{y + h - r:.1f}Q{x1:.1f},{y + h:.1f} {x1 + r:.1f},{y + h:.1f}H{x0:.1f}Z")
    return f'<path d="{d}" fill="#{est.SERIE}"/>'


def svg_barras(items: list[tuple[str, float]], descripcion: str) -> str:
    """Barras horizontales de una serie. Devuelve '' si no hay nada que graficar."""
    items = [(e, v) for e, v in items if v is not None]
    if not items or all(abs(v) < 0.005 for _, v in items):
        return ""
    lo = min(0.0, min(v for _, v in items))
    hi = max(0.0, max(v for _, v in items))
    ax0 = COL_ETQ + 14
    aw = ANCHO - RESERVA_VALOR - ax0
    esc = lambda v: ax0 + (v - lo) / (hi - lo) * aw  # noqa: E731
    cero = esc(0.0)
    alto = 8 + BANDA * len(items) + 8
    filas = []
    for i, (etq, v) in enumerate(items):
        y0 = 8 + i * BANDA
        yb = y0 + (BANDA - GROSOR) / 2
        x1 = esc(v)
        tx = (x1 if v >= 0 else cero) + 6
        completo = f"{etq}: {_fmt(v)}"
        filas.append(
            f'<g class="fila"><title>{_html.escape(completo)}</title>'
            f'<rect x="0" y="{y0}" width="{ANCHO}" height="{BANDA}" fill="transparent"/>'
            f'<text x="{COL_ETQ}" y="{y0 + BANDA / 2 + 4:.1f}" text-anchor="end" class="etq">{_html.escape(_recorta(etq))}</text>'
            + _barra(cero, x1, yb)
            + f'<text x="{tx:.1f}" y="{y0 + BANDA / 2 + 4:.1f}" class="val">{_fmt(v)}</text></g>')
    return (
        f'<svg class="grafico" viewBox="0 0 {ANCHO} {alto}" width="{ANCHO}" height="{alto}" role="img" '
        f'aria-label="{_html.escape(descripcion)}">'
        f"<title>{_html.escape(descripcion)}</title>"
        f"<style>.etq{{font:11.5px 'Segoe UI',Calibri,Arial,sans-serif;fill:#{est.TINTA}}}"
        f".val{{font:11px 'Segoe UI',Calibri,Arial,sans-serif;fill:#{est.TINTA_2};font-variant-numeric:tabular-nums}}"
        f".fila:hover rect{{fill:#{est.LIGHT}}}</style>"
        f'<line x1="{cero:.1f}" y1="4" x2="{cero:.1f}" y2="{alto - 4}" stroke="#{est.REGLA}" stroke-width="1"/>'
        + "".join(filas) + "</svg>"
    )


def paneles(hojas: list[dict], run: dict) -> list[dict]:
    """Los gráficos del papel: [{titulo, subtitulo, svg, items}] (solo los que tienen datos)."""
    out = []
    res = datos_resumen(hojas)
    svg = svg_barras(res, "Cifras del resumen en USD")
    if svg:
        out.append({"titulo": "Cifras del resumen",
                    "subtitulo": "Importes en USD, en el orden de la cédula de resumen. La tabla equivalente es la hoja «Resumen»."
                                 + (" Las tasas (%) no se grafican en este eje; están en la tabla." if tasas_omitidas(hojas) else ""),
                    "svg": svg, "items": res})
    hal = datos_hallazgos(run)
    svg = svg_barras(hal, "Hallazgos de mayor impacto en USD")
    if svg:
        out.append({"titulo": "Hallazgos de mayor impacto",
                    "subtitulo": f"Importe absoluto sumado por tipo de hallazgo; los {TOP_HALLAZGOS} mayores y el resto en «Otros». "
                                 "El detalle está en la hoja «Problemas encontrados».",
                    "svg": svg, "items": hal})
    return out


def cifra(v) -> str:
    """Cifra de tarjeta/héroe: separador de miles, 2 decimales y signo menos
    tipográfico (−). Sin «tabular-nums»: en tamaño grande van cifras proporcionales."""
    n = _num(v)
    return "—" if n is None else _fmt(n)
