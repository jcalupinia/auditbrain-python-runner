"""Filler for INVENTARIOS A9 sheet.

REFACTOR REFERENCIAL (CLAUDE.md):
  Columna C (Saldo SRI/Balance) → fórmula referencial:
    F-101 disponible    → ='DATOS F-101'!C<row>
    Solo balance        → suma de cuentas con casillero coincidente
  Columnas D-G (forma valoración, cantidad, costo) provienen del Kardex
  subido por el cliente y se escriben literales (texto/cantidades).
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a9 import A9_CASILLEROS, A9_HEADER_MAP, A9_SHEET
from backend.app.ict.fillers.base import safe_set, safe_set_formula
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_casillero_ref,
    balance_rows_for_casillero,
    balance_sum_ref,
    balance_codigo_ref,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A9",
                    origen="A9 Inventarios (F-101 + Balance + Kardex)")


class A9Filler:
    anexo_code = "A9"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A9_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, _f104, balance_lookup = lookups_from_context(anexo_data)

        for cell_addr, key in A9_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        kardex_items = anexo_data.get("kardex_items", [])

        for row_idx, casillero in A9_CASILLEROS.items():
            # Col C: saldo referencial (F-101 → Balance)
            ok = set_casillero_ref(
                ws, f"C{row_idx}",
                casillero=str(casillero),
                anexo_data=anexo_data,
                f101_lookup=f101_lookup,
                balance_lookup=balance_lookup,
                anexo="A9",
                origen_prefix=f"A9 fila {row_idx} · ",
            )
            if ok:
                filled += 1
            else:
                warnings.append(
                    f"Casillero F-101 {casillero} no detectado en F-101 ni Balance Mapeado"
                )

            # ── Información contable (col D código, col G costo total) ─────
            rows_bal = balance_rows_for_casillero(
                anexo_data, str(casillero), balance_lookup
            )
            # Col G (Costo Total): ABS para saldos de inventario; 7037 (ajustes)
            # mantiene signo (validado contra PROPHAR — ver spec).
            take_abs = str(casillero) != "7037"
            g_formula = balance_sum_ref(rows_bal, column="D", take_abs=take_abs)
            if g_formula and safe_set_formula(
                ws, f"G{row_idx}", g_formula, anexo="A9", casillero=str(casillero),
                origen=f"A9 fila {row_idx} · Costo Total (balance, "
                       f"{'ABS' if take_abs else 'signo directo'})",
            ):
                filled += 1

            # Cols D-G: del Kardex (literal)
            if kardex_items:
                first_match = kardex_items[0]
                if _safe_set(ws, f"D{row_idx}", first_match.get("codigo_cuenta", "")):
                    filled += 1
                if _safe_set(ws, f"E{row_idx}", first_match.get("forma_valoracion", "PROMEDIO")):
                    filled += 1
                if _safe_set(ws, f"F{row_idx}", first_match.get("cantidad", "")):
                    filled += 1
                if _safe_set(ws, f"G{row_idx}", first_match.get("costo_total", 0.0)):
                    filled += 1
            elif ok:
                warnings.append(
                    f"Casillero {casillero} tiene valor pero no se subió Kardex"
                )

        return {"filled_cells": filled, "warnings": warnings}
