"""Procesador de pérdidas incurridas (NIIF PYMES Sección 11): ejemplo numérico de la ficha CXC-PI-01 (E.6)."""
from backend.app.aud.niif.procesadores import perdidas_incurridas_s11 as pi


def fila(id, cliente, emision, vence, saldo):
    return {"id": id, "cliente": cliente, "emision": emision, "vence": vence, "saldo": saldo, "_row": 2}


A2 = [fila("F-1", "A", "2024-07-01", "2024-08-15", "1000"), fila("F-2", "B", "2024-12-15", "2025-01-14", "500")]
A3 = [fila("F-1", "A", "2024-07-01", "2024-08-15", "400"), fila("F-3", "C", "2025-07-01", "2025-08-15", "2.000,00")]


def correr(**extra):
    datos = {"a2": A2, "a3": A3, **extra.pop("datos", {})}
    return pi.ejecutar(datos, extra, "2025-12-31")


def test_ejemplo_de_la_ficha():
    r = correr()
    tasas = {t["k"]: t["tasa"] for t in r["detalle"]["tasas"]}
    assert tasas["t180"] == 0.4          # 400 ÷ 1.000
    assert tasas["pv"] == 0              # 11.22: corriente sin evento de pérdida
    assert tasas["t730"] is None         # sin historia ni saldos > 730 días: no medible
    f3 = next(f for f in r["rows"] if f["id"] == "F-3")
    assert f3["tramo"] == "91 a 180 días" and f3["perdida"] == "800.00"
    assert r["totals"]["perdida"] == "800.00"
    assert any(e["code"] == "TRAMO_NO_MEDIBLE" for e in r["exceptions"])


def test_tasa_fijada_por_el_auditor_y_descuento():
    r = correr(tasas={"t730": 100}, tasaDesc=10)
    f1 = next(f for f in r["rows"] if f["id"] == "F-1")
    assert f1["perdida"] == "400.00"      # tasa 100 %: se pierde todo el saldo
    f3 = next(f for f in r["rows"] if f["id"] == "F-3")
    assert f3["perdida"] == pi.r2(2000 - 1200 / 1.1)


def test_fiscal_movimiento_y_bajas():
    mov = [{"id": "2024", "inicial": "0", "gasto": "300", "castigos": "0", "recuperaciones": "0"},
           {"id": "2025", "gasto": "0", "castigos": "0", "recuperaciones": "0"}]
    prov = [{"id": "F-1", "cliente": "A", "provision": "200"}, {"id": "F-9", "cliente": "Z", "provision": "100", "diferido": "25"}]
    r = correr(datos={"movimiento": mov, "provision": prov})
    f = r["detalle"]["fiscal"]
    assert f["provAnt"] == 300 and f["gastoEjercicio"] == 500
    assert f["limite1"] == 0             # sin cartera corriente, el 1 % es cero
    assert r["totals"]["noDeducible"] == "500.00"
    assert r["totals"]["bajas"] == "100.00"          # F-9 ya no está en la cartera y su cliente tampoco
    assert r["totals"]["ajuste"] == "500.00"          # 800 recalculado − 300 del mayor
    assert r["detalle"]["movimientoTotales"]["reversion"] == 200


def test_validacion_y_lectura_regional():
    assert pi.a_num("(1.250,50)") == -1250.5 and pi.a_num("1,250.50") == 1250.5
    v = pi.validar_filas("cartera", [fila("F-1", "A", "2025-01-01", "x", "10"), fila("TOTAL", "", "", "", "")])
    assert not v["ok"] and any("fecha inválida" in e["message"] for e in v["errors"])


def test_cedulas_declaradas_son_las_que_se_calculan():
    hojas = pi.hojas(correr())
    nombres = [(h["name"], h["label"]) for h in hojas]
    # Las 12 cédulas de cálculo siempre; las de datos del cliente según los anexos entregados (en su orden).
    assert nombres[:12] == pi.CEDULAS[:12] and nombres == [c for c in pi.CEDULAS if c in nombres]
    for h in hojas:
        assert all(len(f) == len(h["cols"]) for f in h["rows"] + ([h["total"]] if h["total"] else [])), h["name"]


def test_el_ejemplo_del_modulo_es_el_de_la_ficha():
    r = pi.ejecutar(pi.EJEMPLO["datasets"], {}, pi.EJEMPLO["corte"])
    assert r["totals"]["perdida"] == "800.00"
