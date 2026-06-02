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
from backend.app.ict.fillers.helpers import filter_balance_by_casilleros, get_casillero_value


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Wrapper local: delega al central que protege fórmulas + registra trace."""
    from backend.app.ict.fillers.base import safe_set
    return safe_set(ws, cell_addr, value, anexo="A5",
                    origen="A5 Conciliación C/G (F-101 + F-103 + Balance)")


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

        mayor_nd: list[dict] = anexo_data.get("mayor_no_deducibles", []) or []
        balance_mapeado: list[dict] = anexo_data.get("balance_mapeado", []) or []

        # ── Cuadro A: Detalle gastos no deducibles ────────────────────────
        # Source priority: mayor_no_deducibles (Libro Mayor) → balance_mapeado fallback
        # Balance casilleros 806 (no ded locales) y 807 (no ded exterior)
        start_a, end_a = A5_CUADRO_A_RANGE
        max_rows_a = end_a - start_a + 1

        if not mayor_nd and balance_mapeado:
            balance_items = filter_balance_by_casilleros(balance_mapeado, {"806", "807"})
            mayor_nd = [
                {
                    "codigo": item.get("codigo", ""),
                    "nombre": item.get("descripcion", ""),
                    "saldo": item.get("saldo", 0.0),
                }
                for item in balance_items
            ]

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
                "A5: sin gastos no deducibles (mayor_no_deducibles y balance_mapeado 806/807 vacíos). "
                "Sube el Libro Mayor o el Balance Mapeado para poblar el Cuadro A."
            )

        # ── Cuadro B: Prorrateo — base inputs (casilleros 6999 y 7999) ───
        # Template formula G42 calcula el % automáticamente (G33/G41).
        # Template formula G51 calcula el ajuste (G42*G50).
        # El filler solo escribe los totales declarados en filas ancla.
        # Usa get_casillero_value: F-101 primero, balance_mapeado fallback.
        any_cuadro_b = False
        for row, (source, casillero) in A5_CUADRO_B_MAP.items():
            if source == "f101":
                val = get_casillero_value(anexo_data, casillero)
                if val is not None and _safe_set(ws, f"G{row}", val):
                    filled += 1
                    any_cuadro_b = True

        if not any_cuadro_b:
            warnings.append(
                "A5 Cuadro B: sin datos de casilleros 6999, 7999 "
                "(no encontrados en F-101 ni Balance Mapeado)"
            )

        # ── Cuadro C: Participación trabajadores (casilleros 804, 805, 808) ─
        # Usa get_casillero_value: F-101 primero, balance_mapeado fallback.
        for row, casillero in A5_CUADRO_C_MAP.items():
            val = get_casillero_value(anexo_data, casillero)
            if val is not None and _safe_set(ws, f"H{row}", val):
                filled += 1

        # ── Cuadro D: Conciliación gastos no deducibles ──────────────────
        # Usa get_casillero_value: F-101 primero, balance_mapeado fallback.
        for row, casillero in A5_CUADRO_D_MAP.items():
            val = get_casillero_value(anexo_data, casillero)
            if val is not None and _safe_set(ws, f"H{row}", val):
                filled += 1

        # ── Cuadro E: Reversos (gastos no deducibles con signo negativo) ─
        # MVP: se deja en blanco. Los reversos requieren análisis manual
        # o un parser especializado de ajustes de auditoría.

        return {"filled_cells": filled, "warnings": warnings}
