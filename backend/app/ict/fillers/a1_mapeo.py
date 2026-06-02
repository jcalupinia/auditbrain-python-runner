"""Filler for MAPEO A1 sheet usando Balance Mapeado (casillero pre-asignado).

Metodología REPLICADA del anexo oficial ICT 2024 del SRI:

  - Cada casillero F-101 ocupa una o más filas (una por cada cuenta
    contable que mapea a él).
  - PRIMERA fila del casillero:
      A: número de casillero       B: nombre del casillero
      C: valor declarado F-101     D/E/F: primera cuenta del balance
      G: fórmula DIFERENCIA:
         · 1 sola cuenta  → "=F<row>-C<row>"
         · N cuentas      → "=SUM(F<row>:F<row+N-1>)-C<row>"
      H: observaciones (vacío)
  - FILAS SIGUIENTES del mismo casillero:
      Solo D/E/F (código, descripción, saldo de cada cuenta adicional).
      Cols A, B, C, G, H quedan en BLANCO — la fórmula G de la primera
      fila YA suma todo el rango.
  - Casilleros SIN cuentas en el balance: G = "=F<row>-C<row>" (apunta
    a su propia fila, donde F<row> está vacío → fórmula evaluará a
    -C<row>, evidenciando que falta el saldo contable).
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a1 import (
    A1_CASILLEROS_ORDERED,
    A1_FIRST_DATA_ROW,
    A1_HEADER_MAP,
    A1_SHEET,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Wrapper local: delega al central que protege MergedCells + fórmulas
    y registra la escritura en el trace log para la hoja Trazabilidad."""
    from backend.app.ict.fillers.base import safe_set
    return safe_set(ws, cell_addr, value, anexo="A1",
                    origen="A1 Mapeo (F-101 + Balance Mapeado)")


def _safe_set_formula(ws, cell_addr: str, formula: str) -> bool:
    """Wrapper local para fórmulas DELIBERADAS (sobreescribe fórmulas
    viejas del template cuando es necesario, p. ej. =SUM(F13:F25)-C13)."""
    from backend.app.ict.fillers.base import safe_set_formula
    return safe_set_formula(ws, cell_addr, formula, anexo="A1",
                            origen="A1 Mapeo (fórmula calculada)")


