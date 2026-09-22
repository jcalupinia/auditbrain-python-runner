"""Procesador patrimonio: ejemplo de control recalculado a mano, rutas por marco y casos límite."""
import pytest

from backend.app.aud.niif.procesadores import patrimonio as m

EJ = m.EJEMPLO


def _run(ds=None, **param):
    return m.ejecutar(ds or EJ["datasets"], {**EJ["parametros"], **param}, EJ["corte"])


def _codigos(res):
    return {e["code"] for e in res["exceptions"]}


def test_ejemplo_niif_completas_cifras_a_mano():
    r = _run()
    t = r["totals"]
    # 500.000 + 30.000 + 68.000 + 25.000 + 15.000 + 130.000 + 142.000 − 20.000 + 45.000
    assert t["patrimonioCliente"] == "935000.00"
    # −30.000 (aporte reembolsable) − 45.000 (acciones rescatables) + 50.000 (dividendo feb-2026 como pasivo)
    assert t["ajusteNeto"] == "-25000.00" and t["patrimonioAuditado"] == "910000.00" and r["primary"] == "ajusteNeto"
    assert t["difMovimiento"] == "500.00"                 # ORI 12.000 + 3.500 = 15.500 vs 15.000
    assert t["saldoMayor"] == "936200.00" and t["difMayor"] == "-1200.00"
    # 128.000 × 10 % = 12.800 ≤ 500.000 × 50 % − 60.000 = 190.000; apropiada 8.000
    assert t["reservaRequerida"] == "12800.00" and t["ajusteReserva"] == "4800.00"
    assert t["dividendosDeclarados"] == "90000.00" and t["excesoDividendos"] == "10000.00"   # disponibles 80.000 (auditor)
    assert r["detalle"]["div"]["calc"] == 265200          # 150.000 + 128.000 − 12.800
    assert t["aumentosNoInscritos"] == "40000.00" and t["difCapital"] == "40000.00"
    assert t["resultadoRecompras"] == "-1500.00"
    c = _codigos(r)
    for k in ("MOVIMIENTO_NO_CUADRA", "DIF_MAYOR", "RESERVA_LEGAL_NO_APROPIADA", "DIVIDENDOS_SOBRE_UTILIDADES_NO_DISPONIBLES",
              "DIVIDENDO_POSTERIOR_COMO_PASIVO", "DIVIDENDO_POSTERIOR_REVELAR", "CAPITAL_NO_COINCIDE_ESCRITURA", "AUMENTO_NO_INSCRITO",
              "APORTE_ES_PASIVO", "INSTRUMENTO_MAL_CLASIFICADO", "RECOMPRA_CON_RESULTADO", "SIN_ACTA"):
        assert k in c


def test_ruta_pymes_mismo_calculo_otras_citas():
    base, pymes = _run(), _run(_marco=m.MARCO_PYMES, _edicion="2025")
    assert base["totals"] == pymes["totals"]
    msg = lambda r, k: next(e["message"] for e in r["exceptions"] if e["code"] == k)
    assert "PYMES 22.16" in msg(pymes, "RECOMPRA_CON_RESULTADO") and "NIC 32 33" in msg(base, "RECOMPRA_CON_RESULTADO")
    assert "PYMES 32.8" in msg(pymes, "DIVIDENDO_POSTERIOR_COMO_PASIVO") and "NIC 10" in msg(base, "DIVIDENDO_POSTERIOR_COMO_PASIVO")
    assert pymes["detalle"]["edicion"] == "2025"


