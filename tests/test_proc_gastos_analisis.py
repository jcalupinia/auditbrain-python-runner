"""Procesador gastos_analisis: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import gastos_analisis as m

EJ = m.EJEMPLO


def _run(datasets=None, **param):
    return m.ejecutar(datasets or EJ["datasets"], {**EJ["parametros"], **param}, EJ["corte"])


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def _cta(res, c):
    return next(x for x in res["detalle"]["cuentas"] if x["cuenta"] == c)


def _trx(res, c):
    return next(x for x in res["detalle"]["trans"] if x["comp"] == c)


def test_ejemplo_niif_completas_cifras_a_mano():
    r = _run()
    t = r["totals"]
    assert t["gastoTotal"] == "1008000.00" and t["gastoAnterior"] == "886000.00"
    assert t["difConciliacion"] == "3000.00"                 # 1.008.000 − 1.005.000
    # Devengo: FC-103 7.300 × 181 ÷ 365 = 3.620,00; FC-107 12.000 × 120 ÷ 181 = 7.955,80.
    f3, f7 = _trx(r, "FC-103"), _trx(r, "FC-107")
    assert (f3["dias"], f3["diasPeriodo"], f3["diasPost"]) == (365, 184, 181) and round(f3["anticipado"], 2) == 3620.00
    assert (f7["dias"], f7["diasPeriodo"]) == (181, 61) and round(f7["anticipado"], 2) == 7955.80
    assert t["anticipado"] == "11575.80"
    assert t["devengadoNoRegistrado"] == "3000.00"           # FC-106: diciembre completo registrado en enero
    assert t["noRegistradoCorte"] == "4500.00" and t["otroPeriodo"] == "3000.00"   # FC-104 / FC-105
    assert t["ajusteGasto"] == "-7075.80" and r["primary"] == "ajusteGasto"      # 4.500 + 3.000 − 3.000 − 11.575,80
    assert t["noSoportado"] == "18000.00" and t["reclasificaciones"] == "2200.00"
    assert t["noDeducible"] == "4000.00"                     # FC-108 comprobante 1.500 + FC-109 bancarización 2.500
    assert t["partesRelacionadas"] == "13200.00" and t["rpNoReveladas"] == "3200.00"   # 9.000 + 3.000 + 1.200 − 10.000
    assert t["inusuales"] == "30000.00"
    # Análisis global: 5201 +30.000 (20 %) sin explicar; 5101 +50.000 (9,09 %) no excede; 5601 base 0 excede.
    c1, c2, c6 = _cta(r, "5201"), _cta(r, "5101"), _cta(r, "5601")
    assert c1["excede"] == "Sí" and c1["sinExplicar"] == "Sí" and abs(c1["pct"] - 0.2) < 1e-12
    assert c2["excede"] == "No" and c6["excede"] == "Sí" and c6["sinExplicar"] == "No" and c6["extra"] == "Sí"
    assert _cta(r, "5301")["excedePpto"] == "Sí"             # 60.000 vs 45.000: 33 %
    assert round(_cta(r, "5202")["cobertura"], 6) == round(44500 / 45000, 6)
    c = _codigos(r)
    for k in ("VARIACION_SIN_EXPLICAR", "PARTIDA_EXTRAORDINARIA", "NATURALEZA_NO_REVELADA", "DIF_CONCILIACION", "GASTO_NO_SOPORTADO",
              "DATO_VOUCHING_FALTANTE", "CORTE_OTRO_PERIODO", "CORTE_NO_REGISTRADO", "GASTO_ANTICIPADO_EN_RESULTADOS",
              "DEVENGADO_NO_REGISTRADO", "CLASIFICACION_INCORRECTA", "RP_NO_REVELADAS", "RP_SIN_CATEGORIA", "PARTIDA_INUSUAL",
              "SIN_COMPROBANTE_VALIDO", "SIN_BANCARIZACION"):
        assert k in c
    assert "COSTO_VENTAS_NO_SEPARADO" not in c


def test_ruta_pymes_categorias_y_desglose():
    r = _run(_marco=m.MARCO_PYMES, _edicion="2015")
    cat = {x["cat"]: x["importe"] for x in r["detalle"]["rpCat"]}
    assert len(cat) == 5 and cat["Personal clave"] == 3000 and cat[m.SIN_CATEGORIA] == 10200   # «Dominante» no es categoría PYMES
    assert "NATURALEZA_NO_REVELADA" not in _codigos(r)
    sin_cv = [dict(x, clasificacion="Gastos operativos") if x["id"] == "5101" else x for x in EJ["datasets"]["cuentas"]]
    r2 = _run({"cuentas": sin_cv, "transacciones": EJ["datasets"]["transacciones"]}, _marco=m.MARCO_PYMES, _edicion="2025")
    assert "COSTO_VENTAS_NO_SEPARADO" in _codigos(r2)


def test_opcionales_vacios_no_se_llenan_con_cero():
    r = _run(umbralVarAbs=None, gastosSegunEri=None, rpRevelado=None, materialidadEjecucion=20000)
    assert "difConciliacion" not in r["totals"]
    assert {"SIN_CONCILIACION", "SIN_RP_REVELADO"} <= _codigos(r)
    assert _cta(r, "5204")["varPpto"] is None and _cta(r, "5204")["excedePpto"] is None
    r2 = _run(materialidadEjecucion=None)
    assert all(x["revelarSep"] is None for x in r2["detalle"]["trans"] if x["inusual"] == "Sí" and x["enPeriodo"] == "Sí")


def test_sin_muestra_y_saldo_acreedor():
    cu = EJ["datasets"]["cuentas"] + [{"id": "5999", "nombre": "Reverso", "clasificacion": "Otros gastos", "saldo_actual": "-500", "_row": 9}]
    r = _run({"cuentas": cu, "transacciones": []})
    assert r["totals"]["ajusteGasto"] == "0.00" and {"SIN_MUESTRA", "SALDO_ACREEDOR"} <= _codigos(r)


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"cuentas": [], "transacciones": []}, EJ["parametros"], "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], EJ["parametros"], "")
    with pytest.raises(ValueError):
        _run(umbralVarAbs=None, materialidadEjecucion=None)
    with pytest.raises(ValueError):
        _run(umbralVarPct=-1)
    with pytest.raises(ValueError):
        _run(metodoEri="Mixto")
    malo = [dict(EJ["datasets"]["transacciones"][0], soporte="tal vez")]
    with pytest.raises(ValueError):
        _run({"cuentas": EJ["datasets"]["cuentas"], "transacciones": malo})
    v = m.validar_filas("transacciones", [
        {"id": "X1", "fecha_documento": "2025-01-01", "fecha_registro": "x", "importe": "abc", "cuenta": "5", "proveedor": "A",
         "soporte": "quizá", "servicio_desde": "2025-02-01", "_row": 2}])
    assert not v["ok"] and len(v["errors"]) == 4           # fecha, importe, Sí/No, período incompleto


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
    assert d["processor"] == "gastos_analisis" and len(d["program"]) >= 5 and m.RUBRO == "COSTOS_GASTOS"
    assert "PYMES" in d["summary"] and "2025" in d["source_pymes"]["document"]
