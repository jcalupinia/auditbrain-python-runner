"""Arma los pares de comparación período-a-período según el tipo de estado."""
from __future__ import annotations


def build_comparaciones(labels: list[str], tipos: list[str], estado: str) -> list[tuple[str, str]]:
    """estado='esf' → actual vs inmediatamente anterior (cadena completa).
    estado='eri' → parciales entre sí (like-for-like) + anuales encadenados."""
    pares: list[tuple[str, str]] = []
    if estado == "esf":
        for i in range(len(labels) - 1):
            pares.append((labels[i], labels[i + 1]))
        return pares
    # eri: separar por tipo, encadenar dentro de cada grupo
    parc = [labels[i] for i, t in enumerate(tipos) if t == "parcial"]
    anu = [labels[i] for i, t in enumerate(tipos) if t == "anual"]
    for i in range(len(parc) - 1):
        pares.append((parc[i], parc[i + 1]))
    for i in range(len(anu) - 1):
        pares.append((anu[i], anu[i + 1]))
    return pares
