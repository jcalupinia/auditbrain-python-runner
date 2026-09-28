"""Servicio del agente guía «NIIF Piloto» (backend/app/aud/niif/piloto.py).

Mantiene viva la regla: un solo motor para TODAS las pruebas NIIF (las 20 del
catálogo + la planificación NIA), que arma el papel reutilizando el procesador
determinista y VERIFICA que el Excel reabra sin «reparaciones» (regla suprema del
CLAUDE.md). La CLI y el router HTTP consumen este mismo servicio.
"""
import pytest

from backend.app.aud.niif import ejercicio_modelo, piloto, procesadores


def test_listar_incluye_todas_las_pruebas():
    filas = piloto.listar()
    ids = {f["id"] for f in filas}
    assert len(filas) == len(procesadores.PROCESADORES)
    # Herramientas de catálogo y las dos por ficha, más la planificación NIA.
    for esperado in ("arrendamientos", "inventarios_costos", "ppe_propiedad_planta",
                     "ingresos_contratos", "planificacion_nia", "perdidas_incurridas_s11"):
        assert esperado in ids
    for f in filas:
        assert f["nombre"] and isinstance(f["marcos"], list)


def test_requisitos_expone_datasets_parametros_y_requerimientos():
    r = piloto.requisitos("arrendamientos")
    assert r["nombre"] == "Arrendamientos"
    principal = [d for d in r["datasets"] if d["es_principal"]]
    assert len(principal) == 1 and principal[0]["dataset"] == "contratos"
    claves = {c["key"] for c in principal[0]["campos"]}
    assert {"id", "activo", "inicio", "plazo", "pago"} <= claves
    assert "convencionTasa" in r["parametros_por_defecto"]
    assert any(req["id"] == "RQ-001" for req in r["requerimientos_al_cliente"])


def test_requisitos_prueba_desconocida():
    with pytest.raises(piloto.PruebaDesconocida):
        piloto.requisitos("no_existe")


def test_preparar_papel_y_verificacion_excel():
    mod = procesadores.PROCESADORES["arrendamientos"]
    datasets, param, corte = ejercicio_modelo.escenario(mod)
    d, reg = piloto.preparar("arrendamientos", datasets, param, corte)
    contenido = piloto.papel(d, reg, "xlsx")
    assert contenido[:2] == b"PK"  # es un .xlsx (zip)
    v = piloto.verificar_excel(contenido)
    assert v["reabre"] is True and v["n_hojas"] > 0
    # Regla suprema, punto 6: sin celdas de texto que Excel lea como fórmula.
    assert v["celdas_texto_riesgosas"] == []
    resumen = piloto.resumen_run(reg)
    assert resumen["valor_principal"] is not None
    assert resumen["filas_por_dataset"]["contratos"] == len(datasets["contratos"])


def test_encargo_llega_al_papel():
    mod = procesadores.PROCESADORES["cxc_cartera"]
    datasets, param, corte = ejercicio_modelo.escenario(mod)
    encargo = {"client": "Cliente Real S.A.", "ruc": "1790000000001", "preparer": "Auditor X"}
    d, reg = piloto.preparar("cxc_cartera", datasets, param, corte, encargo)
    assert reg["engagement"]["client"] == "Cliente Real S.A."
    assert reg["engagement"]["ruc"] == "1790000000001"
    assert reg["engagement"]["cutoff"] == corte


@pytest.mark.parametrize("pid", ["efectivo_equivalentes", "inventarios_costos", "ingresos_contratos"])
def test_varias_pruebas_arman_excel_verificable(pid):
    mod = procesadores.PROCESADORES[pid]
    datasets, param, corte = ejercicio_modelo.escenario(mod)
    d, reg = piloto.preparar(pid, datasets, param, corte)
    v = piloto.verificar_excel(piloto.papel(d, reg, "xlsx"))
    assert v["reabre"] and v["celdas_texto_riesgosas"] == []
