"""Gráficos SVG propios del dashboard ejecutivo del papel de trabajo NIIF.

Sin librerías ni recursos externos: el HTML funciona sin conexión y WeasyPrint
los imprime en el PDF.

- ``columnas(...)``: gráfico de categorías en cinco variantes elegibles desde el
  selector «Gráfico» del HTML: barras 3D + línea, barras 3D, líneas, área y
  puntos. Una sola medida; cada marca lleva su valor rotulado (no hace falta eje
  con marcas) y un ``<title>`` con el valor completo (hover).
- ``dona(...)``: composición con el porcentaje del componente mayor al centro y
  leyenda con valor y porcentaje de cada parte.

Colores. En el HTML los colores salen de variables CSS del tema elegido
(``style="fill:var(--c-s1)"``), así el selector «Color» los cambia sin volver a
dibujar. Para el PDF (``hex=...``) se escriben colores literales del tema Claro,
porque el renderizador SVG de WeasyPrint no resuelve variables CSS.
La paleta categórica es la de referencia de la skill dataviz, validada con
``validate_palette.js`` sobre las superficies de los cinco temas (orden fijo:
el color sigue a la entidad, nunca al puesto).
"""
from __future__ import annotations

import html as _html
import math

ANCHO, ALTO = 560, 280
M_SUP, M_INF, M_LAT = 34, 50, 16
PROF = 9            # profundidad del efecto 3D
VARIANTES = ("barras_linea", "barras", "lineas", "area", "puntos")
ROTULO_VARIANTE = {"barras_linea": "Barras + línea", "barras": "Barras", "lineas": "Líneas", "area": "Área", "puntos": "Puntos"}

# Tema Claro en literal (PDF). Mismos papeles que las variables del HTML.
CLARO = {
    "s1": "#2a78d6", "s2": "#eb6834", "s3": "#1baf7a", "s4": "#eda100", "s5": "#e87ba4", "s6": "#008300",
    "s7": "#4a3aa7", "s8": "#e34948", "otros": "#9AA4B2",
    "registrado": "#eda100", "recalculado": "#1baf7a", "serie": "#2a78d6", "linea": "#A8872A",
    "alta": "#D93F3F", "media": "#D98A00", "baja": "#2E9E6A", "informativa": "#8A94A6",
    "texto": "#0A2342", "texto2": "#4B5563", "regla": "#D5DCE6", "superficie": "#FFFFFF",
}


def es_ec(v: float, dec: int = 2) -> str:
    """1234567.891 → «1.234.567,89»; negativos con signo menos tipográfico."""
    s = f"{abs(v):,.{dec}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return ("−" if v < 0 else "") + s


def corto(v: float) -> str:
    """Rótulo compacto para marcas: 1,20 M · 240 mil · 90,4 mil · 850,00 (desde 100 mil sin
    decimal, para que la cifra quepa en su columna aunque lleve signo)."""
    a = abs(v)
    if a >= 999_500:
        s = es_ec(a / 1_000_000, 2) + " M"
    elif a >= 99_950:
        s = es_ec(a / 1_000, 0) + " mil"
    elif a >= 10_000:
        s = es_ec(a / 1_000, 1) + " mil"
    else:
        s = es_ec(a, 2 if a % 1 else 0)
    return ("−" if v < 0 else "") + s


def pct(v: float) -> str:
    return es_ec(v * 100, 1) + " %"


class _Pintor:
    """Devuelve el atributo de color según el modo: variable CSS (HTML) o literal (PDF)."""

    def __init__(self, hex_: dict | None):
        self.hex = hex_

    def fill(self, rol: str, opac: float | None = None) -> str:
        o = f";fill-opacity:{opac}" if opac is not None else ""
        if self.hex:
            return f'fill="{self.hex[rol]}"' + (f' fill-opacity="{opac}"' if opac is not None else "")
        return f'style="fill:var(--c-{rol}){o}"'

    def stroke(self, rol: str, ancho: float = 2) -> str:
        if self.hex:
            return f'fill="none" stroke="{self.hex[rol]}" stroke-width="{ancho}"'
        return f'style="fill:none;stroke:var(--c-{rol});stroke-width:{ancho}"'


def _lineas_texto(t: str, maximo: int = 16) -> list[str]:
    palabras, lineas, actual = str(t).split(), [], ""
    for p in palabras:
        if len(actual) + len(p) + (1 if actual else 0) <= maximo:
            actual = f"{actual} {p}".strip()
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    if len(lineas) > 2:
        lineas = [lineas[0], (lineas[1][: maximo - 1] + "…")]
    return [(x[: maximo - 1] + "…") if len(x) > maximo else x for x in lineas] or [""]


