"""HTML ejecutivo del papel de trabajo NIIF — dashboard autocontenido (sin CDN).

Estilo de la referencia «Dashboard Ejecutivo» que la firma entrega a clientes:
fondo azul marino #071B2F con tarjetas #0A2342 y bordes sutiles; barra superior
con los logotipos de la firma y de AUDIT-IA (incrustados, ``marca``) y selectores de **Color** (Ejecutivo, Medianoche,
Esmeralda, Grafito, Claro), **Gráfico** (barras + línea, barras, líneas, área,
puntos) y **Vista** (estándar, compacta, foco en tablas, presentación);
navegación por secciones como pestañas de texto con subrayado dorado; encabezado
con chips de estado; fila de 5 KPI (ícono, rótulo en versalitas, cifra grande en
color y variación ↗/↘) y gráficos SVG propios (barras 3D comparativas y dona).

Por prueba (``graficos.panel`` con el ``PANEL`` de cada procesador):
KPI = resultado principal, población, recalculado, registrado y n.º de problemas;
gráficos = composición del resultado (dona), registrado vs recalculado (barras),
distribución por tramo/categoría (barras) y problemas por severidad.

Impresión: siempre en tema Claro; «Guardar como PDF» del papel completo o de la
pestaña activa. ``para_pdf=True`` devuelve la versión estática que WeasyPrint
convierte en el PDF del servidor (tema Claro con colores literales, todas las
secciones, sin JavaScript ni selectores).
Cifras en formato es-EC (1.234.567,89) en tarjetas, gráficos y tablas.
"""
from __future__ import annotations

import base64
import html as _html
import re

from backend.app.aud.niif.procesadores import estilo_ejecutivo as est
from backend.app.aud.niif.procesadores import graficos, graficos_svg as gs
from backend.app.aud.niif.procesadores import marca

E = _html.escape

# --- temas -------------------------------------------------------------------
_SERIES_OSCURO = {"s1": "#3987e5", "s2": "#d95926", "s3": "#199e70", "s4": "#c98500", "s5": "#d55181",
                  "s6": "#008300", "s7": "#9085e9", "s8": "#e66767", "otros": "#6F7F96"}
_SERIES_CLARO = {k: v for k, v in gs.CLARO.items() if k.startswith("s") and len(k) == 2}
_SERIES_CLARO["otros"] = gs.CLARO["otros"]


def _oscuro(bg, card, card2, borde, texto, texto2, muted):
    return {"bg": bg, "card": card, "card2": card2, "borde": borde, "texto": texto, "texto2": texto2, "muted": muted,
            "oro": "#C7A83C", "oro-txt": "#D9BE5A", "k-azul": "#6DA7EC", "k-verde": "#3CC48C", "k-ambar": "#E9A23B",
            "sube": "#3CC48C", "baja-txt": "#F07171", "alta": "#E5484D", "media": "#F5A524", "baja": "#30A46C",
            "informativa": "#8B97A8", "zebra": "rgba(255,255,255,.035)", "sombra": "0 10px 30px -18px rgba(0,0,0,.8)",
            **{f"c-{k}": v for k, v in _SERIES_OSCURO.items()},
            "c-registrado": _SERIES_OSCURO["s4"], "c-recalculado": _SERIES_OSCURO["s3"], "c-serie": _SERIES_OSCURO["s1"],
            "c-linea": "#C7A83C", "c-alta": "#E5484D", "c-media": "#F5A524", "c-baja": "#30A46C", "c-informativa": "#8B97A8",
            "c-texto": texto, "c-texto2": texto2, "c-regla": borde, "c-superficie": card}


