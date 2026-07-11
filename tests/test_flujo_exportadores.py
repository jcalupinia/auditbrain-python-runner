from backend.app.client_portal.flujo import catalogos, exportadores


class _Nodo:
    def __init__(self, codigo):
        self.codigo = codigo
        self.etiqueta = ""
        self.padre = None
        self.es_hoja = True


def test_txt_esf_signo_activo_tal_cual_pasivo_patrimonio_invertido():
    est = [_Nodo("1"), _Nodo("10101"), _Nodo("2"), _Nodo("201"), _Nodo("3")]
    totales = {"1": 6544486.99, "10101": 1080134.58,
               "2": -2152117.90, "201": -2081476.57, "3": -4392369.09}
    txt = exportadores.txt_esf(totales, estructura=est)
    lineas = txt.strip().split("\n")
    assert lineas[0] == "1 6544486.99"          # activo tal cual
    assert lineas[1] == "10101 1080134.58"
    assert lineas[2] == "2 2152117.90"          # pasivo invertido → positivo
    assert lineas[3] == "201 2081476.57"
    assert lineas[4] == "3 4392369.09"          # patrimonio invertido → positivo


def test_txt_eri_cuentas_raw_y_subtotales_de_cascada():
    est = [_Nodo("50201"), _Nodo("402"), _Nodo("607"), _Nodo("800"), _Nodo("801")]
    totales = {"50201": 12345.67}
    cascada = {"ganancia_bruta": 2684261.97, "utilidad_neta": 340112.95}
    txt = exportadores.txt_eri(totales, cascada, ori=2957.70, estructura=est)
    lineas = txt.strip().split("\n")
    assert lineas[0] == "50201 12345.67"        # cuenta: raw
    assert lineas[1] == "402 2684261.97"        # ganancia bruta (cascada)
    assert lineas[2] == "607 340112.95"         # utilidad neta (cascada)
    assert lineas[3] == "800 2957.70"           # ORI
    assert lineas[4] == "801 343070.65"         # utilidad neta + ORI


def test_fmt_evita_menos_cero_y_usa_punto():
    est = [_Nodo("2")]
    txt = exportadores.txt_esf({"2": -0.0}, estructura=est)
    assert txt.strip() == "2 0.00"              # nunca "-0.00"


def test_xml_101_incluye_detalle_declaracion():
    balanza = [{"sri": "449", "saldo": 800.0}, {"sri": "361", "saldo": 5000.0}]
    xml = exportadores.xml_101(balanza, agregados={})
    assert "<detalleDeclaracion>" in xml
    assert '<campo codigo="449">800.00</campo>' in xml
