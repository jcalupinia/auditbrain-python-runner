from backend.app.client_portal.flujo import catalogos
from backend.app.client_portal.flujo import motor_flujo


def test_cargar_clasificacion_flujo():
    clas = catalogos.cargar_clasificacion_flujo()
    # devuelve {codigo: actividad} con las 3 actividades
    assert set(clas.values()) <= {"OPERACION", "INVERSION", "FINANCIAMIENTO"}
    assert len(clas) > 100  # ~302 rubros clasificados


def test_variaciones():
    tot_ant = {"1010301": 100.0, "20101": -50.0}
    tot_act = {"1010301": 130.0, "20101": -70.0}
    v = motor_flujo.variaciones(tot_ant, tot_act)
    assert v["1010301"] == 30.0
    assert v["20101"] == -20.0


def test_clasificar_flujo_impacto_menos_variacion_y_excluye_efectivo():
    variaciones = {"1010301": 30.0, "20101": -20.0, "10101": 999.0}
    clas = {"1010301": "OPERACION", "20101": "OPERACION", "10101": "OPERACION"}
    act = motor_flujo.clasificar_flujo(variaciones, clas, excluir_prefijo="10101")
    # impacto = -variacion; efectivo (10101) excluido
    assert act["OPERACION"] == round(-30.0 + 20.0, 2)  # -10.0


def test_flujo_efectivo_cuadra_af_cero():
    # Balance: efectivo baja 20 (de 100 a 80); una CxC (operación) sube 20.
    tot_ant = {"10101": 100.0, "1010301": 0.0}
    tot_act = {"10101": 80.0, "1010301": 20.0}
    clas = {"1010301": "OPERACION"}
    r = motor_flujo.flujo_efectivo(tot_ant, tot_act, clas)
    assert r["operacion"] == -20.0            # CxC subió 20 → uso de efectivo
    assert r["incremento_neto"] == -20.0
    assert r["efectivo_inicial"] == 100.0
    assert r["efectivo_final_calculado"] == 80.0
    assert r["efectivo_final_real"] == 80.0
    assert r["cuadre_af"] == 0.0
    assert r["cuadra"] is True
