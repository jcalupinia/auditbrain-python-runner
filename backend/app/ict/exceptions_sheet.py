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
from decimal import Decimal, InvalidOperation
from typing import Literal, TypedDict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from backend.app.ict.fillers.source_data_sheets import _safe_text

SHEET_NAME = "EXCEPCIONES"

#: Formato numérico estándar para importes (CLAUDE.md).
NUM_FMT = "#,##0.00"

# ---- Estilos locales (SRI-like) ----
_THIN = Side(border_style="thin", color="A0A0A0")
_DOUBLE = Side(border_style="double", color="000000")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_TOTAL_BORDER = Border(left=_THIN, right=_THIN, top=_DOUBLE, bottom=_DOUBLE)
_FONT_TITLE = Font(name="Calibri", size=14, bold=True, color="FFFFFF")
_FONT_SUB = Font(name="Calibri", size=9, italic=True, color="404040")
_FONT_HEADER = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
_FONT_DATA = Font(name="Calibri", size=9)
_FONT_MONO = Font(name="Consolas", size=9)
_FONT_TOTAL = Font(name="Calibri", size=10, bold=True)
_FILL_TITLE = PatternFill("solid", fgColor="0A2342")
_FILL_HEADER = PatternFill("solid", fgColor="2D5F8B")
_FILL_TOTAL = PatternFill("solid", fgColor="E8F1F8")

#: Colores por severidad (fondo de la celda).
_SEVERIDAD_FILL = {
    "P0": PatternFill("solid", fgColor="F4B6B6"),   # rojo claro
    "P1": PatternFill("solid", fgColor="F9D9A8"),   # naranja claro
    "P2": PatternFill("solid", fgColor="FBEFB2"),   # amarillo claro
}


def _parse_decimal(value) -> Decimal | None:
    """Convierte un valor a Decimal(str) sin usar float. None si no aplica."""
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _ensure_sheet(wb: Workbook, name: str) -> Worksheet:
    """Crea la hoja `name`, reemplazándola si ya existe."""
    if name in wb.sheetnames:
        del wb[name]
    return wb.create_sheet(title=name)


