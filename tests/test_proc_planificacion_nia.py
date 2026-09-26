"""Planificación de la auditoría (NIA 300, 315, 320, 240, 570): cifras de control resueltas a mano."""
import pytest

from backend.app.aud.niif.procesadores import planificacion_nia as m


def _run(**param):
    e = m.EJEMPLO
    return m.ejecutar(e["datasets"], {**e["parametros"], **param}, e["corte"])


def _area(r, seccion, area):
    return next(a for a in r["detalle"]["areas"] if a["seccion"] == seccion and a["area"] == area)


def test_bases_y_materialidad_del_ejemplo():
    r = _run()
    t = r["totals"]
    # Activos 3.204.200 = pasivos 1.679.700 + patrimonio 1.524.500 (el balance cuadra).
    assert t["activos"] == "3204200.00" and t["patrimonio"] == "1524500.00"
    b = r["detalle"]["bases"]["actual"]
    assert b["Pasivos totales"] == pytest.approx(1679700) and b["Diferencia de cuadre"] == pytest.approx(0)
    # Utilidad antes de impuestos = 4.860.500 + 18.400 − (3.402.300 + 468.900 + 391.700 + 67.500 + 58.300) = 490.200.
    assert t["uai"] == "490200.00"
    # Ingresos 4.860.500 × 1 % = 48.605; ejecución 65 % = 31.593,25; claramente insignificante 5 % = 2.430,25.
    assert (t["materialidad"], t["ejecucion"], t["trivial"]) == ("48605.00", "31593.25", "2430.25")
    # Materialidad indicativa con cada base: activos 1 %, UAI 5 %.
    assert r["detalle"]["indicativa"]["Activos totales"] == pytest.approx(32042)
    assert r["detalle"]["indicativa"]["Utilidad antes de impuestos"] == pytest.approx(24510)


def test_analiticos_y_riesgo_por_area():
    r = _run()
    cs = {c["id"]: c for c in r["detalle"]["cuentas"]}
    # Inventarios sube 301.400 (46,0 %): supera la ejecución y el umbral del 10 % → inusual.
    assert cs["1.1.05"]["var"] == pytest.approx(301400) and cs["1.1.05"]["inusual"] == "Sí"
    # Depreciación acumulada baja 31.700 (8,3 %): supera la ejecución pero no el 10 % → no inusual.
    assert cs["1.2.02"]["inusual"] == "No"
    # Anticipos a empleados 12.300 < 31.593,25 → no significativa; su área queda en riesgo bajo.
    assert cs["1.1.07"]["significativa"] == "No" and _area(r, "Activo", "Otros activos")["riesgo"] == "Bajo"
    # Caja: significativa sin variación inusual pero con un factor de riesgo (F-12) → alto.
    caja = _area(r, "Activo", "Caja y bancos")
    assert (caja["inusuales"], caja["factores"], caja["riesgo"]) == (0, 1, "Alto")
    # Cuentas por cobrar agrupa cartera y provisión: 812.300 − 48.700 = 763.600.
    assert _area(r, "Activo", "Cuentas por cobrar")["actual"] == pytest.approx(763600)
    # Inversiones: significativa, sin variación ni factor → medio.
    assert _area(r, "Activo", "Inversiones")["riesgo"] == "Medio"


def test_riesgos_significativos_y_problemas():
    r = _run()
    rs = r["detalle"]["riesgos"]
    assert rs[0]["riesgo"].startswith("Fraude en el reconocimiento de ingresos") and rs[0]["nivel"] == "Significativo"
    assert rs[1]["riesgo"].startswith("Elusión de los controles") and rs[1]["nivel"] == "Significativo"
    altos = [a for a in r["detalle"]["areas"] if a["riesgo"] == "Alto"]
    assert r["totals"]["riesgosSignificativos"] == f"{2 + len(altos)}.00"
    codigos = [e["code"] for e in r["exceptions"]]
    assert "RIESGO_FRAUDE_INGRESOS" in codigos and "ELUSION_CONTROLES" in codigos
    assert codigos.count("FACTOR_RIESGO") == 5 and "ESF_NO_CUADRA" not in codigos and "BASE_NO_VALIDA" not in codigos


def test_refutar_la_presuncion_exige_motivo():
    r = _run(refutarIngresos="Sí")
    assert r["detalle"]["riesgos"][0]["nivel"] == "Refutado (documentado)"
    assert "REFUTACION_SIN_MOTIVO" in [e["code"] for e in r["exceptions"]]
    r = _run(refutarIngresos="Sí", motivoRefutacion="Ventas de contado con un solo producto y precio regulado")
    codigos = [e["code"] for e in r["exceptions"]]
    assert "REFUTACION_SIN_MOTIVO" not in codigos and "RIESGO_FRAUDE_INGRESOS" not in codigos


