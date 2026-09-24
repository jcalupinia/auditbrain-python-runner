"""Informe PDF de cierre del ICT (REP-009).

Genera el informe de cierre del trabajo (síntesis, excepciones, parámetros,
sello) reutilizando el patrón HTML→PDF de las herramientas NIIF
(`backend/app/aud/niif/procesadores/libro.py`):

  - `build_cierre_html(...)` arma un HTML AUTÓNOMO (sin fuentes, scripts ni
    estilos externos; funciona sin internet), con marca AuditConsulting /
    AUDIT-IA, KPIs y secciones. Con `para_pdf=True` devuelve la versión
    estática (todo visible, sin pestañas ni JS) lista para renderizar el PDF.
  - `build_cierre_pdf(...)` renderiza ese HTML con WeasyPrint (horizontal).
    Si faltan las librerías nativas (Pango/cairo), degrada con
    `PDFCierreNoDisponible` — igual que `libro.pdf` — para que el endpoint
    responda un aviso, no un 500. El HTML siempre trae "Guardar como PDF".

Este informe se arma con datos YA calculados por el motor y por las hojas del
papel de trabajo (excepciones, parámetros, conclusión, sello). NO recalcula
nada: solo presenta.

REGLA DE CLAUDE.md ("Papeles de trabajo NIIF — formatos obligatorios"):
  el HTML autónomo debe funcionar sin internet y llevar dentro los
  descargables; el PDF sale por impresión horizontal ya preparada. El estilo
  de marca (Navy #0A2342, Gold #C7A83C, DM Sans/Segoe UI) sigue
  `docs/CANVA_ESTILO_PoC.md`.
"""

from __future__ import annotations

import html as _html
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from backend.app.ict.exceptions_sheet import EspecHojaExcepciones
    from backend.app.ict.parametros_sheet import ParametrosEncargoDict
    from backend.app.ict.sealing import SelloSalida

# Paleta de marca (CANVA_ESTILO_PoC.md). Copiada como constantes locales para
# no acoplar el ICT al módulo `estilo_ejecutivo` de NIIF.
NAVY = "0A2342"
GOLD = "C7A83C"
DEEP_BLUE = "071B2F"
LIGHT = "F4F7FB"
LINE = "DCE6F1"


class CierreContexto(TypedDict, total=False):
    """Entrada del informe de cierre. Reúne lo que ya produjeron el motor y
    las hojas del papel de trabajo."""

    session_data: dict                       # razon_social, ruc, ejercicio_fiscal
    sintesis: str                            # conclusión validada
    excepciones: "EspecHojaExcepciones"      # spec del motor (REP-006)
    parametros: "ParametrosEncargoDict"      # bloque U (REP-005)
    sello: "SelloSalida"                     # sello del motor (REP-013)
    cuadra_a1: bool
    suficiencia_estado: str


class PDFCierreNoDisponible(ValueError):
    """WeasyPrint (o sus librerías nativas Pango/cairo) no está disponible en
    este entorno. El endpoint lo traduce a un aviso, no a un error 500.
    Espejo de `libro.PDFNoDisponible`."""


