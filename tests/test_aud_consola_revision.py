"""Consola de revisión del auditor (puerta de calidad de la planificación FIN-AP).

Revisa que el motor revisor embebido (``ciclo/consola_revision.py``) recalcule de
forma independiente lo que produjo ``planificacion_nia`` y emita el veredicto
correcto: APTO / OBSERVADO / NO APTO. El patrón es el prompt FIN-AP y el artefacto
``AuditBrain_Analisis_LANSEY`` (mismo motor que el agente auditor del repo
``audit-ia-artefactos``, PR #3).
"""
import copy

import pytest

from backend.app.aud.niif.ciclo import consola_revision as cr
from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.procesadores import planificacion_nia as pl
from backend.app.db.session import SessionLocal
from tests.test_aud_ciclo_http import BASE, FICHA, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


def _run(datasets=None, parametros=None):
    e = pl.EJEMPLO
    return pl.ejecutar(datasets or e["datasets"], parametros or e["parametros"], e["corte"])


def _run_limpio():
    """Ejemplo sin las dos observaciones automáticas (justificación propia y control probado)."""
    par = copy.deepcopy(pl.EJEMPLO["parametros"])
    par["justificacion"] = ("Base ingresos por ser una comercializadora; el 1 % es la práctica habitual de la "
                            "firma para este sector.")
    ds = copy.deepcopy(pl.EJEMPLO["datasets"])
    for f in ds["carta_control_interno"]:
        f["probar_control"] = "Si"
    return _run(ds, par)


# --- recálculo independiente: cero diferencias contra el motor -----------------------------------------------

def test_recalculo_indices_cero_diferencias():
    rep = cr.revisar(_run())
    ind = rep["recalculo_indices"]
    assert ind["total"] == 40  # 20 índices × 2 períodos
    assert ind["diferencias"] == 0
    assert ind["conforme"] is True


def test_recalculo_agregados_cero_diferencias():
    rep = cr.revisar(_run())
    agr = rep["recalculo_agregados"]
    assert agr["diferencias"] == 0
    assert agr["conforme"] is True


def test_cuadre_ambos_periodos():
    rep = cr.revisar(_run())
    assert len(rep["cuadre"]) == 2
    assert all(f["estado"] == "cuadra" for f in rep["cuadre"])


def test_cobertura_conforme():
    rep = cr.revisar(_run())
    cob = rep["cobertura"]
    assert cob["presentes"] == cob["total"] == 11
    assert cob["veredicto"] == "CONFORME"


# --- veredicto -----------------------------------------------------------------------------------------------

def test_veredicto_apto_cuando_no_hay_observaciones():
    rep = cr.revisar(_run_limpio())
    assert rep["veredicto"] == "APTO PARA REVISIÓN DEL SOCIO"
    assert rep["hallazgos"] == []
    assert rep["bloqueos"] == []
    assert rep["aprobacion_socio_requerida"] is True
    assert rep["etiqueta"] == cr.ETIQUETA_PENDIENTE


def test_veredicto_observado_con_observaciones_menores():
    # El ejemplo base usa la justificación automática de la materialidad: OBSERVADO, no NO APTO.
    rep = cr.revisar(_run())
    assert rep["veredicto"] == "OBSERVADO"
    assert rep["bloqueos"] == []
    assert rep["hallazgos"]


def test_veredicto_no_apto_si_un_indice_diverge():
    run = _run()
    run["detalle"]["ind"]["act"]["razonCorriente"] = 9.99  # simula divergencia con el motor
    rep = cr.revisar(run)
    assert rep["veredicto"] == "NO APTO"
    assert rep["recalculo_indices"]["diferencias"] == 1
    assert rep["bloqueos"]


def test_veredicto_no_apto_si_un_agregado_diverge():
    run = _run()
    run["detalle"]["est9"]["act"]["TOTAL ACTIVO"] += 1000  # el agregado deja de coincidir con las cuentas
    rep = cr.revisar(run)
    assert rep["veredicto"] == "NO APTO"
    assert rep["recalculo_agregados"]["diferencias"] >= 1


