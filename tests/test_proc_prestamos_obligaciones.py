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
    # OP-107: DSCR incumplido y sin dispensa, pero el covenant se mide el 30-06-2026 (después del corte):
    # NIC 1 72B → no reclasifica; solo exige la revelación del 76ZA.
    c7 = _c(r, "OP-107")
    assert c7["incump"] == "Sí" and c7["cov_futuro"] == "Sí" and c7["exigible"] == "No"


def test_covenant_medido_despues_del_corte_no_reclasifica():
    r = _run()
    c7 = _c(r, "OP-107")
    # Alemán 100.000 / 12 = 8.333,33 por trimestre; al corte 5 cuotas (58.333,33) y a 12 meses 9 (25.000).
    assert round(c7["cap_c"], 2) == 58333.33 == round(100000 - 5 * 100000 / 12, 2)
    assert round(c7["cap_12"], 2) == 25000.00 == round(100000 - 9 * 100000 / 12, 2)
    assert round(c7["cp"], 2) == 34938.20 == round(58333.33333333333 - 25000 + c7["acc_tie"], 2)   # capital 12 m + interés TIE
    assert round(c7["lp"], 2) == round(c7["ca_tot"] - c7["cp"], 2) == 24624.90
    assert "COVENANT_POSTERIOR_AL_CORTE" in _codigos(r) and "COVENANT_SIN_DISPENSA" not in {
        e["code"] for e in r["exceptions"] if e["message"].startswith("OP-107")}
    t = {k: float(v) for k, v in r["totals"].items()}
    assert t["corriente"] == 395633.02 and t["noCorriente"] == 264332.18 and t["reclasificacionCovenant"] == 127760.65
    # Sin la fecha de medición se mantiene el tratamiento anterior (reclasifica) y se pide el dato (M22).
    sin_fecha = _run(ds=_ds(**{"OP-107": {"fecha_covenant": ""}}))
    c7b = _c(sin_fecha, "OP-107")
    assert c7b["exigible"] == "Sí" and c7b["cp"] == c7b["ca_tot"] and c7b["lp"] == 0
    assert float(sin_fecha["totals"]["corriente"]) == 420257.92 and float(sin_fecha["totals"]["noCorriente"]) == 239707.28
    assert "COVENANT_SIN_FECHA_MEDICION" in {e["code"] for e in sin_fecha["exceptions"] if e["message"].startswith("OP-107")}
    # OP-103 tampoco informa la fecha: se pide, sin cambiar su clasificación.
    assert "COVENANT_SIN_FECHA_MEDICION" in {e["code"] for e in r["exceptions"] if e["message"].startswith("OP-103")}


def test_revelacion_de_incumplimientos_niif7_18_19():
    r = _run()
    rev = {e["message"].split(":")[0] for e in r["exceptions"] if e["code"] == "REVELACION_INCUMPLIMIENTO"}
    assert rev == {"OP-102", "OP-105", "OP-107"}          # covenants incumplidos al corte (OP-107 además con impago)
    msg = next(e["message"] for e in r["exceptions"] if e["code"] == "REVELACION_INCUMPLIMIENTO" and e["message"].startswith("OP-107"))
    assert "NIIF 7 18–19" in msg and "1.645,83" in msg    # pagos tabla 41.645,83 − informados 40.000
    assert "PYMES 11.47" in next(e["message"] for e in _run(PYMES)["exceptions"] if e["code"] == "REVELACION_INCUMPLIMIENTO")


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
