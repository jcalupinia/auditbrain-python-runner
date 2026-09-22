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
    # Intereses NIC 23: 150.000 × 8 % × 305 ÷ 365 = 10.027,40 y 45.000 × 8 % × 121 ÷ 365 = 1.193,42; capitalizado 9.000.
    assert r["totals"]["ajusteIntereses"] == m.r2(150000 * 0.08 * 305 / 365 - 9000 + 45000 * 0.08 * 121 / 365) == "2220.82"
    # Revaluación terreno 360.000 − 300.000 = 60.000 a ORI.
    assert r["totals"]["revaluacionORI"] == "60000.00" and r["totals"]["revaluacionResultado"] == "0.00"
    # Desmantelamiento 50.000 ÷ 1,06^10.
    assert r["totals"]["provDesmantelamiento"] == "27919.74"
    # Roll-forward: 1.115.000 + 212.000 − 30.000 = 1.297.000; dep. acumulada 239.900 + 37.854,11 − 24.300 = 253.454,11.
    assert r["totals"]["costoFinal"] == "1297000.00" and r["totals"]["difCosto"] == "0.00" and r["totals"]["difDepAcum"] == "454.11"
    # Efecto en resultados: −177,81 − 8.000 + 1.777,81 + 2.220,82 = −4.179,18.
    assert r["totals"]["ajusteDep"] == "177.81" and r["totals"]["ajusteResultado"] == "-4179.18" and r["primary"] == "ajusteResultado"
    assert {"DEPRECIACION_DIFERENTE", "TOTALMENTE_DEPRECIADO_EN_USO", "BAJA_MAL_CALCULADA", "DETERIORO", "DESMANTELAMIENTO_NO_RECONOCIDO",
            "DEPRECIACION_EN_CONSTRUCCION", "METODO_NO_RECALCULADO", "REVALUACION_CLASE_INCOMPLETA", "ADICION_GASTO_CAPITALIZADO",
            "INTERESES_DIFERENCIA", "CONCILIACION_AUXILIAR_MAYOR", "REVISAR_COMPONENTES"} <= _codigos(r)


@pytest.mark.parametrize("edicion", ["2015", "2025"])
def test_pymes_intereses_a_gasto(edicion):
    r = correr(_marco=m.MARCO_PYMES, _edicion=edicion)
    assert r["totals"]["ajusteIntereses"] == "-9000.00" and r["totals"]["ajusteResultado"] == "-15400.00"
    assert "INTERESES_CAPITALIZADOS_PYMES" in _codigos(r) and "INTERESES_DIFERENCIA" not in _codigos(r)
    assert r["detalle"]["edicion"] == edicion


def test_sin_tasa_de_capitalizacion_no_inventa():
    r = correr(tasaCapitalizacion=None)
    assert "ajusteIntereses" in r["totals"] and r["totals"]["ajusteIntereses"] == "0.00"
    assert "TASA_CAPITALIZACION_FALTANTE" in _codigos(r)
    assert all(x["cap"] is None for x in r["detalle"]["adiciones"] if x["apto"] == "Sí")


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
