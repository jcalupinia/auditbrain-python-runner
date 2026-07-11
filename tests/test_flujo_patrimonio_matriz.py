from backend.app.client_portal.flujo import patrimonio_matriz as pm


def test_matriz_estructura():
    m = pm.matriz_patrimonio([], [])
    assert len(m["columnas"]) == 18
    assert [c["codigo"] for c in m["columnas"]][:3] == ["301", "302", "303"]
    assert len(m["filas"]) == 16
    codes = [f["codigo"] for f in m["filas"]]
    assert codes[0] == "99" and "990210" in codes and "9902" in codes
    # con balanzas vacías todas las celdas son 0
    for f in m["filas"]:
        assert f["celdas"]["total"] == 0.0


def test_matriz_identidad_final_reexpresado_mas_cambios():
    # 99 (saldo final) = 9901 (reexpresado) + 9902 (cambios) por columna
    m = pm.matriz_patrimonio([], [])
    filas = {f["codigo"]: f["celdas"] for f in m["filas"]}
    for col in m["columnas"]:
        c = col["codigo"]
        assert abs(filas["99"][c] - (filas["9901"][c] + filas["9902"][c])) < 0.01


def test_matriz_resultado_del_ejercicio_va_a_ganancia_neta():
    # una ganancia neta del ejercicio (30701) aparece en 990210 col 30701
    bal_ant = []
    bal_act = [{"cuenta": "3.07.01", "super_cias": "30701", "sri": "", "saldo": -500.0}]
    m = pm.matriz_patrimonio(bal_ant, bal_act)
    filas = {f["codigo"]: f["celdas"] for f in m["filas"]}
    assert filas["990210"]["30701"] == -500.0
    assert filas["99"]["30701"] == -500.0
