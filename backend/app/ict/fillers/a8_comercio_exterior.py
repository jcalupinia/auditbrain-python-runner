"""Filler for COMERCIO EXTERIOR A8 (3 tablas dinámicas).

Reads anexo_data["ats_pagos_exterior"] from ATS XML parser output.

El parser ats_xml.py devuelve pagos con los campos:
  pago_loc_ext, tipo_regi, pais, pais_pago_gen,
  denop_reg_fiscal, sujeto_retencion, comentario

Clasificación de transacciones:
  - Tabla C (Reembolsos):  pago_loc_ext == "03"
  - Tabla A (Con CDI):     tipo_regi == "01" and pago_loc_ext != "03"
  - Tabla B (Sin CDI):     cualquier otro caso

Cada tabla tiene 4 filas disponibles en la plantilla (limitante del template).
Si hay más transacciones se emite un warning y se trunca.
"""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.cell.cell import MergedCell

from backend.app.ict.cell_maps.a8 import (
    A8_HEADER_MAP,
    A8_SHEET,
    A8_TABLA_A_COLS,
    A8_TABLA_A_MAX_ROWS,
    A8_TABLA_A_START_ROW,
    A8_TABLA_B_COLS,
    A8_TABLA_B_MAX_ROWS,
    A8_TABLA_B_START_ROW,
    A8_TABLA_C_COLS,
    A8_TABLA_C_MAX_ROWS,
    A8_TABLA_C_START_ROW,
)


def _safe_set(ws, cell_addr: str, value) -> bool:
    """Set cell value; silently skips MergedCells. Returns True if written."""
    cell = ws[cell_addr]
    if isinstance(cell, MergedCell):
        return False
    cell.value = value
    return True


def _classify_transaction(pago: dict) -> str:
    """Classify ATS pagoExterior into tabla A / B / C.

    Tabla C: reembolsos vía intermediario (pago_loc_ext == "03")
    Tabla A: pagos con CDI aplicado (tipo_regi == "01")
    Tabla B: resto (sin CDI)
    """
    pago_loc_ext = pago.get("pago_loc_ext") or ""
    tipo_regi = pago.get("tipo_regi") or ""

    if pago_loc_ext == "03":
        return "C"
    if tipo_regi == "01":
        return "A"
    return "B"


def _write_transaction(ws, row: int, cols_map: dict, data: dict) -> int:
    """Write a transaction's fields to the given row using cols_map.

    Returns the number of cells successfully written.
    """
    filled = 0
    for col_letter, field_key in cols_map.items():
        val = data.get(field_key)
        if val is not None:
            cell_addr = f"{col_letter}{row}"
            if _safe_set(ws, cell_addr, val):
                filled += 1
    return filled


def _map_pago_to_tabla_a(pago: dict) -> dict:
    """Map ATS pago fields to Tabla A (con CDI) column keys."""
    return {
        "rfc_extranjero": pago.get("denop_reg_fiscal") or "",
        "pais_residencia": pago.get("pais") or "",
        "pais_cdi": pago.get("pais_pago_gen") or pago.get("pais") or "",
        "pais_servicio": pago.get("pais") or "",
        "descripcion_transaccion": pago.get("comentario") or "",
        "es_gravado": pago.get("sujeto_retencion") or "",
    }


def _map_pago_to_tabla_b(pago: dict) -> dict:
    """Map ATS pago fields to Tabla B (sin CDI) column keys."""
    return {
        "rfc_extranjero": pago.get("denop_reg_fiscal") or "",
        "pais_residencia": pago.get("pais") or "",
        "pais_servicio": pago.get("pais") or "",
        "descripcion_transaccion": pago.get("comentario") or "",
        "es_gravado": pago.get("sujeto_retencion") or "",
    }


def _map_pago_to_tabla_c(pago: dict) -> dict:
    """Map ATS pago fields to Tabla C (reembolsos) column keys."""
    return {
        "proveedor_rfc": pago.get("denop_reg_fiscal") or "",
        "proveedor_pais": pago.get("pais") or "",
        "descripcion_transaccion": pago.get("comentario") or "",
        "es_gravado": pago.get("sujeto_retencion") or "",
    }


