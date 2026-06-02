"""Filler for CRÉDITO TRIBUTARIO A7 sheet (2 matrices multi-año).

REFACTOR REFERENCIAL (CLAUDE.md):
  Las hojas DATOS F-101/F-103/F-104 contienen SOLO el período del
  ejercicio actual. Para años anteriores de la matriz, el valor proviene
  de f101_multiyear/f108_multiyear (multi-PDF subido por el cliente)
  y se escribe como literal.

  Para el año actual (último año de cada matriz), cuando el casillero
  proviene del F-101 actualmente subido, se escribe como referencia
  ='DATOS F-101'!C<row> con fallback al Balance.

  Matriz 1 (IR): casilleros 850/851 — año actual referencial.
  Matriz 2 (ISD): año actual referencial al casillero 999/b_1 si existe.

Strategy:
  Matriz 1 (IR) — reads anexo_data["f101_multiyear"] = {year_str: {campo: val}}
  Matriz 2 (ISD) — reads anexo_data["f108_multiyear"] = {year_str: {campo: val}}
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a7 import (
    A7_HEADER_MAP,
    A7_MATRIZ_IR,
    A7_MATRIZ_ISD,
    A7_SHEET,
)
from backend.app.ict.fillers.base import safe_set
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_casillero_ref,
)

_IR_FORMULA_COLS = {"H", "Q", "S"}
_ISD_FORMULA_COLS = {"H", "N", "U"}


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A7",
                    origen="A7 Crédito Tributario (F-101 + F-103)")


def _coerce_float(val) -> float | None:
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
        ws = workbook[A7_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, _f104, balance_lookup = lookups_from_context(anexo_data)

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A7_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        # ── Matriz 1: Crédito IR por año ──────────────────────────────────
        f101_multi: dict = anexo_data.get("f101_multiyear", {}) or {}
        ir_cols = A7_MATRIZ_IR["columns"]
        latest_year = max(A7_MATRIZ_IR["years"])

        for year in A7_MATRIZ_IR["years"]:
            row = A7_MATRIZ_IR["rows"].get(year)
            if row is None:
                continue
            year_data: dict = f101_multi.get(str(year)) or f101_multi.get(year) or {}

            for col_key, col_letter in ir_cols.items():
                if col_letter in _IR_FORMULA_COLS:
                    continue

                # CASO ESPECIAL: valor_generado del año actual → referencial F-101
                if col_key == "valor_generado" and year == latest_year:
                    # Intenta 850 luego 851
                    written = False
                    for cas in ("850", "851"):
                        if set_casillero_ref(
                            ws, f"{col_letter}{row}",
                            casillero=cas,
                            anexo_data=anexo_data,
                            f101_lookup=f101_lookup,
                            balance_lookup=balance_lookup,
                            anexo="A7",
                            origen_prefix=f"A7 Matriz IR año {year} · ",
                        ):
                            filled += 1
                            written = True
                            break
                    if written:
                        continue
                    # fallback al dict multi-año literal
                    val = year_data.get("valor_generado") or year_data.get("850") or year_data.get("851")
                    if val is not None and _safe_set(ws, f"{col_letter}{row}", val):
                        filled += 1
                    continue

                if not year_data:
                    continue

                val = None
                if col_key == "valor_generado":
                    val = year_data.get("valor_generado") or year_data.get("850") or year_data.get("851")
                else:
                    val = year_data.get(col_key)

                if val is None:
                    continue

                text_cols = {"no_resolucion", "registrado_costo", "normativa", "observaciones"}
                fval = _coerce_float(val) if col_key not in text_cols else val
                if fval is None and col_key not in text_cols:
                    continue

                if _safe_set(ws, f"{col_letter}{row}", fval if fval is not None else val):
                    filled += 1

        if not f101_multi:
            warnings.append(
                "A7 Matriz IR: sin datos multi-año (f101_multiyear vacío)"
            )

        # ── Matriz 2: ISD por año ────────────────────────────────────────
        f108_multi: dict = anexo_data.get("f108_multiyear", {}) or {}
        isd_cols = A7_MATRIZ_ISD["columns"]

        for year in A7_MATRIZ_ISD["years"]:
            row = A7_MATRIZ_ISD["rows"].get(year)
            if row is None:
                continue
            year_data = f108_multi.get(str(year)) or f108_multi.get(year) or {}
            if not year_data:
                continue

            for col_key, col_letter in isd_cols.items():
                if col_letter in _ISD_FORMULA_COLS:
                    continue

                val = None
                if col_key == "total_isd_pagado":
                    val = year_data.get("total_isd_pagado") or year_data.get("999") or year_data.get("b_1")
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
                "A7 Matriz ISD: sin datos multi-año (f108_multiyear vacío)"
            )

        return {"filled_cells": filled, "warnings": warnings}
