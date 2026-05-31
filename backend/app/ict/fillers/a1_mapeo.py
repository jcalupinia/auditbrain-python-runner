"""Filler for MAPEO A1 sheet with dynamic row insertion for subaccounts."""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a1 import (
    A1_CASILLEROS_ORDERED,
    A1_FIRST_DATA_ROW,
    A1_HEADER_MAP,
    A1_SHEET,
)
from backend.app.ict.mapping_catalog import get_balance_prefixes_for_casillero


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

        for cell_addr, key in A1_HEADER_MAP.items():
            if _safe_set(ws, cell_addr, session_data.get(key, "")):
                filled += 1

        f101 = anexo_data.get("f101", {})
        balance = anexo_data.get("balance", {})

        current_row = A1_FIRST_DATA_ROW

        for casillero, casillero_nombre in A1_CASILLEROS_ORDERED:
            valor_declarado = f101.get(casillero)
            prefijos = get_balance_prefixes_for_casillero(casillero)

            matching = sorted([
                (codigo, info) for codigo, info in balance.items()
                if any(codigo.startswith(p) for p in prefijos)
            ])

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
                        f"Casillero {casillero}: sin subcuentas en balance "
                        f"(prefijos buscados: {prefijos})"
                    )
                current_row += 1
                continue

            codigo, info = matching[0]
            if _safe_set(ws, f"D{current_row}", codigo): filled += 1
            if _safe_set(ws, f"E{current_row}", info["nombre"]): filled += 1
            if _safe_set(ws, f"F{current_row}", info["saldo"]): filled += 1

            for offset, (codigo, info) in enumerate(matching[1:], start=1):
                ws.insert_rows(current_row + offset)
                if _safe_set(ws, f"D{current_row + offset}", codigo): filled += 1
                if _safe_set(ws, f"E{current_row + offset}", info["nombre"]): filled += 1
                if _safe_set(ws, f"F{current_row + offset}", info["saldo"]): filled += 1

            current_row += len(matching)

        return {"filled_cells": filled, "warnings": warnings}
