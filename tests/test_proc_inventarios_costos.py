"""Inventarios, producción y costo de ventas: ejemplo de control recalculado a mano y casos límite."""
import copy

import pytest

from backend.app.aud.niif.procesadores import inventarios_costos as m

E = m.EJEMPLO


def _run(datasets=None, parametros=None, corte=None):
    return m.ejecutar(datasets or E["datasets"], E["parametros"] if parametros is None else parametros, corte or E["corte"])


def _t(res, k):
    return float(res["totals"][k])


def test_ejemplo_cifras_a_mano():
    res = _run()
    # Costo auditado: 2.500 + 480×1,2 + 2.000×0,55 + 3.500 + 3.200 + 900 + 1.800 + 305×18 + 4.500 + 790×5
    # + 200×40 (E-300) + 100×25 (E-301) + 50×60 (E-302) = 27.516 + 13.500
    assert _t(res, "costoAuditado") == 41016.00
    assert _t(res, "difFisicas") == 16.00           # −20×1,2 + 5×18 − 10×5
    assert _t(res, "difExtension") == -100.00       # B-010: 10×350 − 3.600
    assert _t(res, "difCosto") == 100.00            # A-003: (0,55 − 0,50) × 2.000
    assert _t(res, "difKardexMayor") == -300.00     # 41.000 − 41.300
    # B-010 (350−265)×10 + C-102 (30−26,5)×150 + E-300 (40−33)×200 + E-301 (25−20)×100 + E-302 (60−50)×50
    assert _t(res, "rebajaVnr") == 3775.00
    assert _t(res, "provObsolescencia") == 3050.00  # B-011 25 % (305 d) + B-012 50 % (549 d) + C-100 100 % (945 d)
    # NIC 2.9 / PYMES 13.4 miden al MENOR entre costo y VNR: con precio de venta informado manda la rebaja a VNR y
    # el tramo de obsolescencia no provisiona. B-011 (VNR 1.200−50 = 1.150 > costo 800) y B-012 (VNR 70 > costo 45)
    # tienen VNR por encima del costo, así que sus tramos (800 y 450) quedan en 0. El tramo solo estima el VNR de
    # C-100, que no tiene precio de venta (1.800 × 100 %). Provisión antes de la excepción de NIC 2.32 = 850
    # (B-010) + 525 (C-102) + 1.800 (C-100) + 1.400 (E-300) + 500 (E-301) + 500 (E-302) = 5.575.
    assert res["detalle"]["conc"]["provBase"] == 5575.00
    assert _t(res, "excepcionNic232") == 1400.00    # E-300: el producto terminado se vende con margen (330 − 300)
    assert _t(res, "provisionEstimada") == 4175.00  # 5.575 − 1.400
    assert _t(res, "inventarioNeto") == 36841.00    # 41.016 − 4.175
    assert _t(res, "libroNeto") == 40300.00         # 41.300 − 1.000
    assert _t(res, "ajuste") == -3459.00
    assert res["primary"] == "ajuste"
    # Puente: −100 + 16 + 100 − 300 − (4.175 − 1.000) = −3.459
    assert round(-100 + 16 + 100 - 300 - (4175 - 1000), 2) == _t(res, "ajuste")
    prov = {i["id"]: i["prov"] for i in res["detalle"]["items"]}
    assert prov["B-011"] == 0 and prov["B-012"] == 0 and prov["C-100"] == 1800
    assert prov["E-300"] == 0 and prov["E-301"] == 500 and prov["E-302"] == 500


def test_ejemplo_produccion_costo_ventas_y_corte():
    res = _run()
    op = {x["id"]: x for x in res["detalle"]["prod"]}
    assert op["OP-01"]["tasa"] == 12 and op["OP-01"]["abs"] == 9600 and op["OP-01"]["noAbs"] == 2400
    assert op["OP-01"]["costo"] == 40600 and op["OP-01"]["exceso"] == 2400
    assert op["OP-02"]["costo"] == 50250                       # desperdicio anormal 500 excluido
    assert op["OP-03"]["abs"] == 12000                         # producción alta: no se absorbe más que el CIF real
    assert _t(res, "cifNoAbsorbido") == 2400 and _t(res, "cifExcesoCapitalizado") == 2400
    assert res["detalle"]["conc"]["prodDif"] == 2400           # 151.750 − 149.350
    mv = {x["id"]: x for x in res["detalle"]["mov"]}
    assert mv["Productos terminados"]["cogm"] == 150750 and mv["Productos terminados"]["cogs"] == 149850
    assert mv["Mercaderías"]["dif"] == 0
    assert _t(res, "difCostoVentas") == 1850
    assert _t(res, "corte") == 5300                            # FC-902 2.200 + GR-501 3.100
    assert res["detalle"]["conc"]["difControl"] == pytest.approx(0, abs=1e-9)


