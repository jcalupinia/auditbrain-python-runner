"""Filler for INGRESOS A2 sheet (3 cuadros: Ingresos Ordinarios, IVA vs Facturación, Conciliación).

Strategy:
  Cuadro 1 — writes F-101 casilleros into the (row, col) matrix.
  Cuadro 2 — writes aggregated F-104 monthly IVA casilleros + facturación electrónica.
  Cuadro 3 — propagates the Cuadro 2 net values into column B (valor neto conciliación);
              formula cells (rows 60, 66) are left untouched.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a2 import (
    A2_CUADRO1_CASILLERO_MAP,
    A2_CUADRO1_ROWS,
    A2_CUADRO2_IVA_MAP,
    A2_CUADRO2_ROWS,
    A2_CUADRO2_TOTAL_ROW,
    A2_CUADRO2_FACT_ELEC_COLS,
    A2_CUADRO3_ROWS,
    A2_HEADER_MAP,
    A2_SHEET,
)
from backend.app.ict.fillers.helpers import get_casillero_value


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


class A2Filler:
    anexo_code = "A2"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the INGRESOS A2 sheet.

        Expected keys in anexo_data:
            f101        — dict of casillero_str → float  (from parse_f101)
            f104_monthly — dict of 'MM' → {casilleros: {str→float}, ...} (from parse_f104)
            facturacion  — dict from parse_facturacion (totales + meses)
        """
        ws = workbook[A2_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A2_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        f104_monthly: dict[str, dict] = anexo_data.get("f104_monthly", {})
        facturacion: dict = anexo_data.get("facturacion", {})

        # ── Cuadro 1: Ingresos Ordinarios ────────────────────────────────
        # Usa get_casillero_value: F-101 primero, balance_mapeado fallback
        for (concepto, col), casillero in A2_CUADRO1_CASILLERO_MAP.items():
            row = next(
                (r for r, c in A2_CUADRO1_ROWS.items() if c == concepto), None
            )
            if row is None:
                warnings.append(f"A2 Cuadro1: concepto '{concepto}' no hallado en mapa de filas")
                continue
            val = get_casillero_value(anexo_data, str(casillero))
            if val is not None and val != 0:
                if _safe_set(ws, f"{col}{row}", val):
                    filled += 1
            elif val is None:
                # Only warn for main income lines (not every optional line)
                if concepto in ("ventas_bienes", "ventas_servicios"):
                    warnings.append(
                        f"A2 Cuadro1: casillero {casillero} ({concepto} col {col}) "
                        "no encontrado en F-101 ni Balance Mapeado"
                    )

        # ── Cuadro 2: IVA vs Facturación ─────────────────────────────────
        # Aggregate F-104 casilleros across all months
        iva_totals: dict[str, float] = {}
        for mes_data in f104_monthly.values():
            for cas, val in (mes_data.get("casilleros") or {}).items():
                iva_totals[str(cas)] = iva_totals.get(str(cas), 0.0) + (val or 0.0)

        for (concepto, col), casillero in A2_CUADRO2_IVA_MAP.items():
            row = next(
                (r for r, c in A2_CUADRO2_ROWS.items() if c == concepto), None
            )
            if row is None:
                continue
            val = iva_totals.get(str(casillero))
            if val is not None and val != 0:
                if _safe_set(ws, f"{col}{row}", val):
                    filled += 1

        # Write facturación electrónica totals to Cuadro 2
        if facturacion:
            totales = facturacion.get("totales", {})
            emit_total = totales.get("emitidas", 0.0)
            anul_total = totales.get("anuladas", 0.0)
            total_row = A2_CUADRO2_TOTAL_ROW

            col_emit = A2_CUADRO2_FACT_ELEC_COLS["emitidas"]   # G
            col_anul = A2_CUADRO2_FACT_ELEC_COLS["anuladas"]    # H

            if emit_total:
                if _safe_set(ws, f"{col_emit}{total_row}", emit_total):
                    filled += 1
            if anul_total:
                if _safe_set(ws, f"{col_anul}{total_row}", anul_total):
                    filled += 1

            # Also populate individual month rows when available
            meses = facturacion.get("meses", {})
            for mes_key, mes_vals in meses.items():
                # We only have total rows in template; skip individual month distribution
                _ = mes_vals  # reserved for future use

        # ── Cuadro 3: Conciliación IVA → IR ──────────────────────────────
        # Propagate Cuadro 2 IVA net values into Cuadro 3 column B.
        # Mapping: Cuadro2 concepto → Cuadro3 concepto (same logical lines)
        cuadro2_to_cuadro3 = {
            "ventas_locales_diff_iva": "ventas_locales_diff",
            "ventas_activos_fijos_diff": "ventas_activos_fijos_diff",
            "ventas_locales_0_sin_derecho": "ventas_locales_0_sin_derecho",
            "ventas_activos_0_sin_derecho": "ventas_activos_0_sin_derecho",
            "ventas_locales_0_con_derecho": "ventas_locales_0_con_derecho",
            "ventas_activos_0_con_derecho": "ventas_activos_0_con_derecho",
            "exportaciones_bienes": "exportaciones_bienes",
            "exportaciones_servicios": "exportaciones_servicios",
            "transferencias_no_objeto": "transferencias_no_objeto",
        }

        for c2_concepto, c3_concepto in cuadro2_to_cuadro3.items():
            # Find the row in Cuadro 2
            c2_row = next(
                (r for r, c in A2_CUADRO2_ROWS.items() if c == c2_concepto), None
            )
            # Find the row in Cuadro 3
            c3_row = next(
                (r for r, c in A2_CUADRO3_ROWS.items() if c == c3_concepto), None
            )
            if c2_row is None or c3_row is None:
                continue

            # Compute net value from IVA (col F = e = a+b+c-d is a formula; we derive it)
            # Use the individual IVA columns we already set, sum manually
            val = 0.0
            for col_letter in ("B", "C", "D"):
                cell = ws[f"{col_letter}{c2_row}"]
                cv = getattr(cell, "value", None)
                if cv is not None and not isinstance(cv, str):
                    try:
                        val += float(cv)
                    except (ValueError, TypeError):
                        pass
            # Subtract notas crédito (col E)
            nc_cell = ws[f"E{c2_row}"]
            nc_val = getattr(nc_cell, "value", None)
            if nc_val is not None and not isinstance(nc_val, str):
                try:
                    val -= float(nc_val)
                except (ValueError, TypeError):
                    pass

            if val:
                if _safe_set(ws, f"B{c3_row}", val):
                    filled += 1

        return {"filled_cells": filled, "warnings": warnings}
