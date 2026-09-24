"""Hoja "EXCEPCIONES" del papel de trabajo ICT (REP-006).

Vuelca la especificación de excepciones que produce el motor
(`motor-auditoria-analitica`) a una hoja Excel con una fila por excepción,
mostrando el hash de trazabilidad, la NIA aplicable y el monto involucrado.

CONTRATO CON EL MOTOR (Agente C · `motor/exportar_excepciones.py`, aún NO
existe en el repo del motor). Este módulo asume como ENTRADA el dict que
devolverá `motor.exportar_excepciones.especificar_hoja_excepciones(...)`.
Ese dict es datos puros (sin openpyxl): describe columnas y filas ya
formateadas y sus totales. La responsabilidad de esta capa es SOLO
presentarlo en Excel; NO recalcula montos ni severidades (principio
"Python calcula, la capa de presentación no recalcula").

REGLAS DE CLAUDE.md aplicadas al scaffold:
  - El Excel NO puede levantar el cuadro "Reparaciones" al abrirse: todo
    texto libre pasa por `_safe_text()` (reutilizado de source_data_sheets).
  - Formato profesional tipo SRI: bordes thin en datos, doble en TOTAL,
    Calibri 9 datos / 10 negrita TOTAL / 11 negrita encabezado de bloque,
    numéricos a la derecha con `#,##0.00`, anchos de columna explícitos.
  - Hoja INTERNA del auditor: viaja en el papel de trabajo y se OCULTA en
    el archivo SRI (agregar "EXCEPCIONES" a `service.HIDDEN_SHEETS_FOR_SRI`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypedDict

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet

SHEET_NAME = "EXCEPCIONES"

#: Tipos de columna que el motor puede declarar. Gobiernan alineación,
#: number_format y si el valor entra al total de montos.
TipoColumna = Literal[
    "texto", "monto", "fecha", "hash", "nia", "severidad", "entero", "estado"
]

#: Severidades canónicas del motor (orden de gravedad descendente).
Severidad = Literal["P0", "P1", "P2"]


class ColumnaExcepciones(TypedDict):
    """Definición de una columna de la hoja EXCEPCIONES."""

    clave: str          # clave estable con la que cada fila trae su valor
    titulo: str         # encabezado visible en Excel
    tipo: TipoColumna   # gobierna formato, alineación y agregación


class EspecHojaExcepciones(TypedDict, total=False):
    """Salida esperada de `motor.exportar_excepciones.especificar_hoja_excepciones`.

    `filas` es una lista de dicts indexados por `ColumnaExcepciones["clave"]`.
    `resumen` trae los agregados YA calculados por el motor (nunca se
    recomputan aquí). `engine_version`/`generado_en` alimentan la trazabilidad.
    """

    titulo: str
    columnas: list[ColumnaExcepciones]
    filas: list[dict[str, object]]
    resumen: "ResumenExcepciones"
    engine_version: str
    generado_en: str            # ISO-8601, hora del motor
    run_id: str                 # ExecutionRun.run_id que originó las excepciones


class ResumenExcepciones(TypedDict, total=False):
    """Agregados calculados por el motor (fila TOTAL de la hoja)."""

    total_excepciones: int
    monto_total: str            # Decimal serializado como str (nunca float)
    por_severidad: dict[Severidad, int]
    monto_por_severidad: dict[Severidad, str]


@dataclass
class ExceptionsSheetResult:
    """Resultado del volcado, para que el orquestador (service.generate_excel)
    lo registre en la trazabilidad y en la verificación."""

    sheet_name: str = SHEET_NAME
    filas_escritas: int = 0
    monto_total: str = "0.00"
    por_severidad: dict[str, int] = field(default_factory=dict)
    advertencias: list[str] = field(default_factory=list)


def build_exceptions_sheet(
    wb: Workbook,
    espec: EspecHojaExcepciones,
    *,
    session_data: dict | None = None,
) -> ExceptionsSheetResult:
    """Crea/reemplaza la hoja EXCEPCIONES en `wb` a partir de `espec`.

    Args:
        wb: workbook del ICT (ya cargado desde la plantilla).
        espec: spec de excepciones del motor (ver `EspecHojaExcepciones`).
            Si viene vacío o sin filas, se escribe una hoja con el mensaje
            "Sin excepciones para este ejercicio" (NUNCA se omite la hoja:
            la ausencia de excepciones es en sí un resultado auditable).
        session_data: datos del contribuyente para la cabecera
            (razon_social, ruc, ejercicio_fiscal).

    Comportamiento esperado (a implementar con TDD en el servidor):
        1. Si `SHEET_NAME` ya existe, borrarla y recrearla.
        2. Escribir título de marca + cabecera del encargo.
        3. Escribir encabezados desde `espec["columnas"]`.
        4. Una fila por `espec["filas"]`, aplicando por `tipo`:
           - monto → number_format `#,##0.00`, alineación derecha, Decimal(str).
           - hash  → fuente monoespaciada, `_safe_text` (empieza a menudo con
             dígitos, sin riesgo de fórmula, pero se escapa por robustez).
           - nia   → texto centrado (p.ej. "NIA 240").
           - severidad → color por P0/P1/P2 (rojo/naranja/amarillo).
           - texto/estado/fecha → `_safe_text`, alineación según tipo.
        5. Fila TOTAL desde `espec["resumen"]` (monto_total, conteo),
           en negrita con borde doble y fondo azul claro.
        6. AutoFilter + freeze panes sobre la tabla; anchos explícitos.
        7. Registrar cada escritura relevante en el trace log (base.safe_set /
           safe_set_formula) para que TRAZABILIDAD la recoja.

    Returns:
        ExceptionsSheetResult con conteos para verificación empírica.

    Raises:
        NotImplementedError: scaffold; la implementación va en el servidor.
    """
    raise NotImplementedError(
        "build_exceptions_sheet: scaffold P2-F (REP-006). Ver plan "
        "docs/superpowers/plans/2026-09-24-p2f-workpaper.md, Task 1."
    )


def _write_header(ws: Worksheet, columnas: list[ColumnaExcepciones]) -> int:
    """Escribe la fila de encabezados con estilo SRI. Devuelve la fila
    siguiente (primera fila de datos). Scaffold."""
    raise NotImplementedError


def _write_total_row(
    ws: Worksheet, row: int, resumen: "ResumenExcepciones",
    columnas: list[ColumnaExcepciones],
) -> None:
    """Escribe la fila TOTAL (negrita, borde doble, fondo azul claro) a
    partir de los agregados del motor. Scaffold."""
    raise NotImplementedError