def _una_linea(t: str, maximo: int) -> str:
    """Primera línea del rótulo; «…» si se recortó (el texto completo va en <title>)."""
    ls = _lineas_texto(t, maximo)
    return ls[0] if len(ls) == 1 or ls[0].endswith("…") else ls[0] + "…"


# Tamaño y peso como atributos de presentación: el navegador aplica el CSS de la
# página (que manda), y WeasyPrint, que no resuelve el atajo «font:» con var()
# dentro del SVG, usa estos (sin ellos el texto sale a 16 px y se encima).
_TEXTO = {"val": ("11", "600"), "cat": ("11", "400"), "centro": ("26", "700"),
          "centro-etq": ("11", "400"), "ley": ("12", "600"), "ley2": ("11", "400")}


def _tamanos(svg: str) -> str:
    for c, (t, w) in _TEXTO.items():
        svg = svg.replace(f'class="{c}"', f'class="{c}" font-size="{t}" font-weight="{w}"')
    return svg


def columnas(items: list[tuple[str, float]], variante: str, roles: list[str] | str, descripcion: str,
             hex_: dict | None = None, enteros: bool = False) -> str:
    """Gráfico de categorías (una medida). ``roles``: un rol para todas las marcas
    o uno por categoría (p. ej. severidad o registrado/recalculado)."""
    items = [(e, float(v)) for e, v in items if v is not None]
    if not items:
        return ""
    P = _Pintor(hex_)
    n = len(items)
    rol = (lambda i: roles[i]) if isinstance(roles, list) else (lambda i: roles)
    lo, hi = min(0.0, min(v for _, v in items)), max(0.0, max(v for _, v in items))
    if hi == lo:
        hi = lo + 1
    area_alto = ALTO - M_SUP - M_INF
    y = lambda v: M_SUP + (hi - v) / (hi - lo) * area_alto  # noqa: E731
    y0 = y(0.0)
    banda = (ANCHO - 2 * M_LAT - PROF) / n
    w = min(46.0, banda * 0.52)
    cx = [M_LAT + banda * (i + 0.5) for i in range(n)]
    fmt = (lambda v: str(int(round(v)))) if enteros else corto
    completo = (lambda v: str(int(round(v)))) if enteros else es_ec
    partes = [f'<line x1="{M_LAT}" x2="{ANCHO - M_LAT}" y1="{y0:.1f}" y2="{y0:.1f}" {P.stroke("regla", 1)}/>']
    barras = variante in ("barras", "barras_linea")
    puntos = []
    for i, (etq, v) in enumerate(items):
        xc, yv = cx[i], y(v)
        tt = f"<title>{_html.escape(etq)}: {completo(v)}</title>"
        if barras:
            x0, top, bot = xc - w / 2, min(yv, y0), max(yv, y0)
            alto = max(bot - top, 0.8)
            cara = f'<rect x="{x0:.1f}" y="{top:.1f}" width="{w:.1f}" height="{alto:.1f}" {P.fill(rol(i))}/>'
            techo = (f'<polygon points="{x0:.1f},{top:.1f} {x0 + PROF:.1f},{top - PROF:.1f} {x0 + w + PROF:.1f},{top - PROF:.1f} {x0 + w:.1f},{top:.1f}" '
                     f'{P.fill(rol(i))}/><polygon points="{x0:.1f},{top:.1f} {x0 + PROF:.1f},{top - PROF:.1f} {x0 + w + PROF:.1f},{top - PROF:.1f} {x0 + w:.1f},{top:.1f}" fill="#FFFFFF" fill-opacity="0.32"/>')
            lado = (f'<polygon points="{x0 + w:.1f},{top:.1f} {x0 + w + PROF:.1f},{top - PROF:.1f} {x0 + w + PROF:.1f},{bot - PROF:.1f} {x0 + w:.1f},{bot:.1f}" '
                    f'{P.fill(rol(i))}/><polygon points="{x0 + w:.1f},{top:.1f} {x0 + w + PROF:.1f},{top - PROF:.1f} {x0 + w + PROF:.1f},{bot - PROF:.1f} {x0 + w:.1f},{bot:.1f}" fill="#000000" fill-opacity="0.28"/>')
            # Negativa: la cifra va sobre la línea de cero (debajo de la barra chocaría con el rótulo del eje).
            ly = (top - PROF - 6) if v >= 0 else (y0 - 6)
            partes.append(f'<g class="marca">{tt}{cara}{lado}{techo}'
                          f'<text x="{xc + PROF / 2:.1f}" y="{ly:.1f}" text-anchor="middle" class="val" {P.fill("texto")}>{fmt(v)}</text></g>')
            puntos.append((xc + PROF / 2, top - PROF / 2 if v >= 0 else bot))
        else:
            puntos.append((xc, yv))
    if variante in ("lineas", "area", "puntos", "barras_linea"):
        pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in puntos)
        if variante == "area" and n > 1:
            poli = f"{puntos[0][0]:.1f},{y0:.1f} {pts} {puntos[-1][0]:.1f},{y0:.1f}"
            partes.append(f'<polygon points="{poli}" {P.fill(rol(0), 0.18)}/>')
        if variante in ("lineas", "area", "barras_linea") and n > 1:
            linea_rol = "linea" if variante == "barras_linea" else rol(0)
            partes.append(f'<polyline points="{pts}" {P.stroke(linea_rol, 2)} stroke-linejoin="round" stroke-linecap="round"/>')
        if not barras:
            for i, ((px, py), (etq, v)) in enumerate(zip(puntos, items)):
                r = 6 if variante == "puntos" else 4.5
                ly = py - 12 if v >= 0 or py + 18 > ALTO - M_INF - 4 else py + 18
                partes.append(f'<g class="marca"><title>{_html.escape(etq)}: {completo(v)}</title>'
                              f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r + 2}" {P.fill("superficie")}/>'
                              f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r}" {P.fill(rol(i))}/>'
                              f'<text x="{px:.1f}" y="{ly:.1f}" text-anchor="middle" class="val" {P.fill("texto")}>{fmt(v)}</text></g>')
        elif variante == "barras_linea":
            for px, py in puntos:
                partes.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" {P.fill("linea")}/>')
    max_car = max(6, int(banda / 6.4))  # rótulo partido al ancho real de su banda: no se enciman
    for i, (etq, _) in enumerate(items):
        lineas = _lineas_texto(etq, max_car)
        tsp = "".join(f'<tspan x="{cx[i] + (PROF / 2 if barras else 0):.1f}" dy="{0 if k == 0 else 13}">{_html.escape(t)}</tspan>'
                      for k, t in enumerate(lineas))
        partes.append(f'<text y="{ALTO - M_INF + 18}" text-anchor="middle" class="cat" {P.fill("texto2")}>{tsp}</text>')
    return _tamanos(f'<svg class="grafico" viewBox="0 0 {ANCHO} {ALTO}" role="img" aria-label="{_html.escape(descripcion)}">'
                    f"<title>{_html.escape(descripcion)}</title>" + "".join(partes) + "</svg>")


