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
    # IP-04 es de uso mixto con partes separables: NIC 40.10 lo contabiliza por partes (65 % es PI), así que su
    # ajuste de VR entra a prorrata: (210.000 − 190.000) × 65 % = 13.000.
    assert _t(res, "ajusteVR") == 48000.00                        # 20.000 − 20.000 + 13.000 + 25.000 + 5.000 + 5.000
    ip7 = _it(res, "IP-07")                                       # sin VR → costo (NIC 40.53)
    assert ip7["medida"] == "Costo (VR no fiable)" and ip7["base"] == 240000 and ip7["meses"] == 120
    assert ip7["dep"] == 48000 and ip7["depAnio"] == 4800 and ip7["difDep"] == 3000
    assert ip7["neto"] == 252000 and ip7["det"] == 22000 and ip7["medCosto"] == 230000
    assert _t(res, "efectoCosto") == -25000.00                    # 230.000 − 255.000
    # Reclasificación: solo la parte de uso propio de IP-04 (190.000 × 35 % = 66.500) + IP-05 (venta) 150.000.
    assert _t(res, "reclasificacion") == -216500.00
    assert _it(res, "IP-04")["parte"] == 0.65 and _it(res, "IP-04")["aud"] == 136500.00   # 210.000 × 65 %
    assert _t(res, "piAuditado") == 2586500.00
    assert _t(res, "ajuste") == -198500.00 and res["primary"] == "ajuste"
    assert round(2780000 + 48000 - 25000 - 216500 - 2785000, 2) == _t(res, "ajuste")
    assert _t(res, "difCostoInicial") == 12000.00                 # IP-06: 400.000 + 12.000 − 400.000
    assert _t(res, "difAlquileres") == 8000.00                    # IP-03 2.000 + IP-06 6.000
    assert _t(res, "transfORI") == 80000.00                       # IP-08: 205.000 − 125.000 (40.61-62)
    assert _t(res, "transfResultados") == 0.00 and _t(res, "usoSuperavit") == 0.00
    assert _t(res, "superavitFinal") == 110000.00                 # 30.000 + 80.000 − 0 (NIC 16.41: sigue en patrimonio)
    assert _t(res, "resultadoBajas") == 10000.00 and _t(res, "difBajas") == -10000.00
    assert res["detalle"]["conc"]["difControl"] == pytest.approx(0, abs=1e-9)


def test_clasificacion_y_transferencias():
    res = _run()
    assert _it(res, "IP-04")["clase"] == m.PI_PARTE                            # separable: por partes (NIC 40.10)
    assert _it(res, "IP-05")["clase"] == "Inventario (NIC 2)"
    assert _it(res, "IP-10")["clase"] == m.PI                                  # 5 % ≤ 10 % y no separable
    tr = {x["id"]: x for x in res["detalle"]["transf"]}
    assert tr["IP-08"]["transf"] == "PPE→PI" and tr["IP-08"]["estado"] == "Completa" and tr["IP-08"]["enEj"] == "Sí"
    assert tr["IP-09"]["transf"] == "Inventario→PI" and tr["IP-09"]["estado"].startswith("Sin tratamiento")


def test_problemas_minimos():
    codes = {e["code"] for e in _run()["exceptions"]}
    for c in ("MAL_CLASIFICADO", "USO_MIXTO_SEPARADO", "VR_NO_RECONOCIDO", "VR_NO_FIABLE", "SIN_FUENTE_VR", "SIN_NIVEL_VR", "COSTO_INICIAL",
              "DEP_DIFERENCIA", "DETERIORO", "ALQUILER_NO_CONCILIADO", "ALQUILER_SIN_CONTRATO", "TRANSFERENCIA_SIN_TRATAMIENTO", "TRANSFERENCIA",
              "BAJA_RESULTADO", "DETALLE_MAYOR", "AJUSTE", "SUPERAVIT_AUMENTO", "SUPERAVIT_EN_PATRIMONIO"):
        assert c in codes, c
    assert "SIN_MAYOR" not in codes and "PYMES_MODELO" not in codes
    assert "SIN_SUPERAVIT_REVALUACION" not in codes and "SUPERAVIT_CONSUMIDO" not in codes


