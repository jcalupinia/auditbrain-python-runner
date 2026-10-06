"""Prueba del procesador de PCE por cohortes (AUD-ECL-01), sin base de datos.

Cifras del ejercicio modelo recalculadas a mano (ver el docstring de ``EJEMPLO``):
cohorte «181 a 360 días» con tasa 15 % (terceros) y 100 % (relacionadas); al corte,
un crédito nuevo de 5.000 en esa banda ⇒ PCE 750; cartera anclada 11.300; provisión
1.000 ⇒ ajuste −250.
"""
import pytest

from backend.app.aud.niif.procesadores import pce_cohortes_niif9 as m
from backend.app.aud.niif.procesadores import problemas


def _run(params=None):
    p = {**m.EJEMPLO["parametros"], **(params or {})}
    return m.ejecutar(m.EJEMPLO["datasets"], p, m.EJEMPLO["corte"])


def test_cifras_del_ejemplo_recalculadas_a_mano():
    r = _run()
    assert r["totals"]["pce"] == "750.00"
    assert r["totals"]["cartera"] == "11300.00"
    assert r["totals"]["provisionRegistrada"] == "1000.00"
    assert r["totals"]["ajuste"] == "-250.00"
    assert r["primary"] == "ajuste"


def test_tasas_por_cohorte_ventana_24_meses():
    d = _run()["detalle"]
    tasas = {mm["clave"]: mm["tasaObs"] for mm in d["matriz"] if mm["tasaObs"] is not None}
    assert tasas["NO-RELACIONADOS|181 a 360 días"] == pytest.approx(0.15)
    assert tasas["RELACIONADOS|181 a 360 días"] == pytest.approx(1.0)
    # cohorte t-2 = 2 años antes del corte
    assert d["cortes"] == {"t": "2025-12-31", "t1": "2024-12-31", "t2": "2023-12-31"}


def test_anclaje_a_eeff_por_segmento():
    # EEFF = archivo por segmento ⇒ factor 1; la suma anclada = suma del archivo
    d = _run()["detalle"]
    assert d["anchor"] is True
    assert d["factorAnclaje"]["NO-RELACIONADOS"] == pytest.approx(1.0)
    # anclaje que reduce la exposición a la mitad
    d2 = _run({"eNR_t": 4650, "eR_t": 1000})["detalle"]
    assert d2["factorAnclaje"]["NO-RELACIONADOS"] == pytest.approx(0.5)
    assert d2["totExp"] == pytest.approx(11300 / 2)


def test_desdoblamiento_de_la_banda_abierta():
    d = _run({"desdoblar": "Sí", "umbral": 730})["detalle"]
    assert d["bn"][-2:] == ["361 d — 2 años", "Más de 2 años"]
    d2 = _run({"desdoblar": "No"})["detalle"]
    assert d2["bn"][-1] == "Más de 360 días"


def test_hallazgos_ccceer_del_ejemplo():
    codes = {e["code"] for e in _run()["exceptions"]}
    # el ejemplo (provisión estática, sin movimiento en los mayores) dispara varios hallazgos y avisos
    assert {"H-PROSPECTIVO", "H-CARTERA-ANTIGUA", "H-SEGMENTACION", "H-PROV-ESTATICA",
            "W-SIN-DATOS", "AJUSTE"} <= codes


def test_validacion_del_metodo_contra_castigos():
    # castigos materiales (≥ 5 % de la cohorte) en el mayor del ejercicio t ⇒ aviso
    ds = {**m.EJEMPLO["datasets"],
          "mayor_t": [{"concepto": "Castigo de cartera", "constitucion": "", "reversion": "", "castigos": "2000"}]}
    r = m.ejecutar(ds, m.EJEMPLO["parametros"], m.EJEMPLO["corte"])   # cohorte base = 4000 ⇒ 50 %
    assert any(e["code"] == "W-CASTIGOS-MATERIALES" for e in r["exceptions"])
    assert r["detalle"]["tasaCastigo"] == pytest.approx(0.5)


def test_movimiento_opcional_sin_mayores_no_hay_movimiento():
    # Sin mayores cargados, el movimiento es cero y la provisión no cambia (decisión del dueño).
    d = _run()["detalle"]
    assert d["cargoAcum"] == 0 and d["revAcum"] == 0 and d["castAcum"] == 0
    assert d["finMov"] == d["provIni"]


def test_anexo_inicial_es_una_sumaria():
    # El anexo inicial replica una sumaria: código, descripción, saldo anterior y actual.
    d = _run()["detalle"]
    assert d["provSumaria"] and set(d["provSumaria"][0]) >= {"codigo", "descripcion", "anterior", "actual"}
    assert d["provIni"] == pytest.approx(1000) and d["provReg"] == pytest.approx(1000)


