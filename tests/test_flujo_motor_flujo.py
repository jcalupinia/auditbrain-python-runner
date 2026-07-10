from backend.app.client_portal.flujo import catalogos


def test_cargar_clasificacion_flujo():
    clas = catalogos.cargar_clasificacion_flujo()
    # devuelve {codigo: actividad} con las 3 actividades
    assert set(clas.values()) <= {"OPERACION", "INVERSION", "FINANCIAMIENTO"}
    assert len(clas) > 100  # ~302 rubros clasificados
