from backend.app.client_portal.flujo import previews


def test_map_incluye_columna_nombre():
    bal = [{"cuenta": "1.01.01.02.001", "nombre": "Produbanco Quito",
            "super_cias": "1010103", "sri": "311", "saldo": 351257.23}]
    prev = previews.construir_previews(bal, bal)
    assert prev["MAP"]["cols"] == ["Cuenta", "Nombre", "Super Cías", "SRI", "Saldo"]
    fila = prev["MAP"]["rows"][0]
    assert fila[0] == "1.01.01.02.001"
    assert fila[1] == "Produbanco Quito"
    assert fila[2] == "1010103"
    assert fila[3] == "311"


def test_map_nombre_vacio_no_rompe():
    bal = [{"cuenta": "1.01", "super_cias": "1010101", "sri": "311", "saldo": 10.0}]
    prev = previews.construir_previews(bal, bal)
    assert prev["MAP"]["rows"][0][1] == ""
