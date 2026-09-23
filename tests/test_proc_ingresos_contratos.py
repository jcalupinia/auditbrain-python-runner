"""Procesador ingresos_contratos: ejemplo de control recalculado a mano, tres rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import ingresos_contratos as m

EJ = m.EJEMPLO


def _run(**param):
    return m.ejecutar(EJ["datasets"], {**EJ["parametros"], **param}, EJ["corte"])


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def _linea(res, lid):
    return next(x for x in res["detalle"]["lineas"] if x["id"] == lid)


def test_ejemplo_niif_completas_cifras_a_mano():
    r = _run()
    t = r["totals"]
    # C-01: PVI 100.000 y 25.000 sobre precio 100.000 → 80.000 y 20.000; mantenimiento 3.000/12.000 = 25 % → 5.000.
    assert round(_linea(r, "C-01-1")["asignado"], 2) == 80000 and round(_linea(r, "C-01-2")["bruto"], 2) == 5000
    # C-02: bono al 60 % < 75 % excluido; 180.000/400.000 = 45 % × 500.000 = 225.000.
    assert round(_linea(r, "C-02-1")["recAnio"], 2) == 225000
    # C-11: bono 5.000 al 90 % con 1.000 informado como importe que supera la restricción → se incluye 5.000 − 1.000 = 4.000
    # (inclusión parcial, NIIF 15.56-57); precio de la transacción 20.000 + 4.000 = 24.000 y exceso del cliente 5.000 − 4.000 = 1.000.
    c11 = _linea(r, "C-11-1")
    assert c11["varBase"] == 5000 and c11["varIncluida"] == 4000 and c11["varExceso"] == 1000 and round(c11["recAnio"], 2) == 24000
    assert t["variableExceso"] == "51000.00"                 # 50.000 (C-02, todo o nada) + 1.000 (C-11, parcial)
    # C-05: 121.000 ÷ 1,1² = 100.000; componente 21.000; interés 100.000 × (1,1^(183/365) − 1).
    assert round(_linea(r, "C-05-1")["vp"], 2) == 100000 and t["componenteFinanciero"] == "21000.00"
    assert t["interesDevengado"] == f"{100000 * (1.1 ** (183 / 365) - 1):.2f}"
    # C-04: 5 % × 40.000 = 2.000 de reembolso; NC posteriores 3.500 → 1.500 no provisionadas. C-09-1: 2 % × 6.000 = 120.
    assert t["pasivoReembolso"] == "2120.00" and t["devolucionesNoProvisionadas"] == "1500.00"
    # NIIF 15 B21 c) y B25: activo por el derecho a recuperar los productos = costo de los bienes × devolución esperada.
    # C-04: 24.000 × 5 % = 1.200; C-09-1 no informa el costo → queda vacío y se señala (M22).
    assert round(_linea(r, "C-04-1")["activoDev"], 2) == 1200 and _linea(r, "C-09-1")["activoDev"] is None
    assert t["activoDevoluciones"] == "1200.00"
    # Ajuste: −10.000 + 2.500 − 50.000 − 30.000 − 2.000 − 21.000 − 15.000 + 12.000 − 120 (C-09-1) − 1.000 (C-11-1)
    # = −114.620 (C-12 sin medir queda fuera).
    assert t["ajuste"] == "-114620.00" and r["primary"] == "ajuste"
    assert t["ingresoRegistrado"] == "668166.67" and t["ingresoReconocible"] == "544546.67" and t["difMayor"] == "-1833.33"
    assert t["corteAnticipado"] == "30000.00" and t["corteOmitido"] == "12000.00"
    # Activo: C-02 25.000 + C-07 12.000 + C-10 6.666,67; pasivo: C-01 15.000 + C-03 30.000 + C-06 15.000 + C-08 4.000 + C-09 2.000
    # + C-11 1.000 (bruto 24.000 − facturado 25.000, por la restricción parcial).
    assert t["activoContrato"] == "43666.67" and t["pasivoContrato"] == "67000.00"
    assert t["difAsignacion"] == "20000.00"
    assert _linea(r, "C-12-1")["recAnio"] is None
    for k in ("SIN_CONTRATO", "ERROR_CORTE", "ASIGNACION_INCORRECTA", "VARIABLE_SIN_RESTRICCION", "AVANCE_MAL_CALCULADO",
              "ACTIVO_CONTRATO_NO_PRESENTADO", "PASIVO_CONTRATO_NO_PRESENTADO", "FINANCIACION_NO_SEPARADA",
              "DEVOLUCIONES_NO_PROVISIONADAS", "DIF_MAYOR", "PERDIDA_ESPERADA", "PSI_FALTANTE", "MODIFICACION_SIN_TRATAMIENTO",
              "SIN_FECHA_TRANSFERENCIA", "CONTRATO_SIN_EVIDENCIA", "ACTIVO_DEVOLUCION_SIN_COSTO",
              "VARIABLE_RESTRICCION_TODO_O_NADA"):
        assert k in _codigos(r), k


def test_ruta_pymes_2015_variable_probable():
    r = _run(_marco=m.MARCO_PYMES, _edicion="2015")
    # 60 % > 50 % → bono incluido: 550.000 × 45 % = 247.500 (22.500 más que en NIIF 15).
    assert round(_linea(r, "C-02-1")["recAnio"], 2) == 247500
    # −114.620 + 22.500 (bono de C-02 incluido) = −92.120.
    assert r["totals"]["ajuste"] == "-92120.00"
    # PYMES 2015 no reconoce activo por recuperar productos (23.13 y Sección 21) y no aplica la restricción de NIIF 15.56-57.
    assert r["totals"]["activoDevoluciones"] == "0.00"
    assert {"ACTIVO_DEVOLUCION_SIN_COSTO", "VARIABLE_RESTRICCION_TODO_O_NADA"}.isdisjoint(_codigos(r))
    assert "riesgos y beneficios" in r["detalle"]["modelo"] and r["labels"]["activoContrato"].startswith("Importe bruto adeudado")


def test_ruta_pymes_2025_valor_esperado():
    r = _run(_marco=m.MARCO_PYMES, _edicion="2025", metodoVariable="Valor esperado", umbralAltamenteProbable=55)
    # C-02: 50.000 × 0,60 = 30.000 → 530.000 × 45 % = 238.500; C-11: 5.000 × 0,90 = 4.500.
    assert round(_linea(r, "C-02-1")["recAnio"], 2) == 238500
    # C-11: base 4.500 − 1.000 restringido = 3.500 incluido → exceso 1.500; C-02 exceso 20.000.
    assert r["totals"]["variableExceso"] == "21500.00" and r["totals"]["activoDevoluciones"] == "1200.00"
    assert "cinco pasos" in r["detalle"]["modelo"] and "23.36" in r["detalle"]["cit"]["fin"]


def test_sin_tasa_sin_mayor_quedan_vacios_y_senalados():
    r = _run(tasaDescuento=None, ingresoMayor=None)
    f5 = _linea(r, "C-05-1")
    assert f5["componente"] is None and f5["interes"] is None and f5["vp"] == 121000
    assert {"FINANCIACION_SIN_TASA", "SIN_MAYOR"} <= _codigos(r) and r["totals"]["difMayor"] == "0.00"


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"contratos": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(tasaDescuento=-1)
    with pytest.raises(ValueError):
        _run(umbralAltamenteProbable=150)
    with pytest.raises(ValueError):
        _run(metodoVariable="Otro")
    neg = [{**EJ["datasets"]["contratos"][0], "precio": "-5"}]
    with pytest.raises(ValueError):
        m.ejecutar({"contratos": neg}, EJ["parametros"], EJ["corte"])
    v = m.validar_filas("contratos", [
        {"id": "L1", "contrato": "C", "cliente": "A", "modo": "xyz", "precio": "abc", "registrado": "1", "_row": 2},
        {"id": "L2", "contrato": "C", "cliente": "A", "modo": "En un momento", "precio": "-1", "registrado": "1", "probabilidad": "120", "_row": 3},
    ])
    assert not v["ok"] and len(v["errors"]) == 4


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
    assert d["processor"] == "ingresos_contratos" and len(d["program"]) >= 5 and m.RUBRO == "INGRESOS"
    assert "PYMES 2015" in d["summary"] and "2025" in d["source_pymes"]["document"]
