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


def cuadre(totales: dict[str, float], tolerancia: float = 1.0) -> dict:
    """Verifica Activo = Pasivo + Patrimonio. En el plan Superintendencia,
    Activo es sección '1' (signo +), Pasivo '2' y Patrimonio '3' (crédito, −).
    Se presenta P+Pat en positivo. Cuadra si |dif| ≤ tolerancia."""
    activo = round(float(totales.get("1", 0.0)), 2)
    pas_pat = round(-(float(totales.get("2", 0.0)) + float(totales.get("3", 0.0))), 2)
    dif = round(activo - pas_pat, 2)
    return {
        "activo": activo,
        "pasivo_mas_patrimonio": pas_pat,
        "diferencia": dif,
        "cuadra": abs(dif) <= tolerancia,
    }
