from backend.app.client_portal.flujo import motor_f101


def test_casilleros_agrupa_por_sri():
    balanza = [
        {"sri": "311", "saldo": 100.0},
        {"sri": "311", "saldo": 50.0},
        {"sri": "312", "saldo": 200.0},
        {"sri": "", "saldo": 9.0},
    ]
    cas = motor_f101.casilleros_f101(balanza)
    assert cas == {"311": 150.0, "312": 200.0}


def test_generar_xml_101():
    xml = motor_f101.generar_xml_101({"312": 200.0, "311": 150.0, "313": 0.0})
    assert "<detalleDeclaracion>" in xml and "</detalleDeclaracion>" in xml
    assert '<campo codigo="311">150.00</campo>' in xml
    assert '<campo codigo="312">200.00</campo>' in xml
    assert '313' not in xml  # valor 0 se omite
    # orden ascendente: 311 antes que 312
    assert xml.index('"311"') < xml.index('"312"')


def test_casilleros_completos_resuelve_agregados():
    from backend.app.client_portal.flujo import motor_f101
    balanza = [{"sri": "449", "saldo": 800.0}, {"sri": "361", "saldo": 5000.0}]
    agregados = {"499": ["+449", "+361"], "699": ["+499"]}
    r = motor_f101.casilleros_completos(balanza, agregados)
    assert r["449"] == 800.0
    assert r["361"] == 5000.0
    assert r["499"] == 5800.0     # 449 + 361
    assert r["699"] == 5800.0     # = 499 (agregado de agregado)


def test_casilleros_completos_con_extras_y_resta():
    from backend.app.client_portal.flujo import motor_f101
    r = motor_f101.casilleros_completos([], {"801": ["+6999", "-7999"]},
                                        extras={"6999": 7813.0, "7999": 7241.0})
    assert r["801"] == 572.0      # 6999 - 7999


def test_ori_del_periodo_reclass_actuarial():
    # Casillero 885 (Otro resultado integral del año) = movimiento OCI del período =
    # variación de las cuentas actuariales reclasificadas a patrimonio (30505).
    # Se identifican por CÓDIGO DE CUENTA (Super Cías 30601, pero son OCI). Datos SIGMAN.
    bal_ant = [{"cuenta": "3.02.03.01.002", "saldo": -150453.66},
               {"cuenta": "3.02.03.01.003", "saldo": 40954.69},
               {"cuenta": "1.01.01", "saldo": 999.0}]   # ruido: no ORI
    bal_act = [{"cuenta": "3.02.03.01.002", "saldo": -147076.22},
               {"cuenta": "3.02.03.01.003", "saldo": 40534.95}]
    # act = -106541.27 ; ant = -109498.97 ; variación = 2957.70
    assert motor_f101.ori_del_periodo(bal_ant, bal_act) == 2957.70
