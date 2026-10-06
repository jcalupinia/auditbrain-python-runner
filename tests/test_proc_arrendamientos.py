"""Procesador de arrendamientos (NIIF 16 / Sección 20 PYMES): ejemplo de control recalculado a mano."""
import copy

import pytest

from backend.app.aud.niif.procesadores import arrendamientos as m

EJ = m.EJEMPLO
NIIF = {**EJ["parametros"], "_marco": "NIIF completas"}
PYMES = {**EJ["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"}


def _run(param=NIIF, ds=None, corte=None):
    return m.ejecutar(ds or EJ["datasets"], param, corte or EJ["corte"])


def _c(res, cid):
    return next(c for c in res["detalle"]["contratos"] if c["id"] == cid)


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def test_bodega_anual_a_mano():
    c = _c(_run(), "C-02")
    vp = 10000 * (1 - 1.1 ** -5) / 0.1
    assert round(c["vp"], 2) == 37907.87 == round(vp, 2)
    s1 = vp * 1.1 - 10000
    s2 = s1 * 1.1 - 10000
    s3 = s2 * 1.1 - 10000
    assert round(c["pasivo"], 2) == 17355.37 == round(s3, 2)
    assert round(c["interes"], 2) == 2486.85 == round(s2 * 0.1, 2)
    assert round(c["cp"], 2) == 8264.46 == round(s3 - (s3 * 1.1 - 10000), 2)
    assert round(c["activo_ini"], 2) == 38407.87            # + costos directos 500 (24 c)
    assert round(c["dep"], 2) == 7681.57 and round(c["neto"], 2) == 15363.15


def test_modificacion_remedida_a_mano():
    c = _c(_run(), "C-07")
    ev = c["ev"]
    assert round(ev["antes"], 2) == 30925.16
    assert round(ev["revisado"], 2) == 34172.48 == round(13500 * (1 - 1.09 ** -3) / 0.09, 2)
    assert round(ev["ajuste"], 2) == 3247.31
    assert round(c["interes"], 2) == 3075.52 and round(c["pasivo"], 2) == 23748.00
    assert round(c["dep"], 2) == 10664.94 and round(c["neto"], 2) == 21329.88


def test_venta_con_arrendamiento_posterior_ejemplo_24():
    c = _c(_run(), "C-08")
    s = c["slb"]
    assert round(c["pasivo_ini"], 2) == 1459199.02
    assert s["financiacion"] == 200000
    assert round(s["rou"], 2) == 699555.01 == round(1000000 * (1459199.02 - 200000) / 1800000, 2)
    assert round(s["inmediata"], 2) == 240355.99
    assert round(c["activo_ini"], 2) == 699555.01


def test_componente_indexado_niif_completas_a_mano():
    """27 b y 28: el componente ligado a un índice entra en la medición con el índice de la fecha de comienzo."""
    c = _c(_run(), "C-10")
    i = 1.12 ** (1 / 12) - 1
    assert c["pago_medido"] == 2000 and c["pago_base"] == 1800 and c["pago_ind"] == 200
    assert round(c["vp"], 2) == 60749.51 == round(2000 * (1 - (1 + i) ** -36) / i, 2)
    assert round(c["pasivo"], 2) == 22583.03 == round(2000 * (1 - (1 + i) ** -12) / i, 2)
    assert round(c["interes"], 2) == 3836.58 == round(24000 - (2000 * (1 - (1 + i) ** -24) / i - 2000 * (1 - (1 + i) ** -12) / i), 2)
    assert round(c["dep"], 2) == 20249.84 == round(60749.51 / 36 * 12, 2)
    assert c["q_anio"] == 12 and c["gasto_variable"] == 600            # solo el pago variable no ligado al índice (38 b)
    assert "NIIF 16 párr. 27 b y 28" in c["marco_indexado"]
    assert "INDEXADO_REMEDICION" in _codigos(_run())                   # 42 b: no se registró remedición por cambio de índice


def test_componente_indexado_pymes_se_separa():
    """20.15 b / 20.11: bajo la Sección 20 el componente indexado no se capitaliza; es gasto del período."""
    c = _c(_run(PYMES), "C-10")
    assert c["clasif"] == "Operativo" and c["pago_medido"] == 1800     # se mide solo el pago base
    assert round(c["gasto"], 2) == 21600.00 == 1800 * 12               # gasto lineal del pago base
    assert c["gasto_variable"] == 3000 == (200 + 50) * 12              # componente indexado + pago variable
    assert round(c["gasto"] + c["gasto_variable"], 2) == 24600.00 == (2000 + 50) * 12
    assert "20.15 b" in c["marco_indexado"] and "Excluido del gasto lineal" in c["trat_indexado"]
    assert "INDEXADO_PYMES_GASTO" in _codigos(_run(PYMES))
    assert "INDEXADO_REMEDICION" not in _codigos(_run(PYMES))          # la Sección 20 no tiene remedición por índice
    # La edición 2025 mantiene la Sección 20 sin cambios de fondo: misma ruta y mismo importe.
    assert _c(_run({**PYMES, "_edicion": "2025"}), "C-10")["gasto_variable"] == 3000


def test_indexado_sin_importe_queda_vacio():
    """M22: indexación declarada sin importe → pago base y componente vacíos, nunca 0 por omisión."""
    for param in (NIIF, PYMES):
        c = _c(_run(param), "C-11")
        assert c["ind_decl"] == "Sí" and c["pago_ind"] is None and c["pago_base"] is None
        assert c["gasto_variable"] is None if param is PYMES else c["gasto_variable"] == 0
        assert c["pago_medido"] == 1000                                # no se puede separar: se usa el pago informado
        assert "INDEXADO_SIN_IMPORTE" in _codigos(_run(param))
    # Informado el importe, el componente se separa y el problema se apaga.
    ds = copy.deepcopy(EJ["datasets"])
    c11 = next(x for x in ds["contratos"] if x["id"] == "C-11")
    c11["pago_indexado"] = "150"
    r = _run(PYMES, ds=ds)
    assert _c(r, "C-11")["pago_base"] == 850 and _c(r, "C-11")["gasto_variable"] == 150 * 12
    assert "INDEXADO_SIN_IMPORTE" not in _codigos(r)
    # El componente no puede superar el pago periódico total.
    c11["pago_indexado"] = "1500"
    with pytest.raises(ValueError):
        _run(PYMES, ds=ds)
    assert not m.validar_filas("contratos", ds["contratos"])["ok"]


def test_venta_posterior_medicion_posterior_102a():
    """102A: roll-forward del pasivo y del derecho de uso conservado, sin ganancia posterior sobre el derecho retenido."""
    c = _c(_run(), "C-08")
    assert round(c["pasivo_ini"], 2) == 1459199.02 and round(c["activo_ini"], 2) == 699555.01
    assert round(c["interes"], 2) == 65663.96 == round(1459199.02 * 0.045, 2)
    assert round(c["pagos"], 2) == 120000.00
    assert round(c["pasivo"], 2) == 1404862.97 == round(c["pasivo_ini"] * 1.045 - 120000, 2)
    assert abs(c["comprobacion"]) < 1e-6                                # altas + interés − pagos + remedición = pasivo al corte
    assert round(c["dep"], 2) == 38864.17 == round(699555.01 / 216 * 12, 2)
    assert round(c["neto"], 2) == 660690.84 == round(699555.01 - 38864.17, 2)
    e = next(x for x in _run()["exceptions"] if x["code"] == "VENTA_GANANCIA_POSTERIOR")
    assert float(e["amount"]) == 18500.00 and "102A" in e["message"]
    # M22: sin el dato del cliente el control del 102A queda VACÍO (nunca 0) y se señala qué papel falta.
    ds = copy.deepcopy(EJ["datasets"])
    next(x for x in ds["contratos"] if x["id"] == "C-08")["ganancia_post_reg"] = ""
    sin = _run(ds=ds)
    assert "VENTA_GANANCIA_POSTERIOR" not in _codigos(sin) and "VENTA_102A_SIN_DATO" in _codigos(sin)
    assert _c(sin, "C-08")["ganancia_post_reg"] is None
    fila = next(f for f in next(h for h in m.hojas(sin) if h["name"] == "14_Venta_medicion_post")["rows"] if f[0] == "C-08")
    assert fila[14]["v"] is None and fila[15]["v"] is None            # ganancia registrada y control 102A, vacíos
    assert fila[15]["f"].endswith(',"")')


def test_exentos_y_deterioro():
    r = _run()
    assert _c(r, "C-05")["reconoce"] == "No" and _c(r, "C-05")["gasto"] == 1800          # 300 × 12 ÷ 12 × 6
    assert _c(r, "C-04")["reconoce"] == "No" and _c(r, "C-04")["gasto"] == 960           # 80 × 24 ÷ 24 × 12
    assert _c(r, "C-03")["reconoce"] == "Sí"                                               # automóvil: nunca es de escaso valor (B6)
    c9 = _c(r, "C-09")
    assert round(c9["deterioro"], 2) == 21307.75 and round(c9["neto"], 2) == 50000.00


def test_problemas_niif_completas():
    r = _run()
    assert {"RENOVACION_NO_INCLUIDA", "EXENCION_MAL_APLICADA", "CLASIFICACION_CP_LP", "MODIFICACION_NO_REMEDIDA",
            "PASIVO_DIFERENCIA", "VENTA_GANANCIA", "DETERIORO", "BAJO_VALOR_VEHICULO", "BAJO_VALOR_B5_B7"} <= _codigos(r)
    assert r["primary"] == "ajuste"
    t = r["totals"]
    assert float(t["ajuste"]) == pytest.approx(float(t["pasivo"]) - float(t["pasivoRegistrado"]), abs=0.011)
    assert float(t["corriente"]) + float(t["noCorriente"]) == pytest.approx(float(t["pasivo"]), abs=0.011)
    assert "PYMES_DERECHO_USO" not in _codigos(r)


def test_bajo_valor_b3_b5_b6_b7():
    """NIIF 16 B3 y B5–B7: el bajo valor exige el valor del activo nuevo, uso independiente, no ser automóvil y no subarrendarse."""
    r = _run()
    c3, c4 = _c(r, "C-03"), _c(r, "C-04")
    assert c3["bv"] == "Sí" and c3["bv_auto"] == "Sí" and c3["bv_limite"] == "No"   # B6: automóvil
    assert "C-03" in next(e["message"] for e in r["exceptions"] if e["code"] == "BAJO_VALOR_VEHICULO")
    assert c4["bv_auto"] == "No" and c4["bv_limite"] == "Sí"                        # 1.200 ≤ 5.000 (B3, B8)
    assert "C-04" in next(e["message"] for e in r["exceptions"] if e["code"] == "BAJO_VALOR_B5_B7")   # B5 y B7 sin evidencia
    # B3: sin el valor del activo nuevo la exención ya no se acepta (antes bastaba dejarlo en blanco).
    ds = copy.deepcopy(EJ["datasets"])
    c = next(x for x in ds["contratos"] if x["id"] == "C-04")
    c["valor_razonable"] = ""
    sv = _run(ds=ds)
    assert _c(sv, "C-04")["bv_limite"] == "No" and _c(sv, "C-04")["reconoce"] == "Sí"
    assert {"BAJO_VALOR_SIN_VALOR", "EXENCION_MAL_APLICADA"} <= _codigos(sv)
    # B5 / B7 declarados «no» → tampoco califica; declarados «sí» → califica y se apaga el problema.
    c["valor_razonable"] = "1200"
    c["bajo_valor_b5b7"] = "No"
    no = _run(ds=ds)
    assert _c(no, "C-04")["bv_limite"] == "No" and _c(no, "C-04")["reconoce"] == "Sí"
    assert "BAJO_VALOR_B5_B7" in _codigos(no) and "EXENCION_MAL_APLICADA" in _codigos(no)
    c["bajo_valor_b5b7"] = "Sí"
    ok = _run(ds=ds)
    assert _c(ok, "C-04")["bv_limite"] == "Sí" and _c(ok, "C-04")["reconoce"] == "No" and _c(ok, "C-04")["gasto"] == 960
    assert "BAJO_VALOR_B5_B7" not in _codigos(ok)
    # La Sección 20 no tiene exenciones: los problemas de bajo valor solo corren en NIIF completas.
    assert not [x for x in _codigos(_run(PYMES)) if x.startswith("BAJO_VALOR")]


def test_ruta_pymes():
    r = _run(PYMES)
    cod = _codigos(r)
    assert {"PYMES_DERECHO_USO", "CLASIFICACION_PYMES", "PYMES_EVENTO"} <= cod
    assert "EXENCION_MAL_APLICADA" not in cod and "MODIFICACION_NO_REMEDIDA" not in cod
    assert _c(r, "C-01")["reconoce"] == "No" and _c(r, "C-01")["gasto"] == 18000       # operativo: 1.500 × 12 (20.15)
    assert _c(r, "C-02")["clasif"] == "Financiero"                                       # VP/VR = 94,8 % ≥ 90 % (20.5 d)
    c4 = _c(r, "C-04")                                                                   # VR 1.200 < VP → 20.9 y tasa recalculada
    assert c4["pasivo_ini"] == 1200 and c4["i_used"] > c4["i"]
    assert round(c4["tabla"][-1]["saldo"], 6) == 0
    assert _c(r, "C-08")["slb"] == {"inmediata": 800000, "diferida": 200000}           # 20.34: exceso sobre VR diferido
    r25 = _run({**PYMES, "_edicion": "2025"})
    assert r25["totals"] == r["totals"]                                                  # 2025 no adoptó la NIIF 16


def test_tabla_cierra_en_cero_y_movimiento_cuadra():
    for param in (NIIF, PYMES):
        for c in _run(param)["detalle"]["contratos"]:
            if c["reconoce"] == "Sí":
                assert abs(c["tabla"][-1]["saldo"]) < 1e-6, c["id"]
                assert abs(c["comprobacion"]) < 1e-6, c["id"]


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"contratos": []}, NIIF, "2025-12-31")
    with pytest.raises(ValueError):
        _run({**NIIF, "umbralVP": 150})
    with pytest.raises(ValueError):
        _run({**NIIF, "convencionTasa": "Otra"})
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], NIIF, "")
    ds = copy.deepcopy(EJ["datasets"])
    ds["contratos"][1]["plazo"] = "30"                       # anual con 30 meses → error
    with pytest.raises(ValueError):
        m.ejecutar(ds, NIIF, EJ["corte"])
    ds = copy.deepcopy(EJ["datasets"])
    ds["contratos"][0]["inicio"] = "2026-03-01"
    r = m.ejecutar(ds, NIIF, EJ["corte"])
    assert "NO_COMENZADO" in _codigos(r) and all(c["id"] != "C-01" for c in r["detalle"]["contratos"])
    ds = copy.deepcopy(EJ["datasets"])
    ds["contratos"][6]["fecha_evento"] = "2026-06-01"        # posterior al corte
    assert "EVENTO_NO_APLICADO" in _codigos(m.ejecutar(ds, NIIF, EJ["corte"]))


