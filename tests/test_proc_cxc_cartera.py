"""Procesador cxc_cartera: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import cxc_cartera as m

EJ = m.EJEMPLO


def _run(**param):
    return m.ejecutar(EJ["datasets"], {**EJ["parametros"], **param}, EJ["corte"])


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def test_ejemplo_niif_completas_cifras_a_mano():
    r = _run()
    t = r["totals"]
    assert t["saldo"] == "67000.00"
    # F-008: 20.000 ÷ 1,1^(547/365) = 17.337,95 → interés por devengar 2.662,05.
    assert t["costoAmortizado"] == "64337.95" and t["interesNoDevengado"] == "2662.05"
    # 120 + 80 + 150 + 600 + 1.500 (ind. 50 %) + 1.500 + 1.500 + 173,38 + 180 + 60 + 280 + 0 (nota de crédito)
    assert t["deterioroRequerido"] == "6143.38"
    assert t["ajuste"] == "4143.38" and r["primary"] == "ajuste"
    # Vencidas sin cobro: F-004 3.000 + F-005 3.000 + F-006 2.500 + F-007 1.500 + F-009 6.000 (cobro no posterior) + F-010 2.000
    assert t["vencidoSinCobro"] == "18000.00"
    assert t["difCircularizacion"] == "500.00"          # F-004: 3.500 − 4.000
    assert t["corteAnticipado"] == "8000.00"             # F-002 registrada en dic., despachada en ene.
    vp = next(x for x in r["detalle"]["filas"] if x["factura"] == "F-008")["vpInicial"]
    assert round(vp, 2) == 16528.93                      # 20.000 ÷ 1,21
    c = _codigos(r)
    for k in ("VENCIDA_SIN_COBRO", "DIF_CIRCULARIZACION", "ERROR_CORTE", "FINANCIACION_NO_RECONOCIDA", "DETERIORO_INSUFICIENTE",
              "COBRO_NO_POSTERIOR", "SALDOS_NEGATIVOS"):
        assert k in c


def test_ruta_pymes_conserva_la_tasa_del_tramo_corriente():
    """PYMES 11.22 e) y 11.24: la tasa corriente ya no se fuerza a 0 %; se conserva y se exige el sustento."""
    r = _run(_marco=m.MARCO_PYMES, _edicion="2025")
    # Tramo corriente al 1 %: F-001 12.000 + F-002 8.000 + F-008 17.337,95 (costo amortizado) − F-012 500 = 36.837,95.
    # Deterioro del tramo = 120 + 80 + 173,38 + 0 (la nota de crédito no genera deterioro) = 373,38.
    pv = next(x for x in r["detalle"]["matriz"] if x["k"] == "pv")
    assert pv["tasa"] == 0.01 and round(pv["det"], 2) == 373.38
    assert r["totals"]["deterioroRequerido"] == "6143.38"      # 5.770,00 de los tramos vencidos + 373,38 del corriente
    assert r["totals"]["ajuste"] == "4143.38"                  # 6.143,38 − 2.000 registrados
    assert "TASA_CORRIENTE_PYMES" in _codigos(r)
    assert r["labels"]["deterioroRequerido"].startswith("Pérdida incurrida")
    assert next(x for x in r["detalle"]["tasas"] if x["k"] == "pv")["origen"] == "Fijada por el auditor"


def test_pymes_sin_tasa_corriente_no_inventa_deterioro():
    """Sin tasa el tramo queda vacío (M22) y se pide la evidencia objetiva del grupo, no 0 por omisión."""
    tasas = {k: v for k, v in m.EJEMPLO["parametros"]["tasas"].items() if k != "pv"}
    r = _run(_marco=m.MARCO_PYMES, _edicion="2015", tasas=tasas)
    assert r["totals"]["deterioroRequerido"] == "5770.00"      # solo los tramos vencidos
    assert "TASA_CORRIENTE_PYMES" not in _codigos(r) and "TASA_FALTANTE" in _codigos(r)
    assert next(x for x in r["detalle"]["matriz"] if x["k"] == "pv")["tasa"] is None


def test_sin_tasa_de_mercado_y_tramo_sin_tasa_quedan_vacios():
    tasas = dict(EJ["parametros"]["tasas"])
    del tasas["t60"]
    r = _run(tasaMercado=None, tasas=tasas)
    f8 = next(x for x in r["detalle"]["filas"] if x["factura"] == "F-008")
    f11 = next(x for x in r["detalle"]["filas"] if x["factura"] == "F-011")
    assert f8["interes"] is None and f8["ca"] == 20000
    assert f11["tasa"] is None and f11["det"] is None
    assert {"FINANCIACION_SIN_TASA", "TASA_FALTANTE"} <= _codigos(r)


def test_exceso_de_deterioro_y_descuento_registrado():
    r = _run(provisionRegistrada=9000, descuentoRegistrado=1000)
    assert r["totals"]["ajuste"] == "-2856.62" and r["totals"]["ajusteFinanciacion"] == "1662.05"
    assert "DETERIORO_EXCESIVO" in _codigos(r)


def test_sin_provision_registrada_se_senala():
    r = _run(provisionRegistrada=None)
    assert "SIN_PROVISION_REGISTRADA" in _codigos(r)


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"cartera": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(tasas={"t30": 150})
    with pytest.raises(ValueError):
        _run(tasaMercado=-1)
    v = m.validar_filas("cartera", [{"id": "F-1", "cliente": "A", "emision": "2025-01-01", "vence": "x", "saldo": "abc", "_row": 2},
                                    {"id": "TOTAL", "cliente": "A", "emision": "2025-01-01", "vence": "2025-02-01", "saldo": "1", "tasa_individual": "120", "_row": 3}])
    assert not v["ok"] and len(v["errors"]) == 4


def test_hojas_nombres_y_anchos():
    for _, ds, p, c in m.ESCENARIOS:
        res = m.ejecutar(ds, p, c)
        hs = m.hojas(res)
        assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
        for h in hs:
            for fila in h["rows"] + ([h["total"]] if h["total"] else []):
                assert len(fila) == len(h["cols"]), h["name"]


def test_semaforo_cobros_posteriores():
    """La cédula 05 lleva un Semáforo coloreable por fila que marca la cartera vencida sin cobro posterior."""
    from backend.app.aud.niif.procesadores import base
    h = next(x for x in m.hojas(_run()) if x["name"] == "05_Cobros_posteriores")
    assert "Semáforo" in [c[0] for c in h["cols"]] and h.get("colores") == ["Semáforo"]
    j = [c[0] for c in h["cols"]].index("Semáforo")
    valores = {f[j]["v"] for f in h["rows"]}
    assert valores <= {"Alerta", "Conforme"} and "Alerta" in valores       # F-004, F-005, … vencidas sin cobro
    assert all(base.rol_color(h, "Semáforo", f[j]) in ("alta", "baja") for f in h["rows"])
    assert h["total"][j] == ""                                              # la fila TOTAL no se pinta


def test_conclusion():
    """La cédula 13 lleva indicadores clave con importes en fórmula y un semáforo coloreable en «Estado»."""
    from backend.app.aud.niif.procesadores import base
    con = next(x for x in m.hojas(_run()) if x["name"] == "13_Conclusion")
    assert con["label"] == "Indicadores y conclusión"
    cols = [c[0] for c in con["cols"]]
    assert cols == ["Indicador", "Importe", "Porcentaje", "Cantidad", "Estado"]
    assert "Estado" in con["colores"]
    ji, je = cols.index("Importe"), cols.index("Estado")
    assert any(isinstance(f[ji], dict) and "f" in f[ji] for f in con["rows"])
    roles = {base.rol_color(con, "Estado", f[je]) for f in con["rows"]}
    assert roles & {"alta", "media", "baja"}
    assert "alta" in roles       # el ejemplo tiene ajuste de deterioro: al menos una «Alerta»


def test_lectura():
    """La cédula 14 lee los resultados en causa-efecto con las cifras embebidas por FIXED."""
    lec = next(x for x in m.hojas(_run()) if x["name"] == "14_Lectura")
    assert lec["label"] == "Lectura de resultados"
    assert [c[0] for c in lec["cols"]] == ["Concepto", "Detalle"]
    assert 3 <= len(lec["rows"]) <= 5
    for fila in lec["rows"]:
        assert isinstance(fila[0], str) and fila[0]
        det = fila[1]
        assert isinstance(det, dict) and "f" in det and "FIXED(" in det["f"]
    assert "Detalle" in m.EXPLICA["14_Lectura"]


def test_definicion():
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "cxc_cartera" and len(d["program"]) >= 5
    assert "pce_simplificada" not in d["summary"] and "PYMES" in d["summary"]
