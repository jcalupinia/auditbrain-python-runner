"""Inversiones e instrumentos financieros: ejemplo de la ficha con cifras recalculadas a mano, rutas por marco y límites."""
import copy

import pytest

from backend.app.aud.niif.procesadores import inversiones_instrumentos as m

PYMES_2015 = {"_marco": "NIIF para las PYMES", "_edicion": "2015"}
PYMES_2025 = {"_marco": "NIIF para las PYMES", "_edicion": "2025"}


def correr(datasets=None, **param):
    return m.ejecutar(datasets or m.EJEMPLO["datasets"], {**m.EJEMPLO["parametros"], **param}, m.EJEMPLO["corte"])


def inst(r, i):
    return next(x for x in r["detalle"]["instrumentos"] if x["id"] == i)


def codigos(r, i=None):
    return {e["code"] for e in r["exceptions"] if i is None or e["message"].startswith(i + ":")}


def test_ejemplo_niif_completas_a_mano():
    r = correr()
    cdp = inst(r, "CDP-02")                         # a la par: TIE = cupón
    assert cdp["ca"]["r"] == pytest.approx(0.06, abs=1e-12)
    assert cdp["ca"]["limpio"] == pytest.approx(50000)
    assert cdp["ingEsp"] == pytest.approx(50000 * 0.06 * 169 / 365)          # 1.389,04 devengado, nada registrado
    pag = inst(r, "PAG-07")                         # vida entera: 25.000 × (1 + 5 % × 92/181) × 60 % × 50 %
    assert pag["detCalc"] == pytest.approx(25000 * (1 + 0.05 * 92 / 181) * 0.60 * 0.50)
    assert pag["enfoque"] == "Vida entera (5.5.3)"
    assert inst(r, "ACC-04")["difVR"] == pytest.approx(3000)                # 45.000 − 42.000 a resultados
    assert inst(r, "OBL-10")["detCalc"] == pytest.approx(20000 * 0.015 * 0.45)   # 135 en ORI (5.5.2)
    b1 = inst(r, "BONO-01")                          # descuento: el VA de los 10 flujos a la TIE es el costo
    c = b1["ca"]
    assert c["n"] == 10 and c["c"] == pytest.approx(4000)
    assert m._pv(c["r"], 10, 4000, 100000) == pytest.approx(96000, abs=1e-6)
    assert c["interes"] == pytest.approx(c["sucio"] - c["ini"] + 4000 * 2)   # dos cupones cobrados en 2025
    assert r["totals"]["ajuste"] == "-1318.65"
    assert r["totals"]["difVR"] == "3300.00"                                  # 3.000 + 500 − 1.000 + 800
    assert r["totals"]["saldoLibros"] == "326400.00"
    todos = codigos(r)
    for code in ("CLASIFICACION_INCONSISTENTE", "DIFERENCIA_COSTO_AMORTIZADO", "INTERES_NO_REGISTRADO", "VR_SIN_NIVEL",
                 "DIFERENCIA_VR", "INDICIO_DETERIORO", "RECLASIFICACION_NO_PERMITIDA", "DIVIDENDO_NO_REGISTRADO", "INSTRUMENTO_VENCIDO"):
        assert code in todos, code


def test_clasificacion_niif_completas():
    r = correr()
    esp = {x["id"]: x["esperada"] for x in r["detalle"]["instrumentos"]}
    assert esp["OBL-03"] == "VRORI" and "CLASIFICACION_INCONSISTENTE" in codigos(r, "OBL-03")   # cobrar y vender
    assert esp["BONO-08"] == "VRR" and "CLASIFICACION_INCONSISTENTE" in codigos(r, "BONO-08")   # no SPPI
    assert esp["ACC-05"] == "VRORI" and inst(r, "ACC-05")["consistente"] == "Sí"             # elección 5.7.5
    assert inst(r, "ACC-05")["enfoque"] == "No aplica"                                        # patrimonio sin deterioro
    assert inst(r, "OBL-10")["permitido"].startswith("No")                                    # 4.4.1


@pytest.mark.parametrize("param", [PYMES_2015, PYMES_2025])
def test_ruta_pymes_sin_ori_y_perdida_incurrida(param):
    r = correr(**param)
    assert inst(r, "ACC-05")["esperada"] == "VRR"                     # PYMES no tiene VR con cambios en ORI
    assert "CLASIFICACION_INCONSISTENTE" in codigos(r, "ACC-05")
    assert inst(r, "OBL-03")["esperada"] == "CA"                      # PYMES no clasifica por modelo de negocio
    assert inst(r, "OBL-10")["esperada"] == "CA"
    assert inst(r, "BONO-01")["detCalc"] == 0                         # sin evidencia objetiva no hay pérdida (11.21)
    pag = inst(r, "PAG-07")                                           # 11.25 a: importe en libros × % no recuperable
    assert pag["detCalc"] == pytest.approx(25000 * (1 + 0.05 * 92 / 181) * 0.50)
    assert r["totals"]["ajuste"] == "-5159.35"   # 522,98 + 100 − 132,06 + 3.000 + 500 − 9.817,68 + 800 + 67,40 − 200


