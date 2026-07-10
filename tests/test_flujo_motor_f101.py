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
