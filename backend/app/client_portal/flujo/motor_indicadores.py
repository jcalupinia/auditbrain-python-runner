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


def indicadores(tot_esf: dict[str, float], eri: dict,
                resumen: dict | None = None,
                no_efectivo: dict | None = None,
                tot_esf_ant: dict | None = None) -> dict:
    """Indicadores financieros (liquidez, actividad, endeudamiento y rentabilidad)
    alineados con el dashboard del modelo SIGMAN.

    Args:
        tot_esf: totales por código del ESF (año actual).
        eri: cascada del ER (``utilidad_neta``, ``utilidad_operativa``).
        resumen: salida de ``motor_resumen.balance_resumido`` (para ventas netas,
            costo, cuentas por cobrar/pagar, obligaciones financieras).
        no_efectivo: salida de ``motor_no_efectivo.gastos_no_efectivo``
            (depreciación + amortización para el EBITDA).
        tot_esf_ant: totales del ESF del año anterior (para inventario/CxC
            promedio en los indicadores de actividad).
    """
    activo_total = tot_esf.get("1", 0.0)
    activo_corriente = tot_esf.get("101", 0.0)
    inventarios = tot_esf.get("10103", 0.0)
    pasivo_total = abs(tot_esf.get("2", 0.0))
    pasivo_corriente = abs(tot_esf.get("201", 0.0))
    pasivo_no_corriente = abs(tot_esf.get("202", 0.0))
    patrimonio = abs(tot_esf.get("3", 0.0))

    utilidad_neta = eri.get("utilidad_neta", 0.0)
    utilidad_operativa = eri.get("utilidad_operativa", 0.0)

    # Líneas del balance resumido (año actual) para los indicadores de actividad.
    er = {f["clave"]: f["act"] for f in resumen["er"]} if resumen else {}
    esf_r = {f["clave"]: f["act"] for f in resumen["esf"]} if resumen else {}
    ventas_netas = er.get("ventas_netas", 0.0)
    costo_ventas = er.get("costo_ventas", 0.0)
    cuentas_cobrar = esf_r.get("cuentas_cobrar", 0.0)
    cuentas_pagar = esf_r.get("cuentas_pagar", 0.0)
    oblig_financieras = esf_r.get("obligaciones_financieras", 0.0)

    inv_prom = inventarios
    if tot_esf_ant is not None:
        inv_prom = round((inventarios + tot_esf_ant.get("10103", 0.0)) / 2, 2)

    dep = (no_efectivo or {}).get("DEPRECIACION", 0.0)
    amort = (no_efectivo or {}).get("AMORTIZACION", 0.0)

    dias_cartera = _safe_div(cuentas_cobrar, ventas_netas) * 365
    dias_inventario = _safe_div(inv_prom, costo_ventas) * 365
    dias_proveedores = _safe_div(cuentas_pagar, costo_ventas) * 365

    return {
        # montos base
        "activo_total": round(activo_total, 2),
        "activo_corriente": round(activo_corriente, 2),
        "pasivo_total": round(pasivo_total, 2),
        "pasivo_corriente": round(pasivo_corriente, 2),
        "patrimonio": round(patrimonio, 2),
        "capital_trabajo": round(activo_corriente - pasivo_corriente, 2),
        # liquidez
        "razon_corriente": round(_safe_div(activo_corriente, pasivo_corriente), 4),
        "prueba_acida": round(_safe_div(activo_corriente - inventarios, pasivo_corriente), 4),
        # actividad
        "dias_cartera": round(dias_cartera, 2),
        "dias_inventario": round(dias_inventario, 2),
        "dias_proveedores": round(dias_proveedores, 2),
        "ciclo_efectivo": round(dias_cartera + dias_inventario - dias_proveedores, 2),
        "eficiencia_activos": round(_safe_div(ventas_netas, activo_total), 4),
        # endeudamiento
        "endeudamiento_total": round(_safe_div(pasivo_total, activo_total), 4),
        "endeudamiento_lp": round(_safe_div(pasivo_no_corriente, activo_total), 4),
        "endeudamiento_financiero": round(_safe_div(oblig_financieras, patrimonio), 4),
        "endeudamiento_patrimonial": round(_safe_div(pasivo_total, patrimonio), 4),
        "apalancamiento": round(_safe_div(activo_total, patrimonio), 4),
        # rentabilidad
        "roi": round(_safe_div(utilidad_operativa, activo_total), 4),
        "margen_operativo": round(_safe_div(utilidad_operativa, ventas_netas), 4),
        "roe": round(_safe_div(utilidad_neta, patrimonio), 4),
        "margen_neto": round(_safe_div(utilidad_neta, ventas_netas), 4),
        "roa": round(_safe_div(utilidad_neta, activo_total), 4),
        "ebit": round(utilidad_operativa, 2),
        "ebitda": round(utilidad_operativa + dep + amort, 2),
    }