def build_cierre_html(contexto: CierreContexto, *, para_pdf: bool = False) -> bytes:
    """Arma el HTML autónomo del informe de cierre.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Cabecera de marca (AuditConsulting · AUDIT-IA) + datos del encargo.
        2. Tarjetas KPI: nº de excepciones (con semáforo), monto total,
           estado de cuadratura A1, estado de suficiencia.
        3. Secciones: síntesis (conclusión), tabla de excepciones (hash/NIA/
           monto), tabla de parámetros, y bloque de sello (versión/timestamp/
           hash_salida).
        4. CSS embebido con `@media print { @page { size: A4 landscape } }`.
        5. `para_pdf=True` → sin pestañas/JS/descargas (todo visible).
           `para_pdf=False` → con pestañas, botón "Guardar como PDF" y, si
           se decide, adjuntos base64 (Excel/CSV) como en `libro.html`.
        6. Todo texto escapado con `html.escape` (no romper el HTML).

    Returns:
        bytes UTF-8 del documento HTML.
    """
    sd = contexto.get("session_data") or {}
    excepciones = contexto.get("excepciones") or {}
    parametros = contexto.get("parametros") or {}
    sello = contexto.get("sello") or {}
    resumen = excepciones.get("resumen") or {}

    razon = _e(sd.get("razon_social", "(sin razón social)"))
    ruc = _e(sd.get("ruc", ""))
    ejercicio = _e(sd.get("ejercicio_fiscal", ""))
    sintesis = _e(contexto.get("sintesis", ""))

    total_exc = resumen.get("total_excepciones", 0)
    monto_total = _fmt_monto(resumen.get("monto_total", "0.00"))
    cuadra = contexto.get("cuadra_a1")
    suficiencia = _e(contexto.get("suficiencia_estado", "(no informado)"))

    semaforo = "verde" if total_exc == 0 else ("ambar" if total_exc <= 3 else "rojo")

    # --- KPIs ---
    kpis = "".join([
        _kpi("Excepciones", str(total_exc), semaforo),
        _kpi("Monto total", monto_total, "neutro"),
        _kpi("Cuadratura A1", "Cuadra" if cuadra else "No cuadra",
             "verde" if cuadra else "rojo"),
        _kpi("Suficiencia", suficiencia, "neutro"),
    ])

    # --- Tabla de excepciones ---
    columnas = excepciones.get("columnas") or []
    filas = excepciones.get("filas") or []
    if columnas and filas:
        thead = "".join(f"<th>{_e(c.get('titulo', c.get('clave', '')))}</th>" for c in columnas)
        cuerpo = []
        for fila in filas:
            celdas = []
            for c in columnas:
                val = fila.get(c["clave"])
                val = _fmt_monto(val) if c.get("tipo") == "monto" else _e(val)
                celdas.append(f"<td>{val}</td>")
            cuerpo.append("<tr>" + "".join(celdas) + "</tr>")
        tabla_exc = (f"<table class='data'><thead><tr>{thead}</tr></thead>"
                     f"<tbody>{''.join(cuerpo)}</tbody></table>")
    else:
        tabla_exc = "<p class='muted'>Sin excepciones para este ejercicio.</p>"

    # --- Tabla de parámetros ---
    if parametros:
        filas_p = "".join(
            f"<tr><td>{_e(k)}</td><td>{_e(v)}</td></tr>"
            for k, v in parametros.items()
        )
        tabla_param = (f"<table class='data'><thead><tr><th>Parámetro</th>"
                       f"<th>Valor</th></tr></thead><tbody>{filas_p}</tbody></table>")
    else:
        tabla_param = "<p class='muted'>Sin parámetros registrados.</p>"

    # --- Bloque de sello ---
    sello_html = (
        f"<div class='sello'><strong>Sello:</strong> "
        f"{_e(sello.get('version_app', ''))} · "
        f"{_e(sello.get('timestamp', ''))} · "
        f"hash {_e(sello.get('hash_salida', ''))}</div>"
    )

    boton = ""
    if not para_pdf:
        boton = ("<div class='noprint actions'>"
                 "<button onclick=\"window.print()\">Guardar como PDF</button>"
                 "</div>")

    css = _CSS
    doc = f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de cierre ICT — {razon}</title>
<style>{css}</style>
</head>
<body>
<header class="brand">
  <div class="brand-name">AuditConsulting Auditores Cía. Ltda.</div>
  <div class="brand-sub">AUDIT-IA · Informe de cierre del ICT</div>
</header>
<section class="encargo">
  <div><strong>{razon}</strong></div>
  <div>RUC {ruc} · Ejercicio {ejercicio}</div>
</section>
{boton}
<section class="kpis">{kpis}</section>
<section>
  <h2>Síntesis del trabajo</h2>
  <p class="sintesis">{sintesis or '<span class="muted">(sin síntesis)</span>'}</p>
</section>
<section>
  <h2>Excepciones (hash · NIA · monto)</h2>
  {tabla_exc}
</section>
<section>
  <h2>Parámetros del encargo</h2>
  {tabla_param}
</section>
<section>
  <h2>Sello inmutable</h2>
  {sello_html}
</section>
<footer class="foot">
  Documento generado por AUDIT-IA. Papel de trabajo del auditor — validar antes de cualquier decisión.
