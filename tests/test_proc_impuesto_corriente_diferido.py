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
    # Auditor: +20.000 no deducibles omitidos y participación atribuible a exentos 9.000 (15 % del bruto 60.000, Reglamento LRTI
    # art. 46 num. 5) en vez de 8.550 → 885.000; límite 25 % = 221.250 < 240.000 solicitadas y < 250.000 disponibles
    au = r["detalle"]["au"]
    assert au["pe"] == 9000 and au["b0"] == 885000 and au["lim"] == 221250 and au["disp"] == 250000
    assert t["baseImponibleAuditada"] == "663750.00" and t["excesoAmortizacionPerdidas"] == "18750.00"
    assert t["impuestoCorrienteAuditado"] == "165937.50"          # 663.750,00 × 25 %
    assert t["ajusteCorriente"] == "9800.00"                     # − 156.137,50 (624.550 × 25 %)
    assert t["impuestoPorPagarAuditado"] == "80937.50"           # − 70.000 − 10.000 − 5.000
    assert t["perdidasVencidas"] == "40000.00"                   # 2019: 100.000 − 60.000, venció en 2024


def test_ejemplo_diferido_y_tasa_efectiva_a_mano():
    r = _run()
    t = r["totals"]
    perd = {x["origen"]: x for x in r["detalle"]["perd"]}
    assert [x["origen"] for x in r["detalle"]["perd"]] == [2019, 2020, 2021, 2023]     # FIFO
    assert (perd[2020]["amortAnio"], perd[2021]["amortAnio"], perd[2023]["amortAnio"]) == (30000, 100000, 91250)
    assert perd[2023]["dtaReq"] == 28750 * 25 / 100                                     # 7.187,50
    # Partidas: activo reconocido 30.000 + 10.000 (garantías a 25 %, no 22 %) + 7.500 + 3.750 (deterioro de cartera sobre el
    # límite: el num. 5, 2.º inciso, del art. innumerado tras el art. 28 SÍ lo admite) + 23.750 = 75.000, más 7.187,50 de
    # pérdidas = 82.187,50; pasivo 20.000 + 50.000 + 22.500 = 92.500.
    assert t["dtaReconocido"] == "82187.50" and t["dtlRequerido"] == "92500.00"
    assert t["dtaNoReconocido"] == "6250.00"                     # solo el litigio sin probabilidad (la cartera ya es admitida)
    # 75.000 − 92.500 + 7.187,50 = −10.312,50
    assert t["diferidoNetoRequerido"] == "-10312.50" and t["diferidoNetoRegistrado"] == "6300.00"
    assert t["ajusteDiferido"] == "-16612.50" and t["ajusteDiferidoORI"] == "0.00"
    assert t["gastoDiferidoRequerido"] == "26312.50"             # −11.500 partidas + 37.812,50 pérdidas
    assert t["reclasificacionORI"] == "10000.00"                 # revaluación de terrenos llevada a resultados
    assert t["gastoTotalRequerido"] == "192250.00" and t["gastoTotalRegistrado"] == "175837.50"
    assert t["tasaEfectivaRequerida"] == "22.62"                 # 192.250,00 ÷ 850.000
    # 9.800,00 + 16.612,50 − 10.000 = gasto requerido − registrado = 16.412,50
    assert t["ajusteResultados"] == "16412.50" and r["primary"] == "ajusteResultados"
    etr = r["detalle"]["etr"]
    assert etr["teo"] == 212500 and abs(etr["corr"] - 165937.5) < 1e-9 and abs(etr["neg"]) < 1e-9
    c = _codigos(r)
    for k in ("IR_CORRIENTE_MAL_CALCULADO", "PARTICIPACION_EXENTOS", "NO_DEDUCIBLES_OMITIDOS", "PERDIDAS_SOBRE_LIMITE", "PERDIDAS_VENCIDAS",
              "DTA_SIN_PROBABILIDAD",
              "TASA_REVERSION_INCORRECTA", "ORI_EN_RESULTADOS", "FALTA_COMPENSAR", "TASA_EFECTIVA_INEXPLICADA",
              "DIFERIDO_MAL_MEDIDO", "DTA_PERDIDAS_EXCESO"):
        assert k in c, k
    assert "DTA_NO_PERMITIDO" not in c                           # ninguna partida del ejemplo está fuera del art. innumerado
    # Si la partida se marca como no admitida, el problema sí se emite (y el activo deja de reconocerse).
    no_adm = [dict(f, permitido="No") if f["id"].startswith("Deterioro de cartera") else f for f in EJ["datasets"]["partidas"]]
    r2 = _run({**EJ["datasets"], "partidas": no_adm})
    assert "DTA_NO_PERMITIDO" in _codigos(r2) and r2["totals"]["dtaReconocido"] == "78437.50"
    json.dumps(r)


