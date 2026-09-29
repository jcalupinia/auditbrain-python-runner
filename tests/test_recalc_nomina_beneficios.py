"""Recálculo independiente de «Beneficios sociales y nómina» (consola de revisión)."""
from backend.app.aud.niif import ejercicio_modelo as em
from backend.app.aud.niif.ciclo import revision
from backend.app.aud.niif.ciclo.revision import base
from backend.app.aud.niif.ciclo.revision.recalc import nomina_beneficios as rc
from backend.app.aud.niif.procesadores import PROCESADORES

PID = "nomina_beneficios"


def _run():
    mod = PROCESADORES[PID]
    ds, par, corte = em.escenario(mod)
    return mod, mod.ejecutar(ds, par, corte)


def test_recalculo_coincide_con_el_motor():
    _, run = _run()
    rep = rc.recalcular(run)
    assert rep["ok"], rep
    assert rep["diff"] is not None and rep["diff"] <= 0.01
    # el ajuste re-derivado (Σ recalculado − registrado por pasivo) iguala el declarado
    assert rep["declarado"] is not None and rep["recalculado"] is not None
    assert abs(rep["declarado"] - rep["recalculado"]) <= 0.01
    # cada componente (décimo tercero, décimo cuarto, vacaciones, fondo de reserva,
    # aporte patronal y post-empleo actuarial) coincide con lo que propone el motor
    assert rep["componentes"] and all(c["ok"] for c in rep["componentes"])
    # la suma de los componentes re-derivados reconstruye el total re-derivado
    suma = round(sum(c["recalculado"] for c in rep["componentes"] if c["recalculado"] is not None), 2)
    assert abs(suma - rep["recalculado"]) <= 0.01


def test_esta_registrado_y_el_veredicto_pasa_a_apto():
    mod, run = _run()
    assert revision.recalculo_de(PID) is rc.recalcular
    rep = base.revisar(run, mod, PID)
    assert rep["veredicto"] == "APTO PARA REVISIÓN DEL SOCIO", (rep["veredicto"], rep["bloqueos"], rep["hallazgos"])
    assert rep["recalculo"]["conforme"]
