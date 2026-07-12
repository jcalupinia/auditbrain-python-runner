"""Balance resumido (motor_resumen) — ER + ESF condensados.

Verifica que las líneas condensadas se armen desde los códigos correctos y que
los totales cuadren (Total activo = Total pasivo + patrimonio). Validación
empírica contra SIGMAN: Total activo 6.544.486,99, Utilidad neta 340.112,95.
"""
from backend.app.client_portal.flujo import motor_resumen


def test_balance_resumido_totales_y_cuadre():
    # ESF (año actual): activo 1=101+102, pasivo/patrimonio en crédito (negativo)
    tesf = {
        "101": 5739385.18, "102": 805101.81, "1": 6544486.99,
        "10103": 2824704.20, "10102050201": 1842781.34, "1010207": -147047.63,
        "201": -2081476.57, "202": -70641.33, "2": -2152117.90,
        "201030102": -627995.37 + 28688.32, "201030202": -681878.30 + 43742.46,
        "20104": -7466.49, "20203": 0.0,
        "301": -800.0, "302": 0.0, "303": 0.0, "304": -26108.21,
        "305": 0.0, "306": -4025347.93, "307": -340112.95, "3": -4392369.09,
    }
    teri = {
        "40101": 7599669.59, "40102": 0.0, "501": 4915407.62,
        "50201": 1644205.17, "50202": 345477.39, "50203": 11844.66,
        "50204": 324506.54, "601": 85846.32, "603": 149203.28,
        "605": 0.0, "606": 3131.82, "40106": 0.0, "40107": 0.0,
        "40108": 0.0, "40109": 0.0, "40110": 0.0, "403": 213802.52,
    }
    res = motor_resumen.balance_resumido(tesf, tesf, teri, teri)
    esf = {f["clave"]: f["act"] for f in res["esf"]}
    er = {f["clave"]: f["act"] for f in res["er"]}

    assert esf["total_activo"] == 6544486.99
    assert er["ventas_netas"] == 7599669.59
    assert er["utilidad_bruta"] == round(7599669.59 - 4915407.62, 2)
    # cuadre: total activo = total pasivo + patrimonio
    assert abs(esf["total_activo"] - esf["total_pasivo_patrimonio"]) < 0.05


def test_estructura_de_filas():
    res = motor_resumen.balance_resumido({}, {}, {}, {})
    assert [f["clave"] for f in res["er"]][0] == "ventas_netas"
    assert any(f["clave"] == "total_pasivo_patrimonio" for f in res["esf"])
    for f in res["er"] + res["esf"]:
        assert "concepto" in f and "act" in f and "ant" in f and "es_total" in f
