"""Cédula DM6 — IVA.

Consume PDFs F-104 (Declaración de IVA).
Casilleros principales para llenar las columnas C, D, E de la plantilla DM6:
- C "Ventas tarifa 0% c/ derecho" = casillero 415 (ventas locales) — para M1.
  Si el auditor también quiere sumar 416 (activos fijos c/ derecho), edita
  manualmente. Mantenemos lo más simple.
- D "Ventas tarifa 0% s/ derecho" = casillero 413
- E "Exportaciones" = casillero 417
"""

from __future__ import annotations

from pathlib import Path

from backend.app.aud.obligaciones_fiscales.cedulas import f104_extractor
from backend.app.aud.obligaciones_fiscales.cedulas.base import MESES

code = "DM6"


def expected_inputs() -> list[str]:
    return ["f104"]


def compute_from_months(month_data: dict[str, dict]) -> dict:
    """Combina datos de los 12 meses en estructura para excel_assembler.

    Las claves c411/c412/etc. corresponden 1:1 a casilleros del F-104.
    excel_assembler decide en qué columnas del Excel escribir cada uno.
    """
    rows = []
    for i, mes in enumerate(MESES, start=1):
        key = f"{i:02d}"
        m = month_data.get(key, {})
        cas = m.get("casilleros", {}) if m else {}
        rows.append({
            "mes": mes,
            # Casilleros que poblamos en M1 (columnas C, D, E del DM6):
            "c411": cas.get("411"),     # Ventas locales tarifa diferente de 0
            "c412": cas.get("412"),     # Ventas activos fijos
            "c413": cas.get("413"),     # Ventas locales tarifa 0% s/ derecho
            "c414": cas.get("414"),
            "c415": cas.get("415"),     # Ventas locales tarifa 0% c/ derecho
            "c416": cas.get("416"),
            "c417": cas.get("417"),     # Exportaciones bienes
            "c418": cas.get("418"),     # Exportaciones servicios
            "c419": cas.get("419"),     # Total ventas tarifa diferente de 0
            "c421": cas.get("421"),     # IVA bruto
            "c429": cas.get("429"),     # IVA generado en ventas
            "c480": cas.get("480"),     # Adquisiciones tarifa diferente de 0
            "c499": cas.get("499"),     # Total impuesto a liquidar
            "c529": cas.get("529"),     # Total adquisiciones
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
