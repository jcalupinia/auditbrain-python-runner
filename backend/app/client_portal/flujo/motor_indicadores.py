# backend/app/client_portal/flujo/motor_indicadores.py
"""Indicadores financieros a partir de los totales del ESF y la cascada del ER.

Convenciones de signo del ESF (plan Superintendencia): Activo (código "1") es
POSITIVO; Pasivo ("2") y Patrimonio ("3") vienen en NEGATIVO (crédito) → se
presentan en positivo con ``abs()``.
"""

from __future__ import annotations


def _safe_div(a: float, b: float) -> float:
    """División segura: devuelve 0.0 si el divisor es 0."""
    if not b:
        return 0.0
    return a / b


def indicadores(tot_esf: dict[str, float], eri: dict) -> dict:
    """Calcula los indicadores financieros clásicos (liquidez, endeudamiento,
    apalancamiento y rentabilidad) a partir de los totales por código del ESF
    y del dict de cascada del ER (salida de ``motor_er.cascada_resultados``).

    Args:
        tot_esf: totales por código Super Cías del Estado de Situación
            Financiera (salida de ``motor.totales_por_codigo``).
        eri: cascada de resultados del ER, con al menos las claves
            ``utilidad_neta`` y ``_ingresos_totales``.

    Returns:
        dict con los montos base y los ratios derivados (ratios redondeados a
        4 decimales, montos a 2 decimales).
    """
    activo_total = tot_esf.get("1", 0.0)
    activo_corriente = tot_esf.get("101", 0.0)
    pasivo_total = abs(tot_esf.get("2", 0.0))
    pasivo_corriente = abs(tot_esf.get("201", 0.0))
    patrimonio = abs(tot_esf.get("3", 0.0))

    utilidad_neta = eri.get("utilidad_neta", 0.0)
    ingresos_totales = eri.get("_ingresos_totales", 0.0)

    razon_corriente = _safe_div(activo_corriente, pasivo_corriente)
    capital_trabajo = activo_corriente - pasivo_corriente
    endeudamiento_total = _safe_div(pasivo_total, activo_total)
    apalancamiento = _safe_div(pasivo_total, patrimonio)
    margen_neto = _safe_div(utilidad_neta, ingresos_totales)
    roa = _safe_div(utilidad_neta, activo_total)
    roe = _safe_div(utilidad_neta, patrimonio)

    return {
        "activo_total": round(activo_total, 2),
        "activo_corriente": round(activo_corriente, 2),
        "pasivo_total": round(pasivo_total, 2),
        "pasivo_corriente": round(pasivo_corriente, 2),
        "patrimonio": round(patrimonio, 2),
        "razon_corriente": round(razon_corriente, 4),
        "capital_trabajo": round(capital_trabajo, 2),
        "endeudamiento_total": round(endeudamiento_total, 4),
        "apalancamiento": round(apalancamiento, 4),
        "margen_neto": round(margen_neto, 4),
        "roa": round(roa, 4),
        "roe": round(roe, 4),
    }
