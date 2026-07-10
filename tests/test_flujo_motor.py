from backend.app.client_portal.flujo import catalogos
from backend.app.client_portal.flujo import motor


def test_estructura_esf_carga_y_arbol_por_prefijo():
    est = catalogos.cargar_estructura("esf")
    codes = {n.codigo for n in est}
    # códigos oficiales conocidos del plan Superintendencia
    assert "1" in codes and "101" in codes and "10101" in codes
    # el padre de un código = el prefijo más largo presente en el set
    padres = {n.codigo: n.padre for n in est}
    assert padres["10101"] == "101"
    assert padres["101"] == "1"
    assert padres["1"] is None
    # cada nodo sabe si es hoja (sin hijos en la estructura)
    hojas = {n.codigo for n in est if n.es_hoja}
    assert "1" not in hojas          # nodo raíz no es hoja
    assert any(len(c) >= 7 for c in hojas)  # existen hojas profundas


def test_totales_rollup_por_prefijo():
    # Estructura mínima sintética: 1 -> 101 -> 10101 (hoja) y 10102 (hoja)
    from backend.app.client_portal.flujo.catalogos import Nodo
    est = [
        Nodo("1", "ACTIVO", None, False),
        Nodo("101", "ACTIVO CORRIENTE", "1", False),
        Nodo("10101", "EFECTIVO", "101", True),
        Nodo("10102", "INVERSIONES", "101", True),
    ]
    # SUMIF: saldos ya agrupados por código exacto (equivale a Mapeo!C:C→E:E)
    saldos = {"10101": 450.0, "10102": 1500.0}
    tot = motor.totales_por_codigo(est, saldos)
    assert tot["10101"] == 450.0
    assert tot["10102"] == 1500.0
    assert tot["101"] == 1950.0   # rollup
    assert tot["1"] == 1950.0     # rollup


def test_totales_cuenta_codificada_a_nivel_agregado_no_duplica():
    from backend.app.client_portal.flujo.catalogos import Nodo
    est = [Nodo("1", "ACTIVO", None, False),
           Nodo("101", "ACTIVO CORRIENTE", "1", False),
           Nodo("10101", "EFECTIVO", "101", True)]
    # una cuenta se codificó directo al agregado "101" + otra al hijo "10101"
    saldos = {"101": 100.0, "10101": 450.0}
    tot = motor.totales_por_codigo(est, saldos)
    assert tot["10101"] == 450.0
    assert tot["101"] == 550.0    # 100 directo + 450 del hijo
    assert tot["1"] == 550.0