def _cifra(v: float, unidad: str) -> str:
    """Rótulo de una barra de tablero según su unidad (veces, días, % o USD)."""
    if unidad == "USD":
        return corto(v)
    if unidad == "días":
        return es_ec(v, 0)
    return es_ec(v, 2)   # veces y % (la unidad va en el subtítulo: la barra lleva solo la cifra)


def variacion_tablero(a, b, unidad: str):
    """Variación de un indicador entre la serie anterior (a) y la actual (b): («▲ 12,3 %», signo) o None.
    En los porcentajes es la diferencia en puntos («pp»); en lo demás, la variación relativa."""
    if a is None or b is None:
        return None
    d = b - a
    if abs(d) < 1e-9:
        return "= 0", 0
    flecha = "▲" if d > 0 else "▼"
    if unidad == "%":
        return f"{flecha} {es_ec(abs(d), 2)} pp", (1 if d > 0 else -1)
    if a == 0:
        return None
    return f"{flecha} {es_ec(abs(d) / abs(a) * 100, 1)} %", (1 if d > 0 else -1)


def _paso_nice(rango: float) -> float:
    """Paso «redondo» (1, 2, 2,5 o 5 × 10ⁿ) para unas 4 líneas de cuadrícula."""
    if rango <= 0:
        return 1.0
    bruto = rango / 4
    e = 10 ** math.floor(math.log10(bruto))
    return next(m * e for m in (1, 2, 2.5, 5, 10) if m * e >= bruto)


