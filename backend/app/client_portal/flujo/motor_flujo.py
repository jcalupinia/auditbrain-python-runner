# backend/app/client_portal/flujo/motor_flujo.py
"""Estado de Flujo de Efectivo por método indirecto a partir de las totales del ESF."""
from __future__ import annotations
from collections import defaultdict

PREFIJO_EFECTIVO = "10101"  # Efectivo y equivalentes (plan Superintendencia)


def variaciones(tot_ant: dict[str, float], tot_act: dict[str, float]) -> dict[str, float]:
    """variación por código = total año actual − total año anterior."""
    codes = set(tot_ant) | set(tot_act)
    return {c: round(float(tot_act.get(c, 0.0)) - float(tot_ant.get(c, 0.0)), 2) for c in codes}


def clasificar_flujo(variaciones: dict[str, float], clasificacion: dict[str, str],
                     excluir_prefijo: str = PREFIJO_EFECTIVO) -> dict[str, float]:
    """Agrupa el impacto de cada cuenta por actividad. Impacto = −variación
    (un aumento de activo es uso de efectivo). Excluye el efectivo mismo."""
    act: dict[str, float] = defaultdict(float)
    for cod, var in variaciones.items():
        if cod.startswith(excluir_prefijo):
            continue
        a = clasificacion.get(cod)
        if a is None:
            continue
        act[a] += -float(var)
    return {k: round(v, 2) for k, v in act.items()}