def test_rutas_por_marco():
    costo = _run(parametros={**E["parametros"], "modelo": "costo", "_marco": "NIIF completas"})
    pym = _run(parametros={**E["parametros"], "vr_sin_esfuerzo_desproporcionado": "no", "_marco": "NIIF para las PYMES", "_edicion": "2015"})
    # Ambos miden al costo y coinciden en los inmuebles que no son de uso mixto…
    assert _t(costo, "ajusteVR") == 0 and _t(costo, "transfORI") == 0
    assert _t(pym, "ajusteVR") == 0 and _t(costo, "deterioro") == _t(pym, "deterioro") == 22000
    # IP-01 al costo: base 400.000, 93 meses de 480 → 77.500; neto 422.500.
    for r in (costo, pym):
        assert _it(r, "IP-01")["dep"] == 77500 and _it(r, "IP-01")["medCosto"] == 422500
    # …pero el uso mixto se trata distinto: completas → por partes si es separable (IP-04 65 % PI; IP-10 5 % ≤
    # umbral 10 % → PI entera) = reclasificación 190.000 × 35 % + 150.000 (venta) = −216.500. PYMES 16.4 no usa
    # umbral y, como aquí el VR no se mide sin esfuerzo desproporcionado, IP-04 e IP-10 van enteros a PPE
    # (sección 17): reclasificación 190.000 + 150.000 + 150.000 = −490.000.
    assert _t(costo, "reclasificacion") == -216500 and _t(pym, "reclasificacion") == -490000
    assert _t(costo, "piAuditado") == 1945125 and _t(pym, "piAuditado") == 1759625
    assert _it(pym, "IP-04")["clase"] == m.PPE_MIXTO and _it(pym, "IP-10")["clase"] == m.PPE_MIXTO
    assert "USO_MIXTO_A_PPE" in {e["code"] for e in pym["exceptions"]}
    # PYMES 16.9 no regula la medición de la diferencia: no se calcula y el historial del superávit queda vacío.
    assert "SUPERAVIT_PYMES" in {e["code"] for e in pym["exceptions"]}
    assert pym["detalle"]["sup"][0]["fin"] is None and _t(pym, "superavitFinal") == 0
    # Modelo del costo (NIC 40.59): la transferencia no mueve el importe en libros ni el superávit (30.000 se arrastra).
    assert _t(costo, "superavitFinal") == 30000 and costo["detalle"]["sup"][0]["mov"] == 0
    assert "SIN_VR_REVELACION" in {e["code"] for e in costo["exceptions"]}
    pc = {e["code"] for e in pym["exceptions"]}
    assert "PYMES_MODELO" in pc and "SIN_VR_REVELACION" not in pc
    pym25 = _run(parametros={**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"})
    # PYMES con VR medible: IP-04 (65 %) e IP-10 (95 %) se separan sin umbral (16.4); el VR de IP-10 iguala al
    # importe en libros, así que el ajuste de VR sigue siendo 48.000.
    assert pym25["detalle"]["correcto"] == "valor_razonable" and _t(pym25, "ajusteVR") == 48000
    assert _it(pym25, "IP-10")["parte"] == 0.95 and _t(pym25, "reclasificacion") == -224000
    assert "SIN_NIVEL_VR" in {e["code"] for e in pym25["exceptions"]}
    pym15 = _run(parametros={**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2015"})
    assert "SIN_NIVEL_VR" not in {e["code"] for e in pym15["exceptions"]}
    assert pym15["detalle"]["transf"][0]["trat"].startswith("PYMES 16.9")
    # PYMES que aplica costo pudiendo medir el VR sin esfuerzo desproporcionado.
    al_reves = _run(parametros={**E["parametros"], "modelo": "costo", "_marco": "NIIF para las PYMES"})
    msg = next(e["message"] for e in al_reves["exceptions"] if e["code"] == "PYMES_MODELO")
    assert "16.7" in msg and _t(al_reves, "ajusteVR") == 48000
    h = {x["name"]: x for x in m.hojas(pym25)}
    assert "sección 12" in h["02_Parametros"]["rows"][2][2]


def test_superavit_aumento_se_mantiene_en_patrimonio():
    """NIC 40.61-62 b) ii) y NIC 16.39: el aumento al transferir de PPE revaluada a PI a valor razonable va a
    otro resultado integral y engrosa el superávit de revaluación del inmueble; no pasa por resultados.

    IP-08 a mano: VR al cambio 205.000 − libros al cambio 125.000 = +80.000 → todo a ORI, nada a resultados.
    Superávit: 30.000 (saldo inicial informado) + 80.000 − 0 = 110.000, que permanece en patrimonio.
    """
    res = _run({**E["datasets"]}, {**E["parametros"], "_marco": "NIIF completas"})
    tr = next(x for x in res["detalle"]["transf"] if x["id"] == "IP-08")
    assert tr["dif"] == 80000 and tr["ori"] == 80000 and tr["res"] == 0 and tr["uso"] == 0 and tr["estado"] == "Completa"
    s = res["detalle"]["sup"]
    assert len(s) == 1 and s[0]["id"] == "IP-08" and s[0]["ini"] == 30000 and s[0]["mov"] == 80000
    assert s[0]["uso"] == 0 and s[0]["fin"] == 110000 and s[0]["destino"] == m.DESTINO_SI
    codes = {e["code"] for e in res["exceptions"]}
    assert {"SUPERAVIT_AUMENTO", "SUPERAVIT_EN_PATRIMONIO"} <= codes and "SIN_SUPERAVIT_REVALUACION" not in codes
    msg = next(e["message"] for e in res["exceptions"] if e["code"] == "SUPERAVIT_AUMENTO")
    assert "40.62 b i" in msg                                      # reversión de deterioro: no se separa, se avisa


def test_superavit_disminucion_consume_y_solo_el_exceso_a_resultados():
    """NIC 40.62 a) y NIC 16.40: la disminución se reconoce en ORI hasta agotar el superávit de ESE inmueble.

    IP-08 modificado: VR al cambio 100.000 − libros 125.000 = −25.000; superávit 10.000.
    Uso del superávit = MIN(10.000; 25.000) = 10.000 → a ORI −10.000; exceso a resultados −25.000 + 10.000 = −15.000.
    Saldo final del superávit = 10.000 + 0 − 10.000 = 0.
    """
    res = m.ejecutar(m._SUP_BAJA, {**E["parametros"], "_marco": "NIIF completas"}, E["corte"])
    tr = next(x for x in res["detalle"]["transf"] if x["id"] == "IP-08")
    assert tr["dif"] == -25000 and tr["uso"] == 10000 and tr["ori"] == -10000 and tr["res"] == -15000
    assert _t(res, "transfResultados") == -15000.00 and _t(res, "transfORI") == -10000.00
    assert _t(res, "usoSuperavit") == 10000.00 and _t(res, "superavitFinal") == 0.00
    s = res["detalle"]["sup"][0]
    assert s["ini"] == 10000 and s["mov"] == 0 and s["uso"] == 10000 and s["fin"] == 0 and s["destino"] == m.DESTINO_NO
    codes = {e["code"] for e in res["exceptions"]}
    assert "SUPERAVIT_CONSUMIDO" in codes and "SUPERAVIT_EN_PATRIMONIO" not in codes


def test_superavit_sin_dato_queda_vacio_y_avisa():
    """M22: sin el superávit informado no se puede repartir la disminución → importes vacíos, nunca 0."""
    res = m.ejecutar(m._SUP_SIN_DATO, {**E["parametros"], "_marco": "NIIF completas"}, E["corte"])
    tr = next(x for x in res["detalle"]["transf"] if x["id"] == "IP-08")
    assert tr["dif"] == -25000 and tr["uso"] is None and tr["res"] is None and tr["ori"] is None
    assert tr["estado"] == m.SIN_SUP
    s = res["detalle"]["sup"][0]
    assert s["ini"] is None and s["fin"] is None and s["destino"] == ""
    assert _t(res, "transfResultados") == 0 and _t(res, "transfORI") == 0 and _t(res, "superavitFinal") == 0
    msg = next(e["message"] for e in res["exceptions"] if e["code"] == "SIN_SUPERAVIT_REVALUACION")
    assert "superávit de revaluación" in msg and "estado de cambios en el patrimonio" in msg
    assert "TRANSFERENCIA_SIN_TRATAMIENTO" in {e["code"] for e in res["exceptions"]}


def test_pymes_16_8_deprecia_desde_que_el_vr_dejo_de_medirse():
    """PYMES 16.8: el importe en libros a la fecha en que el VR dejó de medirse es el nuevo costo y la
    depreciación corre desde esa fecha, no desde la adquisición.

    Sin la fecha (EJEMPLO): IP-07 no se recalcula (M22, se avisa); se usa la depreciación registrada 45.000 →
    neto 300.000 − 45.000 = 255.000; recuperable 230.000 → deterioro 25.000; medición 230.000.
    Con la fecha 30-06-2023 y libros 262.000: base 262.000 − 60.000 = 202.000; de 30-06-2023 a 31-12-2025 hay 30
    meses completos de los 600 de vida (50 años) → dep. 202.000 × 30 ÷ 600 = 10.100; del año = 10.100 −
    202.000 × 18 ÷ 600 = 10.100 − 6.060 = 4.040; neto 262.000 − 10.100 = 251.900; deterioro 251.900 − 230.000 =
    21.900; medición 230.000 (la misma que antes: la topa el importe recuperable).
    """
    par = {**E["parametros"], "_marco": "NIIF para las PYMES", "_edicion": "2025"}
    sin_fecha = _run(parametros=par)
    i7 = _it(sin_fecha, "IP-07")
    assert i7["p16_8"] and i7["desdeDep"] is None and i7["dep"] is None and i7["neto"] == 255000 and i7["det"] == 25000
    assert "SIN_FECHA_FIN_VR" in {e["code"] for e in sin_fecha["exceptions"]}
    con_fecha = m.ejecutar(m._PYMES_16_8, par, E["corte"])
    j7 = _it(con_fecha, "IP-07")
    assert j7["costoDep"] == 262000 and j7["desdeDep"] == "2023-06-30" and j7["meses"] == 30
    assert j7["base"] == 202000 and j7["dep"] == 10100 and j7["depAnio"] == 4040
    assert j7["neto"] == 251900 and j7["det"] == 21900 and j7["medCosto"] == 230000
    assert "SIN_FECHA_FIN_VR" not in {e["code"] for e in con_fecha["exceptions"]}
    # En NIIF completas la regla no aplica: se sigue depreciando desde la adquisición (120 meses, dep. 48.000).
    comp = _run({**E["datasets"]}, {**E["parametros"], "_marco": "NIIF completas"})
    assert not _it(comp, "IP-07")["p16_8"] and _it(comp, "IP-07")["dep"] == 48000


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