def test_ejemplo_problemas_minimos():
    codes = {e["code"] for e in _run()["exceptions"]}
    for c in ("DIFERENCIA_FISICA", "KARDEX_MAYOR", "CIF_NO_ABSORBIDO_CAPITALIZADO", "COSTO_VENTAS", "VNR_BAJO_COSTO",
              "LENTA_ROTACION_SIN_PROVISION", "DIF_EXTENSION", "DIF_COSTO_UNITARIO", "APERTURA", "PRODUCCION_NO_CONCILIADA",
              "SIN_PRECIO_VENTA", "VNR_ESTIMADO_ANTIGUEDAD", "SIN_CONTEO", "CORTE", "AJUSTE",
              "EXCEPCION_NIC232", "MP_MARGEN_NEGATIVO", "MP_SIN_DEMOSTRACION_PT"):
        assert c in codes, c
    assert "SIN_MAYOR" not in codes and "SIN_PROVISION_REGISTRADA" not in codes
    assert "REBAJA_MAYOR_QUE_COSTO" not in codes          # ningún VNR del ejemplo es negativo


def test_vnr_negativo_se_limita_al_costo():
    # Costo 10 × 20 = 200; VNR = 5 − 0 − 30 = −25 → rebaja bruta (20 − (−25)) × 10 = 450 > 200.
    # La rebaja se limita al costo (200): el inventario no puede quedar negativo. Exceso señalado 250.
    ds = {"inventario": [m._it("Z-1", "Saldo con VNR negativo", 10, 10, 20, 200, "2025-12-01", 5, "", 30)]}
    res = m.ejecutar(ds, {"saldoMayor": 200, "provisionRegistrada": 0}, E["corte"])
    it = res["detalle"]["items"][0]
    assert it["rebajaBruta"] == 450 and it["rebaja"] == 200 and it["exceso"] == 250 and it["prov"] == 200
    assert _t(res, "provisionEstimada") == 200.00 and _t(res, "inventarioNeto") == 0.00
    exc = next(e for e in res["exceptions"] if e["code"] == "REBAJA_MAYOR_QUE_COSTO")
    assert exc["amount"] == "250.00"


def test_excepcion_nic232_tres_rutas():
    res = _run()
    it = {i["id"]: i for i in res["detalle"]["items"]}
    # 1) Demostrada: margen 330 − 300 = 30 ≥ 0 → la materia prima no se rebaja por debajo del costo (NIC 2.32).
    assert it["E-300"]["ptMargen"] == 30 and it["E-300"]["excepcion"]
    assert it["E-300"]["provBase"] == 1400 and it["E-300"]["prov"] == 0 and it["E-300"]["efectoExc"] == 1400
    # 2) Margen negativo (560 − 600 = −40): no aplica, se rebaja a VNR (25 − 20) × 100 = 500.
    assert it["E-301"]["ptMargen"] == -40 and not it["E-301"]["excepcion"] and it["E-301"]["prov"] == 500
    # 3) Sin el costo ni el precio esperados del producto terminado: no aplica, rebaja (60 − 50) × 50 = 500.
    assert it["E-302"]["ptMargen"] is None and not it["E-302"]["excepcion"] and it["E-302"]["prov"] == 500
    # D-200 cumple la excepción pero su provisión base ya era 0 (VNR 5,50 > costo 5): efecto 0.
    assert it["D-200"]["excepcion"] and it["D-200"]["efectoExc"] == 0
    assert it["A-001"]["esMp"] is False and it["A-001"]["motivoExc"] == m._MOT_NO_MP
    assert _t(res, "excepcionNic232") == 1400.00
    imp = {e["code"]: e["amount"] for e in res["exceptions"]}
    assert imp["EXCEPCION_NIC232"] == "1400.00" and imp["MP_MARGEN_NEGATIVO"] == "500.00"
    assert imp["MP_SIN_DEMOSTRACION_PT"] == "500.00"
    h = {x["name"]: x for x in m.hojas(res)}["11_Excepcion_MP"]
    fila = {f[0]: f for f in h["rows"]}
    assert [fila[k][7]["v"] for k in ("E-300", "E-301", "E-302", "D-200")] == ["Sí", "No", "No", "Sí"]
    assert fila["E-301"][8]["v"] == m._MOT_NEG and fila["E-302"][8]["v"] == m._MOT_FALTA
    assert fila["E-300"][9]["v"] == 1400 and fila["E-300"][10]["v"] == 1400
    assert h["total"][9]["v"] == 5575.00 and h["total"][10]["v"] == 1400.00


def test_excepcion_nic232_sin_demostracion_y_margen_negativo():
    esc = {n: (ds, par, c) for n, ds, par, c in m.ESCENARIOS}
    for n in ("mp_sin_demostracion", "mp_margen_negativo"):
        ds, par, c = esc[n]
        res = m.ejecutar(ds, par, c)
        assert _t(res, "excepcionNic232") == 0.00, n          # ninguna excepción se aplica
        assert _t(res, "provisionEstimada") == 5575.00, n     # se provisiona la rebaja completa
        assert _t(res, "ajuste") == -4859.00, n
    assert "MP_SIN_DEMOSTRACION_PT" in {e["code"] for e in m.ejecutar(*esc["mp_sin_demostracion"])["exceptions"]}
    assert "MP_MARGEN_NEGATIVO" in {e["code"] for e in m.ejecutar(*esc["mp_margen_negativo"])["exceptions"]}


