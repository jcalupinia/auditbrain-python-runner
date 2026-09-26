"""Los gráficos del panel del HTML convertidos a imagen PNG para el Word y el PowerPoint.

El dueño pidió (2026-09-25) que el Word y el PowerPoint se vean igual al HTML. En el
servidor no hay navegador ni un conversor SVG→PNG, así que este módulo dibuja con
matplotlib los MISMOS SVG que genera ``graficos_svg`` para el HTML (mismas coordenadas,
colores, textos y efecto 3D). Si el HTML cambia un gráfico, el Word y el PowerPoint
cambian con él.

Solo interpreta el subconjunto de SVG que produce ``graficos_svg``: ``line`` (con
``stroke-dasharray``/``stroke-opacity``), ``rect`` (con ``rx``), ``polygon``, ``polyline``, ``circle``,
``path`` (M, L, A, Z), ``text``/``tspan``, grupos ``g`` y degradados lineales verticales
(``linearGradient`` en ``defs``, usados como ``fill="url(#id)"``).
"""
from __future__ import annotations

import io
import math
import re
import xml.etree.ElementTree as ET
from functools import lru_cache

from backend.app.aud.niif.procesadores import graficos_svg as gs
from backend.app.aud.niif.procesadores import html_ejecutivo as hx

_NS = "{http://www.w3.org/2000/svg}"


def paleta(tema: str) -> dict:
    """Colores literales del tema del HTML («claro» o «ejecutivo») con los roles de ``graficos_svg``."""
    if tema == "claro":
        return dict(gs.CLARO)
    t = hx.TEMAS[tema][1]
    return {k[2:]: v for k, v in t.items() if k.startswith("c-")}


def _num(t: str | None, defecto: float = 0.0) -> float:
    try:
        return float(t)
    except (TypeError, ValueError):
        return defecto


def _puntos(t: str) -> list[tuple[float, float]]:
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", t or "")]
    return list(zip(nums[0::2], nums[1::2]))


