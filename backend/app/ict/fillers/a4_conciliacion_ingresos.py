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
        # FUENTE ÚNICA (instrucción cliente 2026-06-17): DATOS F-101.
        # Ya NO se leen `mayor_exentos` ni `balance_mapeado` para este
        # cuadro — solo el F-101. El Cuadro 2 (más abajo) sí conserva el
        # fallback al balance vía `balance_lookup`.
        f101: dict = anexo_data.get("f101", {}) or {}
        start_row, end_row = A4_CUADRO1_RANGE

        # FUENTE 2026-06-17 (regla cliente): cas oficiales SRI de
        # ingresos exentos / no objeto que el F-101 declara con valor
        # != 0 se trasladan automaticamente a B16+ (codigo). Para esas
        # filas la col G se sobrescribe con la referencia directa al
        # F-101 ('DATOS F-101'!Cxxx), NO el SUMIF al balance — porque
        # el cliente quiere ver el monto declarado en el F-101.
        # Cobertura ampliada 2026-06-17: incluimos TODOS los cas del rango
        # 6001-6999 que sean ingresos exentos / no objeto segun el catalogo
        # SRI (incluye los "VALOR EXENTO" del subbloque informativo).
        from backend.app.ict.catalogo_f101 import F101_CASILLERO_NAMES
        cas_exentos_f101: list[tuple[str, int | None]] = []
        for cas in sorted(F101_CASILLERO_NAMES.keys(),
                          key=lambda x: int(x) if x.isdigit() else 99999):
            if not cas.isdigit() or not (6001 <= int(cas) <= 6999):
                continue
            nombre = F101_CASILLERO_NAMES[cas].upper()
            # Patrones de "ingresos exentos / no objeto" (rango 6001-6999)
            es_exento = (
                nombre.startswith("VALOR EXENTO") or
                "RENTAS EXENTAS" in nombre or
                "NO OBJETO DE IMPUESTO" in nombre
            )
            if not es_exento:
                continue
            v = f101.get(cas)
            try:
                if v not in (None, "") and abs(float(v)) >= 0.005:
                    cas_exentos_f101.append((cas, f101_lookup.get(cas)))
            except (TypeError, ValueError):
                continue

        # CAMBIO 2026-06-17 (instrucción cliente): A4 Cuadro 1 NO debe
        # tomar la información del balance mapeado. La fuente única es
        # DATOS F-101 — solo se trasladan los cas exentos / no objeto
        # con valor declarado. La lógica anterior que filtraba balance
        # por cas 804/805/812/1112 fue eliminada porque mezclaba
        # cuentas contables del balance con casilleros del F-101.
        if not cas_exentos_f101:
            warnings.append(
                "A4 Cuadro 1: el F-101 no declara valores en cas de "
                "ingresos exentos / no objeto (6042, 6044, ..., 6094, 6150). "
                "El cuadro queda vacío para llenado manual por el auditor."
            )

        # ── Traslado automatico de cas exentos / no objeto del F-101 ──
        # Regla 2026-06-17: si el cliente declara valores en cas de
        # ingresos exentos / no objeto en F-101:
        #   - Col B: numero del casillero (ej. "6090")
        #   - Col G: valor declarado en F-101 ('DATOS F-101'!Cxxx)
        # Las filas que NO se llenan aqui mantienen la formula SUMIF
        # reactiva al balance (escrita abajo) para que el auditor pueda
        # agregar otras cuentas manualmente.
        col_b_a4 = A4_CUADRO1_COLS["casillero"]
        col_g_a4 = A4_CUADRO1_COLS["valor"]
        filas_con_f101_ref: set[int] = set()
        if cas_exentos_f101:
            # Buscar filas libres en B16:B25 (col B vacia en ese momento)
            next_row = start_row
            for cas, row_f101 in cas_exentos_f101:
                # Avanzar hasta encontrar una fila libre en col B
                while next_row <= end_row and ws.cell(next_row, 2).value:
                    next_row += 1
                if next_row > end_row:
                    warnings.append(
                        f"A4 Cuadro 1: cas exento {cas} no se trasladó — "
                        f"todas las filas B16:B25 están ocupadas."
                    )
                    break
                if _safe_set(ws, f"{col_b_a4}{next_row}", cas):
                    filled += 1
                # Col G: referencia directa al valor F-101 declarado
                if row_f101 is not None:
                    formula_g = f"='DATOS F-101'!C{row_f101}"
                    if safe_set_formula(
                        ws, f"{col_g_a4}{next_row}", formula_g, anexo="A4",
                        origen=f"A4 Cuadro 1 · cas {cas} traslado F-101",
                    ):
                        filled += 1
                        filas_con_f101_ref.add(next_row)
                next_row += 1

        # Cuadro 1, col G (G16:G25): fórmula REACTIVA al casillero (col B) en
        # TODAS las 10 filas — matching el template oficial SRI 2024.
        # Patrón: =IF($B<row>="","",ABS(SUMIF('DATOS BALANCE'!$A:$A,$B<row>,'DATOS BALANCE'!$D:$D)))
        # El valor se calcula solo a partir del casillero declarado en col B y
        # las cuentas mapeadas en DATOS BALANCE. Esto evita hardcodear saldos y
        # permite que el auditor cambie un casillero y vea el efecto inmediato.
        # Las filas que ya recibieron formula referencial al F-101 (cas
        # exentos trasladados) NO se sobrescriben con el SUMIF reactivo.
        for row in range(start_row, end_row + 1):
            if row in filas_con_f101_ref:
                continue
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
