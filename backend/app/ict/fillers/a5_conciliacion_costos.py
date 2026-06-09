"""Filler for CONCILIACIÓN COSTOS Y GASTOS A5 (5 cuadros + prorrateo).

REFACTOR REFERENCIAL (CLAUDE.md):
  Cuadro A — Detalle gastos no deducibles. Texto (código, nombre) literal;
              valor → ='DATOS BALANCE'!D<row> cuando viene del balance.
  Cuadro B — Casilleros 6999, 7999 → ='DATOS F-101'!C<row>.
  Cuadro C — Casilleros 804, 805, 808 → ='DATOS F-101'!C<row>.
  Cuadro D — Casilleros 806, 807, 808, 809, 813, 1113 → ='DATOS F-101'!C<row>.
  Cuadro E — Reversos: MVP vacío.
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a5 import (
    A5_CUADRO_A_COLS,
    A5_CUADRO_A_RANGE,
    A5_CUADRO_B_MAP,
    A5_CUADRO_C_MAP,
    A5_CUADRO_D_MAP,
    A5_HEADER_MAP,
    A5_SHEET,
)
from backend.app.ict.fillers.base import safe_set, safe_set_formula
from backend.app.ict.fillers.helpers import filter_balance_by_casilleros
from backend.app.ict.fillers.referential_helpers import (
    lookups_from_context,
    set_balance_item_ref,
    set_casillero_ref,
    libros_sumif_reactivo_formula,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A5",
                    origen="A5 Conciliación C/G (F-101 + Balance)")


class A5Filler:
    anexo_code = "A5"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A5_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, _f104, balance_lookup = lookups_from_context(anexo_data)

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A5_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        mayor_nd: list[dict] = anexo_data.get("mayor_no_deducibles", []) or []
        balance_mapeado: list[dict] = anexo_data.get("balance_mapeado", []) or []

        # ── Cuadro A: Detalle gastos no deducibles ────────────────────────
        start_a, end_a = A5_CUADRO_A_RANGE
        max_rows_a = end_a - start_a + 1

        # mayor_nd: lista de dicts SIN índice → fallback literal.
        # balance fallback: usar índice original para escribir fórmula.
        if mayor_nd:
            items_indexed: list[tuple[int | None, dict]] = [(None, m) for m in mayor_nd]
        else:
            items_indexed = []
            for i, item in enumerate(balance_mapeado):
                if str(item.get("casillero_sri", "")).strip() in {"806", "807"}:
                    items_indexed.append((i, {
                        "codigo": item.get("codigo", ""),
                        "nombre": item.get("descripcion", ""),
                        "saldo": item.get("saldo", 0.0),
                    }))

        if items_indexed:
            for i, (orig_idx, mov) in enumerate(items_indexed[:max_rows_a]):
                row = start_a + i
                codigo = mov.get("codigo", "")
                nombre = mov.get("nombre", "")
                saldo = mov.get("saldo", 0.0)

                col_id = A5_CUADRO_A_COLS["identificacion"]
                if nombre and _safe_set(ws, f"{col_id}{row}", nombre):
                    filled += 1
                col_c = A5_CUADRO_A_COLS["codigo_cuenta"]
                if codigo and _safe_set(ws, f"{col_c}{row}", codigo):
                    filled += 1
                col_d = A5_CUADRO_A_COLS["nombre_cuenta"]
                if nombre and _safe_set(ws, f"{col_d}{row}", nombre):
                    filled += 1

                # Col K: valor → ref a DATOS BALANCE si tenemos índice
                col_k = A5_CUADRO_A_COLS["valor"]
                if orig_idx is not None:
                    if set_balance_item_ref(
                        ws, f"{col_k}{row}",
                        item_index=orig_idx,
                        balance_lookup=balance_lookup,
                        anexo="A5",
                        origen=f"A5 Cuadro A · Balance fila #{orig_idx + 1}",
                    ):
                        filled += 1
                else:
                    if _safe_set(ws, f"{col_k}{row}", saldo):
                        filled += 1

            if len(items_indexed) > max_rows_a:
                warnings.append(
                    f"A5 Cuadro A: se truncaron {len(items_indexed) - max_rows_a} cuentas "
                    f"(máximo {max_rows_a} filas disponibles)"
                )
        else:
            warnings.append(
                "A5: sin gastos no deducibles (mayor_no_deducibles y balance 806/807 vacíos)"
            )

        # Filas del Cuadro A SIN pre-llenado: fórmula reactiva al casillero (col B).
        # La col B (Nº casillero) la escribe el auditor; al hacerlo, el valor en
        # libros (col K) se calcula solo sumando DATOS BALANCE por ese casillero.
        num_prellenadas_a = min(len(items_indexed), max_rows_a) if items_indexed else 0
        col_k_a5 = A5_CUADRO_A_COLS["valor"]
        for row in range(start_a + num_prellenadas_a, end_a + 1):
            formula = libros_sumif_reactivo_formula(f"$B{row}", take_abs=True)
            if safe_set_formula(
                ws, f"{col_k_a5}{row}", formula, anexo="A5",
                origen="A5 Cuadro A · valor en libros reactivo al casillero",
            ):
                filled += 1

        # ── Cuadro B: Prorrateo (casilleros 6999, 7999) referencial ───────
        any_cuadro_b = False
        for row, (source, casillero) in A5_CUADRO_B_MAP.items():
            if source != "f101":
                continue
            ok = set_casillero_ref(
                ws, f"G{row}",
                casillero=str(casillero),
                anexo_data=anexo_data,
                f101_lookup=f101_lookup,
                balance_lookup=balance_lookup,
                anexo="A5",
                origen_prefix="A5 Cuadro B · ",
            )
            if ok:
                filled += 1
                any_cuadro_b = True

        if not any_cuadro_b:
            warnings.append(
                "A5 Cuadro B: sin datos de casilleros 6999, 7999"
            )

        # ── Cuadro C: Participación trabajadores referencial ─────────────
        for row, casillero in A5_CUADRO_C_MAP.items():
            if set_casillero_ref(
                ws, f"H{row}",
                casillero=str(casillero),
                anexo_data=anexo_data,
                f101_lookup=f101_lookup,
                balance_lookup=balance_lookup,
                anexo="A5",
                origen_prefix="A5 Cuadro C · ",
            ):
                filled += 1

        # ── Cuadro D: Conciliación gastos no deducibles referencial ──────
        for row, casillero in A5_CUADRO_D_MAP.items():
            if set_casillero_ref(
                ws, f"H{row}",
                casillero=str(casillero),
                anexo_data=anexo_data,
                f101_lookup=f101_lookup,
                balance_lookup=balance_lookup,
                anexo="A5",
                origen_prefix="A5 Cuadro D · ",
            ):
                filled += 1

        # ── Cuadro E: Reversos — MVP vacío.
        _ = filter_balance_by_casilleros
        return {"filled_cells": filled, "warnings": warnings}