TEMAS = {
    "ejecutivo": ("Ejecutivo", _oscuro("#071B2F", "#0A2342", "#0E2C50", "#1B3A60", "#EAF1FB", "#A6BBD6", "#6F87A6")),
    "medianoche": ("Medianoche", _oscuro("#04060A", "#0D1320", "#121A2A", "#1E2838", "#E8EDF4", "#8B97A8", "#5A6575")),
    "esmeralda": ("Esmeralda", _oscuro("#03201A", "#0A342B", "#0E4034", "#1A5546", "#E6F4EF", "#9CC9B8", "#6F9C8C")),
    "grafito": ("Grafito", _oscuro("#1B1F24", "#252A31", "#2D333B", "#3A424D", "#ECEFF3", "#ABB4C0", "#79828F")),
    "claro": ("Claro", {
        "bg": "#EEF2F7", "card": "#FFFFFF", "card2": "#F4F6F9", "borde": "#E3E8EF", "texto": "#0A2342", "texto2": "#4B5563",
        "muted": "#8A94A6", "oro": "#A8872A", "oro-txt": "#8F7020", "k-azul": "#1C5CAB", "k-verde": "#127A53",
        "k-ambar": "#9A6400", "sube": "#127A53", "baja-txt": "#B42318", "alta": "#D93F3F", "media": "#D98A00", "baja": "#2E9E6A",
        "informativa": "#8A94A6", "zebra": "#F8FAFC", "sombra": "0 1px 2px rgba(10,35,66,.05),0 8px 20px -12px rgba(10,35,66,.25)",
        **{f"c-{k}": v for k, v in _SERIES_CLARO.items()},
        "c-registrado": gs.CLARO["registrado"], "c-recalculado": gs.CLARO["recalculado"], "c-serie": gs.CLARO["serie"],
        "c-linea": gs.CLARO["linea"], "c-alta": gs.CLARO["alta"], "c-media": gs.CLARO["media"], "c-baja": gs.CLARO["baja"],
        "c-informativa": gs.CLARO["informativa"], "c-texto": "#0A2342", "c-texto2": "#4B5563", "c-regla": "#D5DCE6",
        "c-superficie": "#FFFFFF"}),
}
GRAFICOS = gs.ROTULO_VARIANTE
VISTAS = {"estandar": "Estándar", "compacta": "Compacta", "tablas": "Foco en tablas", "presentacion": "Presentación"}
POR_DEFECTO = {"t": "ejecutivo", "g": "barras_linea", "v": "estandar"}

F_TITULO = "Montserrat,'Segoe UI',Calibri,Arial,sans-serif"
F_TEXTO = "Poppins,'Segoe UI',Calibri,Arial,sans-serif"
F_CIFRA = "'Roboto Mono',Consolas,'Courier New',monospace"

_ICONOS = {
    "principal": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.4"/>',
    "poblacion": '<path d="M12 3 3 8l9 5 9-5-9-5Z"/><path d="m3 12 9 5 9-5"/><path d="m3 16 9 5 9-5"/>',
    "recalculado": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 11h2M12 11h2M16 11h0M8 15h2M12 15h2M8 18h2M12 18h4"/>',
    "registrado": '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5v-15Z"/><path d="M5 19.5A1.5 1.5 0 0 0 6.5 21H19"/><path d="M9 7h6"/>',
    "problemas": '<path d="M12 3 2 20h20L12 3Z"/><path d="M12 10v4M12 17h.01"/>',
}


def _icono(nombre: str) -> str:
    return (f'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONOS[nombre]}</svg>')


def _img(nombre: str, clase: str = "") -> str:
    """Logotipo incrustado en base64: el HTML sigue funcionando sin internet."""
    w, h = marca.tamano(nombre)
    cls = f' class="{clase}"' if clase else ""
    return f'<img{cls} src="{marca.data_uri(nombre)}" alt="{E(marca.ALT[nombre])}" width="{w}" height="{h}">'


def _membrete() -> str:
    return (f'<div class="membrete">{_img("auditconsulting_oscuro")}{_img("audit_ia", "logo-ia")}</div>')


