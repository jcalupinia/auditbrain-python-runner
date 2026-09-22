"""Cobertura de seguros de activos: ejemplo de control con cifras recalculadas a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import seguros_cobertura as m

E = m.EJEMPLO


def correr(datasets=None, **param):
    return m.ejecutar(datasets or E["datasets"], {**E["parametros"], **param}, E["corte"])


def _codigos(r):
    return {e["code"] for e in r["exceptions"]}


def _a(r, id):
    return next(a for a in r["detalle"]["activos"] if a["id"] == id)


def _p(r, id):
    return next(x for x in r["detalle"]["polizas"] if x["id"] == id)


def test_ejemplo_cifras_a_mano():
    r = correr()
    t = r["totals"]
    # POL-01: 700.000 / (650.000 + 300.000) = 73,68 % → infraseguro; prorrata EDIF-01 = 700.000 × 650.000 ÷ 950.000.
    assert _p(r, "POL-01")["cob"] == pytest.approx(700000 / 950000) and _p(r, "POL-01")["clasif"] == "Infraseguro"
    ed = _a(r, "EDIF-01")
    assert m.r2(ed["efec"]) == "478947.37" and m.r2(ed["deficit"]) == "171052.63" and ed["clasif"] == "Infraseguro"
    # Pérdida total EDIF-01: 478.947,37 − 2 % × 650.000 = 465.947,37 → no cubierta 184.052,63 (exposición máxima).
    assert ed["deducible"] == pytest.approx(13000) and t["exposicionMaxima"] == "184052.63"
    # Totales: referencia 1.499.000; suma vigente 1.050.000 = 70,05 %; déficit 482.000; sobreseguro 25.000 + 8.000.
    assert t["valorReferencia"] == "1499000.00" and t["sumaAsegurada"] == "1050000.00" and t["coberturaGlobal"] == "70.05"
    assert t["deficitCobertura"] == "482000.00" and t["sobreseguro"] == "33000.00"
    # Sin cobertura: EQC-01, EQC-02 (vencida), BOD-02 (no iniciada), MOB-01 (sin póliza), GEN-01 (inexistente).
    assert r["detalle"]["kpi"]["nSinCobertura"] == 5 and t["sinCoberturaLibros"] == "129000.00" and t["sinCoberturaReferencia"] == "212000.00"
    assert [_a(r, i)["estado"] for i in ("EQC-01", "BOD-02", "MOB-01", "GEN-01")] == ["Vencida", "No iniciada", "Sin póliza", "Póliza no encontrada"]
    # VEH-03 sin tasación: referencia = valor en libros 12.000.
    assert _a(r, "VEH-03")["ref"] == 12000 and _a(r, "VEH-03")["base"] == "Valor en libros"
    # Prima: POL-02 5.475 × 60 ÷ 365 = 900 vs 2.500; POL-01 7.300 × 182 ÷ 365 = 3.640; POL-05 no iniciada: completa.
    assert _p(r, "POL-02")["calc"] == pytest.approx(900) and _p(r, "POL-01")["calc"] == pytest.approx(3640)
    assert _p(r, "POL-05")["restantes"] == 365 and _p(r, "POL-04")["por_vencer"] == 20 and _p(r, "POL-04")["alerta"] == "Por vencer"
    assert t["primaRegistrada"] == "7800.00" and t["primaRecalculada"] == "6200.00" and t["ajustePrima"] == "-1600.00"
    assert t["difMayorPrima"] == "-200.00" and t["siniestrosSinRevelar"] == "18000.00"
    assert r["primary"] == "ajustePrima" and m.TOTAL_EJEMPLO in t
    assert {"POLIZA_VENCIDA", "POLIZA_NO_INICIADA", "POLIZA_POR_VENCER", "INFRASEGURO", "INFRASEGURO_POLIZA", "SOBRESEGURO",
            "ACTIVO_SIN_COBERTURA", "SINIESTRO_SIN_REVELACION", "PRIMA_MAL_DEVENGADA", "REFERENCIA_EN_LIBROS", "EXPOSICION_MAXIMA",
            "CONCILIACION_PRIMA_MAYOR"} <= _codigos(r)
    assert "SINIESTRO_SIN_REVELACION" not in {e["code"] for e in r["exceptions"] if "POL-04" in e["message"]}


@pytest.mark.parametrize("edicion", ["2015", "2025"])
def test_pymes_mismo_resultado(edicion):
    base, r = correr(), correr(_marco=m.MARCO_PYMES, _edicion=edicion)
    assert r["totals"] == base["totals"] and r["detalle"]["edicion"] == edicion and r["detalle"]["marco"] == m.MARCO_PYMES


def test_umbral_cambia_clasificacion():
    r = correr(coberturaMinima=70)
    assert _a(r, "EDIF-01")["clasif"] == "Adecuada" and _a(r, "MAQ-02")["clasif"] == "Infraseguro"
    with pytest.raises(ValueError):
        correr(coberturaMinima=150)
    with pytest.raises(ValueError):
        correr(sobreseguroDesde=90)


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"activos": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    malo = {"activos": E["datasets"]["activos"], "polizas": [{"id": "P", "aseguradora": "x", "vigencia_desde": "2025-05-01",
                                                               "vigencia_hasta": "2025-04-01", "suma_total": "1", "_row": 2}]}
    with pytest.raises(ValueError):
        m.ejecutar(malo, {}, "2025-12-31")
    v = m.validar_filas("activos", [{"id": "A", "descripcion": "a", "valor_libros": "-5", "deducible_pct": "150", "_row": 3}])
    assert not v["ok"] and {e["field"] for e in v["errors"]} == {"valor_libros", "deducible_pct"}
    # Sin pólizas ni mayor: todo sin cobertura; prima anticipada no informada queda en blanco (M22).
    r = m.ejecutar(m._MIN, {}, "2025-12-31")
    assert r["totals"]["deficitCobertura"] == "1000.00" and {"ACTIVO_SIN_COBERTURA", "SIN_MAYOR"} <= _codigos(r)
    assert "difMayorPrima" not in r["totals"]
    # Prima anticipada sin registro: se señala, no se asume cero.
    ds = {"activos": m._MIN["activos"], "polizas": [{"id": "P1", "aseguradora": "x", "vigencia_desde": "2025-07-01",
                                                     "vigencia_hasta": "2026-07-01", "suma_total": "1000", "prima_total": "365", "_row": 2}]}
    r = m.ejecutar(ds, {}, "2025-12-31")
    assert "PRIMA_ANTICIPADA_NO_INFORMADA" in _codigos(r) and r["detalle"]["polizas"][0]["dif"] is None


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
    assert d["processor"] == "seguros_cobertura" and len(d["program"]) >= 5
    assert m.RUBRO == "SEGUROS" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
