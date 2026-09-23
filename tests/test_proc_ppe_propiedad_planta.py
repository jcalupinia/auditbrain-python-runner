"""Propiedad, planta y equipo: ejemplo de control con cifras recalculadas a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import ppe_propiedad_planta as m

E = m.EJEMPLO


def correr(datasets=None, **param):
    return m.ejecutar(datasets or E["datasets"], {**E["parametros"], **param}, E["corte"])


def _codigos(r):
    return {e["code"] for e in r["exceptions"]}


def _activo(r, id):
    return next(a for a in r["detalle"]["activos"] if a["id"] == id)


def test_ejemplo_cifras_a_mano():
    r = correr()
    # VEH-01: (40.000 − 4.000) ÷ 60 × 12 = 7.200 vs 6.000 registrada.
    assert _activo(r, "VEH-01")["dep"] == pytest.approx(7200)
    # VEH-02, baja 30-jun: 27.000 ÷ 60 × 12 × 181 ÷ 365 = 2.677,81; VNL 5.722,19; ganancia 3.277,81 vs 1.500.
    v2 = _activo(r, "VEH-02")
    assert v2["dias"] == 181 and m.r2(v2["dep"]) == "2677.81"
    assert m.r2(v2["nbv_baja"]) == "5722.19" and m.r2(v2["res_calc"]) == "3277.81" and m.r2(v2["res_dif"]) == "1777.81"
    # MOB-01 alta 1-abr: 12.000 ÷ 120 × 12 × 275 ÷ 365 = 904,11 (coincide con lo registrado).
    assert m.r2(_activo(r, "MOB-01")["dep"]) == "904.11"
    # Construcción en curso y terrenos: no se deprecian; el método no lineal queda en blanco (M22).
    assert _activo(r, "OBRA-01")["dep"] == 0 and _activo(r, "TERR-01")["dep"] == 0 and _activo(r, "EQC-01")["dep"] is None
    # MAQ-01: VNL 120.000 − 72.000 = 48.000 vs recuperable 40.000 → 8.000.
    assert r["totals"]["deterioroAdicional"] == "8000.00"
    # Componentes: motor 30.000 de 150.000 = 20 % (significativo con umbral 10 %).
    motor = _activo(r, "MAQ-01-M")
    assert motor["part"] == pytest.approx(0.2) and motor["signif"] == "Sí"
    # Costos por préstamos con el anexo (NIC 23.12 y 14), recalculados a mano (ver test_prestamos_por_activo).
    assert r["totals"]["capitalizablePeriodo"] == "12547.27" and r["totals"]["ajusteIntereses"] == "3547.27"
    # Revaluación terreno 360.000 − 300.000 = 60.000; sin decremento previo informado quedan los 60.000 en ORI (NIC 16.39).
    assert r["totals"]["revaluacionORI"] == "60000.00" and r["totals"]["revaluacionResultado"] == "0.00"
    # MAQ-01 no está revaluado: los 8.000 de deterioro van íntegros a resultados (NIC 36.60-61 no aplica).
    assert r["totals"]["deterioroORI"] == "0.00" and r["totals"]["deterioroResultado"] == "8000.00"
    # Desmantelamiento 50.000 ÷ 1,06^10; no hay provisión registrada, así que no hay descuento que revertir:
    # actualización financiera del período 0 y los 27.919,74 son cambio de estimación contra el costo (CINIIF 1.5 a).
    assert r["totals"]["provDesmantelamiento"] == "27919.74"
    assert r["totals"]["desmantelamientoFinanciero"] == "0.00" and r["totals"]["ajusteDesmantelamiento"] == "27919.74"
    # Roll-forward: 1.115.000 + 212.000 − 30.000 = 1.297.000; dep. acumulada 239.900 + 37.854,11 − 24.300 = 253.454,11.
    assert r["totals"]["costoFinal"] == "1297000.00" and r["totals"]["difCosto"] == "0.00" and r["totals"]["difDepAcum"] == "454.11"
    # Efecto en resultados: −177,81 − 8.000 + 1.777,81 + 3.547,27 = −2.852,73.
    assert r["totals"]["ajusteDep"] == "177.81" and r["totals"]["ajusteResultado"] == "-2852.73" and r["primary"] == "ajusteResultado"
    assert {"DEPRECIACION_DIFERENTE", "TOTALMENTE_DEPRECIADO_EN_USO", "BAJA_MAL_CALCULADA", "DETERIORO", "DESMANTELAMIENTO_NO_RECONOCIDO",
            "DEPRECIACION_EN_CONSTRUCCION", "METODO_NO_RECALCULADO", "REVALUACION_CLASE_INCOMPLETA", "ADICION_GASTO_CAPITALIZADO",
            "INTERESES_DIFERENCIA", "CONCILIACION_AUXILIAR_MAYOR", "REVISAR_COMPONENTES",
            "REVALUACION_SIN_DECREMENTO_PREVIO", "TASA_CAPITALIZACION_DIFIERE"} <= _codigos(r)


@pytest.mark.parametrize("edicion", ["2015", "2025"])
def test_pymes_intereses_a_gasto(edicion):
    r = correr(_marco=m.MARCO_PYMES, _edicion=edicion)
    # Sección 25.2 (igual en 2015 y 2025): no se capitaliza nada, ni siquiera con el anexo de préstamos cargado.
    assert r["totals"]["capitalizablePeriodo"] == "0.00"
    assert r["totals"]["ajusteIntereses"] == "-9000.00" and r["totals"]["ajusteResultado"] == "-15400.00"
    assert "INTERESES_CAPITALIZADOS_PYMES" in _codigos(r) and "INTERESES_DIFERENCIA" not in _codigos(r)
    assert "PRESTAMOS_NO_SE_CAPITALIZAN_PYMES" in _codigos(r) and r["detalle"]["edicion"] == edicion
    assert [a["esp_cap"] for a in r["detalle"]["capitalizacion"]] == [0.0]


def test_sin_tasa_de_capitalizacion_no_inventa():
    """Sin anexo de préstamos y sin tasa en los parámetros: el importe queda vacío, no se asume cero."""
    r = correr(m._SIN_PRESTAMOS, tasaCapitalizacion=None)
    assert "ajusteIntereses" in r["totals"] and r["totals"]["ajusteIntereses"] == "0.00"
    assert "TASA_CAPITALIZACION_FALTANTE" in _codigos(r)
    assert all(x["cap"] is None for x in r["detalle"]["adiciones"] if x["apto"] == "Sí")


def test_prestamos_por_activo():
    """NIC 23.12 (préstamo específico) y 23.14 (tasa de capitalización de los generales), recalculado a mano.

    OBRA-01, desembolsos aptos del período: AD-01 150.000 desde el 1-mar (305 días) y AD-02 45.000 desde el
    1-sep (121 días) = 195.000; base ponderada por tiempo = (150.000 × 305 + 45.000 × 121) ÷ 365 =
    51.195.000 ÷ 365 = 140.260,27.
    PR-01 específico (120.000): costo financiero realmente incurrido 9.000 − rendimientos de la inversión
    temporal 1.200 = 7.800 capitalizables (23.12).
    PR-02 y PR-03 generales: tasa de capitalización = (32.000 + 12.000) ÷ (400.000 + 100.000) = 8,80 % (23.14).
    Proporción de los desembolsos financiada con generales = 1 − 120.000 ÷ 195.000 = 38,461538 %;
    base = 140.260,27 × 38,461538 % = 53.946,26; capitalizable de los generales = 53.946,26 × 8,80 % = 4.747,27.
    Capitalizable del activo = 7.800 + 4.747,27 = 12.547,27. Costos por préstamos incurridos en el período =
    9.000 + 32.000 + 12.000 = 53.000 → el tope del párrafo 14 no muerde (factor 1).
    Capitalizado por el cliente 9.000 → ajuste +3.547,27.
    """
    r = correr()
    c = r["detalle"]["capitalizacion"]
    assert len(c) == 1 and c[0]["activo"] == "OBRA-01"
    a = c[0]
    assert a["desemb"] == 195000 and a["base"] == pytest.approx((150000 * 305 + 45000 * 121) / 365)
    assert m.r2(a["base"]) == "140260.27"
    assert a["esp_imp"] == 120000 and a["esp_cap"] == 7800          # 9.000 − 1.200 (NIC 23.12)
    assert a["tasa"] == pytest.approx(0.088) and a["pct"] == pytest.approx(1 - 120000 / 195000)
    assert m.r2(a["base_gen"]) == "53946.26" and m.r2(a["cap_gen"]) == "4747.27"
    assert m.r2(a["antes"]) == "12547.27" and a["factor"] == 1 and m.r2(a["final"]) == "12547.27"
    assert a["reg"] == 9000 and m.r2(a["dif"]) == "3547.27"
    assert r["totals"]["capitalizableEspecificos"] == "7800.00" and r["totals"]["capitalizableGenerales"] == "4747.27"
    assert r["totals"]["costosPrestamosIncurridos"] == "53000.00"
    # Con el anexo, el capitalizable se mide por activo: el capitalizable por desembolso queda vacío.
    assert all(x["cap"] is None and x["int_dif"] is None for x in r["detalle"]["adiciones"])
    # La tasa del parámetro (8 %) no coincide con la media ponderada del anexo (8,80 %): se usa la del anexo.
    assert "TASA_CAPITALIZACION_DIFIERE" in _codigos(r)


def test_tope_costos_prestamos_incurridos():
    """NIC 23.14, última frase: lo capitalizado en el período no excede los costos por préstamos incurridos.

    Mismo ejemplo con un solo préstamo general de 40.000 y 6.000 de costo del período → tasa 15 %.
    Capitalizable de los generales = 53.946,26 × 15 % = 8.091,94; con el específico 7.800 → 15.891,94.
    Costos incurridos = 9.000 (específico) + 6.000 (general) = 15.000 < 15.891,94 → factor = 15.000 ÷
    15.891,94 = 0,943876 y el capitalizable del período se limita a 15.000,00 (exceso 891,94).
    Capitalizado por el cliente 9.000 → ajuste +6.000,00.
    Efecto neto en resultados = −177,81 − 8.000 + 1.777,81 + 6.000 = −400,00.
    """
    r = m.ejecutar(m._TOPE, E["parametros"], E["corte"])
    a = r["detalle"]["capitalizacion"][0]
    assert a["tasa"] == pytest.approx(0.15) and m.r2(a["cap_gen"]) == "8091.94" and m.r2(a["antes"]) == "15891.94"
    assert a["factor"] == pytest.approx(15000 / (7800 + (150000 * 305 + 45000 * 121) / 365 * (1 - 120000 / 195000) * 0.15))
    assert a["factor"] < 1 and m.r2(a["final"]) == "15000.00" and m.r2(a["dif"]) == "6000.00"
    assert r["totals"]["costosPrestamosIncurridos"] == "15000.00" and r["totals"]["capitalizablePeriodo"] == "15000.00"
    assert r["totals"]["ajusteIntereses"] == "6000.00" and r["totals"]["ajusteResultado"] == "-400.00"
    tope = next(e for e in r["exceptions"] if e["code"] == "TOPE_COSTOS_PRESTAMOS")
    assert tope["amount"] == "891.94"                       # 15.891,94 − 15.000,00


def test_sin_anexo_de_prestamos_sigue_funcionando_y_avisa():
    """Sin el anexo, el cálculo es el de antes (tasa del parámetro por desembolso) y se emite el aviso.

    AD-01: 150.000 × 8 % × 305 ÷ 365 = 10.027,40 y AD-02: 45.000 × 8 % × 121 ÷ 365 = 1.193,42;
    capitalizado 9.000 → ajuste +2.220,82 y efecto neto en resultados −4.179,18.
    """
    r = correr(m._SIN_PRESTAMOS)
    assert r["totals"]["ajusteIntereses"] == m.r2(150000 * 0.08 * 305 / 365 - 9000 + 45000 * 0.08 * 121 / 365) == "2220.82"
    assert r["totals"]["ajusteResultado"] == "-4179.18"
    assert r["detalle"]["capitalizacion"] == [] and r["detalle"]["prestamos"] == []
    assert "SIN_ANEXO_PRESTAMOS" in _codigos(r)
    assert not {"capitalizableEspecificos", "capitalizableGenerales", "costosPrestamosIncurridos",
                "capitalizablePeriodo"} & set(r["totals"])


def test_anexo_de_prestamos_incompleto_no_inventa():
    """M22: sin rendimientos del específico y sin importe del general, los importes quedan vacíos."""
    r = m.ejecutar(m._MIN, {}, "2025-12-31")
    a = r["detalle"]["capitalizacion"][0]
    assert a["activo"] == "V-1" and a["esp_imp"] == 5000
    assert a["esp_cap"] is None and a["tasa"] is None and a["cap_gen"] is None
    assert a["antes"] is None and a["factor"] is None and a["final"] is None and a["dif"] is None
    assert {"PRESTAMO_SIN_RENDIMIENTOS", "PRESTAMO_GENERAL_INCOMPLETO", "TOPE_NO_VERIFICABLE"} <= _codigos(r)
    assert not {"capitalizableEspecificos", "capitalizableGenerales", "capitalizablePeriodo"} & set(r["totals"])
    assert r["totals"]["costosPrestamosIncurridos"] == "1200.00"      # 400 + 800, ambos informados


def test_prestamos_datos_minimos_se_senalan():
    ds = {"activos": [{"id": "V", "descripcion": "v", "clase": "c", "fecha_uso": "2024-01-01", "costo_inicial": "1000", "_row": 2}],
          "prestamos": [{"id": "P1", "_row": 2}, {"id": "P2", "tipo": "Especifico", "costo_financiero": "10", "rendimientos": "0", "_row": 3},
                        {"id": "P3", "tipo": "Específico", "activo": "NO-EXISTE", "costo_financiero": "5", "rendimientos": "0", "_row": 4}]}
    r = m.ejecutar(ds, {}, "2025-12-31")
    assert {"PRESTAMO_SIN_TIPO", "PRESTAMO_SIN_COSTO_FINANCIERO", "PRESTAMO_SIN_ACTIVO",
            "PRESTAMO_ACTIVO_NO_EXISTE"} <= _codigos(r)
    v = m.validar_filas("prestamos", [{"id": "P1", "importe": "xx", "_row": 2}])
    assert not v["ok"] and {e["field"] for e in v["errors"]} == {"importe"}


def test_revaluados_deterioro_y_desmantelamiento():
    """NIC 16.39 (aumento que revierte un decremento previo), NIC 36.60-61 (deterioro contra el superávit) y
    CINIIF 1.5/1.8 (cambio de estimación al costo, actualización financiera a resultados).

    EDIF-R: 200.000 ÷ 480 × 12 = 5.000 de depreciación (igual a la registrada); acumulada 20.000 + 5.000 = 25.000;
    VNL 200.000 − 25.000 = 175.000. Revaluado a 185.000 → aumento 10.000; con decremento previo en resultados de
    12.000, los 10.000 van a resultados (16.39) y 0 a ORI. Deterioro = 185.000 − 170.000 = 15.000; superávit
    disponible = 30.000 previo + 0 del año → los 15.000 van contra el superávit (36.60-61) y 0 a resultados.
    MAQ-R: 100.000 ÷ 120 × 12 = 10.000 (igual a la registrada); acumulada 60.000; VNL 40.000. Revaluado a 42.000 →
    aumento 2.000 sin decremento previo informado → todo a ORI (se avisa). Deterioro = 42.000 − 35.000 = 7.000 sin
    superávit informado → no se reparte: queda en resultados (se avisa).
    Desmantelamiento: VP = 50.000 ÷ 1,06^10 = 27.919,74; registrada al cierre 26.500 → ajuste total 1.419,74;
    actualización del período = 26.000 × 6 % = 1.560,00 (costo financiero); cambio de estimación = 1.419,74 −
    1.560,00 = −140,26 (contra el costo del activo).
    Efecto neto en resultados = −0 (depreciación) − 7.000 (deterioro) + 0 + 0 + 10.000 (revaluación) − 1.560 = 1.440,00.
    """
    r = m.ejecutar(m._REVALUADOS, m.PARAMETROS_REVALUADOS, "2025-12-31")
    e, q = _activo(r, "EDIF-R"), _activo(r, "MAQ-R")
    assert e["dep"] == 5000 and e["nbv"] == 175000 and e["rev_dif"] == 10000
    assert e["rev_res"] == 10000 and e["rev_ori"] == 0            # 16.39: revierte el decremento previo de 12.000
    assert e["perdida"] == 15000 and e["supRem"] == 30000 and e["detORI"] == 15000 and e["detRes"] == 0
    assert q["rev_dif"] == 2000 and q["rev_ori"] == 2000 and q["rev_res"] == 0     # sin decremento previo: todo a ORI
    assert q["perdida"] == 7000 and q["detORI"] is None and q["detRes"] == 7000    # revaluado sin superávit: no se reparte
    assert r["totals"]["deterioroAdicional"] == "22000.00"
    assert r["totals"]["deterioroORI"] == "15000.00" and r["totals"]["deterioroResultado"] == "7000.00"
    assert r["totals"]["revaluacionORI"] == "2000.00" and r["totals"]["revaluacionResultado"] == "10000.00"
    ds = r["detalle"]["desmantelamiento"]
    assert m.r2(ds["vp"]) == "27919.74" and m.r2(ds["dif"]) == "1419.74"
    assert ds["actualizacion"] == 1560 and m.r2(ds["cambio"]) == "-140.26"
    assert r["totals"]["desmantelamientoFinanciero"] == "1560.00" and r["totals"]["ajusteDesmantelamiento"] == "-140.26"
    assert r["totals"]["ajusteResultado"] == "1440.00"
    assert {"REVALUACION_SIN_DECREMENTO_PREVIO", "DETERIORO_SIN_SUPERAVIT", "DESMANTELAMIENTO_DIFERENCIA"} <= _codigos(r)


def test_desmantelamiento_sin_saldo_inicial_no_inventa():
    r = correr(provisionDesmantelamiento=27000)
    assert "SIN_PROVISION_DESMANTELAMIENTO_INICIAL" in _codigos(r)
    assert "desmantelamientoFinanciero" not in r["totals"] and "ajusteDesmantelamiento" not in r["totals"]


def test_revaluacion_disminucion_contra_superavit():
    ds = {"activos": [{"id": "T", "descripcion": "Terreno", "clase": "Terrenos", "fecha_uso": "2010-01-01", "costo_inicial": "100000",
                       "valor_revaluado": "70000", "superavit_previo": "10000", "_row": 2}]}
    r = m.ejecutar(ds, {}, "2025-12-31")
    assert r["totals"]["revaluacionORI"] == "-10000.00" and r["totals"]["revaluacionResultado"] == "-20000.00"
    assert r["totals"]["ajusteResultado"] == "-20000.00"


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"activos": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    malo = {"activos": [{"id": "X", "descripcion": "x", "clase": "c", "costo_inicial": "1", "fecha_baja": "2026-02-01", "_row": 2}]}
    with pytest.raises(ValueError):
        m.ejecutar(malo, {}, "2025-12-31")
    v = m.validar_filas("activos", [{"id": "A", "descripcion": "a", "clase": "c", "costo_inicial": "abc", "vida_meses": "0", "_row": 3}])
    assert not v["ok"] and {e["field"] for e in v["errors"]} == {"costo_inicial", "vida_meses"}
    # Sin mayor ni desmantelamiento: se señala, no se asume cero.
    r = m.ejecutar({"activos": [{"id": "V", "descripcion": "v", "clase": "c", "fecha_uso": "2024-01-01", "costo_inicial": "10000",
                                 "vida_meses": "60", "_row": 2}]}, {}, "2025-12-31")
    assert {"SIN_MAYOR", "DESMANTELAMIENTO_NO_EVALUADO"} <= _codigos(r)
    assert "difCosto" not in r["totals"] and "provDesmantelamiento" not in r["totals"]
    assert r["rows"][0]["depRegistrada"] == "" and r["rows"][0]["diferencia"] == ""


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
    assert d["processor"] == "ppe_propiedad_planta" and len(d["program"]) >= 5
    assert m.RUBRO == "ACTIVOS_FIJOS" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
