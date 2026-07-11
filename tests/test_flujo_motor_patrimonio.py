from backend.app.client_portal.flujo import motor_patrimonio


def test_evolucion_por_componente():
    # patrimonio en negativo (credito)
    tot_ant = {"3": -4104818.99, "304": -135607.0, "306": -3428299.69, "307": -649611.09}
    tot_act = {"3": -4392369.09, "304": -132649.0, "306": -4025347.93, "307": -340112.95}
    r = motor_patrimonio.evolucion(tot_ant, tot_act)
    assert r["reservas"]["saldo_inicial"] == 135607.0
    assert r["reservas"]["saldo_final"] == 132649.0
    assert r["resultado_ejercicio"]["saldo_final"] == 340112.95
    assert r["resultados_acumulados"]["variacion"] == round(4025347.93 - 3428299.69, 2)
    assert r["total_patrimonio"]["saldo_final"] == 4392369.09
    assert r["total_patrimonio"]["variacion"] == round(4392369.09 - 4104818.99, 2)


def test_componente_faltante_es_cero():
    r = motor_patrimonio.evolucion({}, {})
    assert r["capital"]["saldo_inicial"] == 0.0
    assert r["total_patrimonio"]["variacion"] == 0.0
