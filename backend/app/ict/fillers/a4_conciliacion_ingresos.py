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

        # ── Cuadro 1: Detalle de ingresos exentos (Libro Mayor) ───────────
        movimientos: list[dict] = anexo_data.get("mayor_exentos", []) or []
        start_row, end_row = A4_CUADRO1_RANGE
        max_rows = end_row - start_row + 1

        if movimientos:
            for i, mov in enumerate(movimientos[:max_rows]):
                row = start_row + i
                codigo = mov.get("codigo", "")
                nombre = mov.get("nombre", "")
                saldo = mov.get("saldo", 0.0)

                # Col A: identificación (usamos nombre de cuenta como descripción breve)
                col_a = A4_CUADRO1_COLS["identificacion"]
                if nombre and _safe_set(ws, f"{col_a}{row}", nombre):
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
                "A4 Cuadro 1: sin datos de Libro Mayor (mayor_exentos vacío). "
                "Sube el Libro Mayor para poblar el detalle."
            )

        # ── Cuadro 2: Conciliación F-101 casilleros ───────────────────────
        f101: dict[str, float] = anexo_data.get("f101", {}) or {}

        if not f101:
            warnings.append(
                "A4 Cuadro 2: sin datos de F-101 (casilleros 804, 805, 812, 1112 no cargados)"
            )
        else:
            for row, casillero in A4_CUADRO2_CASILLEROS.items():
                val = f101.get(casillero)
                if val is not None:
                    if _safe_set(ws, f"{A4_CUADRO2_COL}{row}", val):
                        filled += 1
                else:
                    warnings.append(
                        f"A4 Cuadro 2 fila {row}: casillero {casillero} no encontrado en F-101"
                    )

        return {"filled_cells": filled, "warnings": warnings}
