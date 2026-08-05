"""Catálogo de categorías fiscales.

Esta es la SEMILLA de sistema. En el Plan 2 el catálogo pasa a ser
configurable por organización en base de datos, tomando estas entradas como
valores iniciales.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Categoria:
    codigo: str
    nombre: str
    naturaleza_esperada: str  # activo | pasivo | ingreso | gasto
    orden: int


CATEGORIAS: dict[str, Categoria] = {
    c.codigo: c
    for c in (
        Categoria("IVA_COMPRAS", "IVA en compras", "activo", 1),
        Categoria("IVA_RETENIDO", "IVA retenido por clientes", "activo", 2),
        Categoria("IVA_VENTAS", "IVA en ventas", "pasivo", 3),
        Categoria("IVA_DIFERIDO", "IVA diferido", "pasivo", 4),
        Categoria("RET_RENTA", "Retenciones en la fuente de renta por pagar", "pasivo", 5),
        Categoria("RET_IVA", "Retenciones de IVA por pagar", "pasivo", 6),
        Categoria("VENTAS", "Ventas", "ingreso", 7),
    )
}

_NATURALEZA_POR_DIGITO = {
    "1": "activo", "2": "pasivo", "3": "patrimonio",
    "4": "ingreso", "5": "gasto", "6": "gasto",
}


def naturaleza_por_codigo(codigo: str) -> str | None:
    """Naturaleza contable según el primer dígito del código de cuenta."""
    primero = (codigo or "").strip()[:1]
    return _NATURALEZA_POR_DIGITO.get(primero)


def categorias_por_naturaleza(naturaleza: str | None) -> list[str]:
    if not naturaleza:
        return []
    return [c.codigo for c in CATEGORIAS.values() if c.naturaleza_esperada == naturaleza]