def test_participacion_exentos_base_bruta_reglamento_46_5():
    """Reglamento LRTI art. 46 num. 5: «el 15% de tales ingresos» → base BRUTA, no neta de gastos atribuibles."""
    r = _run()
    pex = r["detalle"]["pex"]
    # Bruto informado 60.000 × 15 % = 9.000; el cliente declaró 8.550 (15 % de 60.000 − 3.000) → diferencia 450.
    assert pex["bruto"] == 60000 and pex["calc"] == 9000 and pex["registrado"] == 8550 and pex["dif"] == 450
    assert pex["estado"] == "Calculado" and r["detalle"]["au"]["pe"] == 9000
    msg = next(e["message"] for e in r["exceptions"] if e["code"] == "PARTICIPACION_EXENTOS")
    assert "46 num. 5" in msg and "15% de tales ingresos" in msg and "VERIFICAR" not in msg


def test_participacion_exentos_solo_neto_bloquea_el_calculo():
    """Sin el ingreso exento bruto no se reconstruye la base: importe vacío, renglón del cliente y problema (M22)."""
    r = _run(ingresoExentoBruto=None)
    pex = r["detalle"]["pex"]
    assert pex["bruto"] is None and pex["calc"] is None and pex["dif"] is None
    assert pex["estado"] == "Bloqueado por falta de soporte"
    assert r["detalle"]["au"]["pe"] == 8550                                     # conserva el del cliente, no asume 0
    # b0 = 885.000 − 450 = 884.550; límite 25 % = 221.137,50; base 663.412,50; IR 165.853,13; ajuste 9.715,63
    t = r["totals"]
    assert t["baseImponibleAuditada"] == "663412.50" and t["impuestoCorrienteAuditado"] == "165853.13"
    assert t["ajusteCorriente"] == "9715.63" and t["ajusteResultados"] == "16300.00"
    c = _codigos(r)
    assert "PARTICIPACION_EXENTOS_SIN_BASE_BRUTA" in c and "PARTICIPACION_EXENTOS" not in c
    msg = next(e["message"] for e in r["exceptions"] if e["code"] == "PARTICIPACION_EXENTOS_SIN_BASE_BRUTA")
    assert "ingreso exento bruto" in msg and "participación atribuible" in msg and "VERIFICAR" not in msg


