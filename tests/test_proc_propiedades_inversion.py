"""Propiedades de inversión: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import copy

import pytest

from backend.app.aud.niif.procesadores import propiedades_inversion as m

E = m.EJEMPLO


def _run(datasets=None, parametros=None, corte=None):
    return m.ejecutar(datasets or E["datasets"], E["parametros"] if parametros is None else parametros, corte or E["corte"])


def _t(res, k):
    return float(res["totals"][k])


def _it(res, id):
    return next(i for i in res["detalle"]["items"] if i["id"] == id)


def test_ejemplo_cifras_a_mano():
    res = _run({**E["datasets"]}, {**E["parametros"], "_marco": "NIIF completas"})
    assert _t(res, "libros") == 2780000.00
    assert _t(res, "difDetalleMayor") == -5000.00                 # 2.780.000 − 2.785.000
    assert _t(res, "ajusteVR") == 35000.00                        # 20.000 − 20.000 + 25.000 + 5.000 + 5.000
    ip7 = _it(res, "IP-07")                                       # sin VR → costo (NIC 40.53)
    assert ip7["medida"] == "Costo (VR no fiable)" and ip7["base"] == 240000 and ip7["meses"] == 120
    assert ip7["dep"] == 48000 and ip7["depAnio"] == 4800 and ip7["difDep"] == 3000
    assert ip7["neto"] == 252000 and ip7["det"] == 22000 and ip7["medCosto"] == 230000
    assert _t(res, "efectoCosto") == -25000.00                    # 230.000 − 255.000
    assert _t(res, "reclasificacion") == -340000.00               # IP-04 190.000 + IP-05 150.000
    assert _t(res, "piAuditado") == 2450000.00
    assert _t(res, "ajuste") == -335000.00 and res["primary"] == "ajuste"
    assert round(2780000 + 35000 - 25000 - 340000 - 2785000, 2) == _t(res, "ajuste")
    assert _t(res, "difCostoInicial") == 12000.00                 # IP-06: 400.000 + 12.000 − 400.000
    assert _t(res, "difAlquileres") == 8000.00                    # IP-03 2.000 + IP-06 6.000
    assert _t(res, "transfORI") == 80000.00                       # IP-08: 205.000 − 125.000 (40.61-62)
    assert _t(res, "resultadoBajas") == 10000.00 and _t(res, "difBajas") == -10000.00
    assert res["detalle"]["conc"]["difControl"] == pytest.approx(0, abs=1e-9)


def test_clasificacion_y_transferencias():
    res = _run()
    assert _it(res, "IP-04")["clase"] == "PPE (uso propio significativo)"      # 35 % > umbral 10 %
    assert _it(res, "IP-05")["clase"] == "Inventario (NIC 2)"
    assert _it(res, "IP-10")["clase"] == m.PI                                  # 5 % ≤ 10 %
    tr = {x["id"]: x for x in res["detalle"]["transf"]}
    assert tr["IP-08"]["transf"] == "PPE→PI" and tr["IP-08"]["estado"] == "Completa" and tr["IP-08"]["enEj"] == "Sí"
    assert tr["IP-09"]["transf"] == "Inventario→PI" and tr["IP-09"]["estado"].startswith("Sin tratamiento")


def test_problemas_minimos():
    codes = {e["code"] for e in _run()["exceptions"]}
    for c in ("MAL_CLASIFICADO", "USO_MIXTO_SEPARABLE", "VR_NO_RECONOCIDO", "VR_NO_FIABLE", "SIN_FUENTE_VR", "SIN_NIVEL_VR", "COSTO_INICIAL",
              "DEP_DIFERENCIA", "DETERIORO", "ALQUILER_NO_CONCILIADO", "ALQUILER_SIN_CONTRATO", "TRANSFERENCIA_SIN_TRATAMIENTO", "TRANSFERENCIA",
              "BAJA_RESULTADO", "DETALLE_MAYOR", "AJUSTE"):
        assert c in codes, c
    assert "SIN_MAYOR" not in codes and "PYMES_MODELO" not in codes


def test_rutas_por_marco():
    costo = _run(parametros={**E["parametros"], "modelo": "costo", "_marco": "NIIF completas"})
    pym = _run(parametros={**E["parametros"], "vr_sin_esfuerzo_desproporcionado": "no", "_marco": "NIIF para las PYMES", "_edicion": "2015"})
    assert costo["totals"] == pym["totals"]                         # ambos al costo
    assert _t(costo, "ajusteVR") == 0 and _t(costo, "transfORI") == 0
    # IP-01 al costo: base 400.000, 93 meses de 480 → 77.500; neto 422.500.
    assert _it(costo, "IP-01")["dep"] == 77500 and _it(costo, "IP-01")["medCosto"] == 422500
    assert "SIN_VR_REVELACION" in {e["code"] for e in costo["exceptions"]}
    pc = {e["code"] for e in pym["exceptions"]}
    assert "PYMES_MODELO" in pc and "SIN_VR_REVELACION" not in pc
    pym25 = _run(parametros={**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"})
    assert pym25["detalle"]["correcto"] == "valor_razonable" and _t(pym25, "ajusteVR") == 35000
    assert "SIN_NIVEL_VR" in {e["code"] for e in pym25["exceptions"]}
    pym15 = _run(parametros={**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"})
    assert "SIN_NIVEL_VR" not in {e["code"] for e in pym15["exceptions"]}
    assert pym15["detalle"]["transf"][0]["trat"].startswith("PYMES 16.9")
    # PYMES que aplica costo pudiendo medir el VR sin esfuerzo desproporcionado.
    al_reves = _run(parametros={**E["parametros"], "modelo": "costo", "_marco": "NIIF para las PYMES"})
    msg = next(e["message"] for e in al_reves["exceptions"] if e["code"] == "PYMES_MODELO")
    assert "16.7" in msg and _t(al_reves, "ajusteVR") == 35000
    h = {x["name"]: x for x in m.hojas(pym25)}
    assert "sección 12" in h["02_Parametros"]["rows"][2][2]


def test_vacio_y_parametros_invalidos():
    with pytest.raises(ValueError):
        m.ejecutar({"inmuebles": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(parametros={"modelo": "revaluación"})
    with pytest.raises(ValueError):
        _run(parametros={"vr_sin_esfuerzo_desproporcionado": "quizá"})
    with pytest.raises(ValueError):
        _run(parametros={"umbral_uso_propio": 150})


def test_faltantes_y_negativos():
    ds = copy.deepcopy(E["datasets"])
    ip7 = ds["inmuebles"][6]
    ip7["vida_util"] = ""                                         # sin vida útil → se usa la depreciación registrada
    ip7["importe_recuperable"] = ""
    ds["inmuebles"][0]["pct_uso_propio"] = 0.35                   # fracción mal escrita
    ds["inmuebles"][1]["uso"] = "Comodato"                        # uso no reconocido
    ds["inmuebles"][2]["importe_libros"] = -10                    # negativo: se procesa y se ajusta
    del ds["bajas"]
    res = m.ejecutar(ds, {}, E["corte"])
    codes = {e["code"] for e in res["exceptions"]}
    assert {"SIN_VIDA_UTIL", "PCT_USO_FRACCION", "USO_NO_RECONOCIDO", "SIN_MAYOR"} <= codes
    i7 = _it(res, "IP-07")
    assert i7["dep"] is None and i7["det"] is None and i7["neto"] == 255000     # M22: vacío, no cero
    assert _it(res, "IP-03")["ajVR"] == 240010
    assert _t(res, "difDetalleMayor") == 0 and _t(res, "resultadoBajas") == 0


def test_validar_filas():
    v = m.validar_filas("inmuebles", [{"id": "X", "descripcion": "d", "uso": "Alquiler", "costo": "abc", "importe_libros": "1", "_row": 2},
                                      {"id": "TOTAL", "descripcion": "t", "uso": "Alquiler", "costo": "1", "importe_libros": "1", "_row": 3}])
    assert not v["ok"] and len(v["errors"]) == 2
    assert m.validar_filas("bajas", [{"id": "B1", "fecha_baja": "31/08/2025", "producto_neto": "130.000,00", "importe_libros": "110000", "_row": 2}])["ok"]


def test_hojas_y_definicion():
    res = _run()
    hs = m.hojas(res)
    assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
    for h in hs:
        assert len(h["name"]) <= 31
        for fila in h["rows"] + ([h["total"]] if h.get("total") else []):
            assert len(fila) == len(h["cols"]), h["name"]
    assert all(isinstance(f[1], dict) for f in hs[0]["rows"])
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "propiedades_inversion" and len(d["program"]) >= 5
    assert {r["dataset"] for r in d["requests"] if r.get("dataset")} == set(m.DATASETS)
    assert m.RUBRO == "PROPIEDADES_INVERSION" and m.CONTROL in {c["key"] for c in m.CAMPOS[m.PRINCIPAL]}
    for esc, ds, par, corte in m.ESCENARIOS:
        assert m.hojas(m.ejecutar(ds, par, corte))
