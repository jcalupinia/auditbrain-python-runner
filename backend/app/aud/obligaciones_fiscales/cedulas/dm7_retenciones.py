"""Cédula DM7 — Retenciones por pagar de IVA.

Consume PDFs F-104 (sección 'Agente de Retención del IVA').
Casilleros: 721 (10%), 723 (20%), 725 (30%), 727 (50%), 729 (70%),
            731 (100%), 799 (total IVA retenido).
"""

from __future__ import annotations

from pathlib import Path

from backend.app.aud.obligaciones_fiscales.cedulas import f104_extractor
from backend.app.aud.obligaciones_fiscales.cedulas.base import MESES

code = "DM7"


def expected_inputs() -> list[str]:
    # Consume F-104 (donde el SRI pone la sección Agente de Retención IVA)
    return ["f104"]


def compute_from_months(month_data: dict[str, dict]) -> dict:
    """Combina datos de los 12 meses en estructura para excel_assembler."""
    rows = []
    for i, mes in enumerate(MESES, start=1):
        key = f"{i:02d}"
        m = month_data.get(key, {})
        cas = m.get("casilleros", {}) if m else {}
        rows.append({
            "mes": mes,
            "c721": cas.get("721"),
            "c723": cas.get("723"),
            "c725": cas.get("725"),
            "c727": cas.get("727"),
            "c729": cas.get("729"),
            "c731": cas.get("731"),
            "c799": cas.get("799"),
            "has_data": bool(m),
        })
    return {
        "rows": rows,
        "total_months_with_data": sum(1 for r in rows if r["has_data"]),
    }


def compute(inputs: dict[str, list[Path]]) -> dict:
    pdfs = inputs.get("f104", []) or []
    month_data, errors = f104_extractor.extract_all_f104(pdfs)
    out = compute_from_months(month_data)
    out["errors"] = errors
    return out
