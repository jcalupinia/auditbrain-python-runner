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

from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES
from backend.app.ict.catalogo_ingresos_exentos import (
    IE_CASILLERO_INFO,
    ie_descripcion,
    ie_normativa,
)
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
from backend.app.ict.fillers.row_expand import expand_tabular_block


def _safe_set(ws, cell_addr: str, value) -> bool:
    return safe_set(ws, cell_addr, value, anexo="A4",
                    origen="A4 Conciliación Ingresos (F-101 + Balance)")


def _wrap(ws, cell_addr: str) -> None:
    """Activa wrap_text + alineación superior (descripción y normativa del
    catálogo de ingresos exentos pueden ser largas)."""
    from copy import copy
    cell = ws[cell_addr]
    al = copy(cell.alignment)
    al.wrap_text = True
    al.vertical = "top"
    cell.alignment = al


def _cas_exentos_declarados(f101: dict, f101_lookup: dict) -> list:
    """Casilleros de ingresos exentos / no objeto que el F-101 declara con
    valor != 0, en orden creciente. Devuelve [(cas, fila_DATOS_F101_o_None)].

    Detección = casilleros que (a) el F-101 marca como exentos por nombre
    (VALOR EXENTO / RENTAS EXENTAS / NO OBJETO) Y (b) están en la librería
    de ingresos exentos del cliente (CMIE). El filtro por librería excluye
    los casilleros informativos / totales que el cliente NO considera detalle
    (ej. cas 6150 'INGRESOS NO OBJETO DE IMPUESTO A LA RENTA' — informativo).
    """
    out: list[tuple[str, int | None]] = []
    for cas in sorted(F101_CASILLERO_NAMES.keys(),
                      key=lambda x: int(x) if x.isdigit() else 99999):
        if not cas.isdigit() or not (6001 <= int(cas) <= 6999):
            continue
        nombre = F101_CASILLERO_NAMES[cas].upper()
        es_exento = (
            nombre.startswith("VALOR EXENTO") or
            "RENTAS EXENTAS" in nombre or
            "NO OBJETO DE IMPUESTO" in nombre
        )
        if not es_exento:
            continue
        # Filtro CMIE: solo los que el cliente curó como ingresos exentos de
        # detalle. Excluye informativos/totales (ej. 6150) que no están ahí.
        if cas not in IE_CASILLERO_INFO:
            continue
        v = f101.get(cas)
        try:
            if v not in (None, "") and abs(float(v)) >= 0.005:
                out.append((cas, f101_lookup.get(cas)))
        except (TypeError, ValueError):
            continue
    return out


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

        # ── Cuadro 1: Detalle de ingresos exentos (fuente única F-101) ────
        # Los casilleros de ingresos exentos / no objeto (6001-6999) que el
        # F-101 declara con valor != 0 se trasladan automáticamente:
        #   · Col B = número del casillero
        #   · Col E = descripción del tipo de ingreso exento (catálogo CMIE)
        #   · Col F = normativa de respaldo (catálogo CMIE)
        #   · Col G = valor declarado ('DATOS F-101'!Cxxx)
        # Si hay más casilleros que las 10 filas base (16-25), se INSERTAN
        # filas para que entren TODOS (REGLA SUPREMA: no truncar), reajustando
        # la fórmula del total y desplazando el Cuadro 2 hacia abajo.
        f101: dict = anexo_data.get("f101", {}) or {}
        start_row, end_row = A4_CUADRO1_RANGE       # (16, 25)
        base_rows = end_row - start_row + 1         # 10
        cas_exentos_f101 = _cas_exentos_declarados(f101, f101_lookup)
        n_ex = len(cas_exentos_f101)

        # Inserción dinámica si hay más exentos que filas base.
        extra = max(0, n_ex - base_rows)
        if extra > 0:
            total_row_old = end_row + 1             # 26 (fila TOTAL Cuadro 1)
            expand_tabular_block(
                ws, insert_at=total_row_old, amount=extra, style_row=end_row,
                inner_merges=None, last_col=7,
            )
            new_total_row = total_row_old + extra
            ws.cell(new_total_row, 7).value = f"=SUM(G16:G{end_row + extra})"

        end_row_eff = end_row + extra               # última fila de datos
        offset = extra                              # desplazamiento Cuadro 2

        if not cas_exentos_f101:
            warnings.append(
                "A4 Cuadro 1: el F-101 no declara valores en cas de "
                "ingresos exentos / no objeto (6042, 6044, ..., 6094, 6150). "
                "El cuadro queda vacío para llenado manual por el auditor."
            )

        col_b_a4 = A4_CUADRO1_COLS["casillero"]      # B
        col_e_a4 = A4_CUADRO1_COLS["descripcion"]    # E
        col_f_a4 = A4_CUADRO1_COLS["normativa"]      # F
        col_g_a4 = A4_CUADRO1_COLS["valor"]          # G
        filas_con_f101_ref: set[int] = set()
        for i, (cas, row_f101) in enumerate(cas_exentos_f101):
            row = start_row + i
            if _safe_set(ws, f"{col_b_a4}{row}", cas):
                filled += 1
            # Col G: referencia directa al valor F-101 declarado
            if row_f101 is not None:
                formula_g = f"='DATOS F-101'!C{row_f101}"
                if safe_set_formula(
                    ws, f"{col_g_a4}{row}", formula_g, anexo="A4",
                    origen=f"A4 Cuadro 1 · cas {cas} traslado F-101",
                ):
                    filled += 1
                    filas_con_f101_ref.add(row)
            # Col E = descripción del tipo de ingreso exento (catálogo CMIE)
            desc = ie_descripcion(cas)
            if desc and _safe_set(ws, f"{col_e_a4}{row}", desc):
                _wrap(ws, f"{col_e_a4}{row}")
                filled += 1
            # Col F = normativa de respaldo (catálogo CMIE)
            norm = ie_normativa(cas)
            if norm and _safe_set(ws, f"{col_f_a4}{row}", norm):
                _wrap(ws, f"{col_f_a4}{row}")
                filled += 1

        # Col G reactiva (SUMIF al casillero en col B) en las filas que NO
        # recibieron referencia al F-101 — el auditor puede agregar cuentas.
        for row in range(start_row, end_row_eff + 1):
            if row in filas_con_f101_ref:
                continue
            formula = libros_sumif_reactivo_formula(f"${col_b_a4}{row}", take_abs=True)
            if safe_set_formula(
                ws, f"{col_g_a4}{row}", formula, anexo="A4",
                origen="A4 Cuadro 1 · valor en libros reactivo al casillero",
            ):
                filled += 1

        # ── Cuadro 2: Conciliación F-101 casilleros (desplazado +offset) ──
        any_cuadro2 = False
        for row, casillero in A4_CUADRO2_CASILLEROS.items():
            ok = set_casillero_ref(
                ws, f"{A4_CUADRO2_COL}{row + offset}",
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
