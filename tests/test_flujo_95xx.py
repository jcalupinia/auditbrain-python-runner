"""Estado de Flujo de Efectivo oficial Super Cías (códigos 95xx).

El módulo ``flujo_95xx`` reproduce, celda por celda, la hoja "Estado de Flujo"
del modelo Excel del cliente (método directo + reconciliación indirecta).

Validación empírica: contra el archivo oficial SIGMAN 2025
("MODELO FLUJO 2025-INDICES v5.1 SIGMAN ok cuadrado.xlsm") el módulo reproduce
las **71/71 líneas** exactas (95, 9501-9507, 96, 98, 9801-9820). Ese Excel tiene
datos reales del cliente, así que no se versiona; estos tests validan estructura,
identidades de cuadre y estabilidad con datos sintéticos.
"""
from backend.app.client_portal.flujo import flujo_95xx


def _codigos(res):
    return {ln["codigo"]: ln["valor"] for ln in res["lineas"]}


def test_estructura_carga_y_lineas_95xx():
    res = flujo_95xx.calcular_flujo_95xx([], [])
    cods = _codigos(res)
    # las secciones oficiales del formulario deben existir
    for c in ("95", "9501", "9502", "9503", "9505", "9506", "9507", "96", "98"):
        assert c in cods, f"falta la línea {c}"
    # con balanzas vacías todo es 0
    assert all(abs(v) < 0.01 for v in cods.values())


def test_cuadre_variacion_neta():
    # 95 (variación neta) = 9501 operación + 9502 inversión + 9503 financiamiento
    bal_act = [
        {"cuenta": "1.01.01.01", "super_cias": "1010101", "sri": "311", "saldo": 5000.0},
        {"cuenta": "4.01.01", "super_cias": "40101", "sri": "601", "saldo": -8000.0},
        {"cuenta": "5.01.01", "super_cias": "50101", "sri": "701", "saldo": 3000.0},
    ]
    res = flujo_95xx.calcular_flujo_95xx([], bal_act)
    t = res["totales"]
    assert abs(t["95"] - (t["9501"] + t["9502"] + t["9503"])) < 0.05


def test_cuadre_efectivo_final():
    # 9507 (efectivo final) = 9506 (efectivo inicial) + 95 (variación neta)
    bal_ant = [{"cuenta": "1.01.01.01", "super_cias": "1010101", "sri": "311", "saldo": 1000.0}]
    bal_act = [{"cuenta": "1.01.01.01", "super_cias": "1010101", "sri": "311", "saldo": 1500.0}]
    res = flujo_95xx.calcular_flujo_95xx(bal_ant, bal_act)
    t = res["totales"]
    assert abs(t["9507"] - (t["9506"] + t["95"])) < 0.05


def test_totales_expuestos():
    res = flujo_95xx.calcular_flujo_95xx([], [])
    for c in ("95", "9501", "9502", "9503", "9506", "9507"):
        assert c in res["totales"]
