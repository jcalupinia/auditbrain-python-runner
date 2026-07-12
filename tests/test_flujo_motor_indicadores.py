from backend.app.client_portal.flujo import motor_indicadores


def _resumen(ventas=7599669.59):
    # estructura mínima de motor_resumen.balance_resumido (solo lo que usan los indicadores)
    return {
        "er": [{"clave": "ventas_netas", "act": ventas},
               {"clave": "costo_ventas", "act": 4915407.62}],
        "esf": [{"clave": "cuentas_cobrar", "act": 1695733.71},
                {"clave": "cuentas_pagar", "act": 1237442.89},
                {"clave": "obligaciones_financieras", "act": 7466.49}],
    }


def test_indicadores():
    tot_esf = {"1": 6544486.99, "101": 5739385.18, "10103": 2824704.20,
               "2": -2152117.90, "201": -1500000.0, "202": -70641.33, "3": -4392369.09}
    eri = {"utilidad_neta": 340112.95, "utilidad_operativa": 572030.73}
    r = motor_indicadores.indicadores(tot_esf, eri, resumen=_resumen())
    assert r["razon_corriente"] == round(5739385.18/1500000.0, 4)
    assert r["capital_trabajo"] == round(5739385.18-1500000.0, 2)
    assert r["endeudamiento_total"] == round(2152117.90/6544486.99, 4)
    # Margen neto ahora sobre VENTAS NETAS (no ingresos totales)
    assert r["margen_neto"] == round(340112.95/7599669.59, 4)
    assert r["roe"] == round(340112.95/4392369.09, 4)
    # Apalancamiento = Activos / Patrimonio (corregido); D/E es endeud. patrimonial
    assert r["apalancamiento"] == round(6544486.99/4392369.09, 4)
    assert r["endeudamiento_patrimonial"] == round(2152117.90/4392369.09, 4)
    # Prueba ácida = (Act. corriente − Inventarios) / Pasivo corriente
    assert r["prueba_acida"] == round((5739385.18-2824704.20)/1500000.0, 4)


def test_division_por_cero_devuelve_cero():
    r = motor_indicadores.indicadores({"1": 0.0, "101": 0.0, "2": 0.0, "201": 0.0, "3": 0.0},
                                      {"utilidad_neta": 0.0})
    assert r["razon_corriente"] == 0.0 and r["roe"] == 0.0 and r["apalancamiento"] == 0.0
