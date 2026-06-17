"""Filler for CONCILIACIÓN INGRESOS A4 sheet (2 cuadros).

REFACTOR REFERENCIAL (CLAUDE.md) — matching exacto al template oficial SRI:
  Cuadro 1 — Detalle de ingresos exentos (filas 16-25). Cols A-D (texto
              descriptivo: identificación, casillero, código, nombre cuenta)
              se llenan desde el balance/mayor cuando hay datos. La col G
              (valor en libros) SIEMPRE es la fórmula reactiva:
                =IF($B<row>="","",ABS(SUMIF('DATOS BALANCE'!$A:$A,$B<row>,
                                            'DATOS BALANCE'!$D:$D)))
              Esto coincide con las 10 fórmulas G16:G25 del template oficial
              SRI 2024 (ARCOLANDS / cliente PROPHAR), permite recálculo al
              cambiar el casillero, y evita hardcodear saldos.
  Cuadro 2 — Conciliación casilleros F-101 (804, 805, 812, 1112) en G32:G35.
              Valor → ='DATOS F-101'!C<row>, fallback Balance.
  G26, G36, G37 — fórmulas del template (=SUM(G16:G25), =SUM(G32:G35),
                  =G26-G36). NO se tocan.

Total fórmulas esperadas en la hoja generada: 17
  · 10 SUMIF reactivas (G16:G25)
  · 4 referencias F-101 (G32:G35)
  · 3 fórmulas del template (G26, G36, G37)
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
                # Col G la escribimos en el bucle de abajo (fórmula SUMIF reactiva
                # uniforme para TODAS las 10 filas, matching template oficial SRI).

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

        # Cuadro 1, col G (G16:G25): fórmula REACTIVA al casillero (col B) en
        # TODAS las 10 filas — matching el template oficial SRI 2024.
        # Patrón: =IF($B<row>="","",ABS(SUMIF('DATOS BALANCE'!$A:$A,$B<row>,'DATOS BALANCE'!$D:$D)))
        # El valor se calcula solo a partir del casillero declarado en col B y
        # las cuentas mapeadas en DATOS BALANCE. Esto evita hardcodear saldos y
        # permite que el auditor cambie un casillero y vea el efecto inmediato.
        col_b_a4 = A4_CUADRO1_COLS["casillero"]
        col_g_a4 = A4_CUADRO1_COLS["valor"]
        for row in range(start_row, end_row + 1):
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
