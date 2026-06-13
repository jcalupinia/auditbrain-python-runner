"""Regression test: cas 850 / cas 888 son condicionales en A1 (cliente
ICT_20, 2026-06-13).

Regla:
  - Si la empresa MAPEO cas 888 (IR Corriente) a una cuenta del balance
    con saldo != 0 → mostrar cas 888 en A1, ocultar cas 850.
  - Si NO mapeó cas 888 → mostrar cas 850 (IR Causado calculado del F-101)
    como fallback, ocultar cas 888.

Razon: la empresa puede registrar el gasto del impuesto bajo cas 888
(Impuesto Renta CORRIENTE — el efectivamente pagado) o bajo cas 850
(Impuesto Renta CAUSADO — el calculado tributariamente). Si ambos
aparecen en A1, se duplica la informacion del impuesto.
"""
from __future__ import annotations

import openpyxl
import pytest


def _find_cas_row(ws, cas_buscado: str) -> int | None:
    for r in range(13, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if v and str(v).strip() == cas_buscado:
            return r
    return None


def _build_wb_con_888_mapeado(saldo_888: float):
    """Genera ICT con cas 888 mapeado a una cuenta balance con saldo dado."""
    from openpyxl import Workbook
    from backend.app.ict.cell_maps.a1 import A1_SHEET
    from backend.app.ict.fillers.a1_mapeo import A1Filler
    from backend.app.ict.fillers.source_data_sheets import build_f101_sheet

    wb = Workbook()
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]
    wb.create_sheet(A1_SHEET)
    f101_data = {
        "6001": 5000.0, "7001": 2000.0, "801": 3000.0, "803": 300.0,
        "850": 700.0,  # IR causado declarado
        "888": saldo_888 if saldo_888 != 0 else 0,  # IR corriente
        "889": 100.0,
    }
    f101_lookup = build_f101_sheet(wb, f101_data, {})

    balance = []
    if saldo_888 != 0:
        balance.append({
            "casillero_sri": "888", "codigo": "BAL888",
            "descripcion": "GASTO IR CORRIENTE", "saldo": saldo_888,
        })

    filler = A1Filler()
    session_data = {"razon_social": "TEST", "ruc": "T",
                    "ejercicio_fiscal": "2025", "numero_adhesivo": ""}
    anexo_data = {
        "f101": f101_data,
        "balance_mapeado": balance,
        "_f101_lookup": f101_lookup,
        "_balance_lookup": [],
    }
    filler.fill(wb, session_data, anexo_data)
    return wb


def test_cas_888_aparece_si_tiene_cuenta_balance():
    """Cuando empresa mapea cas 888 a cuenta balance → cas 888 aparece, 850 NO."""
    from backend.app.ict.cell_maps.a1 import A1_SHEET
    wb = _build_wb_con_888_mapeado(saldo_888=500.0)
    ws = wb[A1_SHEET]

    row_888 = _find_cas_row(ws, "888")
    row_850 = _find_cas_row(ws, "850")

    assert row_888 is not None, "cas 888 debe aparecer cuando tiene cuenta balance"
    assert row_850 is None, "cas 850 NO debe aparecer cuando cas 888 esta mapeado"


def test_cas_850_aparece_si_cas_888_no_esta_mapeado():
    """Cuando empresa NO mapea cas 888 → cas 850 aparece como fallback, 888 NO."""
    from backend.app.ict.cell_maps.a1 import A1_SHEET
    wb = _build_wb_con_888_mapeado(saldo_888=0)
    ws = wb[A1_SHEET]

    row_888 = _find_cas_row(ws, "888")
    row_850 = _find_cas_row(ws, "850")

    assert row_850 is not None, (
        "cas 850 debe aparecer como fallback cuando cas 888 no esta mapeado"
    )
    assert row_888 is None, (
        "cas 888 NO debe aparecer si no tiene cuenta balance"
    )


def test_nunca_aparecen_ambos_simultaneamente():
    """Cas 850 y cas 888 son MUTUAMENTE EXCLUYENTES en A1 — nunca aparecen ambos."""
    from backend.app.ict.cell_maps.a1 import A1_SHEET

    for saldo in [500.0, 0]:
        wb = _build_wb_con_888_mapeado(saldo_888=saldo)
        ws = wb[A1_SHEET]
        row_888 = _find_cas_row(ws, "888")
        row_850 = _find_cas_row(ws, "850")
        assert not (row_888 and row_850), (
            f"Con saldo_888={saldo}: cas 888 y 850 NUNCA deben aparecer "
            f"juntos (encontrado: 888={row_888}, 850={row_850})"
        )
