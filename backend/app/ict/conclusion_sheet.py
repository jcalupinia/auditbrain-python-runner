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
from openpyxl.worksheet.worksheet import Worksheet

SHEET_NAME = "CONCLUSIÓN"

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

    Raises:
        NotImplementedError: scaffold; implementación en el servidor.
    """
    raise NotImplementedError(
        "build_conclusion_sheet: scaffold P2-F (REP-007). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 3."
    )


def _render_firma(ws: Worksheet, row: int) -> int:
    """Escribe el bloque de firma (Preparó/Revisó/Fecha) con líneas en
    blanco. Devuelve la fila siguiente. Scaffold."""
    raise NotImplementedError


def _render_disclaimer_ia(
    ws: Worksheet, row: int, interpretacion: InterpretacionIA,
) -> int:
    """Escribe el disclaimer IA obligatorio + marca de confianza/revisión
    (controles 4-6 de CLAUDE.md). Devuelve la fila siguiente. Scaffold."""
    raise NotImplementedError