def test_limitada_por_defecto_sin_transacciones_ni_mayor():
    esc = next(e for e in m.ESCENARIOS if e[0] == "pymes_2025_limitada")
    r = m.ejecutar(esc[1], esc[2], esc[3])
    t = r["totals"]
    # 128.000 × 5 % = 6.400 ≤ 500.000 × 20 % − 60.000 = 40.000; apropiada 8.000 → exceso 1.600
    assert t["reservaRequerida"] == "6400.00" and t["ajusteReserva"] == "-1600.00"
    assert t["utilidadesDisponibles"] == "271600.00"      # 150.000 + 128.000 − 6.400
    assert "saldoMayor" not in t and "capitalEscritura" not in t
    assert {"RESERVA_LEGAL_EN_EXCESO", "SIN_SALDO_MAYOR", "SIN_CAPITAL_ESCRITURA", "SIN_TRANSACCIONES"} <= _codigos(r)


def test_perdida_no_exige_reserva_y_disponibles_calculadas():
    r = _run(utilidadNeta=-5000, utilidadesDisponibles=None)
    assert r["totals"]["reservaRequerida"] == "0.00" and r["totals"]["ajusteReserva"] == "-8000.00"
    assert r["totals"]["utilidadesDisponibles"] == "278000.00" and r["totals"]["excesoDividendos"] == "0.00"


def test_tope_limita_la_reserva_y_sin_base():
    r = _run(utilidadNeta=3000000)                       # 300.000 > margen 190.000
    assert r["totals"]["reservaRequerida"] == "190000.00"
    sin_re = {"movimientos": [f for f in EJ["datasets"]["movimientos"] if f["clase"] != "Resultado del ejercicio"],
              "transacciones": EJ["datasets"]["transacciones"]}
    r = _run(sin_re)
    assert "reservaRequerida" not in r["totals"] and "RESERVA_SIN_BASE" in _codigos(r)


def test_recompra_no_deducida():
    tx = [{"id": "R1", "fecha": "2025-05-01", "tipo": "Recompra", "importe": "1000", "acta": "Sí", "cuenta": "Resultados acumulados", "_row": 2}]
    r = _run({"movimientos": EJ["datasets"]["movimientos"], "transacciones": tx})
    assert "RECOMPRA_NO_DEDUCIDA" in _codigos(r) and "RECOMPRA_CON_RESULTADO" not in _codigos(r)


def test_casos_limite():
    with pytest.raises(ValueError):
        m.ejecutar({"movimientos": []}, {}, "2025-12-31")
    with pytest.raises(ValueError):
        m.ejecutar(EJ["datasets"], {}, "")
    with pytest.raises(ValueError):
        _run(pctReserva=120)
    with pytest.raises(ValueError):
        _run(tipoCompania="Colectiva")
    with pytest.raises(ValueError):
        _run(capitalEscritura=-1)
    neg = {"movimientos": [{**EJ["datasets"]["movimientos"][0], "aumentos": "-5"}]}
    with pytest.raises(ValueError):
        _run(neg)
    malo = {**EJ["datasets"], "transacciones": [{"id": "X", "fecha": "2025-05-01", "tipo": "Aporte", "importe": "10", "devolucion": "quizás", "_row": 2}]}
    with pytest.raises(ValueError):
        _run(malo)
    v = m.validar_filas("transacciones", [{"id": "X", "fecha": "x", "tipo": "Donación", "importe": "abc", "acta": "tal vez", "_row": 2}])
    assert not v["ok"] and len(v["errors"]) == 4
    v = m.validar_filas("movimientos", [{"id": "TOTAL", "cuenta": "A", "inicial": "1", "final": "1", "_row": 3}])
    assert not v["ok"]


def test_hojas_nombres_y_anchos():
    for _, ds, p, c in m.ESCENARIOS:
        hs = m.hojas(m.ejecutar(ds, p, c))
        assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
        for h in hs:
            for fila in h["rows"] + ([h["total"]] if h["total"] else []):
                assert len(fila) == len(h["cols"]), h["name"]


def test_definicion():
    d = m.validar_definicion(m.definicion())
    assert d["processor"] == "patrimonio" and len(d["program"]) >= 5
    assert m.RUBRO == "PATRIMONIO" and len(d["requests"]) >= 2
