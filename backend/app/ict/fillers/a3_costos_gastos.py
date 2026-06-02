"""Filler for COSTOS  GASTOS A3 sheet (9 bloques de límites de deducibilidad).

REFACTOR REFERENCIAL (CLAUDE.md):
  Todas las celdas numéricas se escriben como FÓRMULAS que referencian
  'DATOS F-101'!C<row>. Para casilleros compuestos (ej. "7205+7206")
  se construye una fórmula tipo:
      ='DATOS F-101'!C123+'DATOS F-101'!C124

  Si el casillero no está en F-101, intenta el fallback al Balance Mapeado
  con suma de cuentas cuyo casillero_sri coincida.

  Las celdas de porcentaje (0.02, 0.03, 0.05, 0.20), de total y de
  diferencia son fórmulas del template — protegidas por safe_set_formula
  (no se tocan accidentalmente).
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a3 import (
    A3_BLOQUES,
    A3_COMPOUND_CASILLEROS,
    A3_HEADER_MAP,
    A3_SHEET,
    MANUAL_PREFIX,
)
from backend.app.ict.fillers.base import safe_set, safe_set_formula
from backend.app.ict.fillers.helpers import get_casillero_value
from backend.app.ict.fillers.referential_helpers import (
    SHEET_F101,
    balance_rows_for_casillero,
    balance_sum_ref,
    f101_ref,
    lookups_from_context,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A3",
                    origen="A3 Costos y Gastos (F-101)")


def _build_compound_f101_formula(parts: list[str], f101_lookup: dict) -> str | None:
    """Construye fórmula que suma varias referencias F-101 simples.
    Si NINGUNA parte está en el lookup → None. Si algunas están y otras no,
    devuelve fórmula solo con las disponibles."""
    refs = []
    for cas in parts:
        row = f101_lookup.get(str(cas))
        if row is not None:
            refs.append(f"'{SHEET_F101}'!C{row}")
    if not refs:
        return None
    return "=" + "+".join(refs)


def _resolve_casillero_formula(
    casillero_key: str,
    f101_lookup: dict,
    balance_lookup: list,
    anexo_data: dict,
) -> tuple[str | None, str]:
    """Resuelve un casillero (simple o compuesto) a (formula, origen_label).

    Returns:
        formula: cadena `=...` lista para safe_set_formula, o None.
        origen_label: descripción humana para el trace.
    """
    # Compound F-101 (suma de varios casilleros)
    if casillero_key in A3_COMPOUND_CASILLEROS:
        parts = A3_COMPOUND_CASILLEROS[casillero_key]
        formula = _build_compound_f101_formula(parts, f101_lookup)
        if formula:
            return formula, f"F-101 casilleros {'+'.join(parts)}"
        # Fallback: sumar balance de todas las partes
        all_rows: list[int] = []
        for p in parts:
            all_rows.extend(balance_rows_for_casillero(anexo_data, p, balance_lookup))
        bf = balance_sum_ref(all_rows)
        if bf:
            return bf, f"Balance Mapeado · suma de {len(all_rows)} cuentas ({'+'.join(parts)})"
        return None, ""

    # Casillero simple
    formula = f101_ref(casillero_key, f101_lookup)
    if formula:
        return formula, f"F-101 casillero {casillero_key}"
    rows = balance_rows_for_casillero(anexo_data, casillero_key, balance_lookup)
    bf = balance_sum_ref(rows)
    if bf:
        return bf, f"Balance Mapeado · {len(rows)} cuentas con cas {casillero_key}"
    return None, ""


class A3Filler:
    anexo_code = "A3"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A3_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, _f104, balance_lookup = lookups_from_context(anexo_data)

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A3_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        # ── Bloques ─────────────────────────────────────────────────────────
        for bloque_name, rows in A3_BLOQUES:
            for (row, casillero_key, col) in rows:
                if casillero_key.startswith(MANUAL_PREFIX):
                    continue

                formula, origen = _resolve_casillero_formula(
                    casillero_key, f101_lookup, balance_lookup, anexo_data,
                )

                if formula:
                    if safe_set_formula(
                        ws, f"{col}{row}", formula,
                        anexo="A3", casillero=casillero_key,
                        origen=f"A3 {bloque_name} · {origen}",
                    ):
                        filled += 1
                    continue

                # Fallback a valor literal (tests directos sin DATOS sheets)
                if casillero_key in A3_COMPOUND_CASILLEROS:
                    parts = A3_COMPOUND_CASILLEROS[casillero_key]
                    found = any(get_casillero_value(anexo_data, p) is not None for p in parts)
                    if found:
                        total = sum(
                            get_casillero_value(anexo_data, p, default=0.0) or 0.0
                            for p in parts
                        )
                        if _safe_set(ws, f"{col}{row}", total):
                            filled += 1
                            continue
                else:
                    val = get_casillero_value(anexo_data, casillero_key)
                    if val is not None:
                        if _safe_set(ws, f"{col}{row}", val):
                            filled += 1
                            continue

                warnings.append(
                    f"A3 bloque '{bloque_name}' fila {row}: "
                    f"casillero '{casillero_key}' no encontrado en F-101 ni Balance"
                )

        return {"filled_cells": filled, "warnings": warnings}