def _barra_redondeada(x0, top, ww, bot, positiva, r) -> str:
    """Contorno de una barra con las esquinas del extremo libre redondeadas (arriba si es positiva)."""
    r = max(0.0, min(r, ww / 2, (bot - top) / 2))
    if positiva:
        return (f"M{x0:.1f},{bot:.1f} L{x0:.1f},{top + r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x0 + r:.1f},{top:.1f} "
                f"L{x0 + ww - r:.1f},{top:.1f} A{r:.1f},{r:.1f} 0 0 1 {x0 + ww:.1f},{top + r:.1f} L{x0 + ww:.1f},{bot:.1f} Z")
    return (f"M{x0:.1f},{top:.1f} L{x0 + ww:.1f},{top:.1f} L{x0 + ww:.1f},{bot - r:.1f} A{r:.1f},{r:.1f} 0 0 1 {x0 + ww - r:.1f},{bot:.1f} "
            f"L{x0 + r:.1f},{bot:.1f} A{r:.1f},{r:.1f} 0 0 1 {x0:.1f},{bot - r:.1f} Z")


_NIVEL_ROL = {"Verde": "baja", "Amarillo": "media", "Rojo": "alta"}


def agrupadas(categorias: list[str], series: list[tuple[str, list]], descripcion: str, unidad: str = "",
              hex_: dict | None = None, mejor: list | None = None, estados: list | None = None) -> str:
    """Tablero premium (índices por grupo y analítico): barras agrupadas por indicador, una por serie
    (anterior y actual), con degradado, esquinas redondeadas y brillo en el borde; cuadrícula tenue con su
    escala; encima de cada indicador, una píldora con el punto del semáforo de la cédula (``estados``:
    (nivel, etiqueta)) y la variación (▲/▼) en verde si mejora y en rojo si empeora según ``mejor``
    («alto»/«bajo»; gris si no tiene sentido favorable). El texto usa colores de texto, nunca el de la serie."""
    if not categorias or not series:
        return ""
    vals = [v for _, vs in series for v in vs if v is not None]
    if not vals:
        return ""
    import hashlib

    P = _Pintor(hex_)
    roles = ["s1", "s3", "s2", "s4"]
    n, k = len(categorias), len(series)
    uid = "g" + hashlib.md5(repr((descripcion, categorias, series, bool(hex_))).encode()).hexdigest()[:8]

    def stop(rol, off, op):
        if hex_:
            return f'<stop offset="{off}" stop-color="{hex_[rol]}" stop-opacity="{op}"/>'
        return f'<stop offset="{off}" style="stop-color:var(--c-{rol});stop-opacity:{op}"/>'

    defs = "".join(f'<linearGradient id="{uid}{r}" x1="0" y1="0" x2="0" y2="1">{stop(r, 0, 1)}{stop(r, 1, 0.55)}</linearGradient>'
                   f'<linearGradient id="{uid}{r}n" x1="0" y1="1" x2="0" y2="0">{stop(r, 0, 1)}{stop(r, 1, 0.55)}</linearGradient>'
                   for r in roles[:k])
    # Escala: cuadrícula en pasos redondos que incluyen el cero.
    lo, hi = min(0.0, min(vals)), max(0.0, max(vals))
    paso = _paso_nice(hi - lo)
    lo, hi = math.floor(lo / paso) * paso, math.ceil(hi / paso) * paso
    if hi == lo:
        hi = lo + paso
    X0 = M_LAT + 34                      # escala a la izquierda
    sup, inf = 70, ALTO - M_INF          # franja de variaciones arriba; rótulos abajo
    y = lambda v: sup + (hi - v) / (hi - lo) * (inf - sup)  # noqa: E731
    y0 = y(0.0)
    fmt_eje = (lambda v: corto(v)) if unidad == "USD" else (lambda v: es_ec(v, 0 if paso >= 1 else (1 if paso * 10 % 1 == 0 else 2)))
    partes = []
    t = lo
    while t <= hi + paso / 1000:
        yt = y(t)
        if abs(t) > paso / 1000:
            partes.append(f'<line x1="{X0}" x2="{ANCHO - M_LAT}" y1="{yt:.1f}" y2="{yt:.1f}" {P.stroke("regla", 1)} stroke-dasharray="3 4" stroke-opacity="0.6"/>')
        partes.append(f'<text x="{X0 - 6}" y="{yt + 3.5:.1f}" text-anchor="end" class="eje" {P.fill("texto2")}>{fmt_eje(t)}</text>')
        t += paso
    partes.append(f'<line x1="{X0}" x2="{ANCHO - M_LAT}" y1="{y0:.1f}" y2="{y0:.1f}" {P.stroke("regla", 1.5)}/>')
    # Leyenda (arriba a la derecha): muestra con el degradado de la serie.
    lx = ANCHO - M_LAT - 96 * k
    for j, (nombre, _) in enumerate(series):
        partes.append(f'<rect x="{lx + j * 96}" y="9" width="12" height="12" rx="3" fill="url(#{uid}{roles[j]})"/>'
                      f'<text x="{lx + j * 96 + 18}" y="19" class="ley2" {P.fill("texto2")}>{_html.escape(nombre)}</text>')
    banda = (ANCHO - M_LAT - X0) / n
    w = min(30.0, banda * 0.66 / k)
    gap = 4.0
    cifras = []
    for i, cat in enumerate(categorias):
        xc = X0 + banda * (i + 0.5)
        x_ini = xc - (w * k + gap * (k - 1)) / 2
        for j, (nombre, vs) in enumerate(series):
            v = vs[i] if i < len(vs) else None
            if v is None:
                continue
            x0 = x_ini + j * (w + gap)
            yv = y(v)
            top, bot = min(yv, y0), max(yv, y0)
            if bot - top < 1.2:
                top = bot - 1.2 if v >= 0 else top
                bot = top + 1.2
            pos = v >= 0
            d = _barra_redondeada(x0, top, w, bot, pos, 5)
            txt = _cifra(v, unidad)
            partes.append(f'<g class="marca"><title>{_html.escape(cat)} · {_html.escape(nombre)}: {txt}</title>'
                          f'<path d="{d}" fill="url(#{uid}{roles[j]}{"" if pos else "n"})"/>'
                          + (f'<line x1="{x0 + 3:.1f}" x2="{x0 + w - 3:.1f}" y1="{top + 0.8:.1f}" y2="{top + 0.8:.1f}" '
                             f'stroke="#FFFFFF" stroke-opacity="0.55" stroke-width="1.2"/>' if pos and bot - top > 4 else "")
                          + "</g>")
            ancha = len(txt) * 6.1 > w - 2
            if k == 2 and ancha:
                lxv, anc = (x0 + w, "end") if j == 0 else (x0, "start")
            else:
                lxv, anc = x0 + w / 2, "middle"
            ly = (top - 5) if pos else (bot + 12)
            cifras.append(f'<text x="{lxv:.1f}" y="{ly:.1f}" text-anchor="{anc}" class="val" {P.fill("texto")}>{txt}</text>')
        # Variación del indicador (anterior → actual), en una píldora encima del grupo.
        # Delante, el punto del semáforo del indicador (estado al corte), con su etiqueta al pasar el cursor.
        est = estados[i] if estados and i < len(estados) else None
        var = variacion_tablero(series[0][1][i] if i < len(series[0][1]) else None,
                                series[1][1][i] if k >= 2 and i < len(series[1][1]) else None, unidad) if k >= 2 else None
        if var or est:
            txt, signo = var or ("", 0)
            sentido = (mejor[i] if mejor and i < len(mejor) else None)
            rol = ("texto2" if not sentido or signo == 0 else
                   "baja" if (signo > 0) == (sentido == "alto") else "alta")
            ancho_p = (len(txt) * 5.9 + 14 if txt else 8) + (13 if est else 0)
            xp = xc - ancho_p / 2
            partes.append(f'<rect x="{xp:.1f}" y="31" width="{ancho_p:.1f}" height="17" rx="8.5" {P.fill(rol, 0.16)}/>')
            if est:
                partes.append(f'<circle cx="{xp + 10:.1f}" cy="39.5" r="4" {P.fill(_NIVEL_ROL[est[0]])}>'
                              f'<title>Semáforo: {_html.escape(est[0])} · {_html.escape(est[1])}</title></circle>')
            if txt:
                partes.append(f'<text x="{xc + (6.5 if est else 0):.1f}" y="43.5" text-anchor="middle" class="delta" '
                              f'{P.fill(rol)}>{_html.escape(txt)}</text>')
    partes += cifras
    max_car = max(6, int(banda / 6.2))
    for i, cat in enumerate(categorias):
        xc = X0 + banda * (i + 0.5)
        tsp = "".join(f'<tspan x="{xc:.1f}" dy="{0 if q == 0 else 13}">{_html.escape(t)}</tspan>'
                      for q, t in enumerate(_lineas_texto(cat, max_car)))
        partes.append(f'<text y="{inf + 18}" text-anchor="middle" class="cat" {P.fill("texto2")}>{tsp}</text>')
    svg = (f'<svg class="grafico" viewBox="0 0 {ANCHO} {ALTO}" role="img" aria-label="{_html.escape(descripcion)}">'
           f"<title>{_html.escape(descripcion)}</title><defs>{defs}</defs>" + "".join(partes) + "</svg>")
    svg = _tamanos(svg).replace('class="val" font-size="11"', 'class="val" font-size="10"')
    return (svg.replace('class="eje"', 'class="eje" font-size="9" font-weight="400"')
               .replace('class="delta"', 'class="delta" font-size="10" font-weight="700"'))


