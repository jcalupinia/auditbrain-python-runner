"""Beneficios sociales y nómina: ejemplo de control con cifras recalculadas a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import nomina_beneficios as m

E = m.EJEMPLO


def correr(datasets=None, **param):
    return m.ejecutar(datasets or E["datasets"], {**E["parametros"], **param}, E["corte"])


def _codigos(r):
    return {e["code"] for e in r["exceptions"]}


def _e(r, id):
    return next(x for x in r["detalle"]["empleados"] if x["id"] == id)


def _a(r, id):
    return next(x for x in r["detalle"]["actuarial"] if x["id"] == id)


def test_fechas_como_excel():
    from datetime import date
    assert m.d360(date(2025, 1, 1), date(2026, 1, 1)) == 360
    assert m.d360(date(2025, 3, 15), date(2026, 1, 1)) == 286
    assert m.d360(date(2025, 1, 1), date(2025, 7, 1)) == 180
    assert m.edate(date(2024, 2, 29), 12) == date(2025, 2, 28)


def test_ejemplo_cifras_a_mano():
    r = correr()
    t = r["totals"]
    # E01: 1.200 × 360 ÷ 30 = 14.400; horas extras = 1.200 ÷ 240 × (20 × 1,5 + 10 × 2) = 250 → bruto 14.650.
    a = _e(r, "E01")
    assert a["dias"] == 360 and a["anios"] == 10 and a["he_calc"] == pytest.approx(250) and a["bruto"] == pytest.approx(14650)
    # D13 = 14.650 ÷ 360 × 30 ÷ 12 = 101,74; D14 Sierra desde 1-ago = 470 × 150 ÷ 360 = 195,83.
    assert m.r2(a["d13"]) == "101.74" and a["d14_dias"] == 150 and m.r2(a["d14"]) == "195.83"
    # Vacaciones: 10 años → 15 + 5 = 20 días; saldo 10 + 20 − 15 = 15 × 14.650 ÷ 360 = 610,42. FR = 14.650 × 8,33 % = 1.220,35.
    assert a["dias_anuales"] == 20 and a["saldo"] == pytest.approx(15) and m.r2(a["vac"]) == "610.42" and m.r2(a["fr"]) == "1220.35"
    # E02 (Costa): D14 desde 1-mar = 470 × 300 ÷ 360 = 391,67; aporte personal 10.320 × 9,45 % = 975,24 vs 900.
    b = _e(r, "E02")
    assert b["d14_dias"] == 300 and m.r2(b["d14"]) == "391.67" and m.r2(b["ap"]) == "975.24" and m.r2(b["ap_dif"]) == "-75.24"
    # E03 ingresó 1-abr: 270 días; vacaciones 15 × 270 ÷ 360 = 11,25 días × 20 = 225; sin fondo de reserva (13.º mes en 2026).
    c = _e(r, "E03")
    assert c["dias"] == 270 and c["devengados"] == pytest.approx(11.25) and c["vac"] == pytest.approx(225) and c["fr"] == 0
    # E04 salió el 30-jun: 180 días, fondo debido 6.000 × 8,33 % = 499,80; sin décimos ni vacaciones al corte.
    d = _e(r, "E04")
    assert d["activo"] == "No" and d["dias"] == 180 and m.r2(d["fr"]) == "499.80" and d["d13"] == d["d14"] == d["vac"] == 0
    # E05 mensualiza D14 → 0; D13 = 27.000 ÷ 360 × 30 ÷ 12 = 187,50 vs 150.
    assert _e(r, "E05")["d14"] == 0 and _e(r, "E05")["d13"] == pytest.approx(187.5)
    # E06: horas 700 ÷ 240 × 16 × 1,5 = 70 vs 90; bruto 8.400 + 90 = 8.490 vs 8.290 registrado.
    f = _e(r, "E06")
    assert f["he_calc"] == pytest.approx(70) and f["bruto"] == pytest.approx(8490) and f["dif_rem"] == pytest.approx(-200)
    # E07: 13.º mes el 15-nov-2025 → 46 días; 5.640 × 8,33 % × 46 ÷ 360 = 60,03.
    g = _e(r, "E07")
    assert g["dias_fr"] == 46 and m.r2(g["fr"]) == "60.03"
    # Totales.
    assert t["remuneracionRegistrada"] == "95300.00" and t["remuneracionRecalculada"] == "95500.00" and t["difRemuneracion"] == "-200.00"
    assert t["d13Recalculado"] == "575.07" and t["d14Recalculado"] == "1762.50" and t["vacacionesRecalculadas"] == "6296.00"
    assert t["fondoReservaEsperado"] == "7095.55" and t["aportePatronalRecalculado"] == "11578.95" and t["difAportePersonal"] == "-75.23"
    # Desahucio (CT art. 185 con la base del art. 95: sueldo + (horas extras + comisiones del año) ÷ 12).
    # E01 1.200 + 250/12 = 1.220,8333 × 25 % × 10 = 3.052,0833; E02 800 + 720/12 = 860 × 25 % × 5 = 1.075;
    # E03 600 × 25 % × 0 = 0; E05 2.000 + 3.000/12 = 2.250 × 25 % × 15 = 8.437,50; E06 700 + 90/12 = 707,50 × 25 % × 3 = 530,625;
    # E07 470 × 25 % × 1 = 117,50; E08 1.500 × 25 % × 13 = 4.875 → 18.087,71 (antes, solo con el sueldo, 17.017,50).
    assert m.r2(a["accesorias"]) == "20.83" and m.r2(a["rem_ult"]) == "1220.83" and m.r2(a["des_ref"]) == "3052.08"
    assert m.r2(_e(r, "E05")["des_ref"]) == "8437.50" and t["desahucioLegalReferencial"] == "18087.71"
    # Actuarial: JUB 85.000 + 9.500 + 6.800 + 3.200 − 2.500 = 102.000; DES 30.000 + 4.200 + 2.400 − 1.500 − 3.000 = 32.100 vs 32.500.
    assert _a(r, "JUB")["recalc"] == pytest.approx(102000) and _a(r, "DES")["dif_rf"] == pytest.approx(400)
    assert t["gastoActuarialResultados"] == "22900.00" and t["oriActuarial"] == "1700.00" and t["dboInforme"] == "134500.00"
    # Ajuste: 37,49 + 195,84 + 743,33 + 559,82 − 0,01 + 7.000 = 8.536,47.
    assert t["ajustePasivos"] == "8536.47" and r["primary"] == "ajustePasivos" and m.TOTAL_EJEMPLO in t
    assert {"APORTE_IESS", "DECIMO_TERCERO", "DECIMO_CUARTO", "VACACIONES_NO_PROVISIONADAS", "VACACIONES_DIFERENCIA", "FONDO_RESERVA_NO_PAGADO",
            "RECALCULO_NOMINA", "HORAS_EXTRAS", "NETO_NOMINA", "PLANILLA_IESS", "CONCILIACION_MAYOR", "PROVISION_ACTUARIAL",
            "NUEVAS_MEDICIONES_EN_RESULTADOS", "DBO_ROLLFORWARD", "CENSO_ACTUARIAL", "EMPLEADO_SIN_ESTUDIO", "SUPUESTOS_ACTUARIALES",
            "D14_SBU_PAGO"} <= _codigos(r)
    # E07 sin provisión informada: la diferencia queda en blanco (M22) y se señala.
    assert g["vac_dif"] is None and any("E07" in e["message"] for e in r["exceptions"] if e["code"] == "VACACIONES_NO_PROVISIONADAS")


def test_rutas_por_marco():
    base = correr()
    assert base["detalle"]["ruta"] == "ORI"
    # NIIF completas: el parámetro de política no cambia el destino.
    assert correr(actuarialesEn="Resultados")["totals"]["oriActuarial"] == "1700.00"
    r = correr(_marco=m.MARCO_PYMES, _edicion="2015", actuarialesEn="Resultados")
    assert r["totals"]["gastoActuarialResultados"] == "24600.00" and r["totals"]["oriActuarial"] == "0.00"
    assert "POLITICA_ACTUARIAL_PYMES" in _codigos(r) and "NUEVAS_MEDICIONES_EN_RESULTADOS" not in _codigos(r)
    r = correr(_marco=m.MARCO_PYMES, _edicion="2025", actuarialesEn="ORI")
    assert r["totals"]["oriActuarial"] == "1700.00" and r["detalle"]["edicion"] == "2025"
    assert {kk: v for kk, v in r["totals"].items() if "Actuarial" not in kk} == {kk: v for kk, v in base["totals"].items() if "Actuarial" not in kk}


def test_decimo_cuarto_sbu_fecha_de_pago():
    """Sin el SBU de la fecha de pago se provisiona con el del corte y se señala; con él, la provisión sube."""
    base = correr()
    assert "D14_SBU_PAGO" in _codigos(base) and base["totals"]["d14Recalculado"] == "1762.50"
    # E01 Sierra, 150 días: 470 × 150 ÷ 360 = 195,83 → 482 × 150 ÷ 360 = 200,83 (5,00 más por empleado con derecho pleno).
    r = correr(sbuPago=482)
    assert m.r2(_e(r, "E01")["d14"]) == "200.83" and "D14_SBU_PAGO" not in _codigos(r)
    # Total: 1.762,50 × 482 ÷ 470 = 1.807,50; el ajuste a pasivos sube en los mismos 45,00.
    assert r["totals"]["d14Recalculado"] == "1807.50" and r["totals"]["ajustePasivos"] == "8581.47"
    with pytest.raises(ValueError):
        correr(sbuPago=0)


def test_parametros():
    r = correr(sbu=500)
    assert m.r2(_e(r, "E01")["d14"]) == "208.33"
    with pytest.raises(ValueError):
        correr(aportePersonal=150)
    with pytest.raises(ValueError):
        correr(mesInicioD13=13)
    with pytest.raises(ValueError):
        correr(regionPorDefecto="Luna")
    with pytest.raises(ValueError):
        correr(actuarialesEn="Balance")


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"empleados": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    malo = [{"id": "X", "nombre": "x", "fecha_ingreso": "2025-05-01", "fecha_salida": "2025-04-01", "sueldo_mensual": "500",
             "remuneracion_anual": "1", "_row": 2}]
    with pytest.raises(ValueError):
        m.ejecutar({"empleados": malo}, {}, "2025-12-31")
    v = m.validar_filas("empleados", [{**malo[0], "sueldo_mensual": "-5"}])
    assert not v["ok"] and {e["field"] for e in v["errors"]} == {"sueldo_mensual", "fecha_salida"}
    assert m.validar_filas("actuarial", [{**E["datasets"]["actuarial"][1], "_row": 3}])["ok"]      # ganancia actuarial negativa admitida
    # Mínimo: sin estudio actuarial ni mayor; registros no informados quedan en blanco.
    r = m.ejecutar(m._MIN, {}, "2025-12-31")
    assert {"SIN_ESTUDIO_ACTUARIAL", "SIN_MAYOR", "REGISTRO_NO_INFORMADO", "VACACIONES_NO_PROVISIONADAS"} <= _codigos(r)
    assert r["totals"]["ajustePasivos"] == "0.00" and "difMayorNomina" not in r["totals"]
    # Saldo de vacaciones negativo: se señala y la provisión no es negativa.
    ds = {"empleados": [{**m._MIN["empleados"][0], "vac_saldo_inicial": "0", "vac_gozados": "30"}]}
    r = m.ejecutar(ds, {}, "2025-12-31")
    assert "VACACIONES_SALDO_NEGATIVO" in _codigos(r) and r["detalle"]["empleados"][0]["vac"] == 0


def test_hojas_y_definicion():
    for _, ds, p, c in m.ESCENARIOS:
        r = m.ejecutar(ds, p, c)
        hs = m.hojas(r)
        assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
        for h in hs:
            assert len(h["name"]) <= 31
            for f in h["rows"] + ([h["total"]] if h.get("total") else []):
                assert len(f) == len(h["cols"]), h["name"]
        assert [f[0] for f in hs[0]["rows"]] == list(r["labels"].values())
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "nomina_beneficios" and len(d["program"]) >= 5
    assert m.RUBRO == "NOMINA" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