def test_dias_de_credito_y_politica_promedio():
    # Cada factura trae facturación; los días de crédito dan una política promedio (simple) observada.
    d = _run()["detalle"]
    assert d["polObs"] == 91 and d["imputados"] == 0 and d["polCredito"] is None
    # la columna «Días de crédito» del detalle sale por fórmula (vencimiento − facturación)
    hs = m.hojas(_run())
    det = next(h for h in hs if h["name"] == "12_Detalle")
    cols = [c[0] for c in det["cols"]]
    assert "Fecha de facturación" in cols and "Días de crédito" in cols
    j = cols.index("Días de crédito")
    assert det["rows"][0][j]["v"] == 91


def test_imputa_vencimiento_con_la_politica_de_credito():
    # Una factura sin fecha de vencimiento: se imputa vencimiento = facturación + política de crédito.
    ds = {**m.EJEMPLO["datasets"]}
    ds["cartera_t"] = [*m.EJEMPLO["datasets"]["cartera_t"][:3],
                       {"id": "G2", "cliente": "Cliente F", "tipo": "NO-RELACIONADO",
                        "factura": "2025-09-15", "vence": "", "saldo": "4000", "_row": 2}]
    r = m.ejecutar(ds, m.EJEMPLO["parametros"], m.EJEMPLO["corte"])
    assert r["detalle"]["imputados"] == 1
    assert any(e["code"] == "W-VENCIMIENTO-IMPUTADO" for e in r["exceptions"])
    g2 = next(f for f in r["rows"] if f["id"] == "G2")
    assert g2["vence"] == "2025-12-15" and g2["vencImputado"] is True  # 2025-09-15 + 91 días
    # el resultado no cambia (misma banda que con el vencimiento real)
    assert r["totals"]["pce"] == "750.00"


def test_politica_declarada_manda_sobre_la_observada():
    # Si el auditor declara una política de crédito por escrito, esa manda para imputar.
    ds = {**m.EJEMPLO["datasets"]}
    ds["cartera_t"] = [*m.EJEMPLO["datasets"]["cartera_t"][:3],
                       {"id": "G2", "cliente": "Cliente F", "tipo": "NO-RELACIONADO",
                        "factura": "2025-10-01", "vence": "", "saldo": "4000", "_row": 2}]
    r = m.ejecutar(ds, {**m.EJEMPLO["parametros"], "polCredito": 30}, m.EJEMPLO["corte"])
    g2 = next(f for f in r["rows"] if f["id"] == "G2")
    assert g2["vence"] == "2025-10-31" and r["detalle"]["polCredito"] == 30  # 2025-10-01 + 30 días


def test_trazabilidad_entre_cortes():
    d = _run()["detalle"]
    assert d["traza"] == pytest.approx(2 / 3)  # D1 y D3 siguen en t; D2 no


def test_bloqueos_de_entrada():
    with pytest.raises(ValueError):
        m.ejecutar(m.EJEMPLO["datasets"], m.EJEMPLO["parametros"], "")
    with pytest.raises(ValueError):
        m.ejecutar({"cartera_t2": [], "cartera_t1": [], "cartera_t": []},
                   m.EJEMPLO["parametros"], m.EJEMPLO["corte"])
    faltan = {k: v for k, v in m.EJEMPLO["datasets"].items() if k != "cartera_t2"}
    with pytest.raises(ValueError):
        m.ejecutar(faltan, m.EJEMPLO["parametros"], m.EJEMPLO["corte"])


def test_hojas_estructura_y_anchos():
    r = _run()
    hs = m.hojas(r)
    assert [h["name"] for h in hs] == [c[0] for c in m.CEDULAS]
    for h in hs:
        w = len(h["cols"])
        for fila in h["rows"]:
            assert len(fila) == w, (h["name"], fila)
        if h.get("total"):
            assert len(h["total"]) == w


def test_problemas_enlazados_sin_pendientes():
    pend = problemas.pendientes_de(m, m.EJEMPLO["datasets"], m.EJEMPLO["parametros"], m.EJEMPLO["corte"])
    assert pend == []


def test_definicion_valida():
    d = m.definicion()
    assert m.validar_definicion(d) is d
    assert d["processor"] == "pce_cohortes_niif9"
    assert [r["dataset"] for r in d["requests"] if r.get("dataset")] == [
        "cartera_t2", "cartera_t1", "cartera_t", "provision", "mayor_t2", "mayor_t1", "mayor_t"]
    assert len(d["program"]) >= 5
