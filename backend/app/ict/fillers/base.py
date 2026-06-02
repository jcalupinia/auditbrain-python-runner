"""Filler protocol + helpers for ICT 2025 Excel template manipulation.

Este módulo centraliza:
  - load_template(): carga el template oficial preservando fórmulas y links.
  - safe_set(): escribe en una celda de forma segura. NUNCA sobreescribe
    MergedCells ni fórmulas; opcionalmente registra cada escritura en el
    trace log para que generate_excel pueda producir la hoja
    "📋 Trazabilidad" con el linaje completo origen → destino.
  - reset_trace() / get_trace(): API para gestionar el log entre
    invocaciones de generate_excel.
"""

from __future__ import annotations

from contextvars import ContextVar
from pathlib import Path
from typing import Protocol

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import Cell
from openpyxl.worksheet.merge import MergedCell

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "ict_2025_template.xlsx"


def load_template() -> Workbook:
    """Load the official SRI ICT 2025 template preserving formulas."""
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"ICT template not found at {TEMPLATE_PATH}. "
            "Copy the official SRI template here before running ICT generation."
        )
    return load_workbook(TEMPLATE_PATH, data_only=False, keep_links=True)


# ---------------------------------------------------------------------------
# Trace log — registro de origen→destino para la hoja "📋 Trazabilidad"
# Usamos ContextVar para que sea seguro en concurrencia (cada request tiene
# su propio trace) y para que los fillers no tengan que recibir un parámetro.
# ---------------------------------------------------------------------------

_TRACE: ContextVar[list[dict] | None] = ContextVar("_ict_trace", default=None)


def reset_trace() -> None:
    """Inicia un nuevo trace log para la generación actual."""
    _TRACE.set([])


def get_trace() -> list[dict]:
    """Devuelve el trace acumulado (lista de dicts) o vacío si no hay sesión."""
    return _TRACE.get() or []


def _record(anexo: str | None, casillero: str | None, sheet: str,
            cell_addr: str, value, origen: str | None, status: str) -> None:
    """Append a trace entry — silently no-op if no active trace."""
    trace = _TRACE.get()
    if trace is None:
        return
    trace.append({
        "anexo": anexo or "",
        "casillero": str(casillero or ""),
        "sheet": sheet,
        "cell": cell_addr,
        "origen": origen or "",
        "valor": value,
        "status": status,  # "written" | "skipped_formula" | "skipped_merged"
    })


def safe_set_formula(
    ws,
    cell_addr: str,
    formula: str,
    *,
    anexo: str | None = None,
    casillero: str | None = None,
    origen: str | None = None,
) -> bool:
    """Escribe una FÓRMULA en una celda, sobreescribiendo cualquier valor
    o fórmula anterior. Úsalo cuando el filler intencionalmente está
    actualizando una fórmula calculada (p. ej. ``=SUM(F13:F25)-C13`` que
    reemplaza la fórmula vieja del template ``=F15-C13``).

    NO usa el guard de protección de fórmulas porque la intención es
    explícita. Sigue respetando MergedCells y registra la operación en
    el trace log.
    """
    if not isinstance(formula, str) or not formula.startswith("="):
        raise ValueError(f"safe_set_formula esperaba '=...' pero recibió: {formula!r}")
    try:
        cell = ws[cell_addr]
    except Exception:
        _record(anexo, casillero, ws.title, cell_addr, formula, origen, "error")
        return False
    if isinstance(cell, MergedCell):
        _record(anexo, casillero, ws.title, cell_addr, formula, origen, "skipped_merged")
        return False
    cell.value = formula
    _record(anexo, casillero, ws.title, cell_addr, formula, origen, "written")
    return True


