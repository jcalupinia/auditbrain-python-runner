"""Filler for CRÉDITO TRIBUTARIO A7 sheet (2 matrices multi-año).

Strategy:
  Matriz 1 (IR) — reads anexo_data["f101_multiyear"] = {year_str: {campo: val}}
    For each year (2022, 2023, 2024), writes to the corresponding row.
    "valor_generado" is sourced from key "valor_generado" or fallback "850"/"851"
    in the year's data dict. Other per-year columns (devuelto, utilizado, etc.)
    are read directly by column key from the year dict.
    Formula columns H, Q, S are preserved.

  Matriz 2 (ISD) — reads anexo_data["f108_multiyear"] = {year_str: {campo: val}}
    For each year (2021-2025), writes to the corresponding row.
    "total_isd_pagado" is sourced from key "total_isd_pagado" or "999" or "b_1".
    Formula columns H, N, U are preserved.

Both matrices: any unknown/missing year data is silently skipped (partial fill OK).
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a7 import (
    A7_HEADER_MAP,
    A7_MATRIZ_IR,
    A7_MATRIZ_ISD,
    A7_SHEET,
)
from backend.app.ict.fillers.helpers import get_casillero_value

# Formula columns that must NOT be overwritten
_IR_FORMULA_COLS = {"H", "Q", "S"}
_ISD_FORMULA_COLS = {"H", "N", "U"}


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


def _coerce_float(val) -> float | None:
    """Return float or None for non-numeric."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class A7Filler:
    anexo_code = "A7"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the CRÉDITO TRIBUTARIO A7 sheet.

        Expected keys in anexo_data:
            f101_multiyear  — dict {year_str: {campo: val}}
                              Required campos for Matriz IR:
                                "valor_generado" OR casillero "850"/"851"
                                Optional: "devuelto_2022".."devuelto_2024",
                                          "utilizado_2022".."utilizado_2024",
                                          "no_recuperable", "observaciones"
            f108_multiyear  — dict {year_str: {campo: val}}
                              Required campos for Matriz ISD:
                                "total_isd_pagado" OR "999" OR "b_1"
                                Optional: "costo_gasto_YYYY".."credito_YYYY",
                                          "devuelto_YYYY", "no_sujeto_devolucion"
        """
        ws = workbook[A7_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A7_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        # ── Matriz 1: Crédito IR por año generador ───────────────────────
        f101_multi: dict = anexo_data.get("f101_multiyear", {}) or {}
        ir_cols = A7_MATRIZ_IR["columns"]

        for year in A7_MATRIZ_IR["years"]:
            row = A7_MATRIZ_IR["rows"].get(year)
            if row is None:
                continue

            # Accept year as int or str key
            year_data: dict = (
                f101_multi.get(str(year))
                or f101_multi.get(year)
                or {}
            )
            if not year_data:
                continue

            for col_key, col_letter in ir_cols.items():
                # Skip formula columns
                if col_letter in _IR_FORMULA_COLS:
                    continue

                # Resolve value from year_data
                val = None
                if col_key == "valor_generado":
                    # Try explicit key first, then common casillero aliases
                    val = (
                        year_data.get("valor_generado")
                        or year_data.get("850")
                        or year_data.get("851")
                    )
                    # For the latest year, fall back to balance_mapeado casilleros 850/851
                    if not val and year == max(A7_MATRIZ_IR["years"]):
                        val = (
                            get_casillero_value(anexo_data, "850")
                            or get_casillero_value(anexo_data, "851")
                        )
                else:
                    val = year_data.get(col_key)

                if val is None:
                    continue

                fval = _coerce_float(val) if col_key not in ("no_resolucion", "registrado_costo", "normativa", "observaciones") else val
                if fval is None and col_key not in ("no_resolucion", "registrado_costo", "normativa", "observaciones"):
                    continue

                if _safe_set(ws, f"{col_letter}{row}", fval if fval is not None else val):
                    filled += 1

        if not f101_multi:
            warnings.append(
                "A7 Matriz IR: sin datos multi-año (f101_multiyear vacío). "
                "Sube los F-101 de años anteriores para poblar la matriz."
            )

        # ── Matriz 2: ISD por año de pago ────────────────────────────────
        f108_multi: dict = anexo_data.get("f108_multiyear", {}) or {}
        isd_cols = A7_MATRIZ_ISD["columns"]

        for year in A7_MATRIZ_ISD["years"]:
            row = A7_MATRIZ_ISD["rows"].get(year)
            if row is None:
                continue

            year_data = (
                f108_multi.get(str(year))
                or f108_multi.get(year)
                or {}
            )
            if not year_data:
                continue

            for col_key, col_letter in isd_cols.items():
                # Skip formula columns
                if col_letter in _ISD_FORMULA_COLS:
                    continue

                val = None
                if col_key == "total_isd_pagado":
                    # Try explicit key first, then common aliases
                    val = (
                        year_data.get("total_isd_pagado")
                        or year_data.get("999")
                        or year_data.get("b_1")
                    )
                else:
                    val = year_data.get(col_key)

                if val is None:
                    continue

                text_cols = {"observaciones"}
                fval = _coerce_float(val) if col_key not in text_cols else val
                if fval is None and col_key not in text_cols:
                    continue

                if _safe_set(ws, f"{col_letter}{row}", fval if fval is not None else val):
                    filled += 1

        if not f108_multi:
            warnings.append(
                "A7 Matriz ISD: sin datos multi-año (f108_multiyear vacío). "
                "Sube los formularios F-108 para poblar la matriz ISD."
            )

        return {"filled_cells": filled, "warnings": warnings}
