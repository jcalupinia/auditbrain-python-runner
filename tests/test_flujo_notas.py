"""Notas a los Estados Financieros — desglose por rubro (motor_notas).

Verifica que cada nota agrupe las cuentas hoja de su rubro y que el subtotal
cuadre con el rollup del rubro. Validación empírica: contra el archivo SIGMAN
la nota de efectivo (10101) da 1.352.440,67 (ant) / 1.080.134,58 (act).
"""
from backend.app.client_portal.flujo import catalogos, motor, motor_notas


def _tot(estado, balanza):
    est = catalogos.cargar_estructura(estado)
    saldos, _ = motor.homologar_balanza(balanza)
    return est, motor.totales_por_codigo(est, saldos)


def test_nota_agrupa_hojas_y_subtotal_cuadra():
    bal_ant = [
        {"cuenta": "1.01.01.01", "super_cias": "1010101", "sri": "311", "saldo": 100.0},
        {"cuenta": "1.01.01.03", "super_cias": "1010103", "sri": "311", "saldo": 900.0},
    ]
    bal_act = [
        {"cuenta": "1.01.01.01", "super_cias": "1010101", "sri": "311", "saldo": 150.0},
        {"cuenta": "1.01.01.03", "super_cias": "1010103", "sri": "311", "saldo": 950.0},
    ]
    e_esf, ta = _tot("esf", bal_ant)
    _, tc = _tot("esf", bal_act)
    e_eri, tia = _tot("eri", bal_ant)
    _, tic = _tot("eri", bal_act)

    notas = motor_notas.notas_estados(e_esf, e_eri, ta, tc, tia, tic)
    # existe la nota del efectivo (10101)
    efectivo = next(n for n in notas["esf"] if n["codigo"] == "10101")
    assert efectivo["total_ant"] == 1000.0
    assert efectivo["total_act"] == 1100.0
    # el subtotal = suma de las filas de detalle (ambos años)
    assert round(sum(f["ant"] for f in efectivo["filas"]), 2) == efectivo["total_ant"]
    assert round(sum(f["act"] for f in efectivo["filas"]), 2) == efectivo["total_act"]
    # solo lista cuentas con saldo (2 cuentas, no todo el plan)
    assert len(efectivo["filas"]) == 2


def test_no_incluye_rubros_en_cero():
    bal = [{"cuenta": "1.01.01.01", "super_cias": "1010101", "sri": "311", "saldo": 50.0}]
    e_esf, ta = _tot("esf", bal)
    e_eri, tia = _tot("eri", bal)
    notas = motor_notas.notas_estados(e_esf, e_eri, ta, ta, tia, tia)
    # todas las notas ESF tienen saldo ≠ 0 en algún año
    for n in notas["esf"]:
        assert n["total_ant"] or n["total_act"]
    # sin ingresos/gastos → sin notas ERI
    assert notas["eri"] == []
