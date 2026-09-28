"""Puente planificación → pruebas del piloto (backend/app/aud/niif/puente.py).

Mantiene viva la regla: cada herramienta que la planificación asigna a una cuenta
a revisar (``planificacion_nia.HERRAMIENTAS``) resuelve a una prueba real del piloto,
sin lista paralela hardcoded. Y de la corrida de la planificación se deriva la lista
ordenada de pruebas a ejecutar (riesgo primero, luego saldo).
"""
from backend.app.aud.niif import ejercicio_modelo, procesadores, puente
from backend.app.aud.niif.procesadores import planificacion_nia as pn


def test_indice_resuelve_todas_las_herramientas_menos_el_motor_analitico():
    idx = puente.indice_por_herramienta()
    # Toda herramienta del catálogo del piloto queda mapeada; "Asientos de diario"
    # apunta al motor analítico (fuera del piloto) y NO debe estar.
    esperadas = set(pn.HERRAMIENTAS.values()) - {pn.HERRAMIENTAS["Asientos de diario"]}
    assert set(idx) == esperadas
    # Cada destino es una prueba real del piloto.
    for pid in idx.values():
        assert pid in procesadores.PROCESADORES
    # El motor analítico no es una prueba del piloto.
    assert pn.HERRAMIENTAS["Asientos de diario"] not in idx


def _run_planificacion():
    mod = procesadores.PROCESADORES["planificacion_nia"]
    datasets, param, corte = ejercicio_modelo.escenario(mod)
    return mod.ejecutar(datasets, {**(mod.PARAMETROS or {}), **(param or {})}, corte)


def test_sugerencias_lista_pruebas_reales_ordenadas():
    sug = puente.sugerencias(_run_planificacion())
    assert sug["pruebas"], "la planificación de ejemplo debe sugerir pruebas"
    ids = [g["prueba_id"] for g in sug["pruebas"]]
    # Todos los ids son procesadores reales del piloto.
    assert all(pid in procesadores.PROCESADORES for pid in ids)
    # Sin duplicados: una prueba por herramienta.
    assert len(ids) == len(set(ids))
    # Orden: las que tienen riesgo van antes que las que no.
    con_riesgo = [g["con_riesgo"] for g in sug["pruebas"]]
    assert con_riesgo == sorted(con_riesgo, reverse=True)
    # Cada sugerencia trae sus cuentas y un saldo acumulado numérico.
    total_cuentas = 0
    for g in sug["pruebas"]:
        assert g["n_cuentas"] == len(g["cuentas"]) >= 1
        assert isinstance(g["saldo"], (int, float))
        assert g["rubro"]  # el RUBRO del procesador
        total_cuentas += g["n_cuentas"]
    assert sug["cuentas_a_revisar"] == total_cuentas + sum(g["n_cuentas"] for g in sug["sin_prueba"])


def test_sugerencias_con_riesgo_expone_los_codigos():
    sug = puente.sugerencias(_run_planificacion())
    con_riesgo = [g for g in sug["pruebas"] if g["con_riesgo"]]
    assert con_riesgo, "el ejemplo tiene cuentas con riesgo asociado"
    # Al menos una cuenta de esas pruebas trae códigos de riesgo.
    assert any(c["riesgos"] for g in con_riesgo for c in g["cuentas"])


def test_run_sin_detalle_no_rompe():
    # Un run podado (como el que se guarda) no trae 'revisar': no debe fallar.
    assert puente.sugerencias({"detalle": {}}) == {"pruebas": [], "sin_prueba": [], "cuentas_a_revisar": 0}
    assert puente.sugerencias({})["cuentas_a_revisar"] == 0


def test_endpoint_rechaza_prueba_que_no_es_planificacion(client):
    from tests.test_aud_ciclo_http import BASE, _h, _prueba_vnr, _staff_con_proyecto
    tok, pid = _staff_con_proyecto(client)
    prueba = _prueba_vnr(client, tok, pid)
    r = client.get(f"{BASE}/pruebas/{prueba['id']}/pruebas-sugeridas", headers=_h(tok))
    assert r.status_code == 400, r.text