def _arco(cx, cy, r_ext, r_int, a0, a1) -> str:
    """Sector de corona entre los ángulos a0→a1 (radianes, 0 = arriba, sentido horario)."""
    def pt(r, a):
        return cx + r * math.sin(a), cy - r * math.cos(a)
    grande = 1 if a1 - a0 > math.pi else 0
    x1, y1 = pt(r_ext, a0)
    x2, y2 = pt(r_ext, a1)
    x3, y3 = pt(r_int, a1)
    x4, y4 = pt(r_int, a0)
    return (f"M{x1:.2f},{y1:.2f} A{r_ext},{r_ext} 0 {grande} 1 {x2:.2f},{y2:.2f} "
            f"L{x3:.2f},{y3:.2f} A{r_int},{r_int} 0 {grande} 0 {x4:.2f},{y4:.2f} Z")


def dona(items: list[tuple[str, float]], descripcion: str, hex_: dict | None = None) -> str:
    """Dona de composición: porcentaje del componente mayor al centro y leyenda
    (color, rótulo, valor, %) a la derecha. Valores en magnitud (absolutos)."""
    items = [(e, abs(float(v))) for e, v in items if v]
    total = sum(v for _, v in items)
    if not items or total <= 0:
        return ""
    P = _Pintor(hex_)
    cx, cy, r_ext, r_int = 140, ALTO / 2, 108, 70
    roles = [("otros" if e.startswith("Otros") else f"s{min(i, 7) + 1}") for i, (e, _) in enumerate(items)]
    partes, a = [], 0.0
    hueco = 0.012 if len(items) > 1 else 0.0  # separación de 2 px entre porciones (superficie)
    for (etq, v), rol in zip(items, roles):
        ang = v / total * 2 * math.pi
        a0, a1 = a + hueco / 2, a + ang - hueco / 2
        if len(items) == 1:
            partes.append(f'<g class="marca"><title>{_html.escape(etq)}: {es_ec(v)} (100 %)</title>'
                          f'<circle cx="{cx}" cy="{cy}" r="{(r_ext + r_int) / 2}" {P.stroke(rol, r_ext - r_int)}/></g>')
        else:
            partes.append(f'<g class="marca"><title>{_html.escape(etq)}: {es_ec(v)} ({pct(v / total)})</title>'
                          f'<path d="{_arco(cx, cy, r_ext, r_int, a0, max(a1, a0 + 0.002))}" {P.fill(rol)}/></g>')
        a += ang
    mayor = max(items, key=lambda kv: kv[1])
    centro_etq = _una_linea(mayor[0], 18)
    partes.append(f'<text x="{cx}" y="{cy + 4}" text-anchor="middle" class="centro" {P.fill("texto")}>{pct(mayor[1] / total)}</text>'
                  f'<text x="{cx}" y="{cy + 24}" text-anchor="middle" class="centro-etq" {P.fill("texto2")}>{_html.escape(centro_etq)}</text>')
    ly = max(28, cy - len(items) * 13)
    for i, ((etq, v), rol) in enumerate(zip(items, roles)):
        yy = ly + i * 27
        partes.append(f'<rect x="290" y="{yy - 10}" width="12" height="12" rx="3" {P.fill(rol)}/>'
                      f'<text x="310" y="{yy}" class="ley" {P.fill("texto")}><title>{_html.escape(etq)}</title>{_html.escape(_una_linea(etq, 26))}</text>'
                      f'<text x="310" y="{yy + 13}" class="ley2" {P.fill("texto2")}>{es_ec(v)} · {pct(v / total)}</text>')
    return _tamanos(f'<svg class="grafico" viewBox="0 0 {ANCHO} {ALTO}" role="img" aria-label="{_html.escape(descripcion)}">'
                    f"<title>{_html.escape(descripcion)}</title>" + "".join(partes) + "</svg>")
