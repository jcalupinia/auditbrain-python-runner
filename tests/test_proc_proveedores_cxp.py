"""Procesador proveedores_cxp: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import proveedores_cxp as m

EJ = m.EJEMPLO


def _run(ds=None, **param):
    return m.ejecutar(ds or EJ["datasets"], {**EJ["parametros"], **param}, EJ["corte"])


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def test_ejemplo_niif_completas_cifras_a_mano():
    r = _run()
    t = r["totals"]
    # 15.000 + 7.000 + 4.000 + 3.000 + 24.200 + 10.000 − 1.800 + 2.500 + 9.000 + 1.300 + 600 + 5.500
    assert t["saldo"] == "80300.00" and t["difMayor"] == "300.00"
    assert t["pasivoNoRegistrado"] == "9000.00"          # CE-001 6.200 + CE-002 1.850 + CE-006 950
    assert t["corteAnticipado"] == "7000.00"             # P-002 recibida el 6-ene-2026
    assert t["difConfirmacion"] == "1200.00"             # P-003: 5.200 − 4.000
    assert t["pagoMayorSaldo"] == "500.00"               # P-004: pago 3.500 vs saldo 3.000
    f5 = next(x for x in r["detalle"]["filas"] if x["doc"] == "P-005")
    assert round(f5["vp"], 2) == 20000.00                # 24.200 ÷ 1,1²
    assert round(f5["interesDev"], 2) == 978.92          # 20.000 × (1,1^(183/365) − 1)
    assert t["interesNoDevengado"] == "3221.08"          # 24.200 − 20.978,92
    assert t["noCorriente"] == "20978.92" and t["reclasificacionNoCorriente"] == "20978.92"
    assert t["saldosDeudores"] == "1800.00" and t["relacionadas"] == "10000.00"
    # 9.000 − 7.000 − 3.221,08 + 1.800
    assert t["ajusteNeto"] == "578.92" and r["primary"] == "ajusteNeto"
    assert t["saldoAuditado"] == "80878.92"
    c = _codigos(r)
    for k in ("PASIVO_NO_REGISTRADO", "DIF_CONFIRMACION", "ERROR_CORTE_COMPRAS", "FINANCIACION_NO_RECONOCIDA",
              "NO_CORRIENTE_COMO_CORRIENTE", "SALDOS_DEUDORES", "PAGO_MAYOR_SALDO", "PAGO_NO_POSTERIOR", "VENCIDO_MAS_360",
              "MONEDA_EXTRANJERA", "DIF_MAYOR"):
        assert k in c
    # Los anticipos no se compensan por NIC 1.32 / PYMES 2.52, no por NIC 32.42 (activos y pasivos financieros).
    sd = next(e["message"] for e in r["exceptions"] if e["code"] == "SALDOS_DEUDORES")
    assert "NIC 1.32" in sd and "notas de crédito" in sd
    assert "PYMES 2.52" in next(e["message"] for e in _run(_marco=m.MARCO_PYMES)["exceptions"] if e["code"] == "SALDOS_DEUDORES")


def test_ruta_pymes_mismo_calculo_otras_citas():
    base, pymes = _run(), _run(_marco=m.MARCO_PYMES, _edicion="2025")
    assert base["totals"] == pymes["totals"]
    assert "PYMES 11.13" in next(e["message"] for e in pymes["exceptions"] if e["code"] == "FINANCIACION_NO_RECONOCIDA")
    assert "NIIF 9" in next(e["message"] for e in base["exceptions"] if e["code"] == "FINANCIACION_NO_RECONOCIDA")
    assert pymes["detalle"]["edicion"] == "2025"


def test_sin_tasa_sin_busqueda_y_sin_mayor_quedan_senalados():
    r = _run({"proveedores": EJ["datasets"]["proveedores"]}, tasaMercado=None, saldoMayor=None)
    f5 = next(x for x in r["detalle"]["filas"] if x["doc"] == "P-005")
    assert f5["interes"] is None and f5["ca"] == 24200
    assert "saldoMayor" not in r["totals"] and "difMayor" not in r["labels"]
    assert {"FINANCIACION_SIN_TASA", "SIN_BUSQUEDA_PASIVOS", "SIN_SALDO_MAYOR"} <= _codigos(r)


def test_descuento_registrado_y_exceso_no_corriente():
    r = _run(descuentoRegistrado=4000, noCorrienteRegistrado=30000)
    assert r["totals"]["ajusteFinanciacion"] == "-778.92"
    assert r["totals"]["ajusteNeto"] == "4578.92"        # 9.000 − 7.000 + 778,92 + 1.800
    assert r["totals"]["reclasificacionNoCorriente"] == "-9021.08"
    assert "CORRIENTE_COMO_NO_CORRIENTE" in _codigos(r)


def test_ciclo_solo_aplica_a_partidas_de_explotacion():
    # NIC 1.70: el plazo del ciclo (24 meses = 730 días) solo alcanza a las partidas de explotación.
    # P-005 (compra de maquinaria, explotacion="No") conserva el límite de 12 meses: 547 días > 365 → no corriente.
    r = _run(cicloOperacion=24)
    f5 = next(x for x in r["detalle"]["filas"] if x["doc"] == "P-005")
    assert f5["explotacion"] == "No" and f5["limite"] == 365 and f5["noCorr"] is True
    assert r["totals"]["noCorriente"] == "20978.92"
    # Marcado como partida de explotación, el ciclo sí le aplica: 547 < 730 → corriente.
    ds = {**EJ["datasets"], "proveedores": [{**f, "explotacion": "Sí"} if f["id"] == "P-005" else f
                                            for f in EJ["datasets"]["proveedores"]]}
    assert _run(ds, cicloOperacion=24)["totals"]["noCorriente"] == "0.00"
    # Sin la columna y con ciclo > 12 meses: se mantiene el comportamiento actual y se pide el dato (M22).
    ds = {**EJ["datasets"], "proveedores": [{k: v for k, v in f.items() if k != "explotacion"} for f in EJ["datasets"]["proveedores"]]}
    r = _run(ds, cicloOperacion=24)
    assert r["totals"]["noCorriente"] == "0.00" and "PARTIDA_EXPLOTACION_NO_INFORMADA" in _codigos(r)
    assert "PARTIDA_EXPLOTACION_NO_INFORMADA" not in _codigos(_run(ds))      # ciclo 12: no hay nada que preguntar


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"proveedores": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(tasaMercado=-1)
    with pytest.raises(ValueError):
        _run(cicloOperacion=-3)
    malo = {**EJ["datasets"], "pagos_posteriores": [{"id": "X", "proveedor": "A", "fecha": "2026-01-02", "recepcion": "2025-12-01",
                                                    "importe": "10", "registrado": "quizás", "_row": 2}]}
    with pytest.raises(ValueError):
        _run(malo)
    v = m.validar_filas("pagos_posteriores", [{"id": "X", "proveedor": "A", "fecha": "x", "recepcion": "2025-12-01", "importe": "abc",
                                               "registrado": "tal vez", "_row": 2}])
    assert not v["ok"] and len(v["errors"]) == 3
    v = m.validar_filas("proveedores", [{"id": "TOTAL", "proveedor": "A", "emision": "2025-01-01", "vence": "2025-02-01", "saldo": "1", "_row": 3}])
    assert not v["ok"]
    v = m.validar_filas("proveedores", [{"id": "P", "proveedor": "A", "emision": "2025-01-01", "vence": "2025-02-01", "saldo": "1",
                                         "explotacion": "quizás", "_row": 3}])
    assert not v["ok"] and {e.get("field") for e in v["errors"]} == {"explotacion"}


def test_hojas_nombres_y_anchos():
    for _, ds, p, c in m.ESCENARIOS:
        res = m.ejecutar(ds, p, c)
        hs = m.hojas(res)
        assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
        for h in hs:
            for fila in h["rows"] + ([h["total"]] if h["total"] else []):
                assert len(fila) == len(h["cols"]), h["name"]


def test_definicion():
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "proveedores_cxp" and len(d["program"]) >= 5
    assert m.RUBRO == "PROVEEDORES" and len(d["requests"]) >= 2
