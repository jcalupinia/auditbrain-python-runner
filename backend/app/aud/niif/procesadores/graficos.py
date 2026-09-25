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
    s = f"{abs(v):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")  # es-EC: 1.234,56
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


# Tildes que el código en mayúsculas pierde (EVALUACION_INDIVIDUAL → «Evaluación individual»).
_TILDES = {"dias": "días", "credito": "crédito", "garantia": "garantía", "deposito": "depósito", "periodo": "período",
           "numero": "número", "indice": "índice", "maxima": "máxima", "maximo": "máximo", "minimo": "mínimo",
           "tecnica": "técnica", "economica": "económica", "politica": "política", "vehiculo": "vehículo",
           "catalogo": "catálogo", "analisis": "análisis", "metodo": "método", "credito,": "crédito,"}


def _con_tildes(palabra: str) -> str:
    if palabra in _TILDES:
        return _TILDES[palabra]
    for fin, con in (("cion", "ción"), ("sion", "sión"), ("ciones", "ciones"), ("siones", "siones")):
        if len(palabra) > 5 and palabra.endswith(fin):
            return palabra[: -len(fin)] + con
    return palabra


def _humaniza(codigo: str) -> str:
    t = " ".join(_con_tildes(p) for p in str(codigo or "").replace("_", " ").strip().lower().split())
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


# --- Panel ejecutivo por herramienta ------------------------------------------
# Cada procesador declara en su módulo:
#
#   PANEL = {
#       "poblacion":   {"rotulo": "Cartera evaluada",     "total": "cartera"},
#       "recalculado": {"rotulo": "Pérdida recalculada",  "total": "perdida"},
#       "registrado":  {"rotulo": "Provisión registrada", "total": "provReg"},
#       "composicion": {"rotulo": "Pérdida por tramo",  "hoja": "04_Matriz_deterioro", "etiqueta": "Tramo", "valor": "Pérdida"},
#       "distribucion":{"rotulo": "Cartera por tramo",  "hoja": "04_Matriz_deterioro", "etiqueta": "Tramo", "valor": "Saldo"},
#   }
#
# Un importe se toma de ``run["totals"][total]`` o, con {"hoja", "col"}, como la
# suma de esa columna en esa cédula (filas de datos, sin la fila TOTAL). Las series
# (composición, distribución) agrupan por la columna ``etiqueta`` y suman ``valor``,
# o se arman con ``"totales": [[rótulo, clave de run["totals"]], ...]``.
# Filtros de filas (importes y series): ``"donde": {columna: [valores admitidos]}``
# y ``"con_valor": columna`` (solo filas con esa columna calculada). Sirven para que
# registrado y recalculado midan lo mismo (p. ej. solo las líneas medidas) y la
# brecha del comparativo sea el ajuste.
# El resultado principal es siempre ``run["primary"]``.

UMBRAL_ALTA, UMBRAL_MEDIA = 0.05, 0.01
SEVERIDADES = ("Alta", "Media", "Baja", "Informativa")
REGLA_SEVERIDAD = ("Severidad según el importe del hallazgo frente a la población: "
                   "≥ 5 % alta, ≥ 1 % media, menor baja; sin importe, informativa.")


def _cols_idx(h: dict, nombre: str):
    for j, c in enumerate(h.get("cols") or []):
        if c[0] == nombre:
            return j
    return None


def _filas(h: dict, spec: dict) -> list:
    """Filas de datos de la cédula que cumplen los filtros ``donde`` y ``con_valor``."""
    filas = list(h.get("rows") or [])
    for col, admitidos in (spec.get("donde") or {}).items():
        j = _cols_idx(h, col)
        if j is None:
            return []
        adm = {str(a) for a in admitidos}
        filas = [f for f in filas if j < len(f) and str(f[j].get("v") if isinstance(f[j], dict) else f[j]) in adm]
    if spec.get("con_valor"):
        j = _cols_idx(h, spec["con_valor"])
        if j is None:
            return []
        filas = [f for f in filas if j < len(f) and _num(f[j]) is not None]
    return filas