class A1Filler:
    anexo_code = "A1"

    # Casilleros que marcan FIN de bloque mayor — después de ellos
    # se inserta una fila en blanco como separador visual.
    BLOQUE_BREAKS = {"361", "499", "550", "599", "698", "699", "1005", "6999", "7999"}
    # Casilleros que son TOTAL (formato negrita + borde doble)
    TOTAL_CASILLEROS = {"361", "449", "499", "550", "589", "599", "698", "699",
                        "1005", "1045", "6999", "7991", "7992", "7999"}

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A1_SHEET]
        filled = 0
        warnings: list[str] = []

        # Header
        for cell_addr, key in A1_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        f101 = anexo_data.get("f101", {})
        # balance_mapeado is a list of {casillero_sri, codigo, descripcion, saldo}
        balance_mapeado = anexo_data.get("balance_mapeado", [])

        # Group balance items by casillero_sri
        by_casillero: dict[str, list[dict]] = {}
        for item in balance_mapeado:
            cas = str(item.get("casillero_sri", "")).strip()
            if cas:
                by_casillero.setdefault(cas, []).append(item)

        # Tracking de grupos para formatting posterior
        casillero_groups: list[dict] = []
        current_row = A1_FIRST_DATA_ROW

        for casillero, casillero_nombre in A1_CASILLEROS_ORDERED:
            valor_declarado = f101.get(casillero)
            matching = by_casillero.get(casillero, [])
            n_accounts = len(matching)
            is_total = casillero in self.TOTAL_CASILLEROS
            row_start = current_row

            # === Casillero + nombre + valor declarado (cols A, B, C) ===
            if _safe_set(ws, f"A{current_row}", casillero):
                filled += 1
            if _safe_set(ws, f"B{current_row}", casillero_nombre):
                filled += 1
            if valor_declarado is not None:
                if _safe_set(ws, f"C{current_row}", valor_declarado):
                    filled += 1
            else:
                warnings.append(f"Casillero {casillero} no encontrado en F-101")

            if n_accounts == 0:
                # Sin cuentas contables: fórmula G apunta a su propia fila.
                _safe_set_formula(ws, f"G{current_row}", f"=F{current_row}-C{current_row}")
                if valor_declarado is not None and valor_declarado != 0 and not is_total:
                    warnings.append(
                        f"Casillero {casillero} ({casillero_nombre}): declarado "
                        f"{valor_declarado:,.2f} pero el Balance Mapeado no aporta "
                        f"cuentas contables — diferencia será -{valor_declarado:,.2f}"
                    )
                # Trackear grupo (1 fila)
                casillero_groups.append({
                    "casillero": casillero, "row_start": row_start,
                    "row_end": current_row, "is_total": is_total,
                })
                current_row += 1
                # Separador después de bloques mayores
                if casillero in self.BLOQUE_BREAKS:
                    current_row += 1  # fila en blanco
                continue

            # === Primera fila: primera cuenta en D/E/F + fórmula G en SUM range ===
            first = matching[0]
            if _safe_set(ws, f"D{current_row}", first.get("codigo", "")): filled += 1
            if _safe_set(ws, f"E{current_row}", first.get("descripcion", "")): filled += 1
            if _safe_set(ws, f"F{current_row}", first.get("saldo", 0)): filled += 1

            # Fórmula G — metodología oficial 2024:
            #   N cuentas → "=SUM(F<row>:F<row+N-1>)-C<row>"
            #   1 cuenta  → "=F<row>-C<row>"
            if n_accounts > 1:
                end_row = current_row + n_accounts - 1
                formula = f"=SUM(F{current_row}:F{end_row})-C{current_row}"
            else:
                formula = f"=F{current_row}-C{current_row}"
            _safe_set_formula(ws, f"G{current_row}", formula)

            # === Filas adicionales: cuentas extra del mismo casillero ===
            # Sólo D/E/F. NO se pone fórmula en G (queda en blanco) porque la
            # fórmula SUM de la primera fila YA suma todo este rango.
            for offset, item in enumerate(matching[1:], start=1):
                row_n = current_row + offset
                ws.insert_rows(row_n)
                if _safe_set(ws, f"D{row_n}", item.get("codigo", "")): filled += 1
                if _safe_set(ws, f"E{row_n}", item.get("descripcion", "")): filled += 1
                if _safe_set(ws, f"F{row_n}", item.get("saldo", 0)): filled += 1

            # Trackear grupo (N filas)
            casillero_groups.append({
                "casillero": casillero,
                "row_start": row_start,
                "row_end": current_row + n_accounts - 1,
                "is_total": is_total,
            })

            current_row += n_accounts
            # Separador después de bloques mayores
            if casillero in self.BLOQUE_BREAKS:
                current_row += 1  # fila en blanco entre bloques

        # === Reporte de cobertura para warnings ===
        casilleros_a1_set = {c for c, _ in A1_CASILLEROS_ORDERED}

        # Casilleros del balance que NO aparecen en el A1 (quedan disponibles
        # para otros anexos via shared_context, pero son útiles de listar):
        extra_casilleros = set(by_casillero.keys()) - casilleros_a1_set
        if extra_casilleros:
            cuentas_huerfanas = sum(len(by_casillero[c]) for c in extra_casilleros)
            warnings.append(
                f"Balance Mapeado: {len(extra_casilleros)} casilleros con "
                f"{cuentas_huerfanas} cuentas NO mapean al A1 (se trasladan a "
                f"A2-A9 vía shared_context): {sorted(extra_casilleros)[:10]}"
                f"{'...' if len(extra_casilleros) > 10 else ''}"
            )

        # === Aplicar formato profesional al A1 ===
        # REGLA (CLAUDE.md): los anexos del ICT deben verse correctamente
        # presentados, equivalentes al formato oficial del SRI Ecuador.
        try:
            from backend.app.ict.fillers.formatting import format_a1_sheet
            format_a1_sheet(ws, casillero_groups=casillero_groups,
                            first_data_row=A1_FIRST_DATA_ROW)
        except Exception:
            import logging
            logging.exception("format_a1_sheet falló")

        return {"filled_cells": filled, "warnings": warnings}
