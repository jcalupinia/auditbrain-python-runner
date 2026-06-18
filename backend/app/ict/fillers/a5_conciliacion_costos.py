"""Filler for CONCILIACIÓN COSTOS Y GASTOS A5 (5 cuadros + prorrateo).

REFACTOR REFERENCIAL (CLAUDE.md):
  Cuadro A — Detalle gastos no deducibles. FUENTE ÚNICA = DATOS F-101
              (instrucción cliente 2026-06-18, equivalente al A4 de ingresos
              exentos). Los casilleros de gastos no deducibles (rango
              7001-7999, "VALOR NO DEDUCIBLE") que el F-101 declara con
              valor != 0 se trasladan automáticamente:
                · Col B  ← número del casillero
                · Col L  ← ='DATOS F-101'!C<row> (valor declarado)
                · Col K  ← SUMIF reactivo al casillero (valor en libros)
              Si hay más casilleros que las 5 filas base (17-21), se INSERTAN
              filas para que entren TODOS (nunca se trunca — REGLA SUPREMA),
              reajustando la fórmula del total y desplazando los Cuadros
              B/C/D/E hacia abajo.
  Cuadro B — Casilleros 6999, 7999 → ='DATOS F-101'!C<row>.
  Cuadro C — Casilleros 804, 805, 808 → ='DATOS F-101'!C<row>.
  Cuadro D — Casilleros 806, 807, 808, 809, 813, 1113 → ='DATOS F-101'!C<row>.
  Cuadro E — Reversos: MVP vacío.
"""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES
from backend.app.ict.catalogo_gnd import gnd_descripcion, gnd_normativa
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
    set_casillero_ref,
    libros_sumif_reactivo_formula,
)
from backend.app.ict.fillers.row_expand import expand_tabular_block


def _cas_no_deducibles_declarados(f101: dict, f101_lookup: dict) -> list:
    """Casilleros de gastos no deducibles (7001-7999, "VALOR NO DEDUCIBLE")
    que el F-101 declara con valor != 0, en orden creciente.
    Devuelve lista de (cas, fila_en_DATOS_F101_o_None)."""
    out: list[tuple[str, int | None]] = []
    for cas in sorted(F101_CASILLERO_NAMES.keys(),
                      key=lambda x: int(x) if x.isdigit() else 99999):
        if not cas.isdigit() or not (7001 <= int(cas) <= 7999):
            continue
        if not F101_CASILLERO_NAMES[cas].upper().startswith("VALOR NO DEDUCIBLE"):
            continue
        v = f101.get(cas)
        try:
            if v not in (None, "") and abs(float(v)) >= 0.005:
                out.append((cas, f101_lookup.get(cas)))
        except (TypeError, ValueError):
            continue
    return out


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A5",
                    origen="A5 Conciliación C/G (F-101 + Balance)")


def _wrap(ws, cell_addr: str) -> None:
    """Activa wrap_text + alineación superior en una celda (descripción y
    normativa del catálogo GND traen saltos de línea)."""
    from copy import copy
    cell = ws[cell_addr]
    al = copy(cell.alignment)
    al.wrap_text = True
    al.vertical = "top"
    cell.alignment = al


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

        f101: dict = anexo_data.get("f101", {}) or {}

        # ── Cuadro A: Detalle gastos no deducibles (fuente única F-101) ───
        start_a, end_a = A5_CUADRO_A_RANGE          # (17, 21)
        base_rows = end_a - start_a + 1             # 5 filas de plantilla
        cas_nd = _cas_no_deducibles_declarados(f101, f101_lookup)
        n_nd = len(cas_nd)

        # Inserción dinámica: si hay más casilleros que filas base, se
        # insertan filas para que entren TODOS (REGLA SUPREMA: no truncar).
        extra = max(0, n_nd - base_rows)
        if extra > 0:
            total_row_old = end_a + 1               # fila TOTAL (22)
            expand_tabular_block(
                ws, insert_at=total_row_old, amount=extra, style_row=end_a,
                inner_merges=[(5, 6), (7, 8), (9, 10)],  # E:F, G:H, I:J
                last_col=13,
            )
            # La fórmula del total (col K) debe cubrir TODAS las filas nuevas.
            new_total_row = total_row_old + extra
            ws.cell(new_total_row, 11).value = f"=SUM(K17:K{end_a + extra})"

        end_a_eff = end_a + extra                   # última fila de datos
        offset = extra                              # desplazamiento Cuadros B/C/D/E

        col_b = A5_CUADRO_A_COLS["casillero"]        # B
        col_e = A5_CUADRO_A_COLS["descripcion_gasto"]  # E (merged E:F)
        col_g = A5_CUADRO_A_COLS["normativa"]          # G (merged G:H)
        col_k = A5_CUADRO_A_COLS["valor"]            # K
        col_l = A5_CUADRO_A_COLS["valor_declarado"]  # L

        # Traslado: col B = casillero, col L = valor declarado (ref F-101).
        # Col E = descripción del tipo de gasto y col G = normativa aplicable,
        # autocompletadas desde el catálogo GND (librería del cliente).
        for i, (cas, row_f101) in enumerate(cas_nd):
            row = start_a + i
            if _safe_set(ws, f"{col_b}{row}", cas):
                filled += 1
            if row_f101 is not None:
                formula_l = f"='DATOS F-101'!C{row_f101}"
                if safe_set_formula(
                    ws, f"{col_l}{row}", formula_l, anexo="A5", casillero=cas,
                    origen=f"A5 Cuadro A · cas {cas} valor declarado F-101",
                ):
                    filled += 1
            # Descripción del tipo de gasto no deducible (catálogo GND) → col E
            descripcion = gnd_descripcion(cas)
            if descripcion and _safe_set(ws, f"{col_e}{row}", descripcion):
                _wrap(ws, f"{col_e}{row}")
                filled += 1
            # Normativa aplicable (catálogo GND) → col G
            normativa = gnd_normativa(cas)
            if normativa and _safe_set(ws, f"{col_g}{row}", normativa):
                _wrap(ws, f"{col_g}{row}")
                filled += 1

        # Col K (valor en libros): fórmula reactiva al casillero (col B) en
        # TODAS las filas del Cuadro A — al cambiar el casillero, suma DATOS
        # BALANCE por ese casillero.
        for row in range(start_a, end_a_eff + 1):
            formula = libros_sumif_reactivo_formula(f"$B{row}", take_abs=True)
            if safe_set_formula(
                ws, f"{col_k}{row}", formula, anexo="A5",
                origen="A5 Cuadro A · valor en libros reactivo al casillero",
            ):
                filled += 1

        if not cas_nd:
            warnings.append(
                "A5 Cuadro A: el F-101 no declara gastos no deducibles "
                "(casilleros 7xxx 'VALOR NO DEDUCIBLE'). El cuadro queda "
                "para llenado manual por el auditor."
            )

        # ── Cuadro B: Prorrateo (casilleros 6999, 7999) referencial ───────
        # Posiciones desplazadas +offset cuando el Cuadro A creció.
        any_cuadro_b = False
        for row, (source, casillero) in A5_CUADRO_B_MAP.items():
            if source != "f101":
                continue
            ok = set_casillero_ref(
                ws, f"G{row + offset}",
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
                ws, f"H{row + offset}",
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
                ws, f"H{row + offset}",
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
