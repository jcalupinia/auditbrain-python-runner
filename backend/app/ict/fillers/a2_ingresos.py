"""Filler for INGRESOS A2 sheet (3 cuadros: Ingresos Ordinarios, IVA vs Facturación, Conciliación).

REFACTOR REFERENCIAL (CLAUDE.md):
  Todas las celdas numéricas que provienen del F-101 o del F-104 se escriben
  como FÓRMULAS que referencian las hojas DATOS F-101 / DATOS F-104, en
  lugar de valores literales. El auditor hace click en cualquier celda y ve
  el origen exacto.

  Cuadro 1 — referencias a 'DATOS F-101'!C<row> por casillero del F-101.
              Fallback: 'DATOS BALANCE'!D<row> agregando todas las cuentas
              cuyo casillero_sri coincida.
  Cuadro 2 — referencias a 'DATOS F-104'!<total_col><row> (TOTAL ANUAL de
              los 12 meses parseados).
  Cuadro 3 — fórmulas SUMA(B+C+D)-E aplicadas a la propia fila del Cuadro 2.
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a2 import (
    A2_CUADRO1_CASILLERO_MAP,
    A2_CUADRO1_ROWS,
    A2_CUADRO1_TOTAL_COLS,
    A2_CUADRO2_IVA_MAP,
    A2_CUADRO2_ROWS,
    A2_CUADRO2_SOURCE_COL,
    A2_CUADRO2_TOTAL_ROW,
    A2_CUADRO2_VALORNETO_MAP,
    A2_CUADRO2_FACT_ELEC_COLS,
    A2_CUADRO3_ROWS,
    A2_HEADER_MAP,
    A2_SHEET,
)
from backend.app.ict.fillers.base import safe_set, safe_set_formula
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_casillero_ref,
    set_f104_annual_ref,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A2",
                    origen="A2 Ingresos (F-101 + F-104 mensuales)")


class A2Filler:
    anexo_code = "A2"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A2_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, f104_lookup, balance_lookup = lookups_from_context(anexo_data)

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A2_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        facturacion: dict = anexo_data.get("facturacion", {})

        # ── Cuadro 1: Ingresos Ordinarios (referencial F-101 → Balance) ─────
        for (concepto, col), casillero in A2_CUADRO1_CASILLERO_MAP.items():
            row = next(
                (r for r, c in A2_CUADRO1_ROWS.items() if c == concepto), None
            )
            if row is None:
                warnings.append(f"A2 Cuadro1: concepto '{concepto}' no hallado en mapa de filas")
                continue
            ok = set_casillero_ref(
                ws, f"{col}{row}",
                casillero=str(casillero),
                anexo_data=anexo_data,
                f101_lookup=f101_lookup,
                balance_lookup=balance_lookup,
                anexo="A2",
                origen_prefix="A2 Cuadro 1 · ",
            )
            if ok:
                filled += 1
            elif concepto in ("ventas_bienes", "ventas_servicios"):
                warnings.append(
                    f"A2 Cuadro1: casillero {casillero} ({concepto} col {col}) "
                    "no encontrado en F-101 ni Balance Mapeado"
                )

        # ── Cuadro 1: total por fila (col F = suma intra-anexo) + SUM fila 25 ─
        for row, cols in A2_CUADRO1_TOTAL_COLS.items():
            formula = "=" + "+".join(f"{c}{row}" for c in cols)
            if safe_set_formula(ws, f"F{row}", formula, anexo="A2",
                                origen="A2 Cuadro 1 · total ingresos ordinarios"):
                filled += 1
        for col in ("B", "C", "F"):
            if safe_set_formula(ws, f"{col}25", f"=SUM({col}14:{col}24)", anexo="A2",
                                origen="A2 Cuadro 1 · total columna (i)"):
                filled += 1

        # ── Cuadro 2: IVA vs Facturación (referencial F-104 TOTAL ANUAL) ────
        # Cada casillero de IVA mensual se referencia al total anual del
        # casillero en 'DATOS F-104'. Fallback (tests directos sin DATOS
        # sheet): agregamos manualmente los 12 meses.
        f104_monthly: dict[str, dict] = anexo_data.get("f104_monthly", {})
        iva_totals_fallback: dict[str, float] = {}
        for mes_data in f104_monthly.values():
            for cas, val in (mes_data.get("casilleros") or {}).items():
                iva_totals_fallback[str(cas)] = iva_totals_fallback.get(str(cas), 0.0) + (val or 0.0)

        for (concepto, col), casillero in A2_CUADRO2_IVA_MAP.items():
            row = next(
                (r for r, c in A2_CUADRO2_ROWS.items() if c == concepto), None
            )
            if row is None:
                continue
            ok = set_f104_annual_ref(
                ws, f"{col}{row}",
                casillero=str(casillero),
                lookup=f104_lookup,
                anexo="A2",
            )
            if ok:
                filled += 1
                continue
            # Fallback literal
            val = iva_totals_fallback.get(str(casillero))
            if val is not None and val != 0:
                if _safe_set(ws, f"{col}{row}", val):
                    filled += 1

        # ── Cuadro 2: valor neto (col F = facturado, F-104 cas 411-418) y ────
        #    diferencia (col E = columna fuente − F).
        for concepto, casillero in A2_CUADRO2_VALORNETO_MAP.items():
            row = next(
                (r for r, c in A2_CUADRO2_ROWS.items() if c == concepto), None
            )
            if row is None:
                continue
            if set_f104_annual_ref(
                ws, f"F{row}", casillero=str(casillero),
                lookup=f104_lookup, anexo="A2",
            ):
                filled += 1
            else:
                val = iva_totals_fallback.get(str(casillero))
                if val is not None and val != 0:
                    if _safe_set(ws, f"F{row}", val):
                        filled += 1
            # E = (columna fuente B/C/D) − F (valor neto)
            src = A2_CUADRO2_SOURCE_COL.get(concepto)
            if src and safe_set_formula(
                ws, f"E{row}", f"=+{src}{row}-F{row}",
                anexo="A2", origen="A2 Cuadro 2 · diferencia declarado vs facturado",
            ):
                filled += 1

        # Facturación electrónica: NO viene de un formulario SRI parseado,
        # se mantiene como valor literal (origen XML local).
        if facturacion:
            totales = facturacion.get("totales", {})
            emit_total = totales.get("emitidas", 0.0)
            anul_total = totales.get("anuladas", 0.0)
            total_row = A2_CUADRO2_TOTAL_ROW
            col_emit = A2_CUADRO2_FACT_ELEC_COLS["emitidas"]
            col_anul = A2_CUADRO2_FACT_ELEC_COLS["anuladas"]
            if emit_total:
                if _safe_set(ws, f"{col_emit}{total_row}", emit_total):
                    filled += 1
            if anul_total:
                if _safe_set(ws, f"{col_anul}{total_row}", anul_total):
                    filled += 1

        # ── Cuadro 3: Conciliación IVA → IR (fórmula intra-anexo) ──────────
        # El valor neto del Cuadro 3 = B + C + D - E del Cuadro 2 (misma línea
        # lógica). En lugar de calcular y escribir el valor, escribimos la
        # fórmula que suma esas columnas del Cuadro 2; así si los valores
        # del Cuadro 2 cambian (porque DATOS F-104 cambió) el Cuadro 3
        # se recalcula automáticamente.
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
            c2_row = next(
                (r for r, c in A2_CUADRO2_ROWS.items() if c == c2_concepto), None
            )
            c3_row = next(
                (r for r, c in A2_CUADRO3_ROWS.items() if c == c3_concepto), None
            )
            if c2_row is None or c3_row is None:
                continue

            # Fórmula: =B<c2>+C<c2>+D<c2>-E<c2> (todo dentro de A2)
            formula = f"=B{c2_row}+C{c2_row}+D{c2_row}-E{c2_row}"
            if safe_set_formula(
                ws, f"B{c3_row}", formula,
                anexo="A2", casillero=str(c2_concepto),
                origen=f"A2 Cuadro 3 · derivado del Cuadro 2 fila {c2_row}",
            ):
                filled += 1

        # ── Limpieza puntual: E43/E44 (col diferencia de las filas Total y
        #    Transferencias del Cuadro 2) quedan en blanco como en ICT_14.
        #    NO se tocan los 'XXXX' del Cuadro 3 (C52-D59): son celdas de
        #    llenado manual del auditor y ICT_14 las conserva.
        for addr in ("E43", "E44"):
            if ws[addr].value == "XXXX":
                ws[addr].value = None

        return {"filled_cells": filled, "warnings": warnings}