def _suma_col(h: dict, col: str, spec: dict | None = None):
    j = _cols_idx(h, col)
    if j is None:
        return None
    vals = [_num(f[j]) for f in _filas(h, spec or {}) if j < len(f)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else 0.0


def valor_spec(spec: dict | None, run: dict, mapa: dict):
    if not spec:
        return None
    if "total" in spec:
        return _num((run.get("totals") or {}).get(spec["total"]))
    h = mapa.get(spec.get("hoja"))
    return _suma_col(h, spec.get("col"), spec) if h else None


def filas_spec(spec: dict | None, mapa: dict):
    if not spec:
        return None
    if "hoja" in spec:
        h = mapa.get(spec["hoja"])
        return len(_filas(h, spec)) if h else None
    return None


def serie_spec(spec: dict | None, mapa: dict, absoluto: bool = False, run: dict | None = None) -> list[tuple[str, float]]:
    """Agrupa la cédula ``spec["hoja"]`` por ``etiqueta`` y suma ``valor`` (o toma
    ``spec["totales"]``); los 7 mayores (por importe absoluto) y el resto en «Otros».
    Sin ceros. Con ``absoluto`` (dona) el tamaño es el valor absoluto y las partidas
    que restan llevan «(−)» delante del rótulo, para no presentarlas como si sumaran."""
    if not spec:
        return []
    acum: dict[str, float] = {}
    if spec.get("totales"):
        tot = (run or {}).get("totals") or {}
        for rotulo, clave in spec["totales"]:
            v = _num(tot.get(clave))
            if v is not None:
                acum[rotulo] = acum.get(rotulo, 0.0) + v
    else:
        h = mapa.get(spec.get("hoja"))
        if not h:
            return []
        je, jv = _cols_idx(h, spec.get("etiqueta")), _cols_idx(h, spec.get("valor"))
        if je is None or jv is None:
            return []
        for f in _filas(h, spec):
            v = _num(f[jv]) if jv < len(f) else None
            if v is None:
                continue
            e = f[je] if je < len(f) else ""
            e = e.get("v") if isinstance(e, dict) else e
            e = " ".join(str(e if e not in (None, "") else "(sin rótulo)").split())
            acum[e] = acum.get(e, 0.0) + v
    restan = {f"(−) {e}" for e, v in acum.items() if v < 0} if absoluto else set()
    if absoluto:
        acum = {(f"(−) {e}" if v < 0 else e): abs(v) for e, v in acum.items()}
    items = [(e, v) for e, v in acum.items() if abs(v) >= 0.005]
    if len(items) > TOP_HALLAZGOS + 1:
        orden = sorted(items, key=lambda kv: -abs(kv[1]))
        # Una partida que resta nunca se esconde en «Otros» (sumaría como si fuera positiva).
        cabeza = [kv for kv in orden[:TOP_HALLAZGOS] if kv[0] not in restan][:max(0, TOP_HALLAZGOS - len(restan))]
        cabeza += [kv for kv in orden if kv[0] in restan]
        resto = [kv for kv in orden if kv not in cabeza]
        items = cabeza + ([(f"Otros ({len(resto)})", sum(v for _, v in resto))] if resto else [])
    return items


def severidad(run: dict, base: float | None) -> dict:
    cuenta = {s: 0 for s in SEVERIDADES}
    b = abs(base or 0.0)
    for e in run.get("exceptions") or []:
        v = abs(_num(e.get("amount")) or 0.0)
        if v < 0.005:
            cuenta["Informativa"] += 1
        elif b and v / b >= UMBRAL_ALTA:
            cuenta["Alta"] += 1
        elif b and v / b >= UMBRAL_MEDIA:
            cuenta["Media"] += 1
        else:
            cuenta["Baja"] += 1
    return cuenta


def riesgo(cuenta: dict) -> str:
    return "alto" if cuenta.get("Alta") else "medio" if cuenta.get("Media") else "bajo"


def variacion(nuevo, base):
    """Variación relativa (nuevo − base) / |base|, o None si no se puede medir."""
    if nuevo is None or base in (None, 0):
        return None
    return (nuevo - base) / abs(base)


def panel(mod, run: dict, hojas: list[dict]) -> dict:
    """Datos del dashboard de una prueba a partir de ``mod.PANEL``.
    ``faltan`` lista lo que no se pudo resolver (el verificador y los tests lo exigen vacío)."""
    spec = getattr(mod, "PANEL", None) or {}
    mapa = {h["name"]: h for h in hojas}
    tot, etq = run.get("totals") or {}, run.get("labels") or {}
    prim = run.get("primary")
    faltan = []
    if not spec:
        faltan.append("PANEL")
    val = {}
    for k in ("poblacion", "recalculado", "registrado"):
        val[k] = valor_spec(spec.get(k), run, mapa)
        if val[k] is None:
            faltan.append(k)
    series = {}
    for k in ("composicion", "distribucion"):
        series[k] = serie_spec(spec.get(k), mapa, absoluto=(k == "composicion"), run=run)
        if not series[k]:
            faltan.append(k)
    sev = severidad(run, val["poblacion"])
    principal = _num(tot.get(prim))
    return {
        "principal": {"rotulo": etq.get(prim, prim or "Resultado"), "valor": principal,
                      "variacion": variacion((principal or 0) + (val["poblacion"] or 0), val["poblacion"]) if principal is not None else None},
        "poblacion": {"rotulo": (spec.get("poblacion") or {}).get("rotulo", "Población"), "valor": val["poblacion"],
                      "n": filas_spec(spec.get("poblacion"), mapa),
                      # En pruebas de saldo la población ES el saldo registrado: la tarjeta
                      # muestra entonces cuántas partidas lo componen, no el mismo importe.
                      "igual_registrado": (val["poblacion"] is not None and val["registrado"] is not None
                                           and abs(val["poblacion"] - val["registrado"]) < 0.005)},
        "recalculado": {"rotulo": (spec.get("recalculado") or {}).get("rotulo", "Recalculado"), "valor": val["recalculado"],
                        "variacion": variacion(val["recalculado"], val["registrado"])},
        "registrado": {"rotulo": (spec.get("registrado") or {}).get("rotulo", "Registrado"), "valor": val["registrado"]},
        "problemas": {"rotulo": "Problemas encontrados", "valor": len(run.get("exceptions") or []), "severidad": sev},
        "riesgo": riesgo(sev),
        "composicion": {"rotulo": (spec.get("composicion") or {}).get("rotulo", "Composición del resultado"), "items": series["composicion"]},
        "comparativo": {"rotulo": "Registrado vs recalculado",
                        "items": [((spec.get("registrado") or {}).get("rotulo", "Registrado"), val["registrado"] or 0.0),
                                  ((spec.get("recalculado") or {}).get("rotulo", "Recalculado"), val["recalculado"] or 0.0)]},
        "distribucion": {"rotulo": (spec.get("distribucion") or {}).get("rotulo", "Distribución"), "items": series["distribucion"]},
        "severidad": {"rotulo": "Problemas por severidad", "items": [(s, float(sev[s])) for s in SEVERIDADES], "regla": REGLA_SEVERIDAD},
        "faltan": faltan,
    }
