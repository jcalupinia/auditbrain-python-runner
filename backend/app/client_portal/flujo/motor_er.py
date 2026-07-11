"""Cascada de subtotales del Estado de Resultados Integral (ERI).

Toma los totales por código Super Cías del ERI (ya calculados por
``motor.totales_por_codigo`` sobre la estructura ERI) y deriva la secuencia
contable de subtotales: ganancia bruta, utilidad operativa, utilidad antes de
IR, utilidad de operaciones, utilidad neta y resultado integral.
"""

from __future__ import annotations


def cascada_resultados(tot_eri: dict[str, float]) -> dict:
    """Calcula la cascada de subtotales del ER a partir de los totales por código.

    Args:
        tot_eri: totales por código Super Cías del Estado de Resultados
            (salida de ``motor.totales_por_codigo`` sobre la estructura ERI).

    Returns:
        dict con los códigos base (redondeados a 2 decimales) y los
        subtotales derivados de la cascada contable.
    """
    ingresos_ordinarios = tot_eri.get("401", 0.0)
    otros_ingresos = tot_eri.get("403", 0.0)
    costo_ventas = tot_eri.get("501", 0.0)
    gastos = tot_eri.get("502", 0.0)
    participacion = tot_eri.get("601", 0.0)
    impuesto_renta = tot_eri.get("603", 0.0)
    gasto_imp_diferido = tot_eri.get("605", 0.0)
    ingreso_imp_diferido = tot_eri.get("606", 0.0)
    otro_resultado_integral = tot_eri.get("800", 0.0)

    ganancia_bruta = ingresos_ordinarios - costo_ventas
    utilidad_operativa = ingresos_ordinarios + otros_ingresos - costo_ventas - gastos
    utilidad_antes_ir = utilidad_operativa - participacion
    utilidad_operaciones = utilidad_antes_ir - impuesto_renta
    utilidad_neta = utilidad_operaciones - gasto_imp_diferido + ingreso_imp_diferido
    resultado_integral = utilidad_neta + otro_resultado_integral

    return {
        "ingresos_ordinarios": round(ingresos_ordinarios, 2),
        "otros_ingresos": round(otros_ingresos, 2),
        "costo_ventas": round(costo_ventas, 2),
        "gastos": round(gastos, 2),
        "participacion": round(participacion, 2),
        "impuesto_renta": round(impuesto_renta, 2),
        "gasto_imp_diferido": round(gasto_imp_diferido, 2),
        "ingreso_imp_diferido": round(ingreso_imp_diferido, 2),
        "otro_resultado_integral": round(otro_resultado_integral, 2),
        "ganancia_bruta": round(ganancia_bruta, 2),
        "utilidad_operativa": round(utilidad_operativa, 2),
        "utilidad_antes_ir": round(utilidad_antes_ir, 2),
        "utilidad_operaciones": round(utilidad_operaciones, 2),
        "utilidad_neta": round(utilidad_neta, 2),
        "resultado_integral": round(resultado_integral, 2),
    }