def test_validar_filas():
    ok = m.validar_filas("contratos", EJ["datasets"]["contratos"])
    assert ok["ok"], ok["errors"]
    malo = [{**EJ["datasets"]["contratos"][0], "pago": "-5", "periodicidad": "bimestral", "renov_cierta": "quizá", "_row": 3},
            {"id": "TOTAL", "_row": 4}]
    r = m.validar_filas("contratos", malo)
    campos = {e.get("field") for e in r["errors"]}
    assert not r["ok"] and {"pago", "periodicidad", "renov_cierta", "inicio"} <= campos


def test_hojas_y_definicion():
    for _, ds, param, corte in m.ESCENARIOS:
        res = m.ejecutar(ds, param, corte)
        h = m.hojas(res)
        assert [x["name"] for x in h] == [n for n, _ in m.CEDULAS]
        for x in h:
            assert len(x["name"]) <= 31
            for fila in x["rows"] + ([x["total"]] if x["total"] else []):
                assert len(fila) == len(x["cols"]), x["name"]
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "arrendamientos" and len(d["program"]) >= 5
    assert m.RUBRO == "ARRENDAMIENTOS" and m.PRINCIPAL in m.DATASETS and m.kind("contratos") == "contratos"


def test_conclusion():
    """La cédula 17 lleva indicadores clave con importes en fórmula y un «Estado» coloreable."""
    from backend.app.aud.niif.procesadores import base
    h = next(x for x in m.hojas(_run()) if x["name"] == "17_Conclusion")
    cols = [c[0] for c in h["cols"]]
    assert cols[0] == "Indicador" and "Estado" in cols and h.get("colores") == ["Estado"]
    est, imp = cols.index("Estado"), cols.index("Importe")
    importes = [f[imp] for f in h["rows"] if isinstance(f[imp], dict)]
    assert importes and all("f" in f for f in importes)              # cada importe es fórmula, nada pegado
    estados = [f[est] for f in h["rows"] if isinstance(f[est], dict)]
    valores = {f["v"] for f in estados}
    assert valores and valores <= {"Alerta", "Revisar", "Conforme"} and valores <= set(base.NIVEL_COLOR)
    assert all(base.rol_color(h, "Estado", f) in ("alta", "media", "baja") for f in estados)


