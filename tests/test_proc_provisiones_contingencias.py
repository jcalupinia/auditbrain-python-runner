"""Provisiones y contingencias: ejemplo de control con cifras recalculadas a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import provisiones_contingencias as m

E = m.EJEMPLO


def correr(datasets=None, **param):
    return m.ejecutar(datasets or E["datasets"], {**E["parametros"], **param}, E["corte"])


def _codigos(r):
    return {e["code"] for e in r["exceptions"]}


def _x(r, id):
    return next(x for x in r["detalle"]["provisiones"] if x["id"] == id)


def test_ejemplo_cifras_a_mano():
    r = correr()
    t = r["totals"]
    # LIT-01 valor esperado = 150.000×60 % + 80.000×30 % + 0×10 % = 114.000; libros 100.000.
    l1 = _x(r, "LIT-01")
    assert l1["est_ve"] == pytest.approx(114000) and l1["base"] == "Valor esperado (37.39)" and l1["dif"] == pytest.approx(14000)
    # LIT-02 punto medio 80.000 a 2,5 años al 8 % (tasa por defecto): 80.000 ÷ 1,08^2,5.
    l2 = _x(r, "LIT-02")
    assert l2["est"] == 80000 and m.r2(l2["vp"]) == "65997.97" and l2["tasa"] == 8
    # GAR-01 = 12.000×3 %×85 + 5.000×2 %×120 = 42.600; ONE-01 = mín(75.000; 45.000).
    assert _x(r, "GAR-01")["est"] == pytest.approx(42600) and _x(r, "ONE-01")["est"] == 45000
    # DES-01 = 500.000 ÷ 1,07^10 = 254.174,65; reversión 225.000 × 7 % = 15.750.
    d1 = _x(r, "DES-01")
    assert m.r2(d1["vp"]) == "254174.65" and d1["rev_calc"] == pytest.approx(15750) and "CINIIF 1" in d1["contrapartida"]
    # AMB-01 = 200.000 ÷ 1,09^5 = 129.986,28; reversión 190.000 × 9 % = 17.100 vs 5.000.
    a1 = _x(r, "AMB-01")
    assert m.r2(a1["vp"]) == "129986.28" and a1["rev_dif"] == pytest.approx(12100)
    # OTR-01 más probable = 30.000 (valor esperado sería 51.000); LIT-05 hecho posterior 32.000.
    assert _x(r, "OTR-01")["est"] == 30000 and _x(r, "OTR-01")["est_ve"] == pytest.approx(51000)
    assert _x(r, "LIT-05")["est"] == 32000 and _x(r, "LIT-05")["base"].startswith("Hecho posterior")
    # Clasificación.
    assert [_x(r, i)["clasif"] for i in ("LIT-03", "LIT-04", "LIT-06", "ACT-01")] == [
        "Pasivo contingente: revelar", "Pasivo contingente: revelar", "Remota: no revelar", "Activo contingente: revelar"]
    # Totales: requerida = 114.000 + 65.997,97 + 42.600 + 45.000 + 254.174,65 + 60.000 + 129.986,28 + 32.000 + 30.000.
    assert t["librosProvisiones"] == "725000.00" and t["provisionRequerida"] == "773758.90" and t["ajusteProvisiones"] == "48758.90"
    assert t["garantiasCalculadas"] == "47600.00" and t["pasivosContingentes"] == "60000.00" and t["contingentesSinRevelar"] == "20000.00"
    assert t["reversionCalculada"] == "32850.00" and t["activoContingenteReconocido"] == "50000.00" and t["difMayor"] == "-5000.00"
    assert r["primary"] == "ajusteProvisiones" and m.TOTAL_EJEMPLO in t
    assert {"DIFERENCIA_PROVISION", "DIFERENCIA_CARTA_ABOGADO", "DISCREPANCIA_PROBABILIDAD", "CARTA_ANTERIOR_AL_CORTE",
            "PROVISION_NO_REGISTRADA", "PROVISION_POSIBLE_O_REMOTA", "SIN_RESPUESTA_ABOGADO", "CONTINGENCIA_SIN_REVELAR",
            "ONEROSO_NO_PROVISIONADO", "REVERSION_NO_REGISTRADA", "DESCUENTO_NO_APLICADO", "REVERSION_DIFERENCIA",
            "ACTIVO_CONTINGENTE_RECONOCIDO", "ACTIVO_CONTINGENTE_SIN_REVELAR", "GARANTIA_SIN_PROVISION", "CONCILIACION_MAYOR"} <= _codigos(r)
    assert "AJUSTE_SUPERA_MATERIALIDAD" not in _codigos(r)
    assert "AJUSTE_SUPERA_MATERIALIDAD" in _codigos(correr(materialidad=40000))


@pytest.mark.parametrize("edicion", ["2015", "2025"])
def test_pymes_mismo_resultado(edicion):
    base, r = correr(), correr(_marco=m.MARCO_PYMES, _edicion=edicion)
    assert r["totals"] == base["totals"] and r["detalle"]["edicion"] == edicion and r["detalle"]["marco"] == m.MARCO_PYMES


def test_parametros_cambian_descuento():
    # Umbral de 3 años: LIT-02 (2,5 años) ya no se descuenta.
    assert _x(correr(plazoDescuento=3), "LIT-02")["vp"] == 80000
    # Sin tasa por defecto: LIT-02 queda sin valor presente (M22) y se señala.
    r = correr(tasaDescuento=None)
    assert _x(r, "LIT-02")["vp"] is None and _x(r, "LIT-02")["requerida"] is None and "DESCUENTO_SIN_TASA" in _codigos(r)
    with pytest.raises(ValueError):
        correr(tasaDescuento=150)


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"provisiones": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    with pytest.raises(ValueError):
        m.ejecutar({"provisiones": [{"id": "X", "descripcion": "x", "tipo": "Litigio", "_row": 2}]}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar({"provisiones": [{"id": "X", "tipo": "Inventada", "saldo_libros": "1", "_row": 2}]}, {}, "2025-12-31")
    v = m.validar_filas("provisiones", [{"id": "A", "descripcion": "a", "tipo": "Litigio", "saldo_libros": "-5", "importe_1": "10",
                                         "probabilidad_abogado": "quizá", "importe_minimo": "9", "importe_maximo": "3", "_row": 3}])
    assert not v["ok"] and {"saldo_libros", "prob_1", "probabilidad_abogado", "importe_maximo"} <= {e["field"] for e in v["errors"]}
    # Sin evaluación ni mayor: requerida vacía (no cero) y se señala.
    r = m.ejecutar(m._MIN, {}, "2025-12-31")
    assert {"SIN_EVALUACION", "SIN_MAYOR"} <= _codigos(r) and r["detalle"]["provisiones"][0]["requerida"] is None
    assert r["totals"]["provisionRequerida"] == "0.00" and "difMayor" not in r["totals"]
    # Probabilidades que no suman 100: se normaliza y se señala.
    ds = {"provisiones": [{"id": "P", "tipo": "Otro", "obligacion_presente": "si", "probabilidad_gerencia": "probable",
                           "importe_1": "100", "prob_1": "40", "importe_2": "200", "prob_2": "40", "saldo_libros": "0", "_row": 2}]}
    r = m.ejecutar(ds, {}, "2025-12-31")
    assert r["detalle"]["provisiones"][0]["est"] == pytest.approx(150) and "PROBABILIDADES_NO_SUMAN_100" in _codigos(r)
    # Obligación presente No con provisión registrada.
    ds = {"provisiones": [{"id": "Q", "tipo": "Otro", "obligacion_presente": "No", "probabilidad_gerencia": "Remota",
                           "saldo_libros": "500", "_row": 2}]}
    assert "PROVISION_SIN_OBLIGACION" in _codigos(m.ejecutar(ds, {}, "2025-12-31"))


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
    assert d["processor"] == "provisiones_contingencias" and len(d["program"]) >= 5
    assert m.RUBRO == "PROVISIONES" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
