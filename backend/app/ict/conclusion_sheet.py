"""Hoja "CONCLUSIÓN" del papel de trabajo ICT (REP-007).

Sintetiza el resultado del trabajo (excepciones halladas, cuadratura,
alcance corrido vs. no corrido por suficiencia) y deja el espacio de firma
del auditor responsable y del revisor. Es la hoja que cierra el papel de
trabajo antes del sign-off.

FUENTE DE LA SÍNTESIS. El texto de la conclusión puede provenir de:
  (a) el auditor (texto libre validado), o
  (b) una interpretación IA (`backend/app/ict/audit/interpreter.py`).

SI PROVIENE DE IA, se deben cumplir los 6 controles de CLAUDE.md
("Interpretación IA con disclaimer obligatorio") ANTES de renderizar:
  1. schema Pydantic validado, 2. QA evaluator, 3. audit trail,
  4. disclaimer visible al pie (Calibri 8 italic #6B7280),
  5. `confianza_modelo` renderizada (borde rojo + "Revisar manualmente"
     si es "baja"), 6. ícono si `requiere_revision_humana`.
Este scaffold expone `interpretacion` para transportar esos campos y un
helper `_render_disclaimer_ia` que la implementación DEBE invocar cuando
la síntesis sea IA.

REGLAS DE CLAUDE.md:
  - Hoja interna del auditor → ocultar en SRI (agregar "CONCLUSIÓN" a
    `service.HIDDEN_SHEETS_FOR_SRI`).
  - `_safe_text` en todo texto; el Excel no debe pedir reparación.
  - El espacio de firma NUNCA se pre-llena con una firma: son líneas en
    blanco rotuladas (Preparó / Revisó / Fecha).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from backend.app.ict.fillers.source_data_sheets import _safe_text

SHEET_NAME = "CONCLUSIÓN"

_THIN = Side(border_style="thin", color="A0A0A0")
_RED = Side(border_style="medium", color="C00000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_RED_BORDER = Border(left=_RED, right=_RED, top=_RED, bottom=_RED)
_FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
_FONT_SUB = Font(name="Calibri", size=9, italic=True, color="404040")
_FONT_SECTION = Font(name="Calibri", size=11, bold=True, color="0A2342")
_FONT_LABEL = Font(name="Calibri", size=9, bold=True)
_FONT_DATA = Font(name="Calibri", size=9)
_FONT_DISCLAIMER = Font(name="Calibri", size=8, italic=True, color="6B7280")
_FONT_ALERT = Font(name="Calibri", size=9, bold=True, color="C00000")
_FILL_TITLE = PatternFill("solid", fgColor="0A2342")
_FILL_SECTION = PatternFill("solid", fgColor="D6E4F0")

#: Disclaimer obligatorio para bloques con interpretación IA (CLAUDE.md §4).
DISCLAIMER_IA = (
    "Análisis generado por IA. La interpretación debe ser validada por el "
    "auditor responsable antes de cualquier decisión."
)


class InterpretacionIA(TypedDict, total=False):
    """Subconjunto de `AnexoInterpretation` relevante para la conclusión."""

    sintesis: str
    confianza_modelo: Literal["alta", "media", "baja"]
    requiere_revision_humana: bool
    modelo: str
    generado_en: str


class ConclusionContexto(TypedDict, total=False):
    """Entrada de la hoja CONCLUSIÓN.

    `sintesis` es el texto validado (del auditor o IA). Los agregados
    (excepciones, cuadratura, suficiencia) los provee el motor ya calculados;
    esta hoja los cita, no los recomputa.
    """

    sintesis: str
    total_excepciones: int
    monto_total_excepciones: str        # Decimal como str
    cuadra_a1: bool                     # A = P + Pa cuadró
    suficiencia_estado: str             # "Completo" | "Parcial" | "Insuficiente"
    reglas_no_corridas: list[str]       # reglas que la suficiencia dejó fuera
    interpretacion: InterpretacionIA    # presente solo si la síntesis es IA


@dataclass
class ConclusionSheetResult:
    """Resultado del volcado para trazabilidad."""

    sheet_name: str = SHEET_NAME
    tiene_disclaimer_ia: bool = False
    confianza_modelo: str | None = None
    requiere_revision_humana: bool = False
    advertencias: list[str] = field(default_factory=list)


def build_conclusion_sheet(
    wb: Workbook,
    contexto: ConclusionContexto,
    *,
    session_data: dict | None = None,
) -> ConclusionSheetResult:
    """Crea/reemplaza la hoja CONCLUSIÓN en `wb`.

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Si la hoja existe, borrarla y recrearla.
        2. Título de marca + cabecera del encargo.
        3. Bloque "Síntesis del trabajo": el texto `sintesis` con wrap,
           `_safe_text`. Si `interpretacion` viene y es IA:
             - si `confianza_modelo == "baja"`: enmarcar en borde rojo +
               leyenda "Revisar manualmente".
             - si `requiere_revision_humana`: ícono dedicado.
             - SIEMPRE: pie con `DISCLAIMER_IA` (Calibri 8 italic #6B7280).
        4. Bloque "Resultados clave": conteo/monto de excepciones, si A1
           cuadró, estado de suficiencia y reglas no corridas.
        5. Bloque "Firma": líneas rotuladas EN BLANCO para
           Preparó / Revisó / Fecha (nunca pre-llenadas).
        6. Anchos explícitos; registro en trace log.

    Returns:
        ConclusionSheetResult (flags de IA para verificación de controles).
    """
    if SHEET_NAME in wb.sheetnames:
        del wb[SHEET_NAME]
    ws = wb.create_sheet(title=SHEET_NAME)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 60

    result = ConclusionSheetResult()

    # Cabecera de marca.
    ws.merge_cells("A1:B1")
    c = ws.cell(1, 1, value=_safe_text("AUDIT-IA · Conclusión del papel de trabajo"))
    c.font = _FONT_TITLE
    c.fill = _FILL_TITLE
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[1].height = 24
    sd = session_data or {}
    encargo = " · ".join(
        p for p in (
            _safe_text(sd.get("razon_social", "")),
            f"RUC {sd['ruc']}" if sd.get("ruc") else "",
            f"Ejercicio {sd['ejercicio_fiscal']}" if sd.get("ejercicio_fiscal") else "",
        ) if p
    )
    ws.merge_cells("A2:B2")
    c2 = ws.cell(2, 1, value=_safe_text(encargo) if encargo else _safe_text("(encargo sin identificar)"))
    c2.font = _FONT_SUB
    c2.alignment = Alignment(horizontal="left", vertical="center", indent=1)

    row = 4
    interpretacion = contexto.get("interpretacion")

    # Bloque "Síntesis del trabajo".
    ws.cell(row, 1, value=_safe_text("Síntesis del trabajo")).font = _FONT_SECTION
    row += 1
    sintesis = ""
    if interpretacion and interpretacion.get("sintesis"):
        sintesis = interpretacion["sintesis"]
    else:
        sintesis = contexto.get("sintesis", "")
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    sc = ws.cell(row, 1, value=_safe_text(sintesis))
    sc.font = _FONT_DATA
    sc.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    ws.row_dimensions[row].height = 48
    sintesis_row = row
    row += 2

    # Controles IA (4-6 de CLAUDE.md) solo si la síntesis proviene de IA.
    if interpretacion:
        row = _render_disclaimer_ia(ws, row, interpretacion, sintesis_row=sintesis_row)
        result.tiene_disclaimer_ia = True
        result.confianza_modelo = interpretacion.get("confianza_modelo")
        result.requiere_revision_humana = bool(interpretacion.get("requiere_revision_humana"))
        row += 1

    # Bloque "Resultados clave".
    ws.cell(row, 1, value=_safe_text("Resultados clave")).font = _FONT_SECTION
    row += 1
    resultados = [
        ("Excepciones detectadas", str(contexto.get("total_excepciones", 0))),
        ("Monto total de excepciones", str(contexto.get("monto_total_excepciones", "0.00"))),
        ("A1 cuadra (A = P + Pa)", "Sí" if contexto.get("cuadra_a1") else "No"),
        ("Estado de suficiencia", str(contexto.get("suficiencia_estado", "(no informado)"))),
        ("Reglas no corridas", ", ".join(contexto.get("reglas_no_corridas", [])) or "Ninguna"),
    ]
    for etiqueta, valor in resultados:
        lc = ws.cell(row, 1, value=_safe_text(etiqueta))
        lc.font = _FONT_LABEL
        lc.border = _BORDER
        lc.alignment = Alignment(horizontal="left", vertical="center")
        vc = ws.cell(row, 2, value=_safe_text(valor))
        vc.font = _FONT_DATA
        vc.border = _BORDER
        vc.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        row += 1
    row += 1

    # Bloque de firma.
    _render_firma(ws, row)

    return result


def _render_firma(ws: Worksheet, row: int) -> int:
    """Escribe el bloque de firma (Preparó/Revisó/Fecha) con líneas en
    blanco (nunca pre-llenadas). Devuelve la fila siguiente."""
    ws.cell(row, 1, value=_safe_text("Firma y sign-off")).font = _FONT_SECTION
    row += 2
    for etiqueta in ("Preparó", "Revisó", "Fecha"):
        lc = ws.cell(row, 1, value=_safe_text(f"{etiqueta}:"))
        lc.font = _FONT_LABEL
        lc.alignment = Alignment(horizontal="left", vertical="center")
        # Línea en blanco para la firma manuscrita/nombre.
        line = ws.cell(row, 2, value=None)
        line.border = Border(bottom=Side(border_style="thin", color="000000"))
        row += 2
    return row


def _render_disclaimer_ia(
    ws: Worksheet, row: int, interpretacion: InterpretacionIA, *, sintesis_row: int,
) -> int:
    """Escribe el disclaimer IA obligatorio + marca de confianza/revisión
    (controles 4-6 de CLAUDE.md). Devuelve la fila siguiente."""
    confianza = interpretacion.get("confianza_modelo")

    # Control 5: confianza baja → borde rojo sobre la síntesis + leyenda.
    if confianza == "baja":
        for col in (1, 2):
            ws.cell(sintesis_row, col).border = _RED_BORDER
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        alert = ws.cell(row, 1, value=_safe_text("⚠ Revisar manualmente — confianza del modelo: baja"))
        alert.font = _FONT_ALERT
        alert.alignment = Alignment(horizontal="left", vertical="center")
        row += 1

    # Control 6: requiere revisión humana → ícono dedicado.
    if interpretacion.get("requiere_revision_humana"):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        rc = ws.cell(row, 1, value=_safe_text("🔎 Requiere revisión humana antes del sign-off"))
        rc.font = _FONT_ALERT
        rc.alignment = Alignment(horizontal="left", vertical="center")
        row += 1

    # Confianza informada (media/alta) como nota simple.
    if confianza and confianza != "baja":
        nc = ws.cell(row, 1, value=_safe_text(f"Confianza del modelo: {confianza}"))
        nc.font = _FONT_DISCLAIMER
        row += 1

    # Control 4: disclaimer visible al pie (Calibri 8 italic #6B7280).
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    dc = ws.cell(row, 1, value=_safe_text(DISCLAIMER_IA))
    dc.font = _FONT_DISCLAIMER
    dc.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    ws.row_dimensions[row].height = 30
    row += 1
    return row