def _arco(x1, y1, rx, ry, fi, fa, fs, x2, y2, pasos=48):
    """Puntos de un arco SVG (parametrización por extremos → centro, SVG 1.1 F.6.5)."""
    if rx == 0 or ry == 0:
        return [(x2, y2)]
    phi = math.radians(fi)
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    x1p, y1p = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (x1p ** 2) / (rx ** 2) + (y1p ** 2) / (ry ** 2)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx ** 2 * ry ** 2 - rx ** 2 * y1p ** 2 - ry ** 2 * x1p ** 2
    den = rx ** 2 * y1p ** 2 + ry ** 2 * x1p ** 2
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if fa == fs:
        coef = -coef
    cxp, cyp = coef * rx * y1p / ry, -coef * ry * x1p / rx
    cx, cy = cp * cxp - sp * cyp + (x1 + x2) / 2, sp * cxp + cp * cyp + (y1 + y2) / 2

    def ang(ux, uy, vx, vy):
        a = math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
        return a

    t1 = ang(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dt = ang((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not fs and dt > 0:
        dt -= 2 * math.pi
    elif fs and dt < 0:
        dt += 2 * math.pi
    out = []
    for k in range(1, pasos + 1):
        t = t1 + dt * k / pasos
        out.append((cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp))
    return out


def _camino(d: str) -> list[tuple[float, float]]:
    fichas = re.findall(r"[MLAZ]|-?\d+(?:\.\d+)?", d)
    pts: list[tuple[float, float]] = []
    i, cmd = 0, None
    while i < len(fichas):
        f = fichas[i]
        if f in "MLAZ":
            cmd = f
            i += 1
            if cmd == "Z":
                continue
        if cmd in ("M", "L"):
            pts.append((float(fichas[i]), float(fichas[i + 1])))
            i += 2
        elif cmd == "A":
            rx, ry, fi, fa, fs, x2, y2 = (float(v) for v in fichas[i:i + 7])
            x1, y1 = pts[-1]
            pts += _arco(x1, y1, rx, ry, fi, int(fa), int(fs), x2, y2)
            i += 7
        else:
            i += 1
    return pts


@lru_cache(maxsize=128)
def a_png(svg: str, escala: float = 2.5, fondo: str | None = None) -> bytes:
    """Dibuja el SVG de ``graficos_svg`` con matplotlib y devuelve el PNG (en caché: el mismo
    gráfico no se vuelve a dibujar al pedir el Word y el HTML, que trae el Word dentro)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import to_rgba
    from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle

    raiz = ET.fromstring(svg.replace('xmlns="http://www.w3.org/2000/svg"', ""))
    # Degradados lineales verticales de <defs> (tableros): id → (invertido, [(offset, rgba)]).
    degradados = {}
    for g in raiz.iter():
        if g.tag.replace(_NS, "") == "linearGradient":
            paradas = [(_num(st.get("offset")), to_rgba(st.get("stop-color"), _num(st.get("stop-opacity"), 1.0)))
                       for st in g if st.tag.replace(_NS, "") == "stop"]
            degradados[g.get("id")] = (_num(g.get("y1")) > _num(g.get("y2")), paradas)
    _, _, W, H = (float(v) for v in raiz.get("viewBox").split())
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100 * escala)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)
    ax.axis("off")
    fig.patch.set_alpha(0 if fondo is None else 1)
    if fondo:
        fig.patch.set_facecolor(fondo)
    pt = 0.72  # 1 px del viewBox = 0,72 pt con la figura a 100 px por pulgada
    z = [0]

    def zz():
        z[0] += 1
        return z[0]

    def relleno(el):
        f = el.get("fill")
        return None if f in (None, "none") or f.startswith("url(") else f

    def con_degradado(el, patch):
        """Si el relleno es ``url(#id)``, pinta el degradado recortado a la figura (``patch``)."""
        f = el.get("fill") or ""
        m = re.match(r"url\(#([^)]+)\)", f)
        if not m or m.group(1) not in degradados:
            return False
        import numpy as np

        invertido, paradas = degradados[m.group(1)]
        ax.add_patch(patch)
        patch.set_facecolor("none")
        (x0, y0), (x1, y1) = patch.get_path().get_extents(patch.get_patch_transform()).get_points() \
            if hasattr(patch, "get_patch_transform") else patch.get_extents().get_points()
        t = np.linspace(0, 1, 64)
        if invertido:
            t = t[::-1]
        offs = [o for o, _ in paradas]
        img = np.stack([np.interp(t, offs, [c[k] for _, c in paradas]) for k in range(4)], axis=-1)[:, None, :]
        im = ax.imshow(img, extent=(x0, x1, y1, y0), origin="upper", aspect="auto", interpolation="bilinear", zorder=zz())
        im.set_clip_path(patch)
        return True

    def dibuja(el):
        tag = el.tag.replace(_NS, "")
        fo = _num(el.get("fill-opacity"), 1.0)
        if tag in ("svg", "g"):
            for h in el:
                dibuja(h)
        elif tag == "line":
            ln, = ax.plot([_num(el.get("x1")), _num(el.get("x2"))], [_num(el.get("y1")), _num(el.get("y2"))],
                          color=el.get("stroke"), linewidth=_num(el.get("stroke-width"), 1) * pt, zorder=zz(), solid_capstyle="butt",
                          alpha=_num(el.get("stroke-opacity"), 1.0))
            if el.get("stroke-dasharray"):
                ln.set_dashes([_num(v) * pt for v in el.get("stroke-dasharray").split()])
        elif tag == "rect":
            x, y, w, h, rx = (_num(el.get(a)) for a in ("x", "y", "width", "height", "rx"))
            if rx:
                patch = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={min(rx, w / 2, h / 2)}",
                                       facecolor=relleno(el), alpha=fo, linewidth=0, zorder=zz(), mutation_aspect=1)
            else:
                patch = Rectangle((x, y), w, h, facecolor=relleno(el), alpha=fo, linewidth=0, zorder=zz())
            if not con_degradado(el, patch):
                ax.add_patch(patch)
        elif tag == "polygon":
            ax.add_patch(Polygon(_puntos(el.get("points")), closed=True, facecolor=relleno(el), alpha=fo, linewidth=0, zorder=zz()))
        elif tag == "polyline":
            xs, ys = zip(*_puntos(el.get("points")))
            ax.plot(xs, ys, color=el.get("stroke"), linewidth=_num(el.get("stroke-width"), 2) * pt,
                    solid_joinstyle="round", solid_capstyle="round", zorder=zz())
        elif tag == "circle":
            c = (_num(el.get("cx")), _num(el.get("cy")))
            if el.get("stroke") and relleno(el) is None:
                ax.add_patch(Circle(c, _num(el.get("r")), facecolor="none", edgecolor=el.get("stroke"),
                                    linewidth=_num(el.get("stroke-width"), 1) * pt, zorder=zz()))
            else:
                ax.add_patch(Circle(c, _num(el.get("r")), facecolor=relleno(el), alpha=fo, linewidth=0, zorder=zz()))
        elif tag == "path":
            patch = Polygon(_camino(el.get("d")), closed=True, facecolor=relleno(el), alpha=fo, linewidth=0, zorder=zz())
            if not con_degradado(el, patch):
                ax.add_patch(patch)
        elif tag == "text":
            x, y = _num(el.get("x")), _num(el.get("y"))
            ha = {"middle": "center", "end": "right"}.get(el.get("text-anchor"), "left")
            estilo = dict(color=el.get("fill") or "#000000", fontsize=_num(el.get("font-size"), 11) * pt,
                          fontweight="bold" if el.get("font-weight") in ("600", "700", "bold") else "normal",
                          ha=ha, va="baseline", zorder=zz())
            tsp = [h for h in el if h.tag.replace(_NS, "") == "tspan"]
            if tsp:
                yy = y
                for h in tsp:
                    yy += _num(h.get("dy"))
                    ax.text(_num(h.get("x"), x), yy, h.text or "", **estilo)
            else:
                ax.text(x, y, (el.text or "") + "".join((h.tail or "") for h in el), **estilo)

    dibuja(raiz)
    salida = io.BytesIO()
    fig.savefig(salida, format="png", dpi=100 * escala, transparent=fondo is None)
    plt.close(fig)
    return salida.getvalue()


def graficos_panel(p: dict, tema: str) -> list[dict]:
    """Los 4 gráficos del panel del HTML (mismos títulos, subtítulos y variante por defecto
    «barras + línea») como PNG: [{titulo, sub, png, ancho, alto}]."""
    hex_ = paleta(tema)
    comp, cmp_, dist, sev = p["composicion"], p["comparativo"], p["distribucion"], p["severidad"]
    specs = [
        ("Composición del resultado", comp["rotulo"], gs.dona(comp["items"], comp["rotulo"], hex_)),
        (cmp_["rotulo"], cmp_.get("sub") or "Cifra del cliente frente a la recalculada por el auditor (USD).",
         gs.columnas(cmp_["items"], hx.POR_DEFECTO["g"], ["registrado", "recalculado"], cmp_["rotulo"], hex_)),
        (dist["rotulo"], "Distribución de la población (USD).",
         gs.columnas(dist["items"], hx.POR_DEFECTO["g"], "serie", dist["rotulo"], hex_)),
        (sev["rotulo"], sev["regla"],
         gs.columnas(sev["items"], hx.POR_DEFECTO["g"], ["alta", "media", "baja", "informativa"], sev["rotulo"], hex_, enteros=True)),
    ]
    return [{"titulo": t, "sub": s, "png": a_png(svg) if svg else None, "ancho": gs.ANCHO, "alto": gs.ALTO}
            for t, s, svg in specs]


def tableros_panel(p: dict, tema: str) -> list[dict]:
    """Los tableros adicionales del panel del HTML (``PANEL["tableros"]``) como PNG, con el mismo
    formato que ``graficos_panel``."""
    hex_ = paleta(tema)
    salida = []
    for t in p.get("tableros") or []:
        svg = gs.agrupadas(t["categorias"], t["series"], t["rotulo"], t.get("unidad", ""), hex_, t.get("mejor"), t.get("estados"))
        salida.append({"titulo": t["rotulo"], "sub": t.get("sub", ""), "png": a_png(svg) if svg else None,
                       "ancho": gs.ANCHO, "alto": gs.ALTO})
    return salida
