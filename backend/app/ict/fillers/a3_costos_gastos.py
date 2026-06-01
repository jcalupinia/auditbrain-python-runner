"""Filler for COSTOS  GASTOS A3 sheet (9 bloques de límites de deducibilidad).

Strategy:
  For each bloque in A3_BLOQUES:
    - Skip MANUAL_ keys (require client manual entry)
    - Resolve compound casilleros (e.g. "7205+7206") by summing individual values
    - Write the resolved value to column F or G (per cell map)
    - All percentage, total, and difference cells are template formulas — NOT touched

All percentages (0.02, 0.03, 0.05, 0.20) are pre-set in the template as default
values; the filler only overwrites the "Valor" (input) cells.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a3 import (
    A3_BLOQUES,
    A3_COMPOUND_CASILLEROS,
    A3_HEADER_MAP,
    A3_SHEET,
    MANUAL_PREFIX,
)
from backend.app.ict.fillers.helpers import get_casillero_value


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


def _resolve_casillero(casillero_key: str, anexo_data: dict) -> tuple[float | None, bool]:
    """Resolve a casillero key to its numeric value.

    Tries F-101 first; falls back to aggregated balance_mapeado.

    Returns (value, found):
        value — float sum (0.0 for missing individual parts of compound casilleros)
        found — True if at least one individual casillero was present
    """
    if casillero_key in A3_COMPOUND_CASILLEROS:
        parts = A3_COMPOUND_CASILLEROS[casillero_key]
        found = any(get_casillero_value(anexo_data, str(p)) is not None for p in parts)
        total = sum(get_casillero_value(anexo_data, str(p), default=0.0) or 0.0 for p in parts)
        return total, found
    else:
        val = get_casillero_value(anexo_data, str(casillero_key))
        return val, val is not None


class A3Filler:
    anexo_code = "A3"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the COSTOS  GASTOS A3 sheet.

        Expected keys in anexo_data:
            f101 — dict of casillero_str → float  (from parse_f101)
        """
        ws = workbook[A3_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A3_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        # ── Bloques ─────────────────────────────────────────────────────────
        for bloque_name, rows in A3_BLOQUES:
            for (row, casillero_key, col) in rows:
                # Skip manual-entry cells
                if casillero_key.startswith(MANUAL_PREFIX):
                    continue

                val, found = _resolve_casillero(casillero_key, anexo_data)

                if not found:
                    warnings.append(
                        f"A3 bloque '{bloque_name}' fila {row}: "
                        f"casillero '{casillero_key}' no encontrado en F-101"
                    )
                    continue

                if val is not None:
                    if _safe_set(ws, f"{col}{row}", val):
                        filled += 1

        return {"filled_cells": filled, "warnings": warnings}