def safe_set(
    ws,
    cell_addr: str,
    value,
    *,
    anexo: str | None = None,
    casillero: str | None = None,
    origen: str | None = None,
) -> bool:
    """Escribe ``value`` en ``ws[cell_addr]`` de forma defensiva.

    Devuelve True si se escribió, False si se omitió por alguna razón
    (MergedCell, fórmula, o error). En todos los casos registra la
    operación en el trace log si está activo, para auditoría.

    Reglas de protección:
      1. Si la celda es MergedCell → skip (escribir lanzaría AttributeError).
      2. Si la celda tiene una fórmula (cell.data_type == "f" o value que
         empieza con "=") → skip. Esto preserva 100% las fórmulas del
         template oficial del SRI, incluso si el cell_map de un filler
         apunta accidentalmente a una celda calculada.

    Args:
        ws: Worksheet de openpyxl.
        cell_addr: dirección estilo "A1", "C13".
        value: valor a escribir (str, int, float).
        anexo: código del anexo (A1..A9, INDICE) para trazabilidad.
        casillero: número del casillero SRI de origen (opcional).
        origen: descripción humana del origen ("F-101 página 1",
            "Balance Mapeado fila 39", etc).
    """
    try:
        cell = ws[cell_addr]
    except Exception:
        _record(anexo, casillero, ws.title, cell_addr, value, origen, "error")
        return False

    # Guard 1: MergedCell
    if isinstance(cell, MergedCell):
        _record(anexo, casillero, ws.title, cell_addr, value, origen, "skipped_merged")
        return False

    # Guard 2: fórmula. data_type "f" o str que empieza con "=".
    existing = cell.value
    is_formula = (
        getattr(cell, "data_type", None) == "f"
        or (isinstance(existing, str) and existing.startswith("="))
    )
    if is_formula:
        _record(anexo, casillero, ws.title, cell_addr, value, origen, "skipped_formula")
        return False

    cell.value = value
    _record(anexo, casillero, ws.title, cell_addr, value, origen, "written")
    return True


def write_trace_sheet(workbook: Workbook) -> None:
    """Añade una hoja '📋 Trazabilidad' al final del workbook con el log.

    Cada escritura exitosa aparece como una fila con: Anexo, Casillero SRI,
    Hoja destino, Celda destino, Origen, Valor, Estado.

    Si el trace está vacío (p. ej. fillers que no usan safe_set) se crea
    igualmente la hoja con encabezados y una nota explicativa.
    """
    trace = get_trace()

    # Evita duplicado si ya existe (regenerar limpio)
    SHEET_NAME = "TRAZABILIDAD"
    if SHEET_NAME in workbook.sheetnames:
        del workbook[SHEET_NAME]

    ws = workbook.create_sheet(SHEET_NAME)

    # Header
    headers = [
        "Anexo", "Casillero SRI", "Hoja destino", "Celda destino",
        "Origen", "Valor", "Estado",
    ]
    for col, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=col, value=h)
        c.font = c.font.copy(bold=True)

    # Filas: solo escrituras EXITOSAS (las "written"). Las skipped sirven
    # como meta-auditoría pero saturarían la hoja al cliente.
    written = [t for t in trace if t.get("status") == "written"]
    for i, entry in enumerate(written, start=2):
        ws.cell(row=i, column=1, value=entry.get("anexo", ""))
        ws.cell(row=i, column=2, value=entry.get("casillero", ""))
        ws.cell(row=i, column=3, value=entry.get("sheet", ""))
        ws.cell(row=i, column=4, value=entry.get("cell", ""))
        ws.cell(row=i, column=5, value=entry.get("origen", ""))
        val = entry.get("valor", "")
        # Excel acepta los tipos primitivos directamente
        ws.cell(row=i, column=6, value=val if (isinstance(val, (int, float, str)) or val is None) else str(val))
        ws.cell(row=i, column=7, value=entry.get("status", ""))

    # Ancho razonable para columnas (no perfecto pero útil)
    widths = [10, 16, 32, 14, 50, 18, 16]
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Si no hay nada, mensaje informativo
    if not written:
        ws.cell(row=2, column=1, value="(sin entradas)")
        ws.cell(row=2, column=5,
                value="Los fillers de este ICT no registraron trazabilidad detallada. "
                      "Mejorar usando safe_set(... origen='...') en cada cell_map.")


class Filler(Protocol):
    """Protocol every anexo filler implements."""

    anexo_code: str

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill cells in the workbook for this anexo's sheet.

        Returns:
            {filled_cells: int, warnings: list[str]}

        IMPORTANT:
        - Only write cells listed in this anexo's cell_map
        - NEVER overwrite cells with formulas (preserve template)
        """
        ...
