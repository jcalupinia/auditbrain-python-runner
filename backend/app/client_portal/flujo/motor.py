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


def homologar_balanza(balanza: list[dict]) -> tuple[dict[str, float], list[dict]]:
    """Agrupa las filas de la balanza por su Código Super Cías (SUMIF).
    Devuelve (saldos_por_codigo, filas_sin_codigo). Las filas sin código NO se
    pierden: se devuelven aparte para que el auditor las homologue."""
    saldos: dict[str, float] = {}
    sin_codigo: list[dict] = []
    for fila in balanza:
        cod = str(fila.get("super_cias") or "").strip()
        try:
            saldo = float(fila.get("saldo") or 0.0)
        except (TypeError, ValueError):
            saldo = 0.0
        if not cod:
            sin_codigo.append(fila)
            continue
        saldos[cod] = round(saldos.get(cod, 0.0) + saldo, 2)
    return saldos, sin_codigo
