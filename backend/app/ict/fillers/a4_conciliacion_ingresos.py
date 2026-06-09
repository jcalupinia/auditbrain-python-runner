"""Filler for CONCILIACIÓN INGRESOS A4 sheet (2 cuadros).

REFACTOR REFERENCIAL (CLAUDE.md):
  Cuadro 1 — Detalle de ingresos exentos. Texto (código, nombre) se escribe
              literal (vienen del Libro Mayor/Balance, no se referencia hoja
              DATOS para strings descriptivos). El VALOR (saldo) sí se
              referencia a 'DATOS BALANCE'!D<row> cuando la fuente es el
              balance mapeado.
  Cuadro 2 — Conciliación casilleros F-101 (804, 805, 812, 1112). Valor →
              ='DATOS F-101'!C<row>, fallback Balance.
  Filas de SUM y diferencia son fórmulas del template (no se tocan).
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a4 import (
    A4_CUADRO1_COLS,
    A4_CUADRO1_RANGE,
    A4_CUADRO2_CASILLEROS,
    A4_CUADRO2_COL,
    A4_HEADER_MAP,
    A4_SHEET,
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
    return safe_set(ws, cell_addr, value, anexo="A4",
                    origen="A4 Conciliación Ingresos (F-101 + Balance)")


class A4Filler:
    anexo_code = "A4"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A4_SHEET]
        filled = 0
        warnings: list[str] = []

        f101_lookup, _f103, _f104, balance_lookup = lookups_from_context(anexo_data)

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A4_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        # ── Cuadro 1: Detalle de ingresos exentos ────────────────────────
        movimientos: list[dict] = anexo_data.get("mayor_exentos", []) or []
        balance_mapeado: list[dict] = anexo_data.get("balance_mapeado", []) or []
        start_row, end_row = A4_CUADRO1_RANGE
        max_rows = end_row - start_row + 1

        # Fuente: mayor_exentos si existe; si no, filtra balance por casilleros
        # 804/805/812/1112. Para los del balance guardamos su índice original
        # para poder generar la referencia ='DATOS BALANCE'!D<row>.
        if movimientos:
            # mayor_exentos: solo texto + saldo literal (no viene del balance
            # mapeado, no hay índice → fallback a valor literal)
            balance_indexed: list[tuple[int | None, dict]] = [(None, m) for m in movimientos]
        else:
            balance_indexed = []
            for i, item in enumerate(balance_mapeado):
                if str(item.get("casillero_sri", "")).strip() in {"804", "805", "812", "1112"}:
                    balance_indexed.append((i, {
                        "codigo": item.get("codigo", ""),
                        "nombre": item.get("descripcion", ""),
                        "saldo": item.get("saldo", 0.0),
                        "casillero_sri": item.get("casillero_sri", ""),
                    }))

        if balance_indexed:
            for i, (orig_idx, mov) in enumerate(balance_indexed[:max_rows]):
                row = start_row + i
                codigo = mov.get("codigo", "")
                nombre = mov.get("nombre", "")
                saldo = mov.get("saldo", 0.0)
                casillero_num = mov.get("casillero_sri", "")

                col_a = A4_CUADRO1_COLS["identificacion"]
                if nombre and _safe_set(ws, f"{col_a}{row}", nombre):
                    filled += 1
                col_b = A4_CUADRO1_COLS["casillero"]
                if casillero_num and _safe_set(ws, f"{col_b}{row}", casillero_num):
                    filled += 1
                col_c = A4_CUADRO1_COLS["codigo_cuenta"]
                if codigo and _safe_set(ws, f"{col_c}{row}", codigo):
                    filled += 1
                col_d = A4_CUADRO1_COLS["nombre_cuenta"]
                if nombre and _safe_set(ws, f"{col_d}{row}", nombre):
                    filled += 1

                # Col G: SALDO → referencia a DATOS BALANCE si viene de ahí
                col_g = A4_CUADRO1_COLS["valor"]
                if orig_idx is not None:
                    if set_balance_item_ref(
                        ws, f"{col_g}{row}",
                        item_index=orig_idx,
                        balance_lookup=balance_lookup,
                        anexo="A4", casillero=casillero_num,
                        origen=f"A4 Cuadro 1 · Balance fila #{orig_idx + 1}",
                    ):
                        filled += 1
                else:
                    if _safe_set(ws, f"{col_g}{row}", saldo):
                        filled += 1

            if len(balance_indexed) > max_rows:
                warnings.append(
                    f"A4 Cuadro 1: se truncaron {len(balance_indexed) - max_rows} cuentas "
                    f"(máximo {max_rows} filas disponibles)"
                )
        else:
            warnings.append(
                "A4 Cuadro 1: sin datos de ingresos exentos. "
                "Sube el Libro Mayor o el Balance Mapeado para poblar el detalle."
            )

        # Filas del Cuadro 1 SIN pre-llenado: fórmula reactiva al casillero (col B).
        # Cuando el auditor escribe el Nº de casillero, el valor en libros (col G)
        # se calcula solo sumando DATOS BALANCE por ese casillero.
        num_prellenadas = min(len(balance_indexed), max_rows) if balance_indexed else 0
        col_b_a4 = A4_CUADRO1_COLS["casillero"]
        col_g_a4 = A4_CUADRO1_COLS["valor"]
        for row in range(start_row + num_prellenadas, end_row + 1):
            formula = libros_sumif_reactivo_formula(f"${col_b_a4}{row}", take_abs=True)
            if safe_set_formula(
                ws, f"{col_g_a4}{row}", formula, anexo="A4",
                origen="A4 Cuadro 1 · valor en libros reactivo al casillero",
            ):
                filled += 1

        # ── Cuadro 2: Conciliación F-101 casilleros (referencial) ─────────
        any_cuadro2 = False
        for row, casillero in A4_CUADRO2_CASILLEROS.items():
            ok = set_casillero_ref(
                ws, f"{A4_CUADRO2_COL}{row}",
                casillero=str(casillero),
                anexo_data=anexo_data,
                f101_lookup=f101_lookup,
                balance_lookup=balance_lookup,
                anexo="A4",
                origen_prefix="A4 Cuadro 2 · ",
            )
            if ok:
                filled += 1
                any_cuadro2 = True
            else:
                warnings.append(
                    f"A4 Cuadro 2 fila {row}: casillero {casillero} no encontrado en F-101 ni Balance"
                )

        if not any_cuadro2:
            warnings.append(
                "A4 Cuadro 2: sin datos de casilleros 804, 805, 812, 1112. "
                "Sube el F-101 o el Balance Mapeado."
            )

        # filter_balance_by_casilleros import preservado por compatibilidad
        _ = filter_balance_by_casilleros
        return {"filled_cells": filled, "warnings": warnings}