def test_lectura():
    """La cédula 18 lee el resultado y los hallazgos materiales con su cifra embebida por fórmula (FIXED)."""
    h = next(x for x in m.hojas(_run()) if x["name"] == "18_Lectura")
    assert h["label"] == "Lectura de resultados"
    assert [c[0] for c in h["cols"]] == ["Concepto", "Detalle"]
    assert 3 <= len(h["rows"]) <= 5 and not h.get("total") and not h.get("colores")
    det = [f[1] for f in h["rows"]]
    assert all(isinstance(d, dict) and "f" in d for d in det)       # cada Detalle es fórmula, nada pegado
    assert all("FIXED(" in d["f"] for d in det)                     # la cifra va embebida con FIXED
    assert "Detalle" in h["explica"] and len(h["explica"]["Detalle"]) >= 40


def test_semaforo_conciliacion():
    from backend.app.aud.niif.procesadores.base import NIVEL_COLOR
    h = next(x for x in m.hojas(_run()) if x["name"] == "15_Conciliacion")
    assert h["colores"] == ["Semáforo"]
    sem = [c[0] for c in h["cols"]].index("Semáforo")
    valores = {(fila[sem].get("v") if isinstance(fila[sem], dict) else fila[sem]) for fila in h["rows"]}
    assert valores <= {"Alerta", "Conforme"} and valores
    assert valores <= set(NIVEL_COLOR)
    assert h["total"][sem] == ""