def test_veredicto_no_apto_si_el_balance_no_cuadra():
    run = _run()
    e = run["detalle"]["est9"]["act"]
    e["PASIVO + PATRIMONIO TOTAL"] += 5000  # rompe el cuadre
    rep = cr.revisar(run)
    assert rep["veredicto"] == "NO APTO"
    assert any(f["estado"] == "descuadra" for f in rep["cuadre"])


# --- recálculo verdaderamente independiente ------------------------------------------------------------------

def test_indices_independientes_reproducen_al_motor_en_todos_los_escenarios():
    # En cada escenario de control del procesador, la segunda implementación de los índices
    # coincide con la del motor (cero diferencias): el cotejo no está copiando la función.
    for nombre, ds, par, corte in pl.ESCENARIOS:
        run = pl.ejecutar(ds, par, corte)
        rep = cr.revisar(run)
        assert rep["recalculo_indices"]["diferencias"] == 0, f"{nombre}: índices divergen"
        assert rep["recalculo_agregados"]["diferencias"] == 0, f"{nombre}: agregados divergen"


def test_puerta_de_calidad_incluye_aprobacion_del_socio_pendiente():
    rep = cr.revisar(_run())
    aprob = next(c for c in rep["puerta_calidad"] if c["criterio"].startswith("Aprobación del socio"))
    assert aprob["estado"] == "PENDIENTE"


def test_indicios_nia570_en_patrimonio_deficit():
    _, ds, par, corte = next(x for x in pl.ESCENARIOS if x[0] == "patrimonio_deficit")
    rep = cr.revisar(pl.ejecutar(ds, par, corte))
    assert rep["nia570"]  # el déficit patrimonial dispara al menos un indicio


# --- endpoint HTTP -------------------------------------------------------------------------------------------

def _prueba_planificacion_en_revision(client):
    """Crea en la base una planificación en EN_REVISION con sus insumos, lista para revisar."""
    from backend.app.aud.niif.ciclo.models import Prueba

    tok, pid = _staff_con_proyecto(client)
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    reg = {
        "engagement": {"cutoff": pl.EJEMPLO["corte"], "framework": "NIIF completas", "edition": ""},
        "datasets": pl.EJEMPLO["datasets"],
        "parameters": {k: v for k, v in pl.EJEMPLO["parametros"].items() if not k.startswith("_")},
        "run": {"hojas": [{"name": "01_Resumen"}]},  # marca de «ya procesada»
    }
    db = SessionLocal()
    try:
        p = Prueba(project_id=pid, version=1, estado="EN_REVISION", origen="proc:planificacion_nia",
                   definicion=pl.definicion(), registro=reg, revision=1, creada_por="x")
        db.add(p)
        db.commit()
        pid_prueba = p.id
    finally:
        db.close()
    return tok, pid_prueba


def test_endpoint_devuelve_veredicto_y_recalculo(client):
    tok, prueba_id = _prueba_planificacion_en_revision(client)
    r = client.get(f"{BASE}/pruebas/{prueba_id}/consola-revision", headers=_h(tok))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["estado"] == "EN_REVISION" and cuerpo["aprobable"] is True
    rep = cuerpo["reporte"]
    assert rep["veredicto"] in ("APTO PARA REVISIÓN DEL SOCIO", "OBSERVADO")
    assert rep["recalculo_indices"]["diferencias"] == 0
    assert rep["recalculo_agregados"]["diferencias"] == 0
    assert all(f["estado"] == "cuadra" for f in rep["cuadre"])


def test_endpoint_rechaza_prueba_sin_procesar(client):
    from backend.app.aud.niif.ciclo.models import Prueba

    tok, pid = _staff_con_proyecto(client)
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    db = SessionLocal()
    try:
        p = Prueba(project_id=pid, version=1, estado="EN_REVISION", origen="proc:planificacion_nia",
                   definicion=pl.definicion(), registro={}, revision=1, creada_por="x")
        db.add(p)
        db.commit()
        prueba_id = p.id
    finally:
        db.close()
    r = client.get(f"{BASE}/pruebas/{prueba_id}/consola-revision", headers=_h(tok))
    assert r.status_code == 400 and "Procese la planificación" in r.json()["detail"]
