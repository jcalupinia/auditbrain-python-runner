"""Efectivo y equivalentes de efectivo: ejemplo de la ficha recalculado a mano y casos límite."""
import copy

import pytest

from backend.app.aud.niif.procesadores import efectivo_equivalentes as m

E = m.EJEMPLO


def _run(datasets=None, parametros=None, corte=None):
    return m.ejecutar(datasets or E["datasets"], {**E["parametros"], **(parametros or {})}, corte or E["corte"])


def _codigos(r):
    return [x["code"] for x in r["exceptions"]]


def test_ejemplo_cifras_a_mano():
    r = _run()
    t = r["totals"]
    # Libros: 500 + 300 + 125.680,50 + 47.700 + 22.000 + 1.650 − 3.200 + 50.000 + 30.000
    assert t["saldoLibros"] == "274630.50"
    assert t["notas"] == "180.00"                        # NC 300 − ND 120
    # Solo se reclasifica la restricción no corriente: 10.000 de Guayaquil (fin 2027-06-30 >= EDATE(corte;12) =
    # 2026-12-31). El embargo del Internacional (1.650) no tiene fecha de fin: se revela y NO se reclasifica (NIC 7.48).
    assert t["reclasRestringido"] == "10000.00"
    # Certificado Produbanco: vence 2026-03-30 > EDATE(2025-10-01;3) = 2026-01-01 → no cumple el plazo de tres meses.
    assert t["reclasNoEquivalentes"] == "30000.00"
    assert t["auditado"] == "234810.50"                   # 274.630,50 + 180 − 10.000 − 30.000
    assert t["ajuste"] == "-39820.00"                     # 234.810,50 − 274.630,50
    assert t["difNoExplicada"] == "550.00"                # Guayaquil: 47.700 − (45.900 + 2.100 − 300 − 550)
    assert t["difConfirmacion"] == "500.00"               # Produbanco 21.500 vs 22.000
    assert t["partidasAntiguas"] == "2300.00"             # P-03 1.850 (138 días) + P-09 450 (112 días)
    assert r["primary"] == "ajuste"
    cu = {c["id"]: c for c in r["detalle"]["cuentas"]}
    assert cu["1.1.02.01"]["dif"] == 0 and cu["1.1.02.01"]["ajustado"] == pytest.approx(125860.50)
    assert cu["1.1.02.02"]["clasif"] == "No corriente"    # fin 2027-06-30 >= 2026-12-31
    assert cu["1.1.02.04"]["reclasR"] == 0 and cu["1.1.02.04"]["auditado"] == 1650   # embargo sin fecha: se revela, no se reclasifica
    # Póliza: adq 2025-11-15, EDATE(+3) = 2026-02-15; vence 2026-01-14 → cumple el plazo (presunción).
    assert cu["1.1.03.01"]["califica"] == "Sí" and cu["1.1.03.01"]["limite"] == "2026-02-15"
    assert r["detalle"]["conceptos"]["reclasNoCorriente"] == 10000
    c = _codigos(r)
    for code in ("DIFERENCIA_NO_EXPLICADA", "PARTIDA_ANTIGUA", "CONFIRMACION_NO_COINCIDE", "RESTRINGIDO_COMO_DISPONIBLE",
                 "NO_ES_EQUIVALENTE", "CORTE_DEPOSITO_TARDIO", "CORTE_POSTERIOR", "SIN_CONFIRMACION", "SALDO_ACREEDOR",
                 "RESTRINGIDO_REVELAR", "RESTRICCION_SIN_FECHA", "EQUIVALENTE_PRESUNCION"):
        assert code in c, code


def test_hojas_nombres_y_anchos():
    r = _run()
    h = m.hojas(r)
    assert [x["name"] for x in h] == [n for n, _ in m.CEDULAS]
    for x in h:
        assert len(x["name"]) <= 31
        for fila in x["rows"] + ([x["total"]] if x["total"] else []):
            assert len(fila) == len(x["cols"]), x["name"]
    assert sum(isinstance(c, dict) for x in h for f in x["rows"] for c in f) > 100


