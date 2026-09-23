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
    # NIC 16.65–66 / PYMES 17.25: POL-02 daño a activo propio con cobro exigible → 18.000 a resultados;
    # POL-04 daño a activo propio sin cobro exigible → activo contingente (NIC 37.31–35), no suma.
    assert t["compensacionesExigibles"] == "18000.00"
    assert _p(r, "POL-02")["trat_sin"] == m.TRAT_EXIGIBLE and _p(r, "POL-04")["trat_sin"] == m.TRAT_CONTINGENTE
    assert r["primary"] == "ajustePrima" and m.TOTAL_EJEMPLO in t
    assert {"POLIZA_VENCIDA", "POLIZA_NO_INICIADA", "POLIZA_POR_VENCER", "INFRASEGURO", "INFRASEGURO_POLIZA", "SOBRESEGURO",
            "ACTIVO_SIN_COBERTURA", "SINIESTRO_SIN_REVELACION", "PRIMA_MAL_DEVENGADA", "REFERENCIA_EN_LIBROS", "EXPOSICION_MAXIMA",
            "CONCILIACION_PRIMA_MAYOR", "COMPENSACION_EXIGIBLE", "COMPENSACION_ACTIVO_CONTINGENTE"} <= _codigos(r)
    assert "SINIESTRO_SIN_REVELACION" not in {e["code"] for e in r["exceptions"] if "POL-04" in e["message"]}
    assert {"SINIESTRO_SIN_TIPO", "SINIESTRO_SIN_EXIGIBILIDAD"} & _codigos(r) == set()


def _pol_sin(**extra):
    """Un activo y una póliza vigente con un siniestro pendiente, para probar el tipo de siniestro."""
    ds = {"activos": [m._a("A-1", "Equipo", "Maquinaria", "1000", poliza="P1", suma_asignada="1000")],
          "polizas": [{"id": "P1", "aseguradora": "Alfa", "vigencia_desde": "2025-01-01", "vigencia_hasta": "2026-01-01",
                       "suma_total": "1000", "siniestro": "Reclamo", "monto_siniestro": "700", "siniestro_revelado": "Sí",
                       "_row": 2, **extra}]}
    return m.ejecutar(ds, {}, "2025-12-31")


def test_tipo_de_siniestro_enruta_el_tratamiento():
    # Sin tipo: se pide el dato y NO cambia el tratamiento actual (reclamo de terceros, NIC 37.53).
    r = _pol_sin()
    assert "SINIESTRO_SIN_TIPO" in _codigos(r) and _p(r, "P1")["trat_sin"] == m.TRAT_SIN_TIPO
    assert r["totals"]["compensacionesExigibles"] == "0.00"
    # Reclamo de terceros: tratamiento actual, sin problemas de compensación.
    r = _pol_sin(tipo_siniestro="Reclamo de terceros")
    assert _p(r, "P1")["trat_sin"] == m.TRAT_TERCEROS
    assert {"SINIESTRO_SIN_TIPO", "COMPENSACION_EXIGIBLE", "COMPENSACION_ACTIVO_CONTINGENTE"} & _codigos(r) == set()
    # Daño a activo propio exigible: 700 a resultados (NIC 16.65–66 / PYMES 17.25).
    r = _pol_sin(tipo_siniestro="Daño a activo propio", cobro_exigible="Sí")
    assert r["totals"]["compensacionesExigibles"] == "700.00" and "COMPENSACION_EXIGIBLE" in _codigos(r)
    # Daño a activo propio sin exigibilidad informada: activo contingente y se pide el dato (M22).
    r = _pol_sin(tipo_siniestro="Daño a activo propio")
    assert _p(r, "P1")["trat_sin"] == m.TRAT_SIN_EXIGIBILIDAD and r["totals"]["compensacionesExigibles"] == "0.00"
    assert {"SINIESTRO_SIN_EXIGIBILIDAD", "COMPENSACION_ACTIVO_CONTINGENTE"} <= _codigos(r)
    v = m.validar_filas("polizas", [{"id": "P", "aseguradora": "x", "vigencia_desde": "2025-01-01", "vigencia_hasta": "2026-01-01",
                                     "suma_total": "1", "tipo_siniestro": "otra cosa", "cobro_exigible": "tal vez", "_row": 3}])
    assert not v["ok"] and {e["field"] for e in v["errors"]} == {"tipo_siniestro", "cobro_exigible"}


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