def test_impuesto_diferido_reproduce_excel_cliente():
    """NIC 12 / Secc. 29: la diferencia temporaria nace del canon deducible vs (depreciación + interés) del
    arriendo capitalizado. Reproduce el Excel real del cliente (Inkas, oficinas Quito, 24 meses, 8,12% nominal):
    generación y reversión en bruto por año (casilleros F-101 1114 / 1115) y cuadre a cero al fin de la vida."""
    ds = {"contratos": [m._k("Q24", "Oficinas Quito", "2023-07-01", "24", "2400", "Mensual", "8.12", "0")]}
    c = _c(m.ejecutar(ds, {**m.PARAMETROS, "_marco": "NIIF completas"}, "2026-12-31"), "Q24")  # Nominal + 25% por default
    idf = c["idiferido"]
    t = idf["tarifa"]
    assert round(t, 4) == 0.25
    an = idf["anios"]
    assert round(an[2023]["gen"] * t, 2) == 198.26       # generación 2023 (cas 1114)
    assert round(an[2024]["gen"] * t, 2) == 69.66        # generación 2024 (cas 1114)
    assert round(an[2024]["rev"] * t, 2) == -64.24       # reversión 2024 (cas 1115)
    assert round(an[2025]["rev"] * t, 2) == -203.68      # reversión 2025 (cas 1115)
    assert round(idf["gen"] * t, 2) == 267.93 == round(-idf["rev"] * t, 2)     # bruto gen = bruto rev
    assert round((idf["gen"] + idf["rev"]) * t, 6) == 0.0                      # se revierte a cero


