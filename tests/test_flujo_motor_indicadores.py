from backend.app.client_portal.flujo import motor_indicadores


def test_indicadores():
    tot_esf = {"1": 6544486.99, "101": 5739385.18, "2": -2152117.90, "201": -1500000.0, "3": -4392369.09}
    eri = {"utilidad_neta": 340112.95, "_ingresos_totales": 7813472.11, "ganancia_bruta": 2684261.97, "utilidad_operativa": 572030.73}
    r = motor_indicadores.indicadores(tot_esf, eri)
    assert r["razon_corriente"] == round(5739385.18/1500000.0, 4)
    assert r["capital_trabajo"] == round(5739385.18-1500000.0, 2)
    assert r["endeudamiento_total"] == round(2152117.90/6544486.99, 4)
    assert r["margen_neto"] == round(340112.95/7813472.11, 4)
    assert r["roe"] == round(340112.95/4392369.09, 4)


def test_division_por_cero_devuelve_cero():
    r = motor_indicadores.indicadores({"1": 0.0, "101": 0.0, "2": 0.0, "201": 0.0, "3": 0.0},
                                      {"utilidad_neta": 0.0, "_ingresos_totales": 0.0})
    assert r["razon_corriente"] == 0.0 and r["roe"] == 0.0
