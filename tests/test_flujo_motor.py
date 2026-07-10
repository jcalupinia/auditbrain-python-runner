from backend.app.client_portal.flujo import catalogos


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