def test_impuesto_diferido_solo_en_capitalizados():
    """La cédula de diferido solo aplica a contratos capitalizados (NIIF 16 / financiero PYMES). En un
    operativo PYMES o un exento el gasto es el deducible: sin diferencia temporaria → idiferido None."""
    res = _run(PYMES)                                     # EJEMPLO en PYMES: hay operativos y financieros
    for c in res["detalle"]["contratos"]:
        if c["reconoce"] == "Sí":
            assert c["idiferido"] is not None and "anios" in c["idiferido"]
        else:
            assert c["idiferido"] is None


def test_conciliacion_f101_y_asiento():
    """Cédula 20: para el año del corte traslada generación (1114), reversión (1115), efecto neto (889)
    y el saldo del activo por impuesto diferido, con un asiento cuadrado (Debe = Haber)."""
    ds = {"contratos": [m._k("Q24", "Oficinas Quito", "2023-07-01", "24", "2400", "Mensual", "8.12", "0")]}
    res = m.ejecutar(ds, {**m.PARAMETROS, "_marco": "NIIF completas"}, "2024-12-31")  # corte 2024
    h = next(x for x in m.hojas(res) if x["name"] == "20_Conciliacion_F101")
    val = lambda celda: celda["v"] if isinstance(celda, dict) else celda
    filas = {fila[1]: fila for fila in h["rows"]}            # por casillero
    assert round(val(filas["1114"][2]), 2) == 69.66          # generación 2024
    assert round(val(filas["1115"][2]), 2) == -64.24         # reversión 2024
    assert round(val(filas["889"][2]), 2) == 5.42            # efecto neto 2024
    saldo = next(fila for fila in h["rows"] if fila[0].startswith("Saldo"))
    assert round(val(saldo[2]), 2) == 203.68                 # activo por impuesto diferido al corte
    # asiento cuadrado: el Debe de una fila iguala el Haber de otra
    debe = [val(fila[3]) for fila in h["rows"] if isinstance(fila[3], dict)]
    haber = [val(fila[4]) for fila in h["rows"] if isinstance(fila[4], dict)]
    assert round(sum(debe), 2) == round(sum(haber), 2) == 5.42


