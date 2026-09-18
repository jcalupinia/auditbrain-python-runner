"""Bandas de mora de la matriz de pérdidas esperadas.

La mora se cuenta desde la fecha de vencimiento contractual. Una factura cuyo
vencimiento es posterior o igual a la fecha de corte está POR VENCER y nunca cae
en el primer tramo de mora.
"""
from __future__ import annotations

from typing import Any

BANDA_POR_VENCER = "Por vencer"

BANDAS_POR_DEFECTO: list[dict[str, Any]] = [
    {"nombre": BANDA_POR_VENCER, "desde": None, "hasta": 0, "origen": BANDA_POR_VENCER},
    {"nombre": "0 a 30 días", "desde": 1, "hasta": 30, "origen": "0 a 30 días"},
    {"nombre": "31 a 60 días", "desde": 31, "hasta": 60, "origen": "31 a 60 días"},
    {"nombre": "61 a 90 días", "desde": 61, "hasta": 90, "origen": "61 a 90 días"},
    {"nombre": "91 a 180 días", "desde": 91, "hasta": 180, "origen": "91 a 180 días"},
    {"nombre": "181 a 360 días", "desde": 181, "hasta": 360, "origen": "181 a 360 días"},
    {"nombre": "Más de 360 días", "desde": 361, "hasta": None, "origen": "Más de 360 días"},
]


def clasificar(dias: int, bandas: list[dict[str, Any]]) -> str:
    """Devuelve el nombre de la banda que corresponde a esos días de mora."""
    if dias <= 0:
        for b in bandas:
            if b["desde"] is None:
                return b["nombre"]
    for b in bandas:
        if b["desde"] is None:
            continue
        if dias >= b["desde"] and (b["hasta"] is None or dias <= b["hasta"]):
            return b["nombre"]
    raise ValueError(f"No hay banda definida para {dias} días de mora")


def desdoblar(bandas: list[dict[str, Any]], umbral_dias: int) -> list[dict[str, Any]]:
    """Parte la banda abierta en el umbral de incumplimiento.

    Una banda abierta mezcla cartera todavía gestionable con cartera perdida; el
    desdoblamiento separa las dos antes de calcular. Cada mitad conserva el nombre
    de la banda de la que proviene para poder compararla con la política del cliente.
    """
    ultima = bandas[-1]
    if ultima["hasta"] is not None or ultima["desde"] is None or umbral_dias <= ultima["desde"]:
        return bandas
    return bandas[:-1] + [
        {"nombre": f"{ultima['desde']} a {umbral_dias} días", "desde": ultima["desde"],
         "hasta": umbral_dias, "origen": ultima["nombre"]},
        {"nombre": f"Más de {umbral_dias} días", "desde": umbral_dias + 1,
         "hasta": None, "origen": ultima["nombre"]},
    ]