def test_sin_ingresos_exentos_y_participacion_informada_que_no_cuadra():
    _, ds, p, c = next(e for e in m.ESCENARIOS if e[0] == "sin_ingresos_exentos")
    r = m.ejecutar(ds, p, c)
    pex = r["detalle"]["pex"]
    assert pex["estado"] == "Sin ingresos exentos" and pex["calc"] == 0 and r["detalle"]["au"]["pe"] == 0
    # 1.000.000 − 150.000 + 65.000 − 12.000 + 30.000 = 933.000; límite 25 % = 233.250 → base 699.750; IR 174.937,50
    assert r["detalle"]["au"]["b0"] == 933000 and r["totals"]["baseImponibleAuditada"] == "699750.00"
    assert r["totals"]["impuestoCorrienteAuditado"] == "174937.50"
    assert not ({"PARTICIPACION_EXENTOS", "PARTICIPACION_EXENTOS_SIN_BASE_BRUTA"} & _codigos(r))
    # La participación atribuible informada por el cliente se contrasta con el renglón de la conciliación (8.550).
    r2 = _run(participacionExentosInformada=9000)
    assert "PARTICIPACION_EXENTOS_NO_CUADRA" in _codigos(r2)
    assert next(e["amount"] for e in r2["exceptions"] if e["code"] == "PARTICIPACION_EXENTOS_NO_CUADRA") == "450.00"


def test_cedula_participacion_exentos():
    hs = {h["name"]: h for h in m.hojas(_run())}
    filas = hs["13_Partic_exentos"]["rows"]
    assert [f[1]["v"] for f in filas] == [60000.0, 60000.0, 3000.0, 9000.0, 8550.0, 8550.0, 450.0, "Calculado"]
    bloq = {h["name"]: h for h in m.hojas(_run(ingresoExentoBruto=None))}["13_Partic_exentos"]
    assert [f[1]["v"] for f in bloq["rows"]] == ["", 60000.0, 3000.0, "", 8550.0, 8550.0, "", "Bloqueado por falta de soporte"]


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
    # 26.400 (jubilación a 22 %) + 10.000 + 7.500 + 3.750 (cartera) + 20.900 = 68.550; sin activo por pérdidas
    assert r["totals"]["dtaReconocido"] == "68550.00"
    assert "FALTA_COMPENSAR" not in _codigos(r) and "DTA_SIN_PROBABILIDAD" in _codigos(r)


def test_perdida_contable_sin_anexos():
    _, ds, p, c = next(e for e in m.ESCENARIOS if e[0] == "pymes_2025_perdida_sin_anexos")
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
    # Reglamento art. 51: por debajo del 50 % el recargo grava solo esa proporción → 25 + 3 × 30 % = 25,9 %.
    r = _run(proporcionRecargo=30)
    assert r["detalle"]["tarifa"] == 25.9 and r["detalle"]["propRecargo"] == 30
    assert r["totals"]["impuestoCorrienteAuditado"] == m.r2(663750 * 25.9 / 100)
    # Al llegar al 50 % grava toda la base: 25 + 3 = 28 %, aunque la composición societaria sea del 60 %.
    for prop in (50, 60):
        r = _run(proporcionRecargo=prop)
        assert r["detalle"]["propRecargo"] == 100 and r["detalle"]["tarifa"] == 28
        assert r["totals"]["impuestoCorrienteAuditado"] == m.r2(663750 * 28 / 100)
    # NIC 12.47 y 49: esa misma tasa esperada mide el diferido y el activo por pérdidas (antes usaban solo el 25 %).
    fil = {x["partida"]: x for x in r["detalle"]["partidas"]}
    assert fil["Provisión jubilación patronal"]["tasa"] == 28 and fil["Provisión jubilación patronal"]["dtaRec"] == 120000 * 0.28
    assert fil["Provisión por garantías"]["difTasa"] == 22 - 28                # tasa del cliente 22 % frente a 28 %
    assert r["detalle"]["perd"][-1]["dtaReq"] == 28750 * 28 / 100                  # remanente 2023 × 28 %
    # Con tasa futura aprobada, la esperada de los años futuros también lleva el recargo.
    rf = _run(proporcionRecargo=60, tasaFutura=22, anioTasaFutura=2027)
    assert rf["detalle"]["tarifaFutura"] == 25
    assert {x["partida"]: x["tasa"] for x in rf["detalle"]["partidas"]}["PPE — depreciación fiscal acelerada"] == 25


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
        _run(ingresoExentoBruto=-1)
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
