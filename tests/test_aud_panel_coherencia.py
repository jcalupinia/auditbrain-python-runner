"""Coherencia del dashboard (PANEL) con el resultado de cada herramienta NIIF.

El comparativo «registrado vs recalculado» debe medir lo mismo en los dos lados:
su brecha es el ajuste que la herramienta propone (o la parte del ajuste que el
gráfico representa). La dona no presenta como positiva una partida que resta, y
no la esconde en «Otros». Cuando la población es el mismo saldo registrado, la
tarjeta de población muestra cuántas partidas lo componen.
"""
import pytest

from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.procesadores import PROCESADORES, graficos, libro


def _panel(pid):
    mod = PROCESADORES[pid]
    ds, par, corte = em.escenario(mod)
    run = mod.ejecutar(ds, par, corte)
    return graficos.panel(mod, run, mod.hojas(run)), run


def _n(v):
    return float(v)


@pytest.mark.parametrize("pid,clave", [
    ("ingresos_contratos", "ajuste"),            # solo líneas medidas (C-12 sin reconocible queda fuera)
    ("ppe_propiedad_planta", "ajusteDep"),       # solo activos recalculados (EQC-01 no lineal queda fuera)
    ("proveedores_cxp", "ajusteNeto"),
    ("activos_biologicos", "ajuste"),
    ("efectivo_equivalentes", "ajuste"),
    ("impuesto_corriente_diferido", "ajusteResultados"),
    ("patrimonio", "ajusteNeto"),
])
def test_brecha_del_comparativo_es_el_ajuste(pid, clave):
    p, run = _panel(pid)
    brecha = p["recalculado"]["valor"] - p["registrado"]["valor"]
    assert brecha == pytest.approx(_n(run["totals"][clave]), abs=0.01), (pid, brecha, run["totals"][clave])


def test_nomina_compara_solo_pasivos_laborales():
    p, run = _panel("nomina_beneficios")
    conceptos = [e for e, _ in p["composicion"]["items"]]
    assert not any(c.startswith(("Remuneraciones", "Aporte patronal")) for c in conceptos), conceptos
    brecha = p["recalculado"]["valor"] - p["registrado"]["valor"]
    # La brecha = ajuste + provisiones sin registro informado (se reportan como problema, no se ajustan).
    sin_informar = sum(_n(e["amount"]) for e in run["exceptions"]
                       if e["code"] == "VACACIONES_NO_PROVISIONADAS" and "no informada" in e["message"])
    assert brecha == pytest.approx(_n(run["totals"]["ajustePasivos"]) + sin_informar, abs=0.01)


def test_gastos_compara_con_lo_llevado_a_gasto_no_con_lo_facturado():
    p, run = _panel("gastos_analisis")
    brecha = p["recalculado"]["valor"] - p["registrado"]["valor"]
    # Devengado − registrado = devengado no registrado − anticipado llevado a resultados.
    esperado = _n(run["totals"]["devengadoNoRegistrado"]) - _n(run["totals"]["anticipado"])
    assert brecha == pytest.approx(esperado, abs=0.01)


def test_impuesto_dona_corriente_mas_diferido_y_barras_con_nombres():
    p, run = _panel("impuesto_corriente_diferido")
    assert dict(p["composicion"]["items"]) == pytest.approx({
        "Impuesto corriente": _n(run["totals"]["impuestoCorrienteAuditado"]),
        "Impuesto diferido": _n(run["totals"]["gastoDiferidoRequerido"])})
    assert sum(v for _, v in p["composicion"]["items"]) == pytest.approx(_n(run["totals"]["gastoTotalRequerido"]))
    etiquetas = [e for e, _ in p["distribucion"]["items"]]
    assert not any(e.isidentifier() and e.islower() for e in etiquetas), etiquetas  # nada de «utilidad», «perdidas»


def test_dona_marca_lo_que_resta_y_no_lo_esconde_en_otros():
    p, _ = _panel("patrimonio")
    items = dict(p["composicion"]["items"])
    assert "(−) Acciones propias" in items and items["(−) Acciones propias"] == pytest.approx(20000)
    # Serie sintética: muchas partidas y una negativa pequeña que caería en «Otros».
    h = {"name": "X", "cols": [["Clase", "t"], ["Importe", "n"]],
         "rows": [[f"C{i}", 1000.0 - i] for i in range(10)] + [["Resta", -5.0]]}
    serie = graficos.serie_spec({"hoja": "X", "etiqueta": "Clase", "valor": "Importe"}, {"X": h}, absoluto=True)
    assert ("(−) Resta", 5.0) in serie and len(serie) == graficos.TOP_HALLAZGOS + 1


@pytest.mark.parametrize("pid", ["proveedores_cxp", "activos_biologicos", "efectivo_equivalentes", "patrimonio"])
def test_poblacion_igual_al_registrado_muestra_partidas(pid):
    p, _ = _panel(pid)
    assert p["poblacion"]["igual_registrado"] and p["poblacion"]["n"]
    mod = PROCESADORES[pid]
    d = mod.definicion()
    ds, par, corte = em.escenario(mod)
    h = libro.html(d, em._reg(d, mod, ds, par, corte), [], 1, "APROBADO").decode("utf-8")
    assert f'{p["poblacion"]["n"]} partidas' in h and "misma base que el saldo registrado" in h


def test_filtros_del_panel():
    h = {"name": "H", "cols": [["Tipo", "t"], ["A", "n"], ["B", "n"]],
         "rows": [["x", 10.0, 1.0], ["y", 20.0, None], ["x", 5.0, 2.0]]}
    m = {"H": h}
    assert graficos.valor_spec({"hoja": "H", "col": "A", "donde": {"Tipo": ["x"]}}, {}, m) == 15.0
    assert graficos.valor_spec({"hoja": "H", "col": "A", "con_valor": "B"}, {}, m) == 15.0
    assert graficos.filas_spec({"hoja": "H", "con_valor": "B"}, m) == 2
    assert graficos.serie_spec({"totales": [["Uno", "a"], ["Dos", "b"]]}, {}, run={"totals": {"a": "3", "b": "4"}}) == [("Uno", 3.0), ("Dos", 4.0)]
