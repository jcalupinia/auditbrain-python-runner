"""Filler for MAPEO A1 sheet using Balance Mapeado (casillero pre-asignado por cliente)."""

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
    """Set a cell value, skipping if it's a MergedCell (which raises)."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


class A1Filler:
    anexo_code = "A1"

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
            cas = item.get("casillero_sri", "").strip()
            if cas:
                by_casillero.setdefault(cas, []).append(item)

        current_row = A1_FIRST_DATA_ROW

        for casillero, casillero_nombre in A1_CASILLEROS_ORDERED:
            valor_declarado = f101.get(casillero)
            matching = by_casillero.get(casillero, [])

            # Write base row: casillero + nombre + valor declarado
            if _safe_set(ws, f"A{current_row}", casillero):
                filled += 1
            if _safe_set(ws, f"B{current_row}", casillero_nombre):
                filled += 1
            if valor_declarado is not None:
                if _safe_set(ws, f"C{current_row}", valor_declarado):
                    filled += 1
            else:
                warnings.append(f"Casillero {casillero} no encontrado en F-101")

            if not matching:
                if valor_declarado is not None and valor_declarado != 0:
                    warnings.append(
                        f"Casillero {casillero}: sin cuentas en Balance Mapeado"
                    )
                current_row += 1
                continue

            # First account in the base row's D-F columns
            first = matching[0]
            if _safe_set(ws, f"D{current_row}", first.get("codigo", "")): filled += 1
            if _safe_set(ws, f"E{current_row}", first.get("descripcion", "")): filled += 1
            if _safe_set(ws, f"F{current_row}", first.get("saldo", 0)): filled += 1

            # Additional accounts: insert rows below the base
            for offset, item in enumerate(matching[1:], start=1):
                ws.insert_rows(current_row + offset)
                if _safe_set(ws, f"D{current_row + offset}", item.get("codigo", "")): filled += 1
                if _safe_set(ws, f"E{current_row + offset}", item.get("descripcion", "")): filled += 1
                if _safe_set(ws, f"F{current_row + offset}", item.get("saldo", 0)): filled += 1

            current_row += len(matching)

        # Note: casilleros in balance_mapeado that DON'T appear in A1_CASILLEROS_ORDERED
        # are simply not written (the ICT A1 only has selected casilleros from F-101).
        # Track them as info-warnings:
        casilleros_a1_set = {c for c, _ in A1_CASILLEROS_ORDERED}
        extra_casilleros = set(by_casillero.keys()) - casilleros_a1_set
        if extra_casilleros:
            warnings.append(
                f"Balance Mapeado tiene {len(extra_casilleros)} casillero(s) que no se mapean al A1 "
                f"(quedan disponibles para otros anexos): {sorted(extra_casilleros)[:10]}"
                f"{'...' if len(extra_casilleros) > 10 else ''}"
            )

        return {"filled_cells": filled, "warnings": warnings}