class A8Filler:
    anexo_code = "A8"

    def fill(
        self,
        workbook: Workbook,
        session_data: dict,
        anexo_data: dict,
    ) -> dict:
        """Fill the COMERCIO EXTERIOR A8 sheet.

        Expected keys in anexo_data:
            ats_pagos_exterior — list of pago dicts from parse_ats() output
                                 (mapped from pagos_exterior in the parser result)
        Expected keys in session_data:
            razon_social, ruc, ejercicio_fiscal
        """
        ws = workbook[A8_SHEET]
        filled = 0
        warnings: list[str] = []

        # ── Header ──────────────────────────────────────────────────────────
        for cell_addr, key in A8_HEADER_MAP.items():
            val = session_data.get(key, "")
            if _safe_set(ws, cell_addr, val):
                filled += 1

        # ── Clasificar transacciones ─────────────────────────────────────────
        ats_pagos: list[dict] = anexo_data.get("ats_pagos_exterior") or []

        if not ats_pagos:
            warnings.append(
                "A8: sin pagos al exterior detectados en ATS XML "
                "(Tablas A, B y C vacías)"
            )
            return {"filled_cells": filled, "warnings": warnings}

        tabla_a: list[dict] = []
        tabla_b: list[dict] = []
        tabla_c: list[dict] = []

        for pago in ats_pagos:
            cat = _classify_transaction(pago)
            if cat == "A":
                tabla_a.append(pago)
            elif cat == "B":
                tabla_b.append(pago)
            else:
                tabla_c.append(pago)

        # ── Tabla A: Pagos CON CDI ───────────────────────────────────────────
        for i, pago in enumerate(tabla_a[:A8_TABLA_A_MAX_ROWS]):
            row = A8_TABLA_A_START_ROW + i
            mapped = _map_pago_to_tabla_a(pago)
            filled += _write_transaction(ws, row, A8_TABLA_A_COLS, mapped)

        if len(tabla_a) > A8_TABLA_A_MAX_ROWS:
            truncados = len(tabla_a) - A8_TABLA_A_MAX_ROWS
            warnings.append(
                f"A8 Tabla A: se truncaron {truncados} transacciones con CDI "
                f"(máximo {A8_TABLA_A_MAX_ROWS} filas disponibles en plantilla)"
            )

        # ── Tabla B: Pagos SIN CDI ───────────────────────────────────────────
        for i, pago in enumerate(tabla_b[:A8_TABLA_B_MAX_ROWS]):
            row = A8_TABLA_B_START_ROW + i
            mapped = _map_pago_to_tabla_b(pago)
            filled += _write_transaction(ws, row, A8_TABLA_B_COLS, mapped)

        if len(tabla_b) > A8_TABLA_B_MAX_ROWS:
            truncados = len(tabla_b) - A8_TABLA_B_MAX_ROWS
            warnings.append(
                f"A8 Tabla B: se truncaron {truncados} transacciones sin CDI "
                f"(máximo {A8_TABLA_B_MAX_ROWS} filas disponibles en plantilla)"
            )

        # ── Tabla C: Reembolsos vía intermediarios ───────────────────────────
        for i, pago in enumerate(tabla_c[:A8_TABLA_C_MAX_ROWS]):
            row = A8_TABLA_C_START_ROW + i
            mapped = _map_pago_to_tabla_c(pago)
            filled += _write_transaction(ws, row, A8_TABLA_C_COLS, mapped)

        if len(tabla_c) > A8_TABLA_C_MAX_ROWS:
            truncados = len(tabla_c) - A8_TABLA_C_MAX_ROWS
            warnings.append(
                f"A8 Tabla C: se truncaron {truncados} reembolsos "
                f"(máximo {A8_TABLA_C_MAX_ROWS} filas disponibles en plantilla)"
            )

        return {"filled_cells": filled, "warnings": warnings}
