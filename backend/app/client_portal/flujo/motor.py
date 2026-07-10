# backend/app/client_portal/flujo/motor.py
"""Motor de agrupación/homologación: totales por código con rollup y cuadre."""
from __future__ import annotations
from collections import defaultdict

from .catalogos import Nodo


def totales_por_codigo(estructura: list[Nodo], saldos: dict[str, float]) -> dict[str, float]:
    """total(codigo) = saldo exacto (SUMIF) + suma de totales de sus hijos.
    `saldos`: dict {codigo_super_cias: saldo_agrupado}. Devuelve el total por
    cada código de la estructura (con rollup jerárquico)."""
    hijos: dict[str, list[str]] = defaultdict(list)
    for n in estructura:
        if n.padre is not None:
            hijos[n.padre].append(n.codigo)

    total: dict[str, float] = {}

    def calc(cod: str) -> float:
        if cod in total:
            return total[cod]
        t = float(saldos.get(cod, 0.0))
        for h in hijos.get(cod, ()):  # hijos directos
            t += calc(h)
        total[cod] = round(t, 2)
        return total[cod]

    for n in estructura:
        calc(n.codigo)
    return total
