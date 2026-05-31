"""Filler for ÍNDICE sheet."""

from __future__ import annotations

from openpyxl import Workbook

from backend.app.ict.cell_maps.indice import (
    INDICE_APLICA_COLUMN,
    INDICE_APLICA_MAP,
    INDICE_HEADER_MAP,
    INDICE_SHEET,
)


class IndiceFiller:
    anexo_code = "INDICE"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        ws = workbook[INDICE_SHEET]
        filled = 0
        warnings: list[str] = []

        for cell_addr, key in INDICE_HEADER_MAP.items():
            value = session_data.get(key, "")
            ws[cell_addr] = value
            filled += 1

        aplica = anexo_data.get("aplica", {})
        for row_idx, cuadro_key in INDICE_APLICA_MAP.items():
            base_anexo = cuadro_key.split("_C")[0]
            value = aplica.get(base_anexo, "NO")
            ws[f"{INDICE_APLICA_COLUMN}{row_idx}"] = value
            filled += 1

        return {"filled_cells": filled, "warnings": warnings}
