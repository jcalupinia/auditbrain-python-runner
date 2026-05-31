"""Filler for CONCILIACIÓN COSTOS Y GASTOS A5 (5 cuadros + prorrateo).

Cuadro A — Detalle gastos no deducibles (hasta 5 filas dinámicas del Libro Mayor).
Cuadro B — Prorrateo: escribe casilleros 6999 y 7999 del F-101 como base de cálculo.
            El porcentaje (G42) y el ajuste (G51) son fórmulas del template; no se tocan.
Cuadro C — Participación trabajadores: escribe casilleros 804, 805, 808 a columna H.
            La participación resultante (H61) es fórmula del template.
Cuadro D — Conciliación: escribe casilleros 806, 807, 808, 809, 813, 1113 a columna H.
            SUM (H72) y diferencia (H73) son fórmulas del template.
Cuadro E — Reversos (gastos no deducibles con signo negativo): MVP vacío.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a5 import (
    A5_CUADRO_A_COLS,
    A5_CUADRO_A_RANGE,
    A5_CUADRO_B_MAP,
    A5_CUADRO_C_MAP,
    A5_CUADRO_D_MAP,
    A5_HEADER_MAP,
    A5_SHEET,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


class A5Filler:
    anexo_code = "A5"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the CONCILIACIÓN COSTOS Y GASTOS A5 sheet.

        Expected keys in anexo_data:
            f101                  — dict casillero_str → float (from parse_f101)
            mayor_no_deducibles   — list of movimiento dicts from parse_mayor (optional)
                                    Each dict: {codigo, nombre, saldo, ...}
        """
        ws = workbook[A5_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A5_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        f101: dict[str, float] = anexo_data.get("f101", {}) or {}
        mayor_nd: list[dict] = anexo_data.get("mayor_no_deducibles", []) or []

        # ── Cuadro A: Detalle gastos no deducibles (Libro Mayor) ─────────
        start_a, end_a = A5_CUADRO_A_RANGE
        max_rows_a = end_a - start_a + 1

        if mayor_nd:
            for i, mov in enumerate(mayor_nd[:max_rows_a]):
                row = start_a + i
                codigo = mov.get("codigo", "")
                nombre = mov.get("nombre", "")
                saldo = mov.get("saldo", 0.0)

                # Col A: identificación (nombre de cuenta como descripción breve)
                col_id = A5_CUADRO_A_COLS["identificacion"]
                if nombre and _safe_set(ws, f"{col_id}{row}", nombre):
                    filled += 1

                # Col C: código de cuenta contable
                col_c = A5_CUADRO_A_COLS["codigo_cuenta"]
                if codigo and _safe_set(ws, f"{col_c}{row}", codigo):
                    filled += 1

                # Col D: nombre de la cuenta contable
                col_d = A5_CUADRO_A_COLS["nombre_cuenta"]
                if nombre and _safe_set(ws, f"{col_d}{row}", nombre):
                    filled += 1

                # Col K: valor total en libros
                col_k = A5_CUADRO_A_COLS["valor"]
                if _safe_set(ws, f"{col_k}{row}", saldo):
                    filled += 1

            if len(mayor_nd) > max_rows_a:
                warnings.append(
                    f"A5 Cuadro A: se truncaron {len(mayor_nd) - max_rows_a} cuentas "
                    f"(máximo {max_rows_a} filas disponibles)"
                )
        else:
            warnings.append(
                "A5: sin libro mayor de cuentas no deducibles (mayor_no_deducibles vacío). "
                "Sube el Libro Mayor de gastos no deducibles para poblar el Cuadro A."
            )

        # ── Cuadro B: Prorrateo — base inputs (casilleros 6999 y 7999) ───
        # Template formula G42 calcula el % automáticamente (G33/G41).
        # Template formula G51 calcula el ajuste (G42*G50).
        # El filler solo escribe los totales declarados en filas ancla.
        if f101:
            for row, (source, casillero) in A5_CUADRO_B_MAP.items():
                if source == "f101":
                    val = f101.get(casillero)
                    if val is not None and _safe_set(ws, f"G{row}", val):
                        filled += 1
        else:
            warnings.append(
                "A5 Cuadro B: sin datos de F-101 (casilleros 6999, 7999 no cargados)"
            )

        # ── Cuadro C: Participación trabajadores (casilleros 804, 805, 808) ─
        for row, casillero in A5_CUADRO_C_MAP.items():
            val = f101.get(casillero)
            if val is not None and _safe_set(ws, f"H{row}", val):
                filled += 1

        # ── Cuadro D: Conciliación gastos no deducibles ──────────────────
        for row, casillero in A5_CUADRO_D_MAP.items():
            val = f101.get(casillero)
            if val is not None and _safe_set(ws, f"H{row}", val):
                filled += 1

        # ── Cuadro E: Reversos (gastos no deducibles con signo negativo) ─
        # MVP: se deja en blanco. Los reversos requieren análisis manual
        # o un parser especializado de ajustes de auditoría.

        return {"filled_cells": filled, "warnings": warnings}
