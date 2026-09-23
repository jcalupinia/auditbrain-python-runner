"""Activos biológicos y agricultura: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import copy

import pytest

from backend.app.aud.niif.procesadores import activos_biologicos as m

E = m.EJEMPLO


def _run(datasets=None, parametros=None, corte=None):
    return m.ejecutar(datasets or E["datasets"], E["parametros"] if parametros is None else parametros, corte or E["corte"])


def _t(res, k):
    return float(res["totals"][k])


def _it(res, id_):
    return next(a for a in res["detalle"]["items"] if a["id"] == id_)


def test_ejemplo_cifras_a_mano():
    res = _run()
    assert _t(res, "valorLibros") == 1501800.00
    # 191.880 + 231.000 + 650.000 + 135.000 + 80.000 (NIC 16) + 25.000 + 38.000 + 75.240 + 68.000 + 30.000
    assert _t(res, "valorAuditado") == 1524120.00
    assert _t(res, "ajuste") == 22320.00           # −3.120 + 7.000 + 5.000 − 4.000 + 12.240 + 4.000 + 1.200
    assert res["primary"] == "ajuste"
    g1 = _it(res, "G-01")
    assert g1["fu"] == 1560 and g1["ftot"] == 191880 and g1["aj"] == -3120     # (1.600 − 40) × 123
    assert _t(res, "difFisicas") == -2280.00        # G-01 −2 × 1.560; G-04 −2 × 180; C-02 +500 × 2,40
    assert _t(res, "difAnexoMayor") == 1800.00      # 1.501.800 − 1.500.000
    assert _t(res, "plantasProductoras") == 80000.00


def test_transformacion_biologica_y_ganancia():
    res = _run()
    g1 = _it(res, "G-01")
    assert g1["cFis"] == 4380 and g1["cPre"] == 12300               # 3 × 1.460 ; 123 × 100
    assert g1["cTot"] == 191880 - 175200                            # identidad Q1·P1 − Q0·P0
    assert g1["gan"] == 15180 and g1["noRec"] == -3120              # 191.880 − 175.200 − 6.000 + 4.500
    assert _t(res, "cambioFisico") == 72190.00
    assert _t(res, "cambioPrecio") == 118230.00
    assert _t(res, "cambioTotal") == 190420.00
    assert _t(res, "gananciaNoReconocida") == 27320.00
    assert _t(res, "difConciliacion") == 1000.00                    # F-02: 25.000 − (16.000 + 8.000)
    assert _t(res, "deterioroAdicional") == 4000.00                 # G-03: 42.000 − 38.000
    # Puente del ajuste en este ejemplo: no reconocido − diferencia de conciliación − deterioro.
    assert 27320 - 1000 - 4000 == _t(res, "ajuste")
    assert _t(res, "cosechaRecalculada") == 796000.00
    assert _t(res, "cosechaRegistrada") == 782000.00
    assert _t(res, "difCosecha") == 14000.00                        # H-02 7.000 + H-04 6.000 + H-06 1.000


def test_ejemplo_problemas_minimos():
    codes = {e["code"] for e in _run()["exceptions"]}
    for c in ("DIFERENCIA_FISICA", "VALORACION_DIFIERE", "CAMBIO_VR_NO_RECONOCIDO", "COSECHA_NO_A_VR", "MODELO_COSTO_SIN_JUSTIFICAR",
              "CONCILIACION_41_50", "DETERIORO_COSTO", "PLANTA_PRODUCTORA", "ANEXO_MAYOR", "SIN_CONTEO", "SIN_COSTO_VENTA",
              "SIN_DESGLOSE_FISICO_PRECIO"):
        assert c in codes, c
    assert "SIN_MAYOR" not in codes and "SIN_VR" not in codes


def test_rutas_por_marco():
    comp = _run(parametros={**E["parametros"], "_marco": "NIIF completas"})
    pym = _run(parametros={**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"})
    assert _it(comp, "F-01")["ruta"] == "NIC 16"
    assert _it(pym, "F-01")["ruta"] == "Valor razonable"            # PYMES 2015: sin exclusión de plantas productoras
    assert _it(pym, "F-01")["aud"] is None                          # sin VR al corte: M22, vacío
    assert "SIN_VR" in {e["code"] for e in pym["exceptions"]}
    assert _t(pym, "plantasProductoras") == 0
    assert _t(pym, "ajuste") == 22320.00                            # F-01 no medido, el resto igual
    # NIIF completas con VR no fiable: el lote que ya estaba a VR sigue a VR (41.31); el que estaba al costo pasa al costo.
    nf = _run(parametros={**E["parametros"], "vr_fiable": "No", "_marco": "NIIF completas"})
    assert _it(nf, "G-01")["ruta"] == "Valor razonable" and _it(nf, "G-04")["ruta"] == "Costo"
    assert _it(nf, "G-04")["aj"] == 0 and "MODELO_COSTO_SIN_JUSTIFICAR" not in {e["code"] for e in nf["exceptions"]}
    # PYMES con VR que exige esfuerzo desproporcionado: todo al costo, salvo la planta productora de 34.2A.
    pc = _run(parametros={"vr_sin_esfuerzo_desproporcionado": "No", "_marco": "NIIF para las PYMES", "_edicion": "2025"})
    assert all(a["ruta"] == "Costo" for a in pc["detalle"]["items"] if a["id"] != "F-01")
    assert _it(pc, "F-01")["ruta"] == "Sección 17"
    codes = {e["code"] for e in pc["exceptions"]}
    assert {"MODELO_VR_SIN_BASE", "SIN_COSTO"} <= codes
    h = {x["name"]: x for x in m.hojas(pc)}
    assert "Sección 12" in h["02_Parametros"]["rows"][1][1]


def test_planta_productora_pymes_2025_seccion_17():
    """PYMES 2025 párr. 34.2A y 17.3 a): la planta productora medible por separado sale de la Sección 34."""
    p25 = {**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"}
    r25 = _run(parametros=p25)
    f1 = _it(r25, "F-01")
    assert f1["ruta"] == "Sección 17" and f1["aud"] == 80000        # al valor en libros, como la ruta NIC 16
    assert _t(r25, "plantasProductoras") == 80000.00
    # El resto del anexo no cambia: 1.444.120 (PYMES 2015, con F-01 sin medir) + 80.000 de la planta.
    assert _t(r25, "valorAuditado") == 1524120.00 and _t(r25, "ajuste") == 22320.00
    codes = {e["code"] for e in r25["exceptions"]}
    assert "PLANTA_PRODUCTORA" in codes and "SIN_VR" not in codes   # ya no se le exige VR a la planta
    assert "34.2A" in next(e["message"] for e in r25["exceptions"] if e["code"] == "PLANTA_PRODUCTORA")
    assert _t(r25, "cosechaRecalculada") == 796000.00               # su producto sigue en la Sección 34
    # En 2015 no hay exclusión y en NIIF completas la ruta sigue siendo NIC 16.
    assert _it(_run(parametros={**p25, "_edicion": "2015"}), "F-01")["ruta"] == "Valor razonable"
    # Sin el dato de 34.2A la planta se queda en la Sección 34 y se pide (M22).
    ds = copy.deepcopy(E["datasets"])
    next(a for a in ds["activos"] if a["id"] == "F-01")["medible_por_separado"] = ""
    sin = m.ejecutar(ds, p25, E["corte"])
    assert _it(sin, "F-01")["ruta"] == "Valor razonable"
    ex = next(e for e in sin["exceptions"] if e["code"] == "PLANTA_SIN_EVALUAR_34_2A")
    assert "F-01" in ex["message"] and float(ex["amount"]) == 80000
    # Si no puede medirse por separado, toda la planta sigue en la Sección 34 y no se emite el problema.
    next(a for a in ds["activos"] if a["id"] == "F-01")["medible_por_separado"] = "No"
    no = m.ejecutar(ds, p25, E["corte"])
    assert _it(no, "F-01")["ruta"] == "Valor razonable"
    assert "PLANTA_SIN_EVALUAR_34_2A" not in {e["code"] for e in no["exceptions"]}


def test_vacio_y_parametros_invalidos():
    with pytest.raises(ValueError):
        m.ejecutar({"activos": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(parametros={"vr_fiable": "tal vez"})


def test_faltantes_y_negativos():
    ds = copy.deepcopy(E["datasets"])
    ds["activos"][0]["cant_final"] = -5
    ds["activos"][1]["vr_corte"] = ""
    ds["activos"][2]["libros_inicial"] = ""
    del ds["cosecha"]
    res = m.ejecutar(ds, {}, E["corte"])
    codes = {e["code"] for e in res["exceptions"]}
    assert {"CANTIDAD_NEGATIVA", "SIN_VR", "SIN_GANANCIA_REGISTRADA", "SIN_COSECHA", "SIN_MAYOR"} <= codes
    g2 = _it(res, "G-02")
    assert g2["ftot"] is None and g2["aj"] is None                  # M22: vacío, no cero
    assert _t(res, "difAnexoMayor") == 0


def test_validar_filas():
    v = m.validar_filas("activos", [{"id": "X", "categoria": "c", "cant_final": "abc", "valor_libros": "1", "_row": 2},
                                    {"id": "TOTAL", "categoria": "t", "cant_final": "1", "valor_libros": "1", "_row": 3}])
    assert not v["ok"] and len(v["errors"]) == 2
    assert m.validar_filas("cosecha", [{"id": "H1", "producto": "Leche", "cantidad": "1.000,50", "vr_unitario": "0,45",
                                        "valor_registrado": "450", "_row": 2}])["ok"]


def test_hojas_y_definicion():
    res = _run()
    hs = m.hojas(res)
    assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
    for h in hs:
        assert len(h["name"]) <= 31
        for fila in h["rows"] + ([h["total"]] if h.get("total") else []):
            assert len(fila) == len(h["cols"]), h["name"]
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "activos_biologicos" and len(d["program"]) >= 5
    assert {r["dataset"] for r in d["requests"] if r.get("dataset")} == set(m.DATASETS)
    assert m.RUBRO == "BIOLOGICOS" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
    for esc, ds, par, corte in m.ESCENARIOS:
        assert m.hojas(m.ejecutar(ds, par, corte))