def _write_brand_header(ws: Worksheet, session_data: dict | None, span: int) -> int:
    """Escribe la cabecera de marca + datos del encargo. Devuelve la fila
    siguiente disponible."""
    span = max(span, 1)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=span)
    c = ws.cell(1, 1, value=_safe_text("AUDIT-IA · AuditConsulting Auditores Cía. Ltda."))
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
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=span)
    c2 = ws.cell(2, 1, value=_safe_text(encargo) if encargo else _safe_text("(encargo sin identificar)"))
    c2.font = _FONT_SUB
    c2.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    return 4

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

    Returns:
        ExceptionsSheetResult con conteos para verificación empírica.
    """
    columnas: list[ColumnaExcepciones] = list(espec.get("columnas") or [])
    filas: list[dict] = list(espec.get("filas") or [])
    resumen: ResumenExcepciones = espec.get("resumen") or {}  # type: ignore[assignment]
    advertencias: list[str] = []

    span = max(len(columnas), 3)
    ws = _ensure_sheet(wb, SHEET_NAME)
    row = _write_brand_header(ws, session_data, span)

    # Subtítulo con la procedencia del motor.
    titulo = espec.get("titulo") or "Excepciones detectadas por el motor de auditoría"
    ws.cell(row, 1, value=_safe_text(titulo)).font = Font(name="Calibri", size=11, bold=True)
    row += 1
    meta = " · ".join(
        p for p in (
            f"Motor {espec['engine_version']}" if espec.get("engine_version") else "",
            f"Generado {espec['generado_en']}" if espec.get("generado_en") else "",
            f"Corrida {espec['run_id']}" if espec.get("run_id") else "",
        ) if p
    )
    if meta:
        ws.cell(row, 1, value=_safe_text(meta)).font = _FONT_SUB
        row += 1
    row += 1

    if not columnas:
        # Sin definición de columnas: no hay tabla que armar.
        ws.cell(row, 1, value=_safe_text("Sin definición de columnas en la especificación del motor."))
        advertencias.append("La especificación no trae 'columnas'.")
        return ExceptionsSheetResult(
            filas_escritas=0,
            monto_total=str(resumen.get("monto_total", "0.00")),
            por_severidad=dict(resumen.get("por_severidad", {})),
            advertencias=advertencias,
        )

    header_row = _write_header(ws, columnas, start_row=row)
    data_start = header_row

    if not filas:
        ws.merge_cells(start_row=data_start, start_column=1,
                       end_row=data_start, end_column=len(columnas))
        c = ws.cell(data_start, 1, value=_safe_text("Sin excepciones para este ejercicio."))
        c.font = _FONT_DATA
        c.alignment = Alignment(horizontal="left", vertical="center")
        total_row = data_start + 1
    else:
        r = data_start
        for fila in filas:
            for ci, col in enumerate(columnas, start=1):
                _write_cell(ws, r, ci, fila.get(col["clave"]), col["tipo"])
            r += 1
        total_row = r

    _write_total_row(ws, total_row, resumen, columnas)

    # AutoFilter + freeze sobre la tabla de datos.
    last_col = get_column_letter(len(columnas))
    ws.auto_filter.ref = f"A{header_row - 1}:{last_col}{max(total_row - 1, header_row)}"
    ws.freeze_panes = ws.cell(header_row, 1)

    _apply_widths(ws, columnas)

    return ExceptionsSheetResult(
        filas_escritas=len(filas),
        monto_total=str(resumen.get("monto_total", "0.00")),
        por_severidad=dict(resumen.get("por_severidad", {})),
        advertencias=advertencias,
    )


def _write_cell(ws: Worksheet, row: int, col: int, value, tipo: str) -> None:
    """Escribe una celda de datos aplicando formato según `tipo`."""
    cell = ws.cell(row, col)
    cell.border = _BORDER
    if tipo == "monto":
        dec = _parse_decimal(value)
        cell.value = dec if dec is not None else _safe_text(value)
        if dec is not None:
            cell.number_format = NUM_FMT
        cell.font = _FONT_DATA
        cell.alignment = Alignment(horizontal="right", vertical="center")
    elif tipo == "entero":
        try:
            cell.value = int(value) if value is not None and value != "" else None
        except (TypeError, ValueError):
            cell.value = _safe_text(value)
        cell.font = _FONT_DATA
        cell.alignment = Alignment(horizontal="right", vertical="center")
    elif tipo == "hash":
        cell.value = _safe_text(value)
        cell.font = _FONT_MONO
        cell.alignment = Alignment(horizontal="left", vertical="center")
    elif tipo == "nia":
        cell.value = _safe_text(value)
        cell.font = _FONT_DATA
        cell.alignment = Alignment(horizontal="center", vertical="center")
    elif tipo == "severidad":
        sev = str(value or "").strip().upper()
        cell.value = _safe_text(sev)
        cell.font = _FONT_DATA
        cell.alignment = Alignment(horizontal="center", vertical="center")
        fill = _SEVERIDAD_FILL.get(sev)
        if fill is not None:
            cell.fill = fill
    else:  # texto, estado, fecha
        cell.value = _safe_text(value)
        cell.font = _FONT_DATA
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)


def _write_header(ws: Worksheet, columnas: list[ColumnaExcepciones], *, start_row: int) -> int:
    """Escribe la fila de encabezados con estilo SRI. Devuelve la fila
    siguiente (primera fila de datos)."""
    for i, col in enumerate(columnas, start=1):
        c = ws.cell(start_row, i, value=_safe_text(col["titulo"]))
        c.font = _FONT_HEADER
        c.fill = _FILL_HEADER
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = _BORDER
    ws.row_dimensions[start_row].height = 22
    return start_row + 1


def _write_total_row(
    ws: Worksheet, row: int, resumen: "ResumenExcepciones",
    columnas: list[ColumnaExcepciones],
) -> None:
    """Escribe la fila TOTAL (negrita, borde doble, fondo azul claro) a
    partir de los agregados del motor."""
    total_exc = resumen.get("total_excepciones", 0)
    label = f"TOTAL ({total_exc} excepción/es)"
    for i in range(1, len(columnas) + 1):
        c = ws.cell(row, i)
        c.border = _TOTAL_BORDER
        c.fill = _FILL_TOTAL
        c.font = _FONT_TOTAL
    c0 = ws.cell(row, 1, value=_safe_text(label))
    c0.alignment = Alignment(horizontal="left", vertical="center")
    c0.font = _FONT_TOTAL
    c0.fill = _FILL_TOTAL
    c0.border = _TOTAL_BORDER

    monto_total = _parse_decimal(resumen.get("monto_total"))
    for i, col in enumerate(columnas, start=1):
        if col["tipo"] == "monto" and monto_total is not None:
            c = ws.cell(row, i, value=monto_total)
            c.number_format = NUM_FMT
            c.alignment = Alignment(horizontal="right", vertical="center")
            c.font = _FONT_TOTAL
            c.fill = _FILL_TOTAL
            c.border = _TOTAL_BORDER
            break


def _apply_widths(ws: Worksheet, columnas: list[ColumnaExcepciones]) -> None:
    """Anchos de columna explícitos según el tipo de cada columna."""
    ancho_por_tipo = {
        "texto": 40, "estado": 16, "monto": 16, "fecha": 18,
        "hash": 20, "nia": 14, "severidad": 12, "entero": 12,
    }
    for i, col in enumerate(columnas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho_por_tipo.get(col["tipo"], 20)
