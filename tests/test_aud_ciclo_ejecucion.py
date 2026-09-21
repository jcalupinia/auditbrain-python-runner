"""E8 por HTTP: parámetros, metodología, ejecución con contraste y análisis.

El navegador corre domain.mjs y manda su resultado; aquí se simula con el
propio resultado del motor Python (que el espejo ya iguala al del sitio) y con
versiones alteradas, para probar que el servidor rechaza cualquier diferencia.
"""
import copy

import pytest

from backend.app.aud.niif import estudio
from backend.app.aud.niif.ciclo import datos
from tests.test_aud_ciclo_evidencia import MAPA_VNR, XLSX_VNR, _hasta_requerimiento_aprobado, _leer, _subir
from tests.test_aud_ciclo_http import BASE, _accion, _prueba_vnr, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


@pytest.fixture(autouse=True)
def disco_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_CICLO_DIR", str(tmp_path / "aud_pruebas"))
    monkeypatch.setenv("AUD_CICLO_MIN_LIBRE_MB", "0")


def _validada(client):
    tok, p = _hasta_requerimiento_aprobado(client, tok=None)
    for req, nombre, contenido, comp in [
        ("RQ-001", "q.xlsx", XLSX_VNR, "Quito"), ("RQ-001", "g.xlsx", XLSX_VNR, "Guayaquil"),
        ("RQ-002", "p.pdf", b"%PDF", ""), ("RQ-003", "g.pdf", b"%PDF", ""), ("RQ-VNR-04", "po.pdf", b"%PDF", ""),
    ]:
        p = _leer(client, tok, p)
        assert _subir(client, tok, p, req, nombre, contenido, comp).status_code == 201
    p = _leer(client, tok, p)
    p = _accion(client, tok, p, "map_validate",
                {"fileId": p["archivos"][0]["id"], "sheet": "Inventario", "header": 1, "mapping": MAPA_VNR}).json()
    p = _accion(client, tok, p, "validate", {"evidenceReviewed": True, "evidenceReview": "Cotejé originales y extracción.",
                                             "ledger": "470.00", "tolerance": "0"}).json()
    assert p["estado"] == "DOCUMENTACION_VALIDADA", p
    return tok, p


def _navegador(p):
    """Lo que calcularía domain.mjs en el navegador: el mismo resultado."""
    run = estudio.ejecutar_definicion(p["definicion"], p["registro"]["rows"], p["registro"]["parameters"])
    run["exceptions"] = datos.excepciones(p["definicion"], run)
    return run


def test_ejecucion_y_analisis_de_punta_a_punta(client):
    tok, p = _validada(client)

    # Parámetros: sin sustento no se configura.
    r = _accion(client, tok, p, "configure", {"basis": " "})
    assert r.status_code == 400 and "sustento de parámetros" in r.json()["detail"]
    # No se ejecuta antes de aprobar la metodología.
    assert _accion(client, tok, p, "execute", {}).status_code == 400
    p = _accion(client, tok, p, "configure", {"basis": "Precios de venta de la lista vigente al corte; costos de venta del ERI."}).json()
    assert p["estado"] == "PRUEBA_CONFIGURADA"
    assert p["registro"]["parameters"]["cutoff"] == "2025-12-31"
    p = _accion(client, tok, p, "approve_methodology").json()
    assert p["estado"] == "METODOLOGIA_APROBADA"

    # Contraste: sin resultado del navegador, o con cualquier diferencia, no se guarda nada.
    r = _accion(client, tok, p, "execute", {})
    assert r.status_code == 400 and "no llegó el resultado del navegador" in r.json()["detail"]
    nav = _navegador(p)
    alterado = copy.deepcopy(nav)
    alterado["rows"][0]["impairment"] = "49.99"
    r = _accion(client, tok, p, "execute", {"navegador": alterado})
    assert r.status_code == 400 and "fila 1, campos: impairment" in r.json()["detail"]
    sin_exc = {**nav, "exceptions": []}
    r = _accion(client, tok, p, "execute", {"navegador": sin_exc})
    assert r.status_code == 400 and "(excepciones)" in r.json()["detail"]
    assert _leer(client, tok, p)["registro"].get("run") is None

    p = _accion(client, tok, p, "execute", {"navegador": nav}).json()
    assert p["estado"] == "PRUEBA_EJECUTADA", p
    run = p["registro"]["run"]
    # Las 3 partidas del ejemplo VNR: costo 470,00 y deterioro 82,00 (A 50 + C 32).
    assert run["totals"]["cost"] == "470.00" and run["totals"]["impairment"] == "82.00"
    assert [(e["id"], e["code"]) for e in run["exceptions"]] == [("0001", "RESULT"), ("0003", "RESULT")]
    assert len(p["registro"]["runHash"]) == 64 and p["registro"]["executedAt"]

    # Análisis: el preliminar es el del sitio; luego lo reemplaza el auditor.
    r = _accion(client, tok, p, "save_analysis", {"analysis": "x"})
    assert r.status_code == 400 and "Análisis no editable" in r.json()["detail"]
    p = _accion(client, tok, p, "analyze").json()
    assert p["estado"] == "RESULTADOS_ANALIZADOS"
    assert p["registro"]["analysis"].startswith("CONCLUSIÓN PRELIMINAR")
    assert "Excepciones identificadas: 2." in p["registro"]["analysis"]
    r = _accion(client, tok, p, "save_analysis", {"analysis": " ", "conclusion": "c"})
    assert r.status_code == 400 and "Complete el análisis" in r.json()["detail"]
    p = _accion(client, tok, p, "save_analysis", {"analysis": "Dos partidas bajo costo.", "conclusion": "Ajuste de 82,00."}).json()
    assert p["registro"]["analysis"] == "Dos partidas bajo costo." and p["registro"]["conclusion"] == "Ajuste de 82,00."
    assert p["estado"] == "RESULTADOS_ANALIZADOS"

    acciones = [e["accion"] for e in _leer(client, tok, p)["eventos"]]
    assert acciones[-5:] == ["configure", "approve_methodology", "execute", "analyze", "save_analysis"]


def test_la_pce_exige_tramos_validos(client):
    tok, pid = _staff_con_proyecto(client)
    _prueba_vnr(client, tok, pid)  # deja la ficha del encargo en NIIF completas
    p = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "pce"}).json()
    # Se lleva la prueba a DOCUMENTACION_VALIDADA por la base: aquí solo importa configure.
    from backend.app.db.session import SessionLocal
    from backend.app.aud.niif.ciclo.models import Prueba
    db = SessionLocal()
    try:
        x = db.get(Prueba, p["id"])
        x.estado = "DOCUMENTACION_VALIDADA"
        db.commit()
    finally:
        db.close()
    p = _leer(client, tok, p)
    r = _accion(client, tok, p, "configure", {"basis": "Matriz aprobada por el comité de crédito.",
                                              "buckets": [{"min": 0, "max": 30, "rate": "0.01"}]})
    assert r.status_code == 400 and "último rango debe tener límite superior vacío" in r.json()["detail"]
    p = _accion(client, tok, p, "configure", {"basis": "Matriz aprobada por el comité de crédito.",
                                              "buckets": [{"min": 0, "max": 30, "rate": "0.01"}, {"min": 31, "max": None, "rate": "0.2"}]}).json()
    assert p["estado"] == "PRUEBA_CONFIGURADA"
    assert len(p["registro"]["parameters"]["buckets"]) == 2