def test_anexo_vacio():
    with pytest.raises(ValueError):
        m.ejecutar({"cuentas": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(E["datasets"], {}, "")


def test_sin_partidas_y_faltantes():
    d = {"cuentas": [{"id": "B1", "nombre": "Banco", "tipo": "Banco", "saldo_libros": "100", "saldo_banco": "", "_row": 2}]}
    r = m.ejecutar(d, {}, "2025-12-31")
    cu = r["detalle"]["cuentas"][0]
    assert cu["esperado"] is None and cu["dif"] is None        # no se mide: vacío, no cero (M22)
    assert {"SIN_ESTADO_BANCARIO", "SIN_CONFIRMACION"} <= set(_codigos(r))
    assert r["totals"]["auditado"] == "100.00"
    m.hojas(r)


def test_ya_presentado_aparte_no_se_reclasifica():
    d = copy.deepcopy(E["datasets"])
    for c in d["cuentas"]:
        if c["id"] == "1.1.02.02":
            c["presentado_separado"] = "Sí"
    r = _run(d)
    assert r["totals"]["reclasRestringido"] == "0.00"      # Guayaquil ya aparte; el embargo sin fecha nunca se reclasificaba


def test_ruta_por_marco():
    comp = _run(parametros={"_marco": "NIIF completas"})
    p15 = _run(parametros={"_marco": "NIIF para las PYMES", "_edicion": "2015"})
    p25 = _run(parametros={"_marco": "NIIF para las PYMES", "_edicion": "2025"})
    assert comp["totals"] == p15["totals"] == p25["totals"]    # mismo cálculo; cambian las referencias
    assert comp["detalle"]["refs"]["restr"].startswith("NIC 7.48")
    assert p15["detalle"]["refs"]["restr"].startswith("Secciones 7.21")
    assert p25["detalle"]["refs"]["def"] == "Sección 7.2"


def test_parametros():
    with pytest.raises(ValueError):
        _run(parametros={"diasAntiguedad": 0})
    with pytest.raises(ValueError):
        _run(parametros={"tolerancia": -1})
    with pytest.raises(ValueError):
        _run(parametros={"mesesRestriccion": 1.5})
    with pytest.raises(ValueError):
        _run(parametros={"mesesEquivalente": 0})
    r = _run(parametros={"tolerancia": 1000, "mesesRestriccion": 24})
    assert "DIFERENCIA_NO_EXPLICADA" not in _codigos(r) and "CONFIRMACION_NO_COINCIDE" not in _codigos(r)
    cu = {c["id"]: c for c in r["detalle"]["cuentas"]}
    assert cu["1.1.02.02"]["clasif"] == "Corriente"        # fin 2027-06-30 < EDATE(corte;24) = 2027-12-31
    assert cu["1.1.02.02"]["reclasR"] == 0 and r["totals"]["reclasRestringido"] == "0.00"


def test_validar_filas():
    v = m.validar_filas("partidas", [
        {"id": "1", "cuenta": "B1", "tipo": "Cheque pendiente", "fecha_origen": "2025-12-01", "importe": "-5", "_row": 2},
        {"id": "2", "cuenta": "B1", "tipo": "Rarísimo", "fecha_origen": "2025-12-01", "importe": "5", "_row": 3},
        {"id": "3", "cuenta": "B1", "tipo": "Otra", "fecha_origen": "2025-12-01", "importe": "-5", "_row": 4},
    ])
    assert {e["row"] for e in v["errors"]} == {2, 3}
    v = m.validar_filas("cuentas", [{"id": "B1", "nombre": "X", "tipo": "Cohete", "saldo_libros": "1", "restringido": "tal vez", "_row": 2}])
    assert {e["field"] for e in v["errors"]} == {"tipo", "restringido"}
    assert m.validar_filas("cuentas", E["datasets"]["cuentas"])["ok"]
    assert m.validar_filas("partidas", E["datasets"]["partidas"])["ok"]


def test_partida_sin_cuenta_y_otra():
    d = copy.deepcopy(E["datasets"])
    d["partidas"].append({"id": "P-99", "cuenta": "9.9", "tipo": "Otra partida", "fecha_origen": "2025-12-15", "importe": "-10",
                          "fecha_liquidacion": "2026-01-02", "_row": 12})
    r = _run(d)
    assert {"PARTIDA_SIN_CUENTA", "OTRA_PARTIDA"} <= set(_codigos(r))
    assert r["totals"]["auditado"] == "234810.50"            # la partida huérfana no toca ninguna cuenta


def test_definicion():
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "efectivo_equivalentes" and len(d["program"]) >= 5
    assert m.RUBRO == "CAJA_BANCOS" and m.TOTAL_EJEMPLO in _run()["totals"]


def test_bordes_tres_meses_y_al_menos_doce_meses():
    """NIC 7.7 se mide con EDATE(adquisición;3), no con 90 días; NIC 1.66 d) dice «al menos» doce meses."""
    d = {"cuentas": [
        # 92 días corridos, pero exactamente tres meses: EDATE(2025-10-31;3) = 2026-01-31 → sí cumple el plazo.
        {"id": "I1", "nombre": "Póliza 3 meses", "tipo": "Inversión", "saldo_libros": "1000", "saldo_banco": "1000",
         "saldo_confirmado": "1000", "fecha_adquisicion": "2025-10-31", "fecha_vencimiento": "2026-01-31", "_row": 2},
        # Restricción que termina exactamente en corte + 12 meses → no corriente (al menos doce meses).
        {"id": "B1", "nombre": "Banco pignorado", "tipo": "Banco", "saldo_libros": "5000", "saldo_banco": "5000",
         "saldo_confirmado": "5000", "restringido": "Sí", "monto_restringido": "5000", "fin_restriccion": "2026-12-31", "_row": 3},
    ]}
    r = m.ejecutar(d, m.EJEMPLO["parametros"], "2025-12-31")
    cu = {c["id"]: c for c in r["detalle"]["cuentas"]}
    assert cu["I1"]["plazo"] == 92 and cu["I1"]["califica"] == "Sí"
    assert cu["B1"]["clasif"] == "No corriente" and cu["B1"]["reclasR"] == 5000
    assert r["totals"]["reclasNoEquivalentes"] == "0.00" and r["totals"]["reclasRestringido"] == "5000.00"