def _fecha(v) -> str:
    """2025-12-31 → 31/12/2025 (es-EC)."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(v or "").strip()[:10])
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(v or "")


def _vars(t: dict) -> str:
    return ";".join(f"--{k}:{v}" for k, v in t.items())


def _css() -> str:
    temas = "".join(f"body.t-{k}{{{_vars(v)}}}" for k, (_, v) in TEMAS.items())
    claro = _vars(TEMAS["claro"][1])
    return (
        temas +
        f":root{{--f-titulo:{F_TITULO};--f-texto:{F_TEXTO};--f-cifra:{F_CIFRA}}}"
        "*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}"
        "body{margin:0;background:var(--bg);color:var(--texto);font:14px/1.5 var(--f-texto);-webkit-font-smoothing:antialiased}"
        # Barra superior
        ".topbar{position:sticky;top:0;z-index:5;display:flex;flex-wrap:wrap;align-items:center;gap:10px 18px;"
        "padding:10px 20px;background:var(--card);border-bottom:1px solid var(--borde);box-shadow:var(--sombra)}"
        # Logotipos: la firma sobre una placa navy (legible en todos los temas, también Claro)
        ".logos{display:flex;align-items:center;gap:8px;flex:none}"
        ".logo-firma{display:flex;align-items:center;height:44px;padding:5px 12px;border-radius:9px;background:#071B2F;"
        "box-shadow:inset 0 1px 0 rgba(255,255,255,.12)}.logo-firma img{height:34px;width:auto;display:block}"
        ".logo-ia{height:44px;width:auto;border-radius:9px;display:block}"
        # Membrete de impresión y PDF (la barra superior no se imprime)
        ".membrete{display:none;align-items:center;justify-content:space-between;gap:16px;padding:0 0 10px;"
        "margin:0 0 14px;border-bottom:2px solid #C7A83C}.membrete img{height:46px;width:auto;display:block}"
        ".membrete .logo-ia{height:46px}body.pdf .membrete{display:flex}"
        ".marca{display:flex;flex-direction:column;line-height:1.2;min-width:0}"
        ".marca b{font:700 14px var(--f-titulo);letter-spacing:.02em}.marca span{font-size:11.5px;color:var(--texto2)}"
        ".controles{margin-left:auto;display:flex;flex-wrap:wrap;gap:8px;align-items:center}"
        ".controles label{display:flex;align-items:center;gap:6px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--texto2)}"
        ".controles select,.btn{font:500 12.5px var(--f-texto);color:var(--texto);background:var(--card2);"
        "border:1px solid var(--borde);border-radius:8px;padding:6px 10px}"
        ".btn{cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:6px;white-space:nowrap}"
        ".btn:hover{border-color:var(--oro)}"
        ".btn.oro{background:var(--oro);border-color:var(--oro);color:#071B2F;font-weight:700}"
        ".descargas{position:relative}.descargas summary{list-style:none}.descargas summary::-webkit-details-marker{display:none}"
        ".descargas .menu{position:absolute;right:0;top:calc(100% + 6px);min-width:220px;display:grid;gap:6px;padding:10px;"
        "background:var(--card);border:1px solid var(--borde);border-radius:10px;box-shadow:var(--sombra)}"
        "select:focus-visible,.btn:focus-visible,.tab:focus-visible,summary:focus-visible{outline:2px solid var(--oro);outline-offset:2px}"
        # Navegación por secciones
        ".nav{display:flex;gap:4px;overflow-x:auto;padding:0 20px;background:var(--card);border-bottom:1px solid var(--borde);scrollbar-width:thin}"
        ".tab{background:none;border:0;border-bottom:3px solid transparent;color:var(--texto2);font:600 13px var(--f-titulo);"
        "padding:12px 10px 9px;white-space:nowrap;cursor:pointer}"
        ".tab:hover{color:var(--texto)}.tab.on{color:var(--texto);border-bottom-color:var(--oro)}"
        ".wrap{max-width:1320px;margin:0 auto;padding:22px 20px 40px}"
        ".seccion{display:none}.seccion.on{display:block}"
        # Encabezado y chips
        ".encab{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px}"
        "h1{font:700 26px/1.2 var(--f-titulo);margin:0 0 4px;letter-spacing:-.01em}"
        "h2{font:700 18px/1.3 var(--f-titulo);margin:0}"
        ".sub{color:var(--texto2);font-size:13px;margin:0 0 10px}"
        ".chips{display:flex;flex-wrap:wrap;gap:6px}"
        ".chip{font:600 11.5px var(--f-texto);padding:4px 10px;border-radius:999px;background:var(--card2);border:1px solid var(--borde);color:var(--texto2)}"
        ".chip.riesgo-alto{color:var(--alta);border-color:var(--alta)}.chip.riesgo-medio{color:var(--media);border-color:var(--media)}"
        ".chip.riesgo-bajo{color:var(--baja);border-color:var(--baja)}"
        # KPI
        ".kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(200px,100%),1fr));gap:12px;margin-bottom:16px}"
        ".kpi{background:var(--card);border:1px solid var(--borde);border-radius:14px;padding:14px 16px;box-shadow:var(--sombra);min-width:0}"
        ".kpi-cab{display:flex;align-items:center;gap:8px;color:var(--texto2);margin-bottom:8px;min-width:0}"
        ".kpi-ico{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;flex:none;background:var(--card2)}"
        ".kpi-etq{font:600 11px var(--f-titulo);letter-spacing:.09em;text-transform:uppercase;overflow-wrap:anywhere}"
        ".kpi-val{font:700 clamp(22px,2.1vw,30px)/1.15 var(--f-titulo);letter-spacing:-.01em;overflow-wrap:anywhere}"
        ".kpi-exacto{font:12px var(--f-cifra);color:var(--muted);margin-top:2px;overflow-wrap:anywhere}"
        ".kpi-var{font:600 12px var(--f-texto);margin-top:8px;color:var(--texto2);overflow-wrap:anywhere}"
        ".sube{color:var(--sube)}.baja{color:var(--baja-txt)}"
        ".k-oro .kpi-val,.k-oro .kpi-ico{color:var(--oro-txt)}.k-azul .kpi-val,.k-azul .kpi-ico{color:var(--k-azul)}"
        ".k-verde .kpi-val,.k-verde .kpi-ico{color:var(--k-verde)}.k-ambar .kpi-val,.k-ambar .kpi-ico{color:var(--k-ambar)}"
        ".k-alto .kpi-val,.k-alto .kpi-ico{color:var(--alta)}.k-medio .kpi-val,.k-medio .kpi-ico{color:var(--media)}"
        ".k-bajo .kpi-val,.k-bajo .kpi-ico{color:var(--baja)}"
        # Gráficos
        ".graficos{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(470px,100%),1fr));gap:14px}"
        ".tarjeta{background:var(--card);border:1px solid var(--borde);border-radius:14px;padding:14px 16px 8px;box-shadow:var(--sombra);min-width:0}"
        ".tarjeta h3{font:700 14px var(--f-titulo);margin:0}.tarjeta p{font-size:11.5px;color:var(--texto2);margin:2px 0 6px}"
        ".grafico{display:block;width:100%;height:auto}"
        # En pantallas angostas el gráfico conserva un ancho legible y se desplaza DENTRO de su tarjeta.
        ".lienzo{overflow-x:auto;max-width:100%}.lienzo .grafico{min-width:480px}"
        ".grafico .val{font:600 11px var(--f-cifra);paint-order:stroke;stroke:var(--c-superficie);stroke-width:3px;stroke-linejoin:round}"
        ".grafico .cat{font:11px var(--f-texto)}"
        ".grafico .centro{font:700 26px var(--f-titulo)}.grafico .centro-etq{font:11px var(--f-texto)}"
        ".grafico .ley{font:600 12px var(--f-texto)}.grafico .ley2{font:11px var(--f-cifra)}"
        ".grafico .marca:hover{opacity:.85}"
        ".var{display:none}"
        + "".join(f"body.g-{k} .var-{k}{{display:block}}" for k in GRAFICOS) +
        ".sin-datos{color:var(--muted);font-size:12.5px;padding:24px 0;text-align:center}"
        # Secciones de cédula
        ".cedula-cab{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-bottom:10px;"
        "padding-bottom:8px;border-bottom:2px solid var(--oro)}"
        ".panel{background:var(--card);border:1px solid var(--borde);border-radius:14px;padding:12px 14px;box-shadow:var(--sombra);min-width:0}"
        ".scroll{overflow-x:auto;max-width:100%}"
        "table{border-collapse:collapse;width:100%;font-size:12.5px}"
        "th{background:var(--card2);color:var(--texto);text-align:left;font:700 11.5px var(--f-titulo);letter-spacing:.03em;"
        "padding:8px;border-bottom:2px solid var(--oro);white-space:nowrap}"
        "td{padding:6px 8px;border-bottom:1px solid var(--borde);vertical-align:top;color:var(--texto)}"
        "tbody tr:nth-child(even) td{background:var(--zebra)}"
        "td.num{text-align:right;white-space:nowrap;font-family:var(--f-cifra);font-variant-numeric:tabular-nums}"
        "tr.total td{font-weight:700;border-top:2px solid var(--oro);background:var(--card2)}"
        # «Cómo se calcula»: dentro del ancho, fórmulas que saltan de línea (sin desborde)
        "details.calc{margin:0 0 12px;background:var(--card2);border:1px solid var(--borde);border-radius:10px;padding:8px 12px}"
        "details.calc summary{cursor:pointer;font:700 13px var(--f-titulo);color:var(--oro-txt)}"
        "table.calc{table-layout:fixed;width:100%;margin-top:8px}"
        "table.calc col.c1{width:14%}table.calc col.c2{width:24%}table.calc col.c3{width:27%}table.calc col.c4{width:23%}table.calc col.c5{width:12%}"
        "table.calc td{white-space:normal;overflow-wrap:anywhere;word-break:break-word}"
        "table.calc td.mono{font:11.5px var(--f-cifra);white-space:pre-wrap;word-break:break-all}"
        "footer{max-width:1320px;margin:0 auto;padding:0 20px 30px;color:var(--muted);font-size:11.5px}"
        # Vistas
        "body.v-compacta{font-size:13px}body.v-compacta .wrap{padding:14px 14px 30px}body.v-compacta .kpi{padding:10px 12px}"
        "body.v-compacta .kpi-val{font-size:clamp(18px,1.7vw,24px)}body.v-compacta .graficos{gap:10px}body.v-compacta td{padding:4px 6px}"
        "body.v-tablas .kpis,body.v-tablas .graficos{display:none}body.v-tablas table{font-size:13.5px}body.v-tablas .wrap{max-width:none}"
        "body.v-presentacion{font-size:16px}body.v-presentacion .controles label:not(.fijo){display:none}"
        "body.v-presentacion .wrap{max-width:1180px;padding-top:34px}body.v-presentacion h1{font-size:34px}"
        "body.v-presentacion .kpi-val{font-size:clamp(26px,2.8vw,40px)}body.v-presentacion .kpis{grid-template-columns:repeat(auto-fit,minmax(min(210px,100%),1fr))}"
        "@media (max-width:640px){.topbar{padding:10px 14px}.wrap{padding:16px 14px 30px}h1{font-size:21px}.controles{margin-left:0}}"
        "@media (prefers-reduced-motion:reduce){*{transition:none!important}}"
        # Impresión: siempre en Claro
        f"@media print{{body[class]{{{claro}}}"
        ".topbar,.nav,.acciones,.no-print{display:none!important}.wrap{max-width:none;padding:0}.membrete{display:flex!important}"
        "body{background:#fff}.kpi,.tarjeta,.panel{box-shadow:none}"
        # Rejilla fija al imprimir (WeasyPrint no resuelve min() dentro de minmax)
        ".kpis{grid-template-columns:repeat(5,1fr)}.graficos{grid-template-columns:repeat(2,1fr)}"
        "body:not(.imprime-una) .seccion{display:block!important;break-before:page}"
        "body:not(.imprime-una) .seccion:first-of-type{break-before:auto}"
        "body.imprime-una .seccion{display:none!important}body.imprime-una .seccion.imprimir{display:block!important}"
        "details.calc{display:block}details.calc>*{display:block}.tarjeta,.kpi,tr{break-inside:avoid}"
        "*{-webkit-print-color-adjust:exact;print-color-adjust:exact}@page{size:A4 landscape;margin:11mm}}"
    )


def _literal(css: str, tema: dict) -> str:
    """Reemplaza var(--x) por el valor literal del tema (el PDF de WeasyPrint)."""
    base = {"f-titulo": F_TITULO, "f-texto": F_TEXTO, "f-cifra": F_CIFRA, **tema}
    return re.sub(r"var\(--([a-z0-9-]+)\)", lambda m: base.get(m.group(1), m.group(0)), css)


def _kpi(clase, icono, etq, valor, exacto, variacion_html) -> str:
    return (f'<div class="kpi {clase}"><div class="kpi-cab"><span class="kpi-ico">{_icono(icono)}</span>'
            f'<span class="kpi-etq">{E(etq)}</span></div><div class="kpi-val">{valor}</div>'
            + (f'<div class="kpi-exacto">{exacto}</div>' if exacto else "")
            + (f'<div class="kpi-var">{variacion_html}</div>' if variacion_html else "") + "</div>")


def _flecha(v, texto) -> str:
    if v is None:
        return ""
    cls, fl = ("sube", "↗") if v >= 0 else ("baja", "↘")
    return f'<span class="{cls}">{fl} {gs.pct(abs(v))}</span> {E(texto)}'


def _num(v, corto=True) -> str:
    if v is None:
        return "—"
    return gs.corto(v) if corto else gs.es_ec(v)


def kpis_datos(p: dict) -> list[dict]:
    """Las 5 tarjetas del panel como datos (las usan el HTML, el Word y el PowerPoint):
    clase de color, ícono, rótulo, cifra corta, cifra exacta y variación
    (``var``: (fracción, texto) con flecha ↗/↘, o texto simple en ``nota``)."""
    pr, po, rc, rg, pb = p["principal"], p["poblacion"], p["recalculado"], p["registrado"], p["problemas"]
    sev = pb["severidad"]
    resumen_sev = " · ".join(f"{sev[s]} {s.lower()}" for s in ("Alta", "Media", "Baja") if sev.get(s)) or "sin hallazgos con importe"
    var_pr = (pr["valor"] / abs(po["valor"])) if (pr["valor"] is not None and po["valor"]) else None
    if po.get("igual_registrado") and po.get("n"):
        pob = {"clase": "k-azul", "icono": "poblacion", "rotulo": po["rotulo"], "valor": f'{po["n"]} partidas',
               "exacto": "USD " + _num(po["valor"], False), "nota": "misma base que el saldo registrado"}
    else:
        pob = {"clase": "k-azul", "icono": "poblacion", "rotulo": po["rotulo"], "valor": "USD " + _num(po["valor"]),
               "exacto": _num(po["valor"], False), "nota": f'{po["n"]} registros' if po.get("n") else ""}
    return [
        {"clase": "k-oro", "icono": "principal", "rotulo": pr["rotulo"], "valor": "USD " + _num(pr["valor"]),
         "exacto": _num(pr["valor"], False), "var": (var_pr, "de la población")},
        pob,
        {"clase": "k-verde", "icono": "recalculado", "rotulo": rc["rotulo"], "valor": "USD " + _num(rc["valor"]),
         "exacto": _num(rc["valor"], False), "var": (rc["variacion"], "vs registrado")},
        {"clase": "k-ambar", "icono": "registrado", "rotulo": rg["rotulo"], "valor": "USD " + _num(rg["valor"]),
         "exacto": _num(rg["valor"], False), "nota": "según el cliente"},
        {"clase": f"k-{p['riesgo']}", "icono": "problemas", "rotulo": pb["rotulo"], "valor": str(pb["valor"]),
         "exacto": "", "nota": resumen_sev},
    ]


def _kpis(p: dict) -> str:
    return "".join(
        _kpi(k["clase"], k["icono"], k["rotulo"], k["valor"], k["exacto"],
             _flecha(*k["var"]) if "var" in k else E(k.get("nota") or ""))
        for k in kpis_datos(p))


def _tarjeta(titulo, sub, cuerpo) -> str:
    return (f'<div class="tarjeta"><h3>{E(titulo)}</h3>' + (f"<p>{E(sub)}</p>" if sub else "")
            + f'<div class="lienzo">{cuerpo}</div></div>')


def _variantes(items, roles, desc, hex_, enteros=False, solo=None) -> str:
    if not items:
        return '<div class="sin-datos">Sin datos para graficar en este ejemplo.</div>'
    variantes = [solo] if solo else list(GRAFICOS)
    return "".join(f'<div class="var var-{v}">{gs.columnas(items, v, roles, desc, hex_, enteros)}</div>' if not solo
                   else gs.columnas(items, v, roles, desc, hex_, enteros) for v in variantes)


def _graficos(p: dict, hex_: dict | None) -> str:
    solo = "barras" if hex_ else None
    comp, cmp_, dist, sev = p["composicion"], p["comparativo"], p["distribucion"], p["severidad"]
    dona = gs.dona(comp["items"], comp["rotulo"], hex_) or '<div class="sin-datos">Sin componentes con importe.</div>'
    comparativo = _variantes(cmp_["items"], ["registrado", "recalculado"], cmp_["rotulo"], hex_, solo=solo)
    distrib = _variantes(dist["items"], "serie", dist["rotulo"], hex_, solo=solo)
    severidad = _variantes(sev["items"], ["alta", "media", "baja", "informativa"], sev["rotulo"], hex_, enteros=True, solo=solo)
    return ('<div class="graficos">'
            + _tarjeta("Composición del resultado", comp["rotulo"], dona)
            + _tarjeta(cmp_["rotulo"], "Cifra del cliente frente a la recalculada por el auditor (USD).", comparativo)
            + _tarjeta(dist["rotulo"], "Distribución de la población (USD).", distrib)
            + _tarjeta(sev["rotulo"], sev["regla"], severidad)
            + "</div>")


def _tabla(h: dict, celda) -> str:
    cab = "".join(f"<th>{E(c[0])}</th>" for c in h["cols"])
    filas = [(r, False) for r in h.get("rows") or []] + ([(h["total"], True)] if h.get("total") else [])
    cuerpo = "".join(
        "<tr" + (' class="total"' if total else "") + ">"
        + "".join(f'<td class="{"num" if f in ("n", "p", "i") else ""}"'
                  + (f' title="={E(v["f"])}"' if isinstance(v, dict) and "f" in v else "")
                  + f">{celda(v, f)}</td>" for (_, f), v in zip(h["cols"], fila))
        + "</tr>" for fila, total in filas)
    return f'<div class="scroll"><table><thead><tr>{cab}</tr></thead><tbody>{cuerpo}</tbody></table></div>'


def _calc(bloque: list[dict], abierto: bool) -> str:
    if not bloque:
        return ""
    filas = "".join(
        f"<tr><td>{E(b['columna'])}</td><td class='mono'>{E(b['formula'])}</td><td>{E(b['explicacion'])}</td>"
        f"<td class='mono'>{E(b['ejemplo'])}</td><td>{E(b['origen'])}</td></tr>" for b in bloque)
    return (f"<details class='calc'{' open' if abierto else ''}><summary>ⓘ Cómo se calcula esta hoja</summary>"
            "<div class='scroll'><table class='calc'><colgroup><col class='c1'><col class='c2'><col class='c3'><col class='c4'><col class='c5'></colgroup>"
            "<thead><tr><th>Columna</th><th>Fórmula</th><th>Cómo se calcula</th><th>Ejemplo con números reales</th><th>De dónde viene</th></tr></thead>"
            f"<tbody>{filas}</tbody></table></div></details>")


_JS = r"""(function(){
var b=document.body,K='auditia.papel.prefs',D=%s;
function lee(){try{return JSON.parse(localStorage.getItem(K)||'{}')||{}}catch(e){return {}}}
function guarda(p){try{localStorage.setItem(K,JSON.stringify(p))}catch(e){}}
var p=lee();
function aplica(){['t','g','v'].forEach(function(x){
  Array.prototype.slice.call(b.classList).forEach(function(c){if(c.indexOf(x+'-')===0)b.classList.remove(c)});
  b.classList.add(x+'-'+(p[x]||D[x]));var s=document.getElementById('sel-'+x);if(s)s.value=p[x]||D[x];});}
['t','g','v'].forEach(function(x){var s=document.getElementById('sel-'+x);if(s)s.addEventListener('change',function(){p[x]=s.value;guarda(p);aplica();});});
aplica();
var tabs=document.querySelectorAll('.tab');
function muestra(id){document.querySelectorAll('.seccion').forEach(function(s){s.classList.toggle('on',s.id===id)});
  tabs.forEach(function(t){var on=t.getAttribute('data-s')===id;t.classList.toggle('on',on);t.setAttribute('aria-selected',on?'true':'false');});
  window.scrollTo(0,0);}
tabs.forEach(function(t){t.addEventListener('click',function(){muestra(t.getAttribute('data-s'));});});
function imprime(una){if(una){b.classList.add('imprime-una');document.querySelectorAll('.seccion').forEach(function(s){s.classList.toggle('imprimir',s.id===una)});}
  window.print();}
window.addEventListener('afterprint',function(){b.classList.remove('imprime-una');});
document.querySelectorAll('[data-pdf]').forEach(function(x){x.addEventListener('click',function(){var s=x.getAttribute('data-pdf');imprime(s==='todo'?null:s);});});
})();"""


def render(definicion: dict, reg: dict, eventos: list, version: int, estado: str, hojas: list[dict],
           adjuntos: list[tuple[str, str, str, bytes]], celda, como_se_calcula, para_pdf: bool = False) -> str:
    from backend.app.aud.niif.procesadores import PROCESADORES

    e = reg.get("engagement") or {}
    run = reg.get("run") or {}
    mod = PROCESADORES.get(definicion.get("processor", ""))
    proc_hojas = run.get("hojas") or []
    p = graficos.panel(mod, run, proc_hojas)
    hex_ = gs.CLARO if para_pdf else None
    nombre = definicion.get("name", "")
    riesgo_txt = {"alto": "Riesgo alto", "medio": "Riesgo medio", "bajo": "Riesgo bajo"}[p["riesgo"]]
    chips = (f'<span class="chip riesgo-{p["riesgo"]}">▲ {riesgo_txt}</span>'
             f'<span class="chip">Corte {E(_fecha(e.get("cutoff")))}</span><span class="chip">Versión {version}</span>'
             f'<span class="chip">{E(est.estado_es(estado))}</span><span class="chip">{E(str(e.get("framework", "")))}</span>')
    boton_pdf = lambda sid: "" if para_pdf else f'<button class="btn acciones" type="button" data-pdf="{sid}">⬇ Guardar como PDF · esta sección</button>'  # noqa: E731

    secciones = [(
        "s-panel", "Panel",
        f'<div class="encab"><div><h1>{E(nombre)}</h1>'
        f'<p class="sub">{E(str(e.get("client", "")))} · RUC {E(str(e.get("ruc", "")))} · {E(definicion.get("area", ""))}</p>'
        f'<div class="chips">{chips}</div></div>{boton_pdf("s-panel")}</div>'
        f'<div class="kpis">{_kpis(p)}</div>{_graficos(p, hex_)}')]
    for i, h in enumerate(hojas):
        sid = f"s-{i}"
        cuerpo = (f'<div class="cedula-cab"><h2>{E(h["label"])}</h2>{boton_pdf(sid)}</div>'
                  f'<div class="panel">{_calc(como_se_calcula(h, hojas), para_pdf)}{_tabla(h, celda)}</div>')
        secciones.append((sid, h["label"], cuerpo))

    cuerpo_secc = "".join(
        f'<section class="seccion{" on" if k == 0 else ""}" id="{sid}" aria-label="{E(etq)}">{html_}</section>'
        for k, (sid, etq, html_) in enumerate(secciones))
    css = _css()
    if para_pdf:
        css = _literal(css, TEMAS["claro"][1])
        return ("<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
                f"<title>{E(nombre)}</title><style>{css}"
                ".seccion{display:block!important;break-before:page}.seccion:first-of-type{break-before:auto}"
                "details.calc>summary{list-style:none}</style></head>"
                f'<body class="t-claro g-barras v-estandar pdf"><main class="wrap">{_membrete()}{cuerpo_secc}</main>'
                f"<footer>AuditConsulting Auditores Cía. Ltda. · AUDIT-IA · Papel de trabajo generado por la herramienta; "
                f"las cifras son de la prueba ejecutada.</footer></body></html>")

    opciones = lambda d, sel: "".join(f'<option value="{k}"{" selected" if k == sel else ""}>{E(v if isinstance(v, str) else v[0])}</option>' for k, v in d.items())  # noqa: E731
    base = re.sub(r"[^\w-]+", "_", nombre or "papel")[:60] + f"_v{version}"
    descargas = "".join(
        f'<a class="btn" download="{base}.{ext}" href="data:{mime};base64,{base64.b64encode(datos).decode()}">⬇ {E(etq)}</a>'
        for ext, etq, mime, datos in adjuntos)
    topbar = (
        f'<header class="topbar"><div class="logos"><span class="logo-firma">{_img("auditconsulting_blanco")}</span>'
        f'{_img("audit_ia", "logo-ia")}</div>'
        '<div class="marca"><b>AuditConsulting Auditores</b><span>AUDIT-IA · Papel de trabajo NIIF</span></div>'
        '<div class="controles">'
        f'<label>Color <select id="sel-t" aria-label="Color">{opciones(TEMAS, POR_DEFECTO["t"])}</select></label>'
        f'<label>Gráfico <select id="sel-g" aria-label="Gráfico">{opciones(GRAFICOS, POR_DEFECTO["g"])}</select></label>'
        f'<label class="fijo">Vista <select id="sel-v" aria-label="Vista">{opciones(VISTAS, POR_DEFECTO["v"])}</select></label>'
        f'<details class="descargas"><summary class="btn oro">⬇ Descargas</summary><div class="menu">{descargas}'
        '<button class="btn" type="button" data-pdf="todo">⬇ Guardar como PDF · papel completo</button></div></details>'
        "</div></header>")
    nav = ('<nav class="nav" role="tablist" aria-label="Secciones">' + "".join(
        f'<button class="tab{" on" if k == 0 else ""}" role="tab" aria-selected="{"true" if k == 0 else "false"}" data-s="{sid}" type="button">{E(etq)}</button>'
        for k, (sid, etq, _) in enumerate(secciones)) + "</nav>")
    clases = " ".join(f"{k}-{v}" for k, v in POR_DEFECTO.items())
    return ("<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
            f"<title>{E(nombre)}</title><style>{css}</style></head>"
            f'<body class="{clases}">{topbar}{nav}<main class="wrap">{_membrete()}{cuerpo_secc}</main>'
            "<footer>AuditConsulting Auditores Cía. Ltda. · AUDIT-IA · Funciona sin conexión. Pase el cursor sobre un importe "
            "para ver su fórmula; «ⓘ Cómo se calcula esta hoja» explica cada columna. En el Excel las fórmulas son editables y trazables.</footer>"
            f"<script>{_JS % __import__('json').dumps(POR_DEFECTO)}</script></body></html>")
