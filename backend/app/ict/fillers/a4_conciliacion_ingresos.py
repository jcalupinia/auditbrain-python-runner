"""Filler for CONCILIACIÓN INGRESOS A4 sheet (2 cuadros).

Strategy:
  Cuadro 1 — writes up to 10 rows of detalle de ingresos exentos from Libro Mayor.
    Input: anexo_data["mayor_exentos"] = list of movimiento dicts
           {codigo, nombre, saldo, debe, haber, tipo}
    Writes columns A (identificacion=nombre), C (codigo), D (nombre), G (saldo)
    Columns B (casillero), E (descripcion), F (normativa) are manual entry — NOT touched.

  Cuadro 2 — writes F-101 casilleros 804, 805, 812, 1112 to column G.
    Input: anexo_data["f101"] = {casillero_str: float}
    Formula rows (G36 =SUM, G37 =diferencia) are preserved.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a4 import (
    A4_CUADRO1_COLS,
    A4_CUADRO1_RANGE,
    A4_CUADRO2_CASILLEROS,
    A4_CUADRO2_COL,
    A4_HEADER_MAP,
    A4_SHEET,
)
from backend.app.ict.fillers.helpers import filter_balance_by_casilleros, get_casillero_value


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


class A4Filler:
    anexo_code = "A4"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the CONCILIACIÓN INGRESOS A4 sheet.

        Expected keys in anexo_data:
            f101          — dict of casillero_str → float  (from parse_f101)
            mayor_exentos — list of movimiento dicts from parse_mayor (optional)
        """
        ws = workbook[A4_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A4_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        # ── Cuadro 1: Detalle de ingresos exentos ────────────────────────
        # Source priority: mayor_exentos (Libro Mayor upload) → balance_mapeado fallback
        movimientos: list[dict] = anexo_data.get("mayor_exentos", []) or []
        balance_mapeado: list[dict] = anexo_data.get("balance_mapeado", []) or []
        start_row, end_row = A4_CUADRO1_RANGE
        max_rows = end_row - start_row + 1

        # If no mayor_exentos, try populating from balance_mapeado items
        # with casilleros 804, 805, 812, 1112
        if not movimientos and balance_mapeado:
            balance_items = filter_balance_by_casilleros(
                balance_mapeado, {"804", "805", "812", "1112"}
            )
            # Convert balance items to movimiento-like dicts for uniform handling
            movimientos = [
                {
                    "codigo": item.get("codigo", ""),
                    "nombre": item.get("descripcion", ""),
                    "saldo": item.get("saldo", 0.0),
                    "casillero_sri": item.get("casillero_sri", ""),
                }
                for item in balance_items
            ]

        if movimientos:
            for i, mov in enumerate(movimientos[:max_rows]):
                row = start_row + i
                codigo = mov.get("codigo", "")
                nombre = mov.get("nombre", "")
                saldo = mov.get("saldo", 0.0)
                casillero_num = mov.get("casillero_sri", "")

                # Col A: identificación (usamos nombre de cuenta como descripción breve)
                col_a = A4_CUADRO1_COLS["identificacion"]
                if nombre and _safe_set(ws, f"{col_a}{row}", nombre):
                    filled += 1

                # Col B: número de casillero (from balance_mapeado items)
                col_b = A4_CUADRO1_COLS["casillero"]
                if casillero_num and _safe_set(ws, f"{col_b}{row}", casillero_num):
                    filled += 1

                # Col C: código de cuenta contable
                col_c = A4_CUADRO1_COLS["codigo_cuenta"]
                if codigo and _safe_set(ws, f"{col_c}{row}", codigo):
                    filled += 1

                # Col D: nombre de la cuenta contable
                col_d = A4_CUADRO1_COLS["nombre_cuenta"]
                if nombre and _safe_set(ws, f"{col_d}{row}", nombre):
                    filled += 1

                # Col G: valor total en libros
                col_g = A4_CUADRO1_COLS["valor"]
                if _safe_set(ws, f"{col_g}{row}", saldo):
                    filled += 1

            if len(movimientos) > max_rows:
                warnings.append(
                    f"A4 Cuadro 1: se truncaron {len(movimientos) - max_rows} cuentas "
                    f"(máximo {max_rows} filas disponibles)"
                )
        else:
            warnings.append(
                "A4 Cuadro 1: sin datos de ingresos exentos. "
                "Sube el Libro Mayor o el Balance Mapeado para poblar el detalle."
            )

        # ── Cuadro 2: Conciliación F-101 casilleros ───────────────────────
        # Uses get_casillero_value: F-101 preferred, balance_mapeado fallback
        any_cuadro2 = False
        for row, casillero in A4_CUADRO2_CASILLEROS.items():
            val = get_casillero_value(anexo_data, casillero)
            if val is not None:
                if _safe_set(ws, f"{A4_CUADRO2_COL}{row}", val):
                    filled += 1
                    any_cuadro2 = True
            else:
                warnings.append(
                    f"A4 Cuadro 2 fila {row}: casillero {casillero} no encontrado en F-101 "
                    "ni en Balance Mapeado"
                )

        if not any_cuadro2:
            warnings.append(
                "A4 Cuadro 2: sin datos de casilleros 804, 805, 812, 1112. "
                "Sube el F-101 o el Balance Mapeado."
            )

        return {"filled_cells": filled, "warnings": warnings}
