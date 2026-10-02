"""Revisor genérico por contrato (``ciclo.revision.base``) para las 20 herramientas.

No prueba la planificación (tiene su propio revisor rico en
``test_aud_consola_revision``): prueba que, sobre el resultado de cualquier
herramienta del catálogo, el revisor genérico no inventa bloqueos, resuelve el
panel, ve los problemas enlazados y emite un veredicto coherente.
"""
import pytest

from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.ciclo import revision
from backend.app.aud.niif.ciclo.revision import base
from backend.app.aud.niif.procesadores import PROCESADORES

CATALOGO = [pid for pid in PROCESADORES if pid != "planificacion_nia"]


def _run(pid):
    mod = PROCESADORES[pid]
    ds, par, corte = em.escenario(mod)
    return mod, mod.ejecutar(ds, par, corte)


@pytest.mark.parametrize("pid", CATALOGO)
def test_revisor_generico_no_inventa_bloqueos(pid):
    mod, run = _run(pid)
    rep = base.revisar(run, mod, pid)
    # El escenario modelo es un papel bien formado: nunca debe salir NO APTO por el papel.
    assert rep["bloqueos"] == [], (pid, rep["bloqueos"])
    assert rep["veredicto"] in ("APTO PARA REVISIÓN DEL SOCIO", "OBSERVADO")
    assert rep["modo"] == "generico"


@pytest.mark.parametrize("pid", CATALOGO)
def test_revisor_generico_panel_y_problemas(pid):
    mod, run = _run(pid)
    rep = base.revisar(run, mod, pid)
    puerta = {c["criterio"]: c["estado"] for c in rep["puerta_calidad"]}
    # El panel resuelve y ningún problema con importe queda sin enlazar (sin cifras pegadas).
    assert puerta["Panel ejecutivo resuelto (mismos gráficos del HTML)"] == "PASA"
    assert puerta["Sin cifras pegadas: problemas enlazados a su celda (decisión del dueño)"] == "PASA"
    # Los hallazgos de la prueba se resumen para el auditor (informativo).
    assert rep["problemas"]["total"] == len(run.get("exceptions") or [])


def test_recalculo_por_rubro_se_resuelve_por_registro():
    # Sin módulo de recálculo, el registro devuelve None (no rompe).
    assert revision.recalculo_de("no_existe_este_rubro") is None
