from backend.app.client_portal.flujo import motor_er


def test_cascada_resultados():
    tot = {"401": 7599669.59, "403": 213802.52, "501": 4915407.62, "502": 2326033.76,
           "601": 85846.32, "603": 149203.28, "605": 0.0, "606": 3131.82, "800": 2957.70}
    r = motor_er.cascada_resultados(tot)
    assert r["ganancia_bruta"] == 2684261.97
    assert r["utilidad_operativa"] == 572030.73
    assert r["utilidad_antes_ir"] == 486184.41
    assert r["utilidad_operaciones"] == 336981.13
    assert r["utilidad_neta"] == 340112.95
    assert r["resultado_integral"] == 343070.65


def test_cascada_con_codigos_faltantes_usa_cero():
    r = motor_er.cascada_resultados({"401": 1000.0, "501": 400.0})
    assert r["ganancia_bruta"] == 600.0
    assert r["utilidad_neta"] == 600.0
