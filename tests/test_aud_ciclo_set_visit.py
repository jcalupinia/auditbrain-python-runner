"""Corrección de la «Visita de auditoría» (Preliminar/Final) de una planificación ya
avanzada SIN reiniciarla (acción ``set_visit``).

Incidente 2026-10-05: la visita se congela al crear la prueba y vive en dos sitios
(``engagement.visit`` para el HTML del artefacto y el parámetro ``tipoRevision`` +
``mesesTranscurridos`` para el Excel/Word/PDF del procesador). Antes, corregirla
obligaba a ``edit_context``, que reinicia la prueba al paso 2 y borra el trabajo.
``set_visit`` actualiza ambas fuentes, re-ejecuta el papel y NO cambia el estado.
"""
import pytest

from backend.app.aud.niif.ciclo import servicio
from backend.app.aud.niif.ciclo.models import Prueba
from backend.app.aud.niif.procesadores import planificacion_nia as m
from backend.app.db.session import SessionLocal
from tests.test_aud_ciclo_http import _staff_con_proyecto

CORTE = "2026-08-31"   # corte en agosto (mes 8)


def _prueba_planificacion(db, pid, *, visit="Final", meses=12, con_run=True):
    e = m.EJEMPLO
    par = {**e["parametros"], "tipoRevision": visit, "mesesTranscurridos": meses, "corte": CORTE}
    reg = {
        "engagement": {"client": "Comercial Andina de Ejemplo S.A.", "cutoff": CORTE,
                       "framework": "NIIF completas", "edition": "", "visit": visit},
        "parameters": par, "datasets": e["datasets"],
        "analysis": "Análisis", "conclusion": "Conclusión", "conclusionReviewed": False,
        "notes": [], "rows": [], "flows": [],
    }
    if con_run:
        run = m.ejecutar(e["datasets"], par, CORTE)
        reg["run"] = run
    p = Prueba(project_id=pid, version=1, estado="RESULTADOS_ANALIZADOS", origen="proc:planificacion_nia",
               definicion=m.definicion(), registro=reg, revision=1, creada_por="staff@a.ec")
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_set_visit_cambia_ambas_fuentes_y_no_reinicia(client):
    tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        p = _prueba_planificacion(db, pid, visit="Final", meses=12)
        hash_antes = p.registro.get("runHash")
        p = servicio.aplicar_accion(db, p, "set_visit", p.revision, {"visit": "Preliminar"}, "staff@a.ec")
        reg = p.registro
        # Ambas fuentes de verdad quedan en «Preliminar».
        assert reg["engagement"]["visit"] == "Preliminar"           # HTML del artefacto
        assert reg["parameters"]["tipoRevision"] == "Preliminar"    # Excel/Word/PDF del procesador
        assert reg["parameters"]["mesesTranscurridos"] == 8         # meses = mes del corte (agosto)
        # NO se reinicia: el estado del ciclo se mantiene; el trabajo (análisis/conclusión) sigue.
        assert p.estado == "RESULTADOS_ANALIZADOS"
        assert reg["analysis"] == "Análisis" and reg["conclusion"] == "Conclusión"
        # Se re-ejecutó: el papel refleja la nueva visita (runHash distinto, executedAt presente).
        assert reg.get("runHash") and reg["runHash"] != hash_antes
        assert reg.get("executedAt")
    finally:
        db.close()


def test_set_visit_sin_run_actualiza_parametros_sin_ejecutar(client):
    tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        p = _prueba_planificacion(db, pid, visit="Final", meses=12, con_run=False)
        p = servicio.aplicar_accion(db, p, "set_visit", p.revision, {"visit": "Preliminar"}, "staff@a.ec")
        reg = p.registro
        assert reg["engagement"]["visit"] == "Preliminar"
        assert reg["parameters"]["tipoRevision"] == "Preliminar" and reg["parameters"]["mesesTranscurridos"] == 8
        assert "run" not in reg and p.estado == "RESULTADOS_ANALIZADOS"
    finally:
        db.close()


def test_set_visit_valida_el_valor(client):
    tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        p = _prueba_planificacion(db, pid, con_run=False)
        with pytest.raises(servicio.ReglaIncumplida):
            servicio.aplicar_accion(db, p, "set_visit", p.revision, {"visit": "Intermedia"}, "staff@a.ec")
    finally:
        db.close()


def test_set_visit_vuelve_a_final_pone_doce_meses(client):
    tok, pid = _staff_con_proyecto(client)
    db = SessionLocal()
    try:
        p = _prueba_planificacion(db, pid, visit="Preliminar", meses=8, con_run=False)
        p = servicio.aplicar_accion(db, p, "set_visit", p.revision, {"visit": "Final"}, "staff@a.ec")
        assert p.registro["parameters"]["mesesTranscurridos"] == 12
        assert p.registro["engagement"]["visit"] == "Final"
    finally:
        db.close()
