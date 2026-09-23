"""Procesador de arrendamientos (NIIF 16 / Sección 20 PYMES): ejemplo de control recalculado a mano."""
import copy

import pytest

from backend.app.aud.niif.procesadores import arrendamientos as m

EJ = m.EJEMPLO
NIIF = {**EJ["parametros"], "_marco": "NIIF completas"}
PYMES = {**EJ["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}


def _run(param=NIIF, ds=None, corte=None):
    return m.ejecutar(ds or EJ["datasets"], param, corte or EJ["corte"])


def _c(res, cid):
    return next(c for c in res["detalle"]["contratos"] if c["id"] == cid)


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def test_bodega_anual_a_mano():
    c = _c(_run(), "C-02")
    vp = 10000 * (1 - 1.1 ** -5) / 0.1
    assert round(c["vp"], 2) == 37907.87 == round(vp, 2)
    s1 = vp * 1.1 - 10000
    s2 = s1 * 1.1 - 10000
    s3 = s2 * 1.1 - 10000
    assert round(c["pasivo"], 2) == 17355.37 == round(s3, 2)
    assert round(c["interes"], 2) == 2486.85 == round(s2 * 0.1, 2)
    assert round(c["cp"], 2) == 8264.46 == round(s3 - (s3 * 1.1 - 10000), 2)
    assert round(c["activo_ini"], 2) == 38407.87            # + costos directos 500 (24 c)
    assert round(c["dep"], 2) == 7681.57 and round(c["neto"], 2) == 15363.15


def test_modificacion_remedida_a_mano():
    c = _c(_run(), "C-07")
    ev = c["ev"]
    assert round(ev["antes"], 2) == 30925.16
    assert round(ev["revisado"], 2) == 34172.48 == round(13500 * (1 - 1.09 ** -3) / 0.09, 2)
    assert round(ev["ajuste"], 2) == 3247.31
    assert round(c["interes"], 2) == 3075.52 and round(c["pasivo"], 2) == 23748.00
    assert round(c["dep"], 2) == 10664.94 and round(c["neto"], 2) == 21329.88


def test_venta_con_arrendamiento_posterior_ejemplo_24():
    c = _c(_run(), "C-08")
    s = c["slb"]
    assert round(c["pasivo_ini"], 2) == 1459199.02
    assert s["financiacion"] == 200000
    assert round(s["rou"], 2) == 699555.01 == round(1000000 * (1459199.02 - 200000) / 1800000, 2)
    assert round(s["inmediata"], 2) == 240355.99
    assert round(c["activo_ini"], 2) == 699555.01


def test_exentos_y_deterioro():
    r = _run()
    assert _c(r, "C-05")["reconoce"] == "No" and _c(r, "C-05")["gasto"] == 1800          # 300 × 12 ÷ 12 × 6
    assert _c(r, "C-04")["reconoce"] == "No" and _c(r, "C-04")["gasto"] == 960           # 80 × 24 ÷ 24 × 12
    assert _c(r, "C-03")["reconoce"] == "Sí"                                               # automóvil: nunca es de escaso valor (B6)
    c9 = _c(r, "C-09")
    assert round(c9["deterioro"], 2) == 21307.75 and round(c9["neto"], 2) == 50000.00


def test_problemas_niif_completas():
    r = _run()
    assert {"RENOVACION_NO_INCLUIDA", "EXENCION_MAL_APLICADA", "CLASIFICACION_CP_LP", "MODIFICACION_NO_REMEDIDA",
            "PASIVO_DIFERENCIA", "VENTA_GANANCIA", "DETERIORO", "BAJO_VALOR_VEHICULO", "BAJO_VALOR_B5_B7"} <= _codigos(r)
    assert r["primary"] == "ajuste"
    t = r["totals"]
    assert float(t["ajuste"]) == pytest.approx(float(t["pasivo"]) - float(t["pasivoRegistrado"]), abs=0.011)
    assert float(t["corriente"]) + float(t["noCorriente"]) == pytest.approx(float(t["pasivo"]), abs=0.011)
    assert "PYMES_DERECHO_USO" not in _codigos(r)


def test_bajo_valor_b3_b5_b6_b7():
    """NIIF 16 B3 y B5–B7: el bajo valor exige el valor del activo nuevo, uso independiente, no ser automóvil y no subarrendarse."""
    r = _run()
    c3, c4 = _c(r, "C-03"), _c(r, "C-04")
    assert c3["bv"] == "Sí" and c3["bv_auto"] == "Sí" and c3["bv_limite"] == "No"   # B6: automóvil
    assert "C-03" in next(e["message"] for e in r["exceptions"] if e["code"] == "BAJO_VALOR_VEHICULO")
    assert c4["bv_auto"] == "No" and c4["bv_limite"] == "Sí"                        # 1.200 ≤ 5.000 (B3, B8)
    assert "C-04" in next(e["message"] for e in r["exceptions"] if e["code"] == "BAJO_VALOR_B5_B7")   # B5 y B7 sin evidencia
    # B3: sin el valor del activo nuevo la exención ya no se acepta (antes bastaba dejarlo en blanco).
    ds = copy.deepcopy(EJ["datasets"])
    c = next(x for x in ds["contratos"] if x["id"] == "C-04")
    c["valor_razonable"] = ""
    sv = _run(ds=ds)
    assert _c(sv, "C-04")["bv_limite"] == "No" and _c(sv, "C-04")["reconoce"] == "Sí"
    assert {"BAJO_VALOR_SIN_VALOR", "EXENCION_MAL_APLICADA"} <= _codigos(sv)
    # B5 / B7 declarados «no» → tampoco califica; declarados «sí» → califica y se apaga el problema.
    c["valor_razonable"] = "1200"
    c["bajo_valor_b5b7"] = "No"
    no = _run(ds=ds)
    assert _c(no, "C-04")["bv_limite"] == "No" and _c(no, "C-04")["reconoce"] == "Sí"
    assert "BAJO_VALOR_B5_B7" in _codigos(no) and "EXENCION_MAL_APLICADA" in _codigos(no)
    c["bajo_valor_b5b7"] = "Sí"
    ok = _run(ds=ds)
    assert _c(ok, "C-04")["bv_limite"] == "Sí" and _c(ok, "C-04")["reconoce"] == "No" and _c(ok, "C-04")["gasto"] == 960
    assert "BAJO_VALOR_B5_B7" not in _codigos(ok)
    # La Sección 20 no tiene exenciones: los problemas de bajo valor solo corren en NIIF completas.
    assert not [x for x in _codigos(_run(PYMES)) if x.startswith("BAJO_VALOR")]


def test_ruta_pymes():
    r = _run(PYMES)
    cod = _codigos(r)
    assert {"PYMES_DERECHO_USO", "CLASIFICACION_PYMES", "PYMES_EVENTO"} <= cod
    assert "EXENCION_MAL_APLICADA" not in cod and "MODIFICACION_NO_REMEDIDA" not in cod
    assert _c(r, "C-01")["reconoce"] == "No" and _c(r, "C-01")["gasto"] == 18000       # operativo: 1.500 × 12 (20.15)
    assert _c(r, "C-02")["clasif"] == "Financiero"                                       # VP/VR = 94,8 % ≥ 90 % (20.5 d)
    c4 = _c(r, "C-04")                                                                   # VR 1.200 < VP → 20.9 y tasa recalculada
    assert c4["pasivo_ini"] == 1200 and c4["i_used"] > c4["i"]
    assert round(c4["tabla"][-1]["saldo"], 6) == 0
    assert _c(r, "C-08")["slb"] == {"inmediata": 800000, "diferida": 200000}           # 20.34: exceso sobre VR diferido
    r25 = _run({**PYMES, "_edicion": "2025"})
    assert r25["totals"] == r["totals"]                                                  # 2025 no adoptó la NIIF 16


def test_tabla_cierra_en_cero_y_movimiento_cuadra():
    for param in (NIIF, PYMES):
        for c in _run(param)["detalle"]["contratos"]:
            if c["reconoce"] == "Sí":
                assert abs(c["tabla"][-1]["saldo"]) < 1e-6, c["id"]
                assert abs(c["comprobacion"]) < 1e-6, c["id"]


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"contratos": []}, NIIF, "2025-12-31")
    with pytest.raises(ValueError):
        _run({**NIIF, "umbralVP": 150})
    with pytest.raises(ValueError):
        _run({**NIIF, "convencionTasa": "Otra"})
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], NIIF, "")
    ds = copy.deepcopy(EJ["datasets"])
    ds["contratos"][1]["plazo"] = "30"                       # anual con 30 meses → error
    with pytest.raises(ValueError):
        m.ejecutar(ds, NIIF, EJ["corte"])
    ds = copy.deepcopy(EJ["datasets"])
    ds["contratos"][0]["inicio"] = "2026-03-01"
    r = m.ejecutar(ds, NIIF, EJ["corte"])
    assert "NO_COMENZADO" in _codigos(r) and all(c["id"] != "C-01" for c in r["detalle"]["contratos"])
    ds = copy.deepcopy(EJ["datasets"])
    ds["contratos"][6]["fecha_evento"] = "2026-06-01"        # posterior al corte
    assert "EVENTO_NO_APLICADO" in _codigos(m.ejecutar(ds, NIIF, EJ["corte"]))


def test_validar_filas():
    ok = m.validar_filas("contratos", EJ["datasets"]["contratos"])
    assert ok["ok"], ok["errors"]
    malo = [{**EJ["datasets"]["contratos"][0], "pago": "-5", "periodicidad": "bimestral", "renov_cierta": "quizá", "_row": 3},
            {"id": "TOTAL", "_row": 4}]
    r = m.validar_filas("contratos", malo)
    campos = {e.get("field") for e in r["errors"]}
    assert not r["ok"] and {"pago", "periodicidad", "renov_cierta", "inicio"} <= campos


def test_hojas_y_definicion():
    for _, ds, param, corte in m.ESCENARIOS:
        res = m.ejecutar(ds, param, corte)
        h = m.hojas(res)
        assert [x["name"] for x in h] == [n for n, _ in m.CEDULAS]
        for x in h:
            assert len(x["name"]) <= 31
            for fila in x["rows"] + ([x["total"]] if x["total"] else []):
                assert len(fila) == len(x["cols"]), x["name"]
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "arrendamientos" and len(d["program"]) >= 5
    assert m.RUBRO == "ARRENDAMIENTOS" and m.PRINCIPAL in m.DATASETS and m.kind("contratos") == "contratos"
