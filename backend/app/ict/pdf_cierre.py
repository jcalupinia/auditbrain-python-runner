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

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "build_cierre_html: scaffold P2-F (REP-009). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 5."
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
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "build_cierre_pdf: scaffold P2-F (REP-009). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 5."
    )
