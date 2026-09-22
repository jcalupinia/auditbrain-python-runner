"""Procesador impuesto_corriente_diferido: ejemplo recalculado a mano, rutas por marco y casos límite."""
import json

import pytest

from backend.app.aud.niif.procesadores import impuesto_corriente_diferido as m

EJ = m.EJEMPLO


def _run(ds=None, **param):
    return m.ejecutar(ds or EJ["datasets"], {**EJ["parametros"], **param}, EJ["corte"])


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def test_ejemplo_impuesto_corriente_a_mano():
    r = _run()
    t = r["totals"]
    # Base del cliente = suma de la conciliación: 1.000.000 − 150.000 − 60.000 + 45.000 + 3.000 + 8.550 − 12.000 − 240.000 + 30.000
    assert t["baseImponibleCliente"] == "624550.00"
    # Auditor: +20.000 no deducibles omitidos → 884.550; límite 25 % = 221.137,50 < 240.000 solicitadas y < 250.000 disponibles
    au = r["detalle"]["au"]
    assert au["b0"] == 884550 and au["lim"] == 221137.5 and au["disp"] == 250000
    assert t["baseImponibleAuditada"] == "663412.50" and t["excesoAmortizacionPerdidas"] == "18862.50"
    assert t["impuestoCorrienteAuditado"] == "165853.13"          # 663.412,50 × 25 %
    assert t["ajusteCorriente"] == "9715.63"                     # − 156.137,50 (624.550 × 25 %)
    assert t["impuestoPorPagarAuditado"] == "80853.13"           # − 70.000 − 10.000 − 5.000
    assert t["perdidasVencidas"] == "40000.00"                   # 2019: 100.000 − 60.000, venció en 2024


def test_ejemplo_diferido_y_tasa_efectiva_a_mano():
    r = _run()
    t = r["totals"]
    perd = {x["origen"]: x for x in r["detalle"]["perd"]}
    assert [x["origen"] for x in r["detalle"]["perd"]] == [2019, 2020, 2021, 2023]     # FIFO
    assert (perd[2020]["amortAnio"], perd[2021]["amortAnio"], perd[2023]["amortAnio"]) == (30000, 100000, 91137.5)
    assert perd[2023]["dtaReq"] == 28862.5 * 25 / 100                                   # 7.215,625
    # Partidas: activo reconocido 30.000 + 10.000 (garantías a 25 %, no 22 %) + 7.500 + 23.750; pasivo 20.000 + 50.000 + 22.500
    assert t["dtaReconocido"] == "78465.63" and t["dtlRequerido"] == "92500.00"
    assert t["dtaNoReconocido"] == "10000.00"                    # cartera no admitida 3.750 + litigio sin probabilidad 6.250
    assert t["diferidoNetoRequerido"] == "-14034.38" and t["diferidoNetoRegistrado"] == "6300.00"
    assert t["ajusteDiferido"] == "-20334.38" and t["ajusteDiferidoORI"] == "0.00"
    assert t["gastoDiferidoRequerido"] == "30034.38"             # −7.750 partidas + 37.784,375 pérdidas
    assert t["reclasificacionORI"] == "10000.00"                 # revaluación de terrenos llevada a resultados
    assert t["gastoTotalRequerido"] == "195887.50" and t["gastoTotalRegistrado"] == "175837.50"
    assert t["tasaEfectivaRequerida"] == "23.05"                 # 195.887,50 ÷ 850.000
    # 9.715,625 + 20.334,375 − 10.000 = gasto requerido − registrado
    assert t["ajusteResultados"] == "20050.00" and r["primary"] == "ajusteResultados"
    etr = r["detalle"]["etr"]
    assert etr["teo"] == 212500 and abs(etr["corr"] - 165853.125) < 1e-9 and abs(etr["neg"]) < 1e-9
    c = _codigos(r)
    for k in ("IR_CORRIENTE_MAL_CALCULADO", "NO_DEDUCIBLES_OMITIDOS", "PERDIDAS_SOBRE_LIMITE", "PERDIDAS_VENCIDAS", "DTA_SIN_PROBABILIDAD",
              "DTA_NO_PERMITIDO", "TASA_REVERSION_INCORRECTA", "ORI_EN_RESULTADOS", "FALTA_COMPENSAR", "TASA_EFECTIVA_INEXPLICADA",
              "DIFERIDO_MAL_MEDIDO", "DTA_PERDIDAS_EXCESO"):
        assert k in c, k
    json.dumps(r)