</footer>
</body>
</html>"""
    return doc.encode("utf-8")


def _e(value) -> str:
    """Escapa texto para HTML (nunca None)."""
    return _html.escape("" if value is None else str(value))


def _fmt_monto(value) -> str:
    """Formatea un importe con miles y dos decimales; escapado."""
    if value is None or value == "":
        return ""
    try:
        d = Decimal(str(value))
        return _e(f"{d:,.2f}")
    except (InvalidOperation, ValueError):
        return _e(value)


def _kpi(titulo: str, valor: str, tono: str) -> str:
    return (f"<div class='kpi kpi-{tono}'>"
            f"<div class='kpi-val'>{_e(valor)}</div>"
            f"<div class='kpi-tit'>{_e(titulo)}</div></div>")


_CSS = (
    "*{box-sizing:border-box} "
    "body{font-family:'DM Sans','Segoe UI',Arial,sans-serif;margin:0;"
    "color:#071B2F;background:#F4F7FB;padding:24px} "
    "@media print{@page{size:A4 landscape;margin:12mm} .noprint{display:none} "
    "body{background:#fff;padding:0}} "
    ".brand{background:#0A2342;color:#fff;padding:16px 20px;border-bottom:4px solid #C7A83C} "
    ".brand-name{font-size:18px;font-weight:700} "
    ".brand-sub{font-size:12px;color:#C7A83C} "
    ".encargo{padding:12px 20px;border-bottom:1px solid #DCE6F1} "
    ".actions{padding:12px 20px} "
    "button{background:#C7A83C;border:0;color:#071B2F;font-weight:700;"
    "padding:8px 16px;border-radius:6px;cursor:pointer} "
    ".kpis{display:flex;gap:12px;flex-wrap:wrap;padding:16px 20px} "
    ".kpi{flex:1;min-width:140px;background:#fff;border:1px solid #DCE6F1;"
    "border-radius:8px;padding:14px;border-left:5px solid #0A2342} "
    ".kpi-verde{border-left-color:#2E7D32} .kpi-ambar{border-left-color:#ED9C28} "
    ".kpi-rojo{border-left-color:#C00000} .kpi-neutro{border-left-color:#0A2342} "
    ".kpi-val{font-size:22px;font-weight:700} "
    ".kpi-tit{font-size:11px;color:#5b6b7b;text-transform:uppercase} "
    "section{padding:8px 20px} "
    "h2{color:#0A2342;font-size:15px;border-bottom:2px solid #C7A83C;"
    "padding-bottom:4px} "
    "table.data{width:100%;border-collapse:collapse;font-size:12px} "
    "table.data th{background:#0A2342;color:#fff;text-align:left;padding:6px} "
    "table.data td{border:1px solid #DCE6F1;padding:5px} "
    ".muted{color:#8a97a5;font-style:italic} "
    ".sintesis{white-space:pre-wrap} "
    ".sello{font-family:Consolas,monospace;font-size:11px;background:#fff;"
    "border:1px solid #DCE6F1;padding:10px;border-radius:6px;word-break:break-all} "
    ".foot{padding:16px 20px;color:#8a97a5;font-size:10px;font-style:italic}"
)


def build_cierre_pdf(contexto: CierreContexto) -> bytes:
    """Renderiza el informe de cierre a PDF (WeasyPrint, horizontal).

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. `import weasyprint` dentro de try/except; si falla (ImportError u
           OSError por libs nativas) → `raise PDFCierreNoDisponible(...)`.
        2. `contenido = build_cierre_html(contexto, para_pdf=True)`.
        3. `return weasyprint.HTML(string=contenido.decode()).write_pdf()`.

    Raises:
        PDFCierreNoDisponible: si WeasyPrint no está disponible en el entorno.
    """
    try:
        import weasyprint  # requiere Pango/cairo/gdk-pixbuf nativos
    except Exception as e:  # ImportError o OSError al cargar las libs nativas
        raise PDFCierreNoDisponible(
            "El PDF de cierre en el servidor no está disponible en este entorno "
            "(faltan las librerías nativas de WeasyPrint). Use «Guardar como PDF» "
            "desde el HTML autónomo del informe de cierre."
        ) from e
    contenido = build_cierre_html(contexto, para_pdf=True)
    return weasyprint.HTML(string=contenido.decode("utf-8")).write_pdf()
