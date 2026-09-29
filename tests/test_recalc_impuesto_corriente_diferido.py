"""Recálculo independiente de «Impuesto corriente y diferido» (consola de revisión)."""
from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.ciclo import revision
from backend.app.aud.niif.ciclo.revision import base
from backend.app.aud.niif.ciclo.revision.recalc import impuesto_corriente_diferido as rc
from backend.app.aud.niif.procesadores import PROCESADORES

PID = "impuesto_corriente_diferido"


def _run():
    mod = PROCESADORES[PID]
    ds, par, corte = em.escenario(mod)
    return mod, mod.ejecutar(ds, par, corte)


def test_recalculo_coincide_con_el_motor():
    _, run = _run()
    rep = rc.recalcular(run)
    assert rep["ok"], rep
    assert rep["diff"] is not None and rep["diff"] <= 0.01
    # el ajuste neto re-derivado coincide con el resultado principal del motor
    assert rep["declarado"] == rep["recalculado"]
    # y cada componente (corriente, diferido a resultados, reclasificación ORI) cuadra
    assert all(c["ok"] for c in rep["componentes"]), rep["componentes"]


def test_esta_registrado_y_el_veredicto_pasa_a_apto():
    mod, run = _run()
    assert revision.recalculo_de(PID) is rc.recalcular
    rep = base.revisar(run, mod, PID)
    assert rep["veredicto"] == "APTO PARA REVISIÓN DEL SOCIO", (rep["veredicto"], rep["bloqueos"], rep["hallazgos"])
    assert rep["recalculo"]["conforme"]