def test_escenario_de_perdida_base_no_valida_e_indicio_570():
    _, ds, par, corte = m.ESCENARIOS[1]
    r = m.ejecutar(ds, par, corte)
    # Costo de ventas +700.000 → utilidad antes de impuestos 490.200 − 700.000 = −209.800.
    assert r["totals"]["uai"] == "-209800.00"
    codigos = [e["code"] for e in r["exceptions"]]
    assert "BASE_NO_VALIDA" in codigos and "PERDIDA_EJERCICIO" in codigos and "ENCARGO_INICIAL" in codigos
    assert "ESF_NO_CUADRA" not in codigos and r["detalle"]["marco"] == m.MARCO_PYMES


def test_balance_que_no_cuadra_y_sin_anio_anterior():
    ds = [{**x, "saldo_anterior": ""} for x in m.EJEMPLO["datasets"]["estados"] if x["id"] != "3.1.04"]
    r = m.ejecutar({"estados": ds}, {}, "2025-12-31")
    codigos = [e["code"] for e in r["exceptions"]]
    assert "ESF_NO_CUADRA" in codigos and "SIN_ANIO_ANTERIOR" in codigos and "SIN_CUESTIONARIO" in codigos
    # Sin saldos del año anterior no hay variaciones inusuales.
    assert all(c["inusual"] == "No" for c in r["detalle"]["cuentas"])


@pytest.mark.parametrize("param, mensaje", [
    ({"baseMaterialidad": "Utilidad bruta"}, "Base de la materialidad"),
    ({"pctBase": 0}, "Porcentaje aplicado"),
    ({"pctEjecucion": 120}, "Materialidad de ejecución"),
    ({"encargoInicial": "Tal vez"}, "Encargo inicial"),
    ({"fechaFinal": "31/02/2026"}, "Fecha de la visita final"),
])
def test_parametros_invalidos(param, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        _run(**param)


def test_anexo_vacio_y_grupo_desconocido():
    with pytest.raises(ValueError, match="estados financieros comparativos"):
        m.ejecutar({"estados": []}, {}, "2025-12-31")
    fila = {"id": "9", "cuenta": "X", "grupo": "Cuentas de orden", "saldo_actual": "10", "_row": 2}
    assert not m.validar_filas("estados", [fila])["ok"]
    assert not m.validar_filas("factores", [{"id": "F", "factor": "x", "respuesta": "Quizá", "_row": 2}])["ok"]


def test_area_por_defecto_segun_la_cuenta():
    assert m._area_defecto("Bancos locales", "Activo corriente") == "Caja y bancos"
    assert m._area_defecto("Proveedores del exterior", "Pasivo corriente") == "Proveedores y cuentas por pagar"
    assert m._area_defecto("Ventas de servicios", "Ingresos") == "Ingresos"
    assert m._area_defecto("Gastos de viaje", "Gastos") == "Costos y gastos"
    assert m._herramienta("CUENTAS POR COBRAR") == "Cuentas por cobrar y pérdida crediticia esperada"


def test_hojas_con_las_cedulas_y_el_ancho_de_columnas():
    r = _run()
    hs = m.hojas(r)
    assert [h["name"] for h in hs] == [n for n, _ in m.CEDULAS]
    for h in hs:
        for fila in h["rows"]:
            assert len(fila) == len(h["cols"]), h["name"]
    plan = next(h for h in hs if h["name"] == "10_Plan")
    # Solo las áreas de riesgo alto o medio entran al plan.
    assert len(plan["rows"]) == sum(1 for a in r["detalle"]["areas"] if a["riesgo"] != "Bajo")


def test_panel_con_textos_propios_y_las_demas_herramientas_sin_cambio():
    from backend.app.aud.niif.procesadores import PROCESADORES, graficos
    from backend.app.aud.niif.procesadores import html_ejecutivo as hx

    r = _run()
    r["hojas"] = m.hojas(r)
    p = graficos.panel(m, r, r["hojas"])
    assert not p["faltan"] and p["comparativo"]["rotulo"] == "Umbrales de la planificación"
    assert p["problemas"]["rotulo"] == "Asuntos para la planificación"
    tarjetas = hx.kpis_datos(p)
    assert tarjetas[2]["nota"] == "NIA 320 párr. 11" and "var" not in tarjetas[2]
    # Las pruebas sustantivas conservan el comparativo «registrado vs recalculado».
    otro = PROCESADORES["cxc_cartera"]
    assert graficos.textos(otro.PANEL)["comparativo"] == "Registrado vs recalculado"
    assert graficos.textos(otro.PANEL)["nota_registrado"] == "según el cliente"