def test_limites_vacio_parametro_y_faltantes():
    with pytest.raises(ValueError):
        m.ejecutar({"inversiones": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        correr(frecuenciaDefecto=5)
    with pytest.raises(ValueError):
        m.ejecutar(m.EJEMPLO["datasets"], {}, "")
    ds = copy.deepcopy(m.EJEMPLO["datasets"])
    b = ds["inversiones"][0]
    b["cupon"] = ""                                   # sin cupón no se inventa el costo amortizado (M22)
    b["sppi"] = ""                                    # sin SPPI la clasificación no se determina
    r = correr(ds)
    x = inst(r, "BONO-01")
    assert x["ca"] is None and x["esperada"] == "" and x["ajuste"] is None
    assert "CLASIFICACION_NO_DETERMINABLE" in codigos(r, "BONO-01")
    ds["inversiones"][1]["saldo_libros"] = "(500)"   # saldo negativo se acepta y se mide
    assert inst(correr(ds), "CDP-02")["difMed"] == pytest.approx(50500)


def test_validacion_de_filas():
    v = m.validar_filas("inversiones", [{"id": "X", "emisor": "E", "tipo": "Bono", "clasificacion": "CA", "saldo_libros": "1",
                                         "nivel": "4", "pd": "120", "frecuencia": "5", "_row": 2}])
    assert not v["ok"] and {e["field"] for e in v["errors"]} >= {"nivel", "pd", "frecuencia"}


def test_cedulas_declaradas_y_completas():
    for _, ds, par, corte in m.ESCENARIOS:
        hojas = m.hojas(m.ejecutar(ds, par, corte))
        assert [(h["name"], h["label"]) for h in hojas] == m.CEDULAS
        for h in hojas:
            assert all(len(f) == len(h["cols"]) for f in h["rows"] + ([h["total"]] if h["total"] else [])), h["name"]
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "inversiones_instrumentos" and len(d["program"]) >= 5


def _extra(nombre):
    _, ds, par, corte = next(e for e in m.ESCENARIOS if e[0] == nombre)
    return m.ejecutar(ds, par, corte)


def test_pymes_2025_11_9za_deuda_no_basica_pero_sppi():
    """11.9ZA: sin cumplir 11.9 a)-d), la deuda con flujos solo de principal e intereses sigue a costo amortizado."""
    r25, r15 = _extra("pymes_2025_11_9za_y_11_25b"), _extra("pymes_2015_11_9za_y_11_25b")
    x25, x15 = inst(r25, "OBL-12"), inst(r15, "OBL-12")
    assert x25["esperada"] == "CA" and x15["esperada"] == "VRR"      # 2015 solo mira 11.9 a)-d)
    assert x25["ca"]["r"] == pytest.approx(0.08, abs=1e-12)          # a la par: TIE = cupón
    assert x25["ca"]["limpio"] == pytest.approx(10000)
    assert x25["ingEsp"] == pytest.approx(10000 * 0.08 * 334 / 365)  # 732,05 del 31-ene al 31-dic
    assert "11.9ZA" in x25["fundamento"] and "11.9ZA" not in x15["fundamento"]
    assert x25["difMed"] == pytest.approx(0) and x25["ajuste"] == pytest.approx(0)


def test_pymes_11_25b_usa_la_estimacion_de_venta():
    """11.25 b): pérdida = importe en libros − mejor estimación de lo que se recibiría si se vendiera al cierre."""
    r = _extra("pymes_2025_11_9za_y_11_25b")
    a13 = inst(r, "ACC-13")
    assert a13["esperada"] == "COSTO" and a13["enfoque"] == "Pérdida incurrida (11.25 b)"
    assert a13["detCalc"] == pytest.approx(2000)      # 9.000 de costo − 7.000 de estimación de venta
    assert a13["ajuste"] == pytest.approx(-1500)      # 0 de diferencia de medición − (2.000 − 500 registrados)
    a14 = inst(r, "ACC-14")                           # sin estimación de venta no se inventa un 0 (M22)
    assert a14["detCalc"] is None and a14["ajuste"] is None
    assert "DETERIORO_SIN_DATOS" in codigos(r, "ACC-14")
    assert "SIN_MEDICION" in codigos(r)
    assert r["totals"]["ajuste"] == "-6659.35"        # −5.159,35 del ejercicio modelo − 1.500 de ACC-13
