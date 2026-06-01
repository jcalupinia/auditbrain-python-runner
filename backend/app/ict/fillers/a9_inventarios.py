"""Filler for INVENTARIOS A9 sheet."""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.a9 import A9_CASILLEROS, A9_HEADER_MAP, A9_SHEET
from backend.app.ict.fillers.helpers import get_casillero_value


class A9Filler:
    anexo_code = "A9"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[A9_SHEET]
        filled = 0
        warnings: list[str] = []

        for cell_addr, key in A9_HEADER_MAP.items():
            ws[cell_addr] = session_data.get(key, "")
            filled += 1

        kardex_items = anexo_data.get("kardex_items", [])

        for row_idx, casillero in A9_CASILLEROS.items():
            # Usa get_casillero_value: F-101 primero, balance_mapeado fallback
            valor = get_casillero_value(anexo_data, casillero)
            if valor is not None:
                ws[f"C{row_idx}"] = valor
                filled += 1
            else:
                warnings.append(f"Casillero F-101 {casillero} no detectado en F-101 ni Balance Mapeado")

            # Best-effort: first kardex item (more sophisticated matching in future)
            if kardex_items:
                first_match = kardex_items[0]
                ws[f"D{row_idx}"] = first_match.get("codigo_cuenta", "")
                ws[f"E{row_idx}"] = first_match.get("forma_valoracion", "PROMEDIO")
                ws[f"F{row_idx}"] = first_match.get("cantidad", "")
                ws[f"G{row_idx}"] = first_match.get("costo_total", 0.0)
                filled += 4
            elif valor is not None and valor > 0:
                warnings.append(
                    f"Casillero {casillero} tiene valor pero no se subió Kardex"
                )

        return {"filled_cells": filled, "warnings": warnings}
