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
    # Neto en libros del auxiliar: 24.000 + 16.000 + 150.000 + 185.000 + 18.000 + 41.250 + 12.000 + 30.000 + 26.800 + 0 + 7.000
    assert _t(res, "netoAuxiliar") == 510050.00
    assert _t(res, "netoAuditado") == 467050.00
    assert _t(res, "ajuste") == -45000.00           # 467.050 − 512.050 (mayor)
    assert round(2000 - 10000 - 15000 - 18000 - 12000 + 10000 - 2000, 2) == _t(res, "ajuste")
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
    assert _it(res, "MAR-01")["amort"] == 15000        # 150.000 ÷ 120 × 12 (no hay vida indefinida)
    assert _it(res, "GW-01")["amort"] == 20000         # goodwill se amortiza (19.23)
    assert _it(res, "DES-01")["cap"] == "No"           # desarrollo a gasto (18.14)
    assert _t(res, "bajaNoCapitalizable") == 101250.00  # 18.000 + 41.250 + 12.000 + 30.000
    assert _t(res, "netoAuditado") == 370800.00
    codes = {e["code"]: e for e in res["exceptions"]}
    assert float(codes["SIN_AMORTIZAR_PYMES"]["amount"]) == 35000
    assert float(codes["DESARROLLO_CAPITALIZADO_PYMES"]["amount"]) == 83250
    assert "REVERSION_GOODWILL" in codes and "SIN_PRUEBA_DETERIORO" not in codes
    # La vida máxima es un parámetro: 96 meses.
    r96 = _run({**PYM, "vidaMaxPymes": 96, "_edicion": "2025"})
    assert _it(r96, "MAR-01")["amort"] == 18750 and r96["detalle"]["edicion"] == "2025"
    h = {x["name"]: x for x in m.hojas(r96)}
    assert "secciones 18, 19 y 27" in h["02_Parametros"]["rows"][1][1] and h["02_Parametros"]["rows"][2][1] == 1


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