def test_rutas_por_marco():
    comp = _run(parametros={**E["parametros"], "_marco": "NIIF completas"})
    pym = _run(parametros={**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"})
    # La medición base es la misma; lo único que cambia por marco es la excepción de NIC 2.32, que las
    # Secciones 13.19 y 27.2-27.4 de la NIIF para las PYMES no recogen.
    assert {k for k in comp["totals"] if comp["totals"][k] != pym["totals"][k]} == {
        "excepcionNic232", "provisionEstimada", "inventarioNeto", "ajuste"}
    assert float(pym["totals"]["excepcionNic232"]) == 0 and float(pym["totals"]["provisionEstimada"]) == 5575.00
    assert float(pym["totals"]["ajuste"]) == -4859.00
    codes = {e["code"] for e in pym["exceptions"]}
    assert "EXCEPCION_NIC232_NO_EN_PYMES" in codes and "EXCEPCION_NIC232" not in codes
    assert not any(i["excepcion"] for i in pym["detalle"]["items"])
    assert pym["detalle"]["pymes"] and pym["detalle"]["edicion"] == "2025"
    assert "27.2" in pym["labels"]["rebajaVnr"]
    msg = next(e["message"] for e in pym["exceptions"] if e["code"] == "VNR_BAJO_COSTO")
    assert "PYMES 13.4" in msg
    h = {x["name"]: x for x in m.hojas(pym)}
    assert "secciones 13 y 27" in h["02_Parametros"]["rows"][1][1]


def test_vacio_y_parametros_invalidos():
    with pytest.raises(ValueError):
        m.ejecutar({"inventario": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(parametros={"obsPct1": 150})
    with pytest.raises(ValueError):
        _run(parametros={"obsDias1": 400, "obsDias2": 365})
    with pytest.raises(ValueError):
        _run(parametros={"obsDias1": -1})


def test_faltantes_y_negativos():
    ds = copy.deepcopy(E["datasets"])
    ds["inventario"][0]["cant_kardex"] = -5
    ds["inventario"][0]["valor_kardex"] = -12.5
    ds["produccion"][0]["capacidad_normal"] = ""
    ds["produccion"][1]["cif_fijo_capitalizado"] = ""
    del ds["movimiento"]
    res = m.ejecutar(ds, {}, E["corte"])
    codes = {e["code"] for e in res["exceptions"]}
    assert {"KARDEX_NEGATIVO", "SIN_CAPACIDAD_NORMAL", "SIN_CIF_CAPITALIZADO", "SIN_MOVIMIENTO", "SIN_MAYOR",
            "SIN_PROVISION_REGISTRADA"} <= codes
    op1 = res["detalle"]["prod"][0]
    assert op1["tasa"] is None and op1["costo"] is None       # M22: vacío, no cero
    # Sin mayor, el libro toma el kardex: diferencia kardex–mayor 0.
    assert _t(res, "difKardexMayor") == 0


def test_validar_filas():
    v = m.validar_filas("inventario", [{"id": "X", "descripcion": "d", "cant_kardex": "abc", "costo_unitario": "1", "valor_kardex": "1", "_row": 2},
                                       {"id": "TOTAL", "descripcion": "t", "cant_kardex": "1", "costo_unitario": "1", "valor_kardex": "1", "_row": 3}])
    assert not v["ok"] and len(v["errors"]) == 2
    assert m.validar_filas("corte", [{"id": "F1", "tipo": "Compra", "fecha_documento": "31/12/2025", "fecha_registro": "2026-01-02",
                                      "importe": "1.500,00", "_row": 2}])["ok"]


def test_hojas_y_definicion():
    res = _run()
    hs = m.hojas(res)
    assert [(h["name"], h["label"]) for h in hs][:1] == [m.CEDULAS[0]]
    assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
    for h in hs:
        assert len(h["name"]) <= 31
        for fila in h["rows"] + ([h["total"]] if h.get("total") else []):
            assert len(fila) == len(h["cols"]), h["name"]
    res_tot = {h["name"]: h for h in hs}["01_Resumen"]["rows"]
    assert any(isinstance(c, dict) for f in res_tot for c in f)
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "inventarios_costos" and len(d["program"]) >= 5
    assert {r["dataset"] for r in d["requests"] if r.get("dataset")} == set(m.DATASETS)
    assert m.RUBRO == "INVENTARIOS" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
    for esc, ds, par, corte in m.ESCENARIOS:
        assert m.hojas(m.ejecutar(ds, par, corte))
