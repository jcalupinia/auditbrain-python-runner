"""Procesador de préstamos y obligaciones financieras (NIIF 9 / NIC 1 · PYMES Secciones 11 y 4): ejemplo recalculado a mano."""
import copy

import pytest

from backend.app.aud.niif.procesadores import prestamos_obligaciones as m

EJ = m.EJEMPLO
NIIF = {**EJ["parametros"], "_marco": "NIIF completas"}
PYMES = {**EJ["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}


def _run(param=NIIF, ds=None, corte=None):
    return m.ejecutar(ds or EJ["datasets"], param, corte or EJ["corte"])


def _c(res, pid):
    return next(c for c in res["detalle"]["prestamos"] if c["id"] == pid)


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def _ds(**cambios):
    ds = copy.deepcopy(EJ["datasets"])
    for pid, campos in cambios.items():
        next(f for f in ds["prestamos"] if f["id"] == pid).update(campos)
    return ds


def test_frances_con_comision_a_gasto_a_mano():
    c = _c(_run(), "OP-101")
    i = 0.11 / 12
    cuota = 120000 * i / (1 - (1 + i) ** -36)
    assert round(cuota, 2) == 3928.65 == round(c["cuota"], 2)
    cap23 = 120000 * (1 + i) ** 23 - cuota * ((1 + i) ** 23 - 1) / i
    assert round(c["cap_c"], 2) == 47940.12 == round(cap23, 2)
    assert round(c["acc_nom"], 2) == 226.81 == round(cap23 * i * 16 / 31, 2)     # 15-dic → 31-dic de 31 días
    # TIE: el valor actual de las 36 cuotas a la TIE es el neto recibido (120.000 − 2.400)
    va = sum(cuota / (1 + c["tie"]) ** t for t in range(1, 37))
    assert va == pytest.approx(117600, abs=1e-6)
    assert round(c["tie_anual"] * 100, 2) == 13.13
    assert c["trat"] == "Gasto" and round(c["por_amortizar"], 2) == 379.36
    assert round(c["gasto_tie"], 2) == 8334.99 and round(c["int_anio"], 2) == 7478.25
    assert abs(c["comprobacion"]) < 1e-6                                           # movimiento: inicio + alta + gasto − pagos = corte


def test_aleman_intereses_y_covenant_con_dispensa_posterior():
    c = _c(_run(), "OP-102")
    assert c["k"] == 3 and round(c["cap_c"], 2) == 170000.00
    assert round(c["pagos"], 2) == 44250.00 == (10000 + 5000) + (10000 + 4750) + (10000 + 4500)
    assert round(c["acc_nom"], 2) == 1416.67 == round(170000 * 0.025 * 30 / 90, 2)
    assert c["incump"] == "Sí" and c["disp_valida"] == "No" and c["exigible"] == "Sí"
    assert c["cp"] == c["ca_tot"] and c["lp"] == 0                                 # NIC 1 74: toda la deuda corriente


def test_bullet_tie_y_confirmacion():
    c = _c(_run(), "OP-104")
    assert round(c["acc_nom"], 2) == 49.45 == round(150000 * 0.06 / 182, 2)
    # TIE semestral: VA de 9.000 × 4 + 150.000 = neto 148.500
    r = c["tie"]
    assert sum(9000 / (1 + r) ** t for t in range(1, 5)) + 150000 / (1 + r) ** 4 == pytest.approx(148500, abs=1e-6)
    assert c["cp_venc"] == pytest.approx(c["acc_tie"])                            # bullet: solo el interés devengado es corriente
    assert round(c["dif_conf"], 2) == 3841.41                                      # 150.000 − 145.000 − 1.158,59 por amortizar


def test_dispensa_valida_y_ratios():
    r = _run()
    c5 = _c(r, "OP-105")
    assert c5["incump"] == "Sí" and c5["disp_valida"] == "Sí" and c5["exigible"] == "No"   # dispensa al corte con gracia ≥ 12 m (75)
    rt = r["detalle"]["ratios"]
    assert rt["DSCR"]["ratio"] == pytest.approx(200000 / r["detalle"]["servicio"]) and rt["DSCR"]["cumple"] == "No"
    assert rt["Deuda / EBITDA"]["cumple"] == "No" and rt["Cobertura de intereses"]["cumple"] == "Sí"
    assert _c(r, "OP-107")["exigible"] == "Sí"                                     # DSCR calculado incumplido, sin dispensa


def test_problemas_minimos_y_totales():
    r = _run()
    assert {"CONFIRMACION_DIFERENCIA", "INTERES_DEVENGADO_NO_REGISTRADO", "COMISIONES_A_GASTO", "CLASIFICACION_CP_LP",
            "COVENANT_SIN_DISPENSA", "ENDEUDAMIENTO_SOBRE_LIMITE", "DISPENSA_POSTERIOR", "NO_DESEMBOLSADO",
            "GASTO_FINANCIERO_DIFERENCIA", "PAGOS_DIFERENCIA", "PASIVO_DIFERENCIA"} <= _codigos(r)
    assert r["primary"] == "ajuste"
    t = {k: float(v) for k, v in r["totals"].items()}
    assert t["ajuste"] == pytest.approx(t["pasivo"] - t["pasivoRegistrado"], abs=0.011)
    assert t["corriente"] + t["noCorriente"] == pytest.approx(t["pasivo"], abs=0.011)
    assert t["pasivo"] == 659965.19 and t["ajuste"] == 5075.37
    assert all(c["id"] != "OP-108" for c in r["detalle"]["prestamos"])             # desembolsado después del corte
    # préstamos cuadrados: sin diferencias de centavos por redondeo de los datos
    msgs = [e["message"] for e in r["exceptions"] if e["code"] == "PASIVO_DIFERENCIA"]
    assert not any(x.startswith(("OP-103", "OP-105", "OP-106")) for x in msgs)


def test_ruta_pymes_mismas_cifras_otras_citas():
    rn, rp = _run(), _run(PYMES)
    assert rn["totals"] == rp["totals"]
    com = next(e["message"] for e in rp["exceptions"] if e["code"] == "COMISIONES_A_GASTO")
    assert "11.13" in com and "tasa nominal" in com
    assert any("4.7" in e["message"] for e in rp["exceptions"] if e["code"] == "COVENANT_SIN_DISPENSA")
    marco = next(f for f in m.hojas(rp)[1]["rows"] if f[0] == "Marco y ruta de cálculo")[1]
    assert "Sección 11" in marco
    marco25 = next(f for f in m.hojas(_run({**PYMES, "_edicion": "2025"}))[1]["rows"] if f[0] == "Marco y ruta de cálculo")[1]
    assert "2025" in marco25


def test_sin_datos_de_entidad_ratios_vacios():
    r = _run({"_marco": "NIIF completas"})
    assert all(x["ratio"] is None and x["cumple"] == "" for n, x in r["detalle"]["ratios"].items() if n != "Cobertura de intereses")
    assert "ENDEUDAMIENTO_SOBRE_LIMITE" not in _codigos(r)
    assert "COVENANT_SIN_EVALUAR" in _codigos(r)
    assert _c(r, "OP-107")["exigible"] == "No"                                     # sin datos no se presume incumplimiento


def test_patrimonio_negativo_y_ebit():
    r = _run({**NIIF, "patrimonio": -50000, "baseCobertura": "EBIT"})
    rt = r["detalle"]["ratios"]
    assert rt["Deuda / patrimonio"]["ratio"] is None and "RATIO_NO_CALCULABLE" in _codigos(r)
    assert rt["Cobertura de intereses"]["num"] == 220000


def test_tasa_cero_sin_comisiones():
    ds = {"prestamos": [m._p("Z-1", "Banco", "2025-01-01", "12000", "12", "0", "Mensual", "Francés", "6000")]}
    c = _c(m.ejecutar(ds, NIIF, "2025-06-30"), "Z-1")
    assert c["tie"] == pytest.approx(0, abs=1e-12) and c["cuota"] == 1000 and round(c["cap_c"], 2) == 7000   # 5 cuotas pagadas; la 6.ª vence el 1-jul


def test_errores_de_entrada():
    with pytest.raises(ValueError):
        m.ejecutar({"prestamos": []}, NIIF, EJ["corte"])
    with pytest.raises(ValueError):
        _run(ds=_ds(**{"OP-101": {"tasa": ""}}))
    with pytest.raises(ValueError):
        _run(ds=_ds(**{"OP-102": {"plazo": "61"}}))                                # no múltiplo de trimestres
    with pytest.raises(ValueError):
        _run(ds=_ds(**{"OP-101": {"comisiones": "120000"}}))
    with pytest.raises(ValueError):
        _run({**NIIF, "baseCobertura": "Ventas"})
    with pytest.raises(ValueError):
        _run({**NIIF, "totalActivos": -1})
    with pytest.raises(ValueError):
        _run(ds=_ds(**{"OP-103": {"id": "OP-101"}}))                               # operación repetida
    v = m.validar_filas("prestamos", [{"_row": 2, "id": "X", "banco": "B", "desembolso": "2025-01-01", "monto": "-5", "plazo": "12",
                                       "tasa": "150", "periodicidad": "quincenal", "sistema": "otro", "saldo_reg": "1",
                                       "covenant": "ventas", "incumplido": "tal vez"}])
    campos = {e.get("field") for e in v["errors"]}
    assert not v["ok"] and {"monto", "tasa", "periodicidad", "sistema", "covenant", "incumplido"} <= campos


def test_hojas_y_definicion():
    for esc, ds, par, corte in m.ESCENARIOS:
        res = m.ejecutar(ds, par, corte)
        hs = m.hojas(res)
        assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
        for h in hs:
            assert len(h["name"]) <= 31
            for f in h["rows"] + ([h["total"]] if h.get("total") else []):
                assert len(f) == len(h["cols"]), (esc, h["name"])
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "prestamos_obligaciones" and len(d["program"]) >= 5
    assert m.kind("prestamos") == "prestamos" and m.RUBRO == "PRESTAMOS"
