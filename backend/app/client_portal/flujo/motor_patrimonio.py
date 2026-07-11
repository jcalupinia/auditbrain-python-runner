# backend/app/client_portal/flujo/motor_patrimonio.py
"""Estado de Evolución del Patrimonio a nivel de componente.

Convenciones de signo del ESF (plan Superintendencia): Patrimonio (código
"3xx") viene en NEGATIVO (crédito) → se presenta en positivo con ``abs()``.
"""

from __future__ import annotations

CODIGOS = {
    "301": "capital",
    "302": "aportes_socios",
    "303": "prima_emision",
    "304": "reservas",
    "305": "otros_resultados_integrales",
    "306": "resultados_acumulados",
    "307": "resultado_ejercicio",
}


def evolucion(tot_ant: dict[str, float], tot_act: dict[str, float]) -> dict:
    """Evolución del patrimonio por componente: saldo inicial/final y variación.

    Patrimonio viene en negativo (crédito) → se presenta en positivo con
    ``abs()``.

    Args:
        tot_ant: totales por código Super Cías del ESF del año anterior
            (salida de ``motor.totales_por_codigo``).
        tot_act: totales por código Super Cías del ESF del año actual.

    Returns:
        dict con una clave por componente (``capital``, ``aportes_socios``,
        ``prima_emision``, ``reservas``, ``otros_resultados_integrales``,
        ``resultados_acumulados``, ``resultado_ejercicio``) más
        ``total_patrimonio``, cada una con ``codigo``, ``saldo_inicial``,
        ``saldo_final`` y ``variacion``.
    """
    componentes = {}
    for cod, nombre in CODIGOS.items():
        ini = round(abs(float(tot_ant.get(cod, 0.0))), 2)
        fin = round(abs(float(tot_act.get(cod, 0.0))), 2)
        componentes[nombre] = {
            "codigo": cod,
            "saldo_inicial": ini,
            "saldo_final": fin,
            "variacion": round(fin - ini, 2),
        }
    tot_ini = round(abs(float(tot_ant.get("3", 0.0))), 2)
    tot_fin = round(abs(float(tot_act.get("3", 0.0))), 2)
    componentes["total_patrimonio"] = {
        "codigo": "3",
        "saldo_inicial": tot_ini,
        "saldo_final": tot_fin,
        "variacion": round(tot_fin - tot_ini, 2),
    }
    return componentes