def test_recalc_cruza_el_impuesto_diferido():
    """El recálculo del revisor re-deriva generación y reversión del diferido (segunda implementación) y
    coincide con el motor."""
    from backend.app.aud.niif.ciclo.revision.recalc import arrendamientos as rc
    r = rc.recalcular(_run())
    difer = [c for c in r["componentes"] if "diferencias temporarias" in c["concepto"]]
    assert len(difer) == 2 and all(c["ok"] and c["diff"] == 0.0 for c in difer)


def test_extraccion_por_ia_del_contrato():
    """La herramienta declara la extracción por IA del contrato (como ppe y la planificación): el servicio y el
    frontend la activan genéricamente. Con un chat simulado, la fila extraída trae los datos de hecho y deja la
    tasa vacía (es juicio del auditor con la referencial del BCE), por lo que la validación la marca como faltante."""
    import json
    from backend.app.aud.niif.ciclo import extraccion_ia as ex
    assert m.EXTRACCION_DATASETS == ("contratos",)
    assert "Banco Central" in m.EXTRACCION_INSTRUCCIONES["contratos"]
    assert m.EXTRACCION_ENUMS["contratos"]["periodicidad"] == ["Mensual", "Trimestral", "Semestral", "Anual"]

    class _Resp:
        def __init__(self, c):
            self.content, self.model = c, "falso"
    fila = {"id": "C-01", "activo": "Oficina Quito", "inicio": "2024-07-01", "plazo": 24, "pago": 2400,
            "periodicidad": "Mensual", "momento": "Final", "tasa": "", "clasif_pymes": ""}
    chat = lambda messages, system=None: _Resp(json.dumps({"filas": [fila]}))
    res = ex.extraer_filas(m._CONTRATOS, "Contrato de arrendamiento de la oficina de Quito…",
                           instrucciones=m.EXTRACCION_INSTRUCCIONES["contratos"],
                           enums=m.EXTRACCION_ENUMS["contratos"], chat=chat)
    assert res["n"] == 1
    row = res["rows"][0]
    assert row["activo"] == "Oficina Quito" and row["plazo"] == 24 and row["periodicidad"] == "Mensual"
    assert row["tasa"] == "" and row["clasif_pymes"] == ""          # la IA no inventa la tasa ni la clasificación
    val = m.validar_filas("contratos", [row])
    # faltan solo los campos que no vienen del contrato: la tasa (la fija el auditor con la del BCE) y el
    # pasivo registrado (saldo del mayor); todo lo demás lo extrajo la IA del contrato.
    assert not val["ok"] and {e["field"] for e in val["errors"]} == {"tasa", "pasivo_reg"}


