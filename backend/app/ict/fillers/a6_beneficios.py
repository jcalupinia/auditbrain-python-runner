"""Filler for BENEFICIOS TRIBUTARIOS A6 sheet (3 cuadros).

Cuadro A — Deducciones adicionales:
    • Escribe detalle de cuentas (código, nombre, valor en libros) en filas 17-23.
    • Escribe casillero 810 del F-101 en G25 (total del contribuyente).
    • G26 = -G24+G25 es fórmula del template (diferencia) — no se toca.

Cuadro B — Contratos de inversión vigentes:
    • Escribe filas dinámicas (No. resolución, fecha, monto opcional) en filas 32-38.
    • Campos descriptivos (norma, años, período, tarifa) son entrada manual.

Cuadro C — Exoneraciones / disminución de tarifa IR:
    • Escribe flags (utilizado: Sí/No), montos y resolución por tipo de exoneración.
    • Conceptos (col A) están pre-llenados en el template — no se tocan.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a6 import (
    A6_CUADRO_A_CASILLERO_810_CELL,
    A6_CUADRO_A_COLS,
    A6_CUADRO_A_RANGE,
    A6_CUADRO_B_COLS,
    A6_CUADRO_B_RANGE,
    A6_CUADRO_C_COLS,
    A6_CUADRO_C_ROWS,
    A6_HEADER_MAP,
    A6_SHEET,
)
from backend.app.ict.fillers.helpers import filter_balance_by_casilleros, get_casillero_value


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


class A6Filler:
    anexo_code = "A6"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the BENEFICIOS TRIBUTARIOS A6 sheet.

        Expected keys in anexo_data:
            f101                — dict casillero_str → float (from parse_f101)
            deducciones_detail  — list of dicts {codigo_cuenta, nombre_cuenta, valor_libros}
                                  (optional; populates Cuadro A detail rows)
            contratos_inversion — list of dicts {no_resolucion, fecha, monto_incentivo}
                                  (optional; populates Cuadro B)
            exoneraciones       — dict keyed by tipo (see A6_CUADRO_C_ROWS)
                                  Each value: dict {utilizado, monto_incentivo, no_resolucion,
                                                     periodo_inicio}
                                  (optional; populates Cuadro C)
        """
        ws = workbook[A6_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A6_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        balance_mapeado: list[dict] = anexo_data.get("balance_mapeado", []) or []

        # ── Cuadro A: Deducciones adicionales — casillero 810 ───────────
        # Usa get_casillero_value: F-101 primero, balance_mapeado fallback.
        casillero_810 = get_casillero_value(anexo_data, "810")
        if casillero_810 is not None:
            if _safe_set(ws, A6_CUADRO_A_CASILLERO_810_CELL, casillero_810):
                filled += 1

        # Cuadro A detail rows: código, nombre, valor_libros
        # Source priority: deducciones_detail → balance_mapeado casillero 810 items
        deducciones: list[dict] = anexo_data.get("deducciones_detail", []) or []
        if not deducciones and balance_mapeado:
            balance_items = filter_balance_by_casilleros(balance_mapeado, {"810"})
            deducciones = [
                {
                    "codigo_cuenta": item.get("codigo", ""),
                    "nombre_cuenta": item.get("descripcion", ""),
                    "valor_libros": item.get("saldo", 0.0),
                }
                for item in balance_items
            ]

        start_a, end_a = A6_CUADRO_A_RANGE
        max_rows_a = end_a - start_a + 1

        for i, item in enumerate(deducciones[:max_rows_a]):
            row = start_a + i
            codigo = item.get("codigo_cuenta", "")
            nombre = item.get("nombre_cuenta", "")
            valor = item.get("valor_libros", 0.0)

            col_cod = A6_CUADRO_A_COLS["codigo_cuenta"]
            if codigo and _safe_set(ws, f"{col_cod}{row}", codigo):
                filled += 1

            col_nom = A6_CUADRO_A_COLS["nombre_cuenta"]
            if nombre and _safe_set(ws, f"{col_nom}{row}", nombre):
                filled += 1

            col_val = A6_CUADRO_A_COLS["valor_libros"]
            if _safe_set(ws, f"{col_val}{row}", valor):
                filled += 1

        if len(deducciones) > max_rows_a:
            warnings.append(
                f"A6 Cuadro A: se truncaron {len(deducciones) - max_rows_a} deducciones "
                f"(máximo {max_rows_a} filas disponibles)"
            )

        # ── Cuadro B: Contratos de inversión vigentes ────────────────────
        contratos: list[dict] = anexo_data.get("contratos_inversion", []) or []
        start_b, end_b = A6_CUADRO_B_RANGE
        max_rows_b = end_b - start_b + 1

        for i, c in enumerate(contratos[:max_rows_b]):
            row = start_b + i
            no_res = c.get("no_resolucion", "")
            fecha = c.get("fecha", "")
            monto = c.get("monto_incentivo")

            col_res = A6_CUADRO_B_COLS["no_resolucion"]
            if no_res and _safe_set(ws, f"{col_res}{row}", no_res):
                filled += 1

            col_fecha = A6_CUADRO_B_COLS["fecha"]
            if fecha and _safe_set(ws, f"{col_fecha}{row}", fecha):
                filled += 1

            col_monto = A6_CUADRO_B_COLS["monto_incentivo"]
            if monto is not None and _safe_set(ws, f"{col_monto}{row}", monto):
                filled += 1

        if len(contratos) > max_rows_b:
            warnings.append(
                f"A6 Cuadro B: se truncaron {len(contratos) - max_rows_b} contratos "
                f"(máximo {max_rows_b} filas disponibles)"
            )

        # ── Cuadro C: Exoneraciones / disminución de tarifa ─────────────
        exoneraciones: dict = anexo_data.get("exoneraciones", {}) or {}

        for row, tipo_key in A6_CUADRO_C_ROWS.items():
            exo = exoneraciones.get(tipo_key)
            if not exo:
                continue

            col_util = A6_CUADRO_C_COLS["utilizado"]
            utilizado = exo.get("utilizado", "No")
            if _safe_set(ws, f"{col_util}{row}", utilizado):
                filled += 1

            col_monto = A6_CUADRO_C_COLS["monto_incentivo"]
            monto = exo.get("monto_incentivo")
            if monto is not None and _safe_set(ws, f"{col_monto}{row}", monto):
                filled += 1

            col_res = A6_CUADRO_C_COLS["no_resolucion"]
            no_res = exo.get("no_resolucion", "")
            if no_res and _safe_set(ws, f"{col_res}{row}", no_res):
                filled += 1

            col_per = A6_CUADRO_C_COLS["periodo_inicio"]
            periodo = exo.get("periodo_inicio", "")
            if periodo and _safe_set(ws, f"{col_per}{row}", periodo):
                filled += 1

        # ── Warnings ────────────────────────────────────────────────────────
        if not contratos and not exoneraciones:
            warnings.append(
                "A6: sin contratos de inversión ni exoneraciones declaradas "
                "(Cuadros B y C vacíos)"
            )

        return {"filled_cells": filled, "warnings": warnings}
