"""Activos intangibles y goodwill: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import copy

import pytest

from backend.app.aud.niif.procesadores import intangibles_goodwill as m

E = m.EJEMPLO
COMP = {**E["parametros"], "_marco": "NIIF completas"}
PYM = {**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}


def _run(parametros=None, datasets=None):
    return m.ejecutar(datasets or E["datasets"], COMP if parametros is None else parametros, E["corte"])


def _t(res, k):
    return float(res["totals"][k])


def _it(res, id):
    return next(x for x in res["detalle"]["items"] if x["id"] == id)


def test_ejemplo_niif_completas_a_mano():
    res = _run()
    # Neto en libros del auxiliar: 24.000 + 16.000 + 150.000 + 185.000 + 18.000 + 41.250 + 12.000 + 30.000 + 26.800 + 0
    #                              + 7.000 + 24.000 (CON-01) + 55.000 (CON-02)
    assert _t(res, "netoAuxiliar") == 589050.00
    assert _t(res, "netoAuditado") == 549050.00
    assert _t(res, "ajuste") == -42000.00           # 549.050 − 591.050 (mayor)
    assert round(2000 - 10000 - 15000 - 18000 - 12000 + 10000 + 3000 - 2000, 2) == _t(res, "ajuste")
    # Amortización del año: recalculada por la herramienta 41.950 (12.000 + 6.000 + 3.750 + 7.200 + 4.000 + 9.000 de CON-01);
    # auditada 66.950 = esas 41.950 + las 25.000 de CON-02, aceptadas por la excepción documentada; registrada 71.950.
    assert _t(res, "amortCalculada") == 41950.00
    assert _t(res, "amortAuditada") == 66950.00
    assert _t(res, "amortRegistrada") == 71950.00
    assert _t(res, "difAmortizacion") == -5000.00   # −2.000 (LIC-01) − 3.000 (CON-01)
    assert _t(res, "bajaNoCapitalizable") == 30000.00  # INV-01 18.000 + DES-02 12.000
    assert _it(res, "LIC-01")["amort"] == 6000         # 24.000 ÷ 36 × 9 meses (abr-dic)
    assert _it(res, "DES-01")["amort"] == 3750         # 45.000 ÷ 36 × 3 meses
    assert _it(res, "SW-02")["amort"] == 0             # totalmente amortizado
    assert _it(res, "MAR-01")["amort"] == 0 and _it(res, "MAR-01")["detCalc"] == 10000   # indefinida: 150.000 − MAX(140.000; 130.000)
    gw = _it(res, "GW-01")
    assert gw["amort"] == 0 and gw["revCalc"] == 0 and gw["aud"] == 170000  # goodwill: sin amortizar ni revertir
    pat = _it(res, "PAT-01")
    assert pat["amort"] == 7200                        # (80.000 − 8.000) ÷ 120 × 12
    assert pat["librosAntes"] == 26800 and pat["revCalc"] == 10000   # MIN(40.000 − 26.800; 10.000)
    assert pat["aud"] == 36800 == pat["limite"]        # tope NIC 36.117: 80.000 − 43.200
    assert _it(res, "SW-03")["difAcum"] == 1000        # esperada 12.000 ÷ 36 × 18 = 6.000 vs 1.000 + 4.000
    assert res["primary"] == "ajuste"


def test_metodo_por_ingresos_bloqueado_y_excepcion_documentada():
    """NIC 38.98A: bloqueado sin justificación; 98C: aceptado con la circunstancia documentada."""
    res = _run()
    con1, con2 = _it(res, "CON-01"), _it(res, "CON-02")
    # CON-01: método por ingresos sin justificación → se recalcula lineal 36.000 ÷ 48 × 12 = 9.000 (registró 12.000).
    assert con1["metAp"] == "Lineal (presunción no refutada)" and con1["recalc"]
    assert con1["amort"] == 9000 and con1["amortAud"] == 9000 and con1["difAmort"] == -3000
    assert con1["aud"] == 27000 and con1["ajuste"] == 3000      # 36.000 − 9.000 vs libros 36.000 − 12.000
    # CON-02: circunstancia «a» documentada → se acepta lo registrado y la herramienta no recalcula (M22).
    assert con2["metAp"] == "Ingresos (excepción documentada)" and not con2["recalc"]
    assert con2["circ"] == "a" and con2["circLab"].startswith("a) el intangible se expresa")
    assert con2["amort"] is None and con2["amortAud"] == 25000 and con2["difAmort"] is None
    assert con2["aud"] == 55000 and con2["ajuste"] == 0 and con2["difAcum"] is None
    codes = {e["code"]: e for e in res["exceptions"]}
    assert float(codes["METODO_INGRESOS_SIN_JUSTIFICAR"]["amount"]) == -3000     # efecto en resultados
    assert "CON-01" in codes["METODO_INGRESOS_SIN_JUSTIFICAR"]["message"] and "98C" in codes["METODO_INGRESOS_SIN_JUSTIFICAR"]["message"]
    assert float(codes["METODO_INGRESOS_EXCEPCION"]["amount"]) == 25000
    assert "CON-01" not in codes["DIF_AMORTIZACION"]["message"]   # el hallazgo del método no se duplica


def test_metodo_normal_y_justificacion_que_no_invoca_circunstancia():
    ds = copy.deepcopy(E["datasets"])
    con1 = next(f for f in ds["intangibles"] if f["id"] == "CON-01")
    con1["metodo_amortizacion"] = "Lineal"              # método normal: se recalcula igual que sin método informado
    res = _run(datasets=ds)
    assert _it(res, "CON-01")["metAp"] == "Lineal" and _it(res, "CON-01")["amort"] == 9000
    assert "METODO_INGRESOS_SIN_JUSTIFICAR" not in {e["code"] for e in res["exceptions"]}
    assert "CON-01" in next(e for e in res["exceptions"] if e["code"] == "DIF_AMORTIZACION")["message"]
    # Justificación que no invoca ninguna de las dos circunstancias de la norma: sigue bloqueado.
    ds2 = copy.deepcopy(E["datasets"])
    con2 = next(f for f in ds2["intangibles"] if f["id"] == "CON-02")
    con2["justificacion_ingresos"] = "Política contable del grupo"
    r2 = _run(datasets=ds2)
    x = _it(r2, "CON-02")
    assert x["circLab"] == "No invoca ninguna de las dos circunstancias"
    assert x["metAp"] == "Lineal (presunción no refutada)"
    # (100.000 − 0) ÷ 96 × 12 = 12.500, con tope en el pendiente 80.000
    assert x["amort"] == 12500 and x["difAmort"] == -12500
    assert "CON-02" in next(e for e in r2["exceptions"] if e["code"] == "METODO_INGRESOS_SIN_JUSTIFICAR")["message"]


def test_metodo_distinto_del_lineal_no_se_recalcula():
    ds = copy.deepcopy(E["datasets"])
    sw = next(f for f in ds["intangibles"] if f["id"] == "SW-01")
    sw["metodo_amortizacion"] = "Unidades producidas"
    res = _run(datasets=ds)
    x = _it(res, "SW-01")
    assert x["metAp"] == "Otro método informado (no recalculado)" and x["amort"] is None
    assert x["amortAud"] == 12000 and x["aud"] == 24000          # se acepta lo registrado: el neto no cambia
    assert float({e["code"]: e for e in res["exceptions"]}["METODO_NO_RECALCULADO"]["amount"]) == 12000
    assert _t(res, "netoAuditado") == 549050.00


def test_problemas_minimos_completas():
    codes = {e["code"] for e in _run()["exceptions"]}
    for c in ("INVESTIGACION_CAPITALIZADA", "DESARROLLO_NO_CUMPLE_57", "DIF_AMORTIZACION", "SIN_PRUEBA_DETERIORO",
              "DETERIORO_NO_RECONOCIDO", "REVERSION_GOODWILL", "REVERSION_NO_RECONOCIDA", "RESIDUAL_NO_NULO",
              "SIN_REVISION_VIDA", "ACUMULADA_INCONSISTENTE", "AUXILIAR_MAYOR", "AJUSTE"):
        assert c in codes, c
    assert "SIN_AMORTIZAR_PYMES" not in codes and "DESARROLLO_CAPITALIZADO_PYMES" not in codes


def test_ruta_pymes_a_mano():
    res = _run(PYM)
    assert res["detalle"]["pymes"]
    # PYMES 18.20 y 19.23 (2015) / 19.34 (2025): los diez años son el TOPE de la mejor estimación de la gerencia
    # cuando la vida no puede establecerse con fiabilidad, no una vida por defecto. MAR-01 y GW-01 no traen vida:
    # no se amortizan (importe vacío, M22) y se pide la estimación de la gerencia.
    mar, gw = _it(res, "MAR-01"), _it(res, "GW-01")
    assert mar["amort"] is None and mar["vidaAp"] is None and mar["tipoVida"] == "Sin estimación (18.20)"
    assert gw["amort"] is None and gw["vidaAp"] is None
    assert mar["aud"] == 140000        # 150.000 − deterioro 10.000 (libros 150.000 − MAX(140.000; 130.000)), sin amortizar
    assert gw["aud"] == 170000         # 200.000 − 30.000 de deterioro previo; recuperable 185.000 > 170.000
    assert _it(res, "DES-01")["cap"] == "No"           # desarrollo a gasto (18.14)
    assert _t(res, "bajaNoCapitalizable") == 101250.00  # 18.000 + 41.250 + 12.000 + 30.000
    # Neto auditado 474.800 = 24.000 (SW-01) + 18.000 (LIC-01) + 140.000 (MAR-01) + 170.000 (GW-01)
    #                        + 36.800 (PAT-01) + 0 (SW-02) + 7.000 (SW-03) + 24.000 (CON-01) + 55.000 (CON-02);
    # el resto se da de baja. En la edición 2015 no existe la presunción del 18.22A: CON-01 y CON-02 conservan
    # su amortización registrada (12.000 y 25.000) y la herramienta no las recalcula.
    assert _t(res, "netoAuditado") == 474800.00
    assert _t(res, "ajuste") == -116250.00              # 474.800 − 591.050 (mayor)
    assert _t(res, "amortCalculada") == 29200.00        # 12.000 + 6.000 + 7.200 + 0 + 4.000 (MAR-01 y GW-01 vacías)
    assert _t(res, "amortAuditada") == 66200.00         # + 12.000 (CON-01) + 25.000 (CON-02) aceptadas
    con1 = _it(res, "CON-01")
    assert con1["metAp"] == "Ingresos (sin presunción: PYMES 2015)" and con1["amort"] is None and con1["amortAud"] == 12000
    assert float({e["code"]: e for e in res["exceptions"]}["METODO_INGRESOS_PYMES_2015"]["amount"]) == 37000  # 12.000 + 25.000
    codes = {e["code"]: e for e in res["exceptions"]}
    assert float(codes["VIDA_NO_ESTIMADA"]["amount"]) == 320000    # 150.000 + 170.000 en libros sin amortizar
    assert float(codes["DESARROLLO_CAPITALIZADO_PYMES"]["amount"]) == 83250
    assert "SIN_AMORTIZAR_PYMES" not in codes           # ya no se amortiza con el tope por defecto
    assert "REVERSION_GOODWILL" in codes and "SIN_PRUEBA_DETERIORO" not in codes
    # La vida máxima es un tope, no una vida: PAT-01 trae 120 meses y con tope 96 se limita a 96.
    r96 = _run({**PYM, "vidaMaxPymes": 96, "_edicion": "2025"})
    pat = _it(r96, "PAT-01")
    assert pat["vidaAp"] == 96 and pat["amort"] == 9000 and pat["aud"] == 35000   # (80.000 − 8.000) ÷ 96 × 12
    c96 = {e["code"]: e for e in r96["exceptions"]}
    assert float(c96["VIDA_EXCEDE_TOPE_PYMES"]["amount"]) == 25000  # 80.000 − 45.000 − 10.000 en libros
    assert r96["detalle"]["edicion"] == "2025"
    # La edición 2025 sí trae la presunción del 18.22A: CON-01 vuelve a bloquearse y se recalcula lineal.
    assert r96["detalle"]["presuncion"] and _it(r96, "CON-01")["amort"] == 9000
    assert float({e["code"]: e for e in r96["exceptions"]}["METODO_INGRESOS_SIN_JUSTIFICAR"]["amount"]) == -3000
    assert _it(r96, "CON-02")["metAp"] == "Ingresos (excepción documentada)"
    h = {x["name"]: x for x in m.hojas(r96)}
    assert "secciones 18, 19 y 27" in h["02_Parametros"]["rows"][1][1] and h["02_Parametros"]["rows"][2][1] == 1
    assert h["02_Parametros"]["rows"][4][1] == 1 and "18.22A" in h["02_Parametros"]["rows"][4][2]


def test_pymes_goodwill_con_vida_estimada_se_amortiza():
    """Con la mejor estimación de la gerencia en la ficha, el goodwill PYMES sí se amortiza (19.23 / 19.34)."""
    ds = copy.deepcopy(E["datasets"])
    gw = next(f for f in ds["intangibles"] if f["id"] == "GW-01")
    gw["vida_meses"] = 60
    res = _run(PYM, ds)
    assert _it(res, "GW-01")["amort"] == 40000          # 200.000 ÷ 60 × 12 (tope del pendiente 170.000)
    codes = {e["code"]: e for e in res["exceptions"]}
    assert float(codes["SIN_AMORTIZAR_PYMES"]["amount"]) == 40000
    assert "MAR-01" in codes["VIDA_NO_ESTIMADA"]["message"] and "GW-01" not in codes["VIDA_NO_ESTIMADA"]["message"]


def test_goodwill_amortizado_en_completas():
    ds = copy.deepcopy(E["datasets"])
    gw = next(f for f in ds["intangibles"] if f["id"] == "GW-01")
    gw["amort_registrada"] = 20000
    codes = {e["code"] for e in _run(datasets=ds)["exceptions"]}
    assert "GOODWILL_AMORTIZADO_NIIF_COMPLETAS" in codes


def test_vacio_y_parametros_invalidos():
    with pytest.raises(ValueError):
        m.ejecutar({"intangibles": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run({"vidaMaxPymes": 180})
    ds = copy.deepcopy(E["datasets"])
    ds["intangibles"][0]["vida_meses"] = 0
    with pytest.raises(ValueError):
        _run(datasets=ds)


def test_faltantes_y_negativos():
    ds = copy.deepcopy(E["datasets"])
    ds["intangibles"][0]["costo"] = -100
    ds["intangibles"][2]["valor_uso"] = ""
    ds["intangibles"][2]["vr_menos_costos"] = ""
    res = m.ejecutar(ds, {}, E["corte"])
    codes = {e["code"] for e in res["exceptions"]}
    assert {"VALOR_NEGATIVO", "SIN_MAYOR"} <= codes
    mar = _it(res, "MAR-01")
    assert mar["rec"] is None and mar["detCalc"] is None   # M22: no medido queda vacío
    assert _t(res, "difAuxMayor") == 0


def test_validar_filas():
    v = m.validar_filas("intangibles", [{"id": "X", "descripcion": "d", "tipo": "Software", "costo": "abc", "_row": 2},
                                        {"id": "TOTAL", "descripcion": "t", "tipo": "x", "costo": "1", "_row": 3}])
    assert not v["ok"] and len(v["errors"]) == 2
    assert m.validar_filas("intangibles", [{"id": "A", "descripcion": "d", "tipo": "Marca", "costo": "1.500,00",
                                            "fecha_disponible": "31/12/2025", "_row": 2}])["ok"]


def test_hojas_y_definicion():
    hs = m.hojas(_run())
    assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
    for h in hs:
        assert len(h["name"]) <= 31
        for fila in h["rows"] + ([h["total"]] if h.get("total") else []):
            assert len(fila) == len(h["cols"]), h["name"]
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "intangibles_goodwill" and len(d["program"]) >= 5
    assert {r["dataset"] for r in d["requests"] if r.get("dataset")} == set(m.DATASETS)
    assert m.RUBRO == "INTANGIBLES" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
    for esc, ds, par, corte in m.ESCENARIOS:
        assert m.hojas(m.ejecutar(ds, par, corte))