def test_movimiento_saldos_anterior_vs_actual():
    """Cédula 21: el anexo trae los saldos del balance al corte anterior y al actual; la herramienta recalcula
    el actual y muestra la diferencia. Los saldos del contrato se extraen aparte; el anexo es solo saldos."""
    h = next(x for x in m.hojas(_run()) if x["name"] == "21_Movimiento_Saldos")
    cols = [c[0] for c in h["cols"]]
    assert cols[:5] == ["Contrato", "Pasivo registrado anterior", "Pasivo registrado actual", "Pasivo recalculado", "Diferencia pasivo"]
    val = lambda celda: celda["v"] if isinstance(celda, dict) else celda
    fila = next(f for f in h["rows"] if f[0] == "C-02")
    assert round(val(fila[1]), 2) == 24868.52                 # pasivo registrado anterior (del anexo)
    assert round(val(fila[2]), 2) == 17355.37                 # pasivo registrado actual (del anexo)
    assert round(val(fila[3]), 2) == 17355.37                 # pasivo recalculado (hoja 10)
    assert abs(val(fila[4])) < 0.005                          # diferencia pasivo ≈ 0
    assert round(val(fila[5]), 2) == 23044.72                 # derecho de uso registrado anterior


def test_campos_saldos_anteriores_y_ayuda_bce():
    """El anexo declara los saldos del corte anterior y la tasa trae la guía del BCE; la extracción no llena saldos."""
    claves = {c["key"] for c in m._CONTRATOS}
    assert {"pasivo_reg_ant", "pasivo_cp_reg_ant", "activo_reg_ant"} <= claves
    tasa = next(c for c in m._CONTRATOS if c["key"] == "tasa")
    assert "Banco Central" in tasa["label"] or "BCE" in tasa["label"]
    assert "SALDOS DEL BALANCE" in m.EXTRACCION_INSTRUCCIONES["contratos"]
