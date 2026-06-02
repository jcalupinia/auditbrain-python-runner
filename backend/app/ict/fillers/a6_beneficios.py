"""Filler for BENEFICIOS TRIBUTARIOS A6 sheet (3 cuadros).

REFACTOR REFERENCIAL (CLAUDE.md):
  Cuadro A — Detalle deducciones (texto literal) + valor referencial al
              balance ('DATOS BALANCE'!D<row>). G25 (casillero 810 contrib.)
              → ='DATOS F-101'!C<row>.
  Cuadro B — Contratos de inversión: data manual del cliente (literal).
  Cuadro C — Exoneraciones: flags y montos manuales del cliente (literal).
"""

from __future__ import annotations

from openpyxl import Workbook

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
from backend.app.ict.fillers.base import safe_set
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_balance_item_ref,
    set_casillero_ref,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A6",
                    origen="A6 Beneficios (F-101)")


class A6Filler:
    anexo_code = "A6"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A6_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, _f104, balance_lookup = lookups_from_context(anexo_data)

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A6_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        balance_mapeado: list[dict] = anexo_data.get("balance_mapeado", []) or []

        # ── Cuadro A: Casillero 810 (referencial F-101 → Balance) ─────────
        if set_casillero_ref(
            ws, A6_CUADRO_A_CASILLERO_810_CELL,
            casillero="810",
            anexo_data=anexo_data,
            f101_lookup=f101_lookup,
            balance_lookup=balance_lookup,
            anexo="A6",
            origen_prefix="A6 Cuadro A · ",
        ):
            filled += 1

        # Detalle filas con datos del balance (810)
        deducciones: list[dict] = anexo_data.get("deducciones_detail", []) or []
        if deducciones:
            items_indexed: list[tuple[int | None, dict]] = [(None, d) for d in deducciones]
        else:
            items_indexed = []
            for i, item in enumerate(balance_mapeado):
                if str(item.get("casillero_sri", "")).strip() == "810":
                    items_indexed.append((i, {
                        "codigo_cuenta": item.get("codigo", ""),
                        "nombre_cuenta": item.get("descripcion", ""),
                        "valor_libros": item.get("saldo", 0.0),
                    }))

        start_a, end_a = A6_CUADRO_A_RANGE
        max_rows_a = end_a - start_a + 1

        for i, (orig_idx, item) in enumerate(items_indexed[:max_rows_a]):
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
            if orig_idx is not None:
                if set_balance_item_ref(
                    ws, f"{col_val}{row}",
                    item_index=orig_idx,
                    balance_lookup=balance_lookup,
                    anexo="A6", casillero="810",
                    origen=f"A6 Cuadro A · Balance fila #{orig_idx + 1}",
                ):
                    filled += 1
            else:
                if _safe_set(ws, f"{col_val}{row}", valor):
                    filled += 1

        if len(items_indexed) > max_rows_a:
            warnings.append(
                f"A6 Cuadro A: se truncaron {len(items_indexed) - max_rows_a} deducciones"
            )

        # ── Cuadro B: Contratos de inversión (manual del cliente) ─────────
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
                f"A6 Cuadro B: se truncaron {len(contratos) - max_rows_b} contratos"
            )

        # ── Cuadro C: Exoneraciones (manual del cliente) ──────────────────
        exoneraciones: dict = anexo_data.get("exoneraciones", {}) or {}
        for row, tipo_key in A6_CUADRO_C_ROWS.items():
            exo = exoneraciones.get(tipo_key)
            if not exo:
                continue
            col_util = A6_CUADRO_C_COLS["utilizado"]
            if _safe_set(ws, f"{col_util}{row}", exo.get("utilizado", "No")):
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

        if not contratos and not exoneraciones:
            warnings.append(
                "A6: sin contratos de inversión ni exoneraciones (Cuadros B y C vacíos)"
            )

        return {"filled_cells": filled, "warnings": warnings}
