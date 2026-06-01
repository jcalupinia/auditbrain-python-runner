"""Shared helpers for ICT fillers.

Provides utilities to share data across anexos, specifically:
- aggregate_balance_by_casillero: sum saldos per casillero from balance_mapeado
- get_casillero_value: F-101 preferred, balance_mapeado fallback
- filter_balance_by_casilleros: filter balance items by casillero set
"""

from __future__ import annotations


def aggregate_balance_by_casillero(balance_mapeado: list[dict]) -> dict[str, float]:
    """Sum saldos per casillero_sri from balance_mapeado list.

    Args:
        balance_mapeado: list of {casillero_sri, codigo, descripcion, saldo}

    Returns:
        {casillero_sri: total_saldo} aggregated.
    """
    agg: dict[str, float] = {}
    for item in balance_mapeado or []:
        cas = str(item.get("casillero_sri", "")).strip()
        if not cas:
            continue
        try:
            saldo = float(item.get("saldo", 0) or 0)
        except (ValueError, TypeError):
            continue
        agg[cas] = agg.get(cas, 0.0) + saldo
    return agg


def get_casillero_value(anexo_data: dict, casillero: str, default=None):
    """Get a casillero value from F-101 (preferred) or aggregated balance_mapeado (fallback).

    Args:
        anexo_data: the merged session context (contains f101 + balance_mapeado)
        casillero: e.g. "311" or "7185"
        default: returned if neither source has the casillero

    Returns:
        float value, or `default` if absent.
    """
    casillero = str(casillero).strip()
    f101 = anexo_data.get("f101", {}) or {}
    if casillero in f101:
        return f101[casillero]
    # Try balance_mapeado fallback
    balance_agg = aggregate_balance_by_casillero(anexo_data.get("balance_mapeado", []))
    if casillero in balance_agg:
        return balance_agg[casillero]
    return default


def filter_balance_by_casilleros(balance_mapeado: list[dict], casilleros: set[str]) -> list[dict]:
    """Return balance_mapeado items whose casillero_sri is in the given set."""
    target = {str(c).strip() for c in casilleros}
    return [
        item for item in (balance_mapeado or [])
        if str(item.get("casillero_sri", "")).strip() in target
    ]