def test_ruta_pymes_mismo_calculo_otras_citas():
    base, p15, p25 = _run(), _run(_marco=m.MARCO_PYMES, _edicion="2015"), _run(_marco=m.MARCO_PYMES, _edicion="2025")
    assert base["totals"] == p15["totals"] == p25["totals"]
    msg = lambda r: next(e["message"] for e in r["exceptions"] if e["code"] == "TASA_REVERSION_INCORRECTA")
    assert "NIC 12.47" in msg(base) and "PYMES 2015" in msg(p15) and "PYMES 2025" in msg(p25)


def test_tasa_futura_sin_compensacion_y_sin_probabilidad_de_perdidas():
    r = _run(tasaFutura=22, anioTasaFutura=2027, derechoCompensar="No", probabilidadPerdidas="No")
    fil = {x["partida"]: x for x in r["detalle"]["partidas"]}
    assert fil["PPE — depreciación fiscal acelerada"]["tasa"] == 22            # revierte en 2028
    assert fil["Provisión por garantías"]["tasa"] == 25                        # revierte en 2026
    assert r["totals"]["dtaReconocido"] == "64800.00"                          # sin activo por pérdidas
    assert "FALTA_COMPENSAR" not in _codigos(r) and "DTA_SIN_PROBABILIDAD" in _codigos(r)


def test_perdida_contable_sin_anexos():
    _, ds, p, c = m.ESCENARIOS[2]
    r = m.ejecutar(ds, p, c)
    assert r["totals"]["impuestoCorrienteAuditado"] == "0.00"
    assert r["detalle"]["au"]["perd"] == 0                                     # sin utilidad gravable no se amortiza
    assert {"PERDIDAS_SIN_ANEXO", "SIN_PARTIDAS", "SALDO_A_FAVOR"} <= _codigos(r)


def test_registrados_vacios_asumen_la_conciliacion_del_cliente():
    r = _run(impuestoCorrienteRegistrado=None, saldoCorrienteRegistrado=None, gastoDiferidoRegistrado=None)
    assert r["totals"]["impuestoCorrienteRegistrado"] == "156137.50"           # 624.550 × 25 %
    assert r["totals"]["reclasificacionORI"] == "0.00" and "gastoDiferidoRegistrado" not in r["totals"]
    assert "SIN_DATOS_REGISTRADOS" in _codigos(r)


def test_recargo_paraisos_fiscales():
    r = _run(proporcionRecargo=50)                                             # 25 + 3 × 50 % = 26,5 %
    assert r["detalle"]["tarifa"] == 26.5
    assert r["totals"]["impuestoCorrienteAuditado"] == m.r2(663412.5 * 26.5 / 100)


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"conciliacion": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(tasaIR=-1)
    with pytest.raises(ValueError):
        _run(participacion=150)
    with pytest.raises(ValueError):
        _run(tasaFutura=22)                                                    # sin año de vigencia
    with pytest.raises(ValueError):
        _run(derechoCompensar="quizás")
    sin_utilidad = {"conciliacion": [f for f in EJ["datasets"]["conciliacion"] if f["tipo"] != "utilidad"]}
    with pytest.raises(ValueError):
        _run(sin_utilidad)
    signo = {**EJ["datasets"], "conciliacion": EJ["datasets"]["conciliacion"] + [
        {"id": "X", "concepto": "No deducible", "tipo": "no deducibles", "importe": "-10", "_row": 9}]}
    with pytest.raises(ValueError):
        _run(signo)
    v = m.validar_filas("conciliacion", [{"id": "1", "concepto": "A", "tipo": "raro", "importe": "abc", "_row": 2},
                                         {"id": "2", "concepto": "B", "tipo": "participación", "importe": "150", "_row": 3}])
    assert not v["ok"] and len(v["errors"]) == 3
    v = m.validar_filas("partidas", [{"id": "P", "naturaleza": "otro", "libros": "1", "base_fiscal": "0", "permitido": "tal vez",
                                      "probable": "Sí", "_row": 2}])
    assert not v["ok"] and len(v["errors"]) == 2
    v = m.validar_filas("perdidas", [{"id": "20X1", "importe": "5", "_row": 2}])
    assert not v["ok"]


def test_hojas_nombres_y_anchos():
    for _, ds, p, c in m.ESCENARIOS:
        hs = m.hojas(m.ejecutar(ds, p, c))
        assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
        for h in hs:
            assert len(h["name"]) <= 31
            for fila in h["rows"] + ([h["total"]] if h["total"] else []):
                assert len(fila) == len(h["cols"]), h["name"]


def test_definicion():
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "impuesto_corriente_diferido" and len(d["program"]) >= 5
    assert m.RUBRO == "IMPUESTOS" and {r.get("dataset") for r in d["requests"]} >= set(m.DATASETS)
    assert m.TOTAL_EJEMPLO in _run()["totals"]
