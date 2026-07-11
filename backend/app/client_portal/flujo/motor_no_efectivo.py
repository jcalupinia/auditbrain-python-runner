# backend/app/client_portal/flujo/motor_no_efectivo.py
"""Movimientos que NO son desembolso de efectivo (depreciación, amortización,
deterioro) — los add-backs de la conciliación del Estado de Flujo de Efectivo
por método indirecto.

Se calcula a partir de las totales del ERI por código (con rollup jerárquico,
igual que los demás motores) y el catálogo ``no_efectivo_eri.csv``. Cada código
del catálogo se reporta a su nivel (7 dígitos), sin solaparse con otro, de modo
que la suma directa no duplica.
"""
from __future__ import annotations
from collections import defaultdict

CATEGORIAS = ("DEPRECIACION", "AMORTIZACION", "DETERIORO")


def gastos_no_efectivo(tot_eri: dict[str, float],
                       catalogo: dict[str, str]) -> dict:
    """Suma el gasto del período de las cuentas no monetarias, por categoría.

    `tot_eri`: totales del ERI por código (salida de ``motor.totales_por_codigo``).
    `catalogo`: {codigo_eri: categoria} (salida de ``catalogos.cargar_no_efectivo``).

    Devuelve ``{categoria: monto, ..., "total": T, "detalle": {codigo: monto}}``
    incluyendo solo los códigos con monto distinto de cero en el detalle.
    """
    por_categoria: dict[str, float] = defaultdict(float)
    detalle: dict[str, float] = {}
    for cod, cat in catalogo.items():
        monto = round(float(tot_eri.get(cod, 0.0)), 2)
        por_categoria[cat] += monto
        if monto:
            detalle[cod] = monto

    resultado: dict = {c: round(por_categoria.get(c, 0.0), 2) for c in CATEGORIAS}
    # categorías fuera del set canónico (por si el catálogo agrega otra)
    for c, v in por_categoria.items():
        if c not in resultado:
            resultado[c] = round(v, 2)
    resultado["total"] = round(sum(por_categoria.values()), 2)
    resultado["detalle"] = detalle
    return resultado
