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
    assert t["rpNoReveladaMarcada"] == "1200.00"             # solo FC-115 está marcada «No» en la nota
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
              "SIN_COMPROBANTE_VALIDO", "SIN_BANCARIZACION", "RP_TRANSACCION_NO_REVELADA", "DATO_RP_REVELADA_FALTANTE"):
        assert k in c
    assert "COSTO_VENTAS_NO_SEPARADO" not in c
    # Con la manifestación escrita de la administración sí se concluye sobre la integridad.
    assert "RP_INTEGRIDAD_NO_CONCLUIDA" not in c
    assert r["detalle"]["rpEstado"] == "Revelación incompleta: hay transacciones sin revelar"


def test_integridad_partes_relacionadas_sin_evidencia_no_concluye():
    """Decisión del socio: sin evidencia de población completa se procesa, pero no se concluye."""
    r = _run(rpEvidenciaIntegridad=None)
    # La población se procesa igual: 9.000 (FC-111) + 3.000 (FC-114) + 1.200 (FC-115) = 13.200.
    assert r["totals"]["partesRelacionadas"] == "13200.00" and r["totals"]["rpNoReveladas"] == "3200.00"
    assert r["detalle"]["rpEstado"] == "No concluida por falta de evidencia de población completa"
    e = next(x for x in r["exceptions"] if x["code"] == "RP_INTEGRIDAD_NO_CONCLUIDA")
    assert e["amount"] == "13200.00" and "NIA 550 párr. 26" in e["message"]
    # Con evidencia pero sin el importe revelado en notas tampoco se concluye.
    assert _run(rpRevelado=None)["detalle"]["rpEstado"] == "No concluida: falta el importe revelado en notas"
    # Todas las transacciones marcadas en la nota y nota = 13.200 → concluye completa.
    ds = {"cuentas": EJ["datasets"]["cuentas"],
          "transacciones": [dict(x, revelada_rp="Sí") if x.get("parte_relacionada") == "Sí" else x
                            for x in EJ["datasets"]["transacciones"]]}
    r2 = _run(ds, rpRevelado=13200)
    assert r2["totals"]["rpNoReveladaMarcada"] == "0.00"
    assert r2["detalle"]["rpEstado"] == "Revelación completa según la evidencia examinada"
    assert {"RP_TRANSACCION_NO_REVELADA", "DATO_RP_REVELADA_FALTANTE", "RP_INTEGRIDAD_NO_CONCLUIDA"}.isdisjoint(_codigos(r2))
    # Sin transacciones con partes relacionadas: no hay nada que revelar, pero la evidencia sigue haciendo falta.
    sin_rp = [{k: ("No" if k == "parte_relacionada" else v) for k, v in x.items()} for x in EJ["datasets"]["transacciones"]]
    r3 = _run({"cuentas": EJ["datasets"]["cuentas"], "transacciones": sin_rp})
    assert r3["totals"]["partesRelacionadas"] == "0.00"
    assert r3["detalle"]["rpEstado"] == "Sin transacciones con partes relacionadas en la muestra"
    assert _run({"cuentas": EJ["datasets"]["cuentas"], "transacciones": sin_rp},
                rpEvidenciaIntegridad=None)["detalle"]["rpEstado"] == "No concluida por falta de evidencia de población completa"


def test_cedula_integridad_y_maestro_obligatorio():
    r = _run()
    h = next(x for x in m.hojas(r) if x["name"] == "11_RP_Integridad")
    assert [c[0] for c in h["cols"]][:5] == ["Comprobante", "Proveedor", "Cuenta", "Importe", "Categoría informada"]
    assert [f[0] for f in h["rows"]] == ["FC-111", "FC-114", "FC-115"]
    # Categoría válida para NIIF completas: «Dominante» y «Personal clave» sí; FC-115 no trae categoría.
    assert [f[5]["v"] for f in h["rows"]] == ["Sí", "Sí", "No"]
    assert [f[6] for f in h["rows"]] == ["Sí", None, "No"]          # incluida en la nota (vacío = no informado, M22)
    assert [f[7]["v"] for f in h["rows"]] == [0.0, 0.0, 1200.0]     # importe no revelado según la marca
    assert h["total"][3]["v"] == 13200.0 and h["total"][7]["v"] == 1200.0
    assert h["total"][8]["v"] == "Revelación incompleta: hay transacciones sin revelar"
    # En PYMES «Dominante» no es categoría de la Sección 33.10.
    hp = next(x for x in m.hojas(_run(_marco=m.MARCO_PYMES, _edicion="2015")) if x["name"] == "11_RP_Integridad")
    assert [f[5]["v"] for f in hp["rows"]] == ["No", "Sí", "No"]
    # El maestro completo de partes relacionadas y la manifestación escrita son PBC obligatorios.
    rq = {x["id"]: x for x in m.definicion()["requests"]}
    assert rq["RQ-006"]["required"] and "COMPLETO" in rq["RQ-006"]["document"] and "población" in rq["RQ-006"]["content"].lower()
    assert rq["RQ-008"]["required"] and "NIA 550 párr. 26" in rq["RQ-008"]["content"]


def test_ruta_pymes_categorias_y_desglose():
    r = _run(_marco=m.MARCO_PYMES, _edicion="2015")
    cat = {x["cat"]: x["importe"] for x in r["detalle"]["rpCat"]}
    assert len(cat) == 5 and cat["Personal clave"] == 3000 and cat[m.SIN_CATEGORIA] == 10200   # «Dominante» no es categoría PYMES
    assert "NATURALEZA_NO_REVELADA" not in _codigos(r)
    sin_cv = [dict(x, clasificacion="Gastos operativos") if x["id"] == "5101" else x for x in EJ["datasets"]["cuentas"]]
    ds = {"cuentas": sin_cv, "transacciones": EJ["datasets"]["transacciones"]}
    r2 = _run(ds, _marco=m.MARCO_PYMES, _edicion="2025")
    assert "COSTO_VENTAS_NO_SEPARADO" in _codigos(r2)
    # NIC 1.103 lo exige igual en NIIF completas (antes solo se validaba en PYMES).
    r3 = _run(ds)
    assert "COSTO_VENTAS_NO_SEPARADO" in _codigos(r3)
    assert any("NIC 1 párr. 103" in e["message"] for e in r3["exceptions"] if e["code"] == "COSTO_VENTAS_NO_SEPARADO")


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
