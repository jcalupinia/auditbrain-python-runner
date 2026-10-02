"""Consola-chat del piloto de planificación: el agente determinista que guía al
preparador (qué subir, cuándo procesar y enviar) y al auditor (veredicto y aprobación).
"""
import copy

from backend.app.aud.niif.ciclo import consola_chat as chat
from backend.app.aud.niif.procesadores import planificacion_nia as pl
from backend.app.db.session import SessionLocal
from tests.test_aud_ciclo_http import BASE, FICHA, _staff_con_proyecto
from tests.test_aud_niif_fichas import _h


# --- guion determinista (función pura) -----------------------------------------------------------------------

def test_fase_por_estado():
    assert chat.fase_de("PRUEBA_SELECCIONADA", ["Balance"]) == chat.FASE_DOCUMENTOS
    assert chat.fase_de("REQUERIMIENTO_APROBADO", []) == chat.FASE_PROCESAR
    assert chat.fase_de("DOCUMENTACION_VALIDADA", []) == chat.FASE_PROCESAR
    assert chat.fase_de("PRUEBA_EJECUTADA", []) == chat.FASE_ENVIAR
    assert chat.fase_de("EN_REVISION", []) == chat.FASE_REVISAR
    assert chat.fase_de("APROBADO", []) == chat.FASE_APROBADA


def test_preparador_pide_documentos_pendientes():
    g = chat.guion({"estado": "REQUERIMIENTO_APROBADO", "cliente": "ACME", "huecos": ["Balance al corte"],
                    "pendientes": ["Balance al corte", "Carta de control interno"], "recibidos": 1, "total": 3}, "preparador")
    assert g["fase"] == chat.FASE_DOCUMENTOS
    assert g["siguiente"]["accion"] == "subir"
    texto = " ".join(m["texto"] for m in g["mensajes"])
    assert "Balance al corte" in texto and "Carta de control interno" in texto and "1 de 3" in texto


def test_preparador_procesa_cuando_no_faltan_documentos():
    g = chat.guion({"estado": "REQUERIMIENTO_APROBADO", "cliente": "ACME", "huecos": []}, "preparador")
    assert g["fase"] == chat.FASE_PROCESAR and g["siguiente"]["accion"] == "procesar"


def test_preparador_envia_cuando_esta_producida():
    g = chat.guion({"estado": "RESULTADOS_ANALIZADOS", "cliente": "ACME", "tiene_run": True}, "preparador")
    assert g["fase"] == chat.FASE_ENVIAR and g["siguiente"]["accion"] == "enviar"


def test_auditor_ve_veredicto_apto_y_puede_aprobar():
    g = chat.guion({"estado": "EN_REVISION", "cliente": "ACME", "veredicto": "APTO PARA REVISIÓN DEL SOCIO",
                    "bloqueos": [], "hallazgos": []}, "auditor")
    assert g["fase"] == chat.FASE_REVISAR and g["siguiente"]["accion"] == "aprobar"
    assert "APTO" in " ".join(m["texto"] for m in g["mensajes"])


def test_auditor_no_apto_ofrece_devolver():
    g = chat.guion({"estado": "EN_REVISION", "cliente": "ACME", "veredicto": "NO APTO",
                    "bloqueos": ["El balance corte actual no cuadra (diferencia 5000.00)."], "hallazgos": []}, "auditor")
    assert g["siguiente"]["accion"] == "devolver"
    assert "no cuadra" in " ".join(m["texto"] for m in g["mensajes"]).lower()


def test_auditor_sin_veredicto_ofrece_revisar():
    g = chat.guion({"estado": "EN_REVISION", "cliente": "ACME"}, "auditor")
    assert g["siguiente"]["accion"] == "revisar"


def test_preparador_en_revision_espera_al_auditor():
    g = chat.guion({"estado": "EN_REVISION", "cliente": "ACME"}, "preparador")
    assert g["siguiente"]["accion"] == "esperar"


def test_el_agente_dice_que_el_gobierno_es_automatico():
    # Solo en la planificación: la frase de gobierno automático es propia de ese piloto.
    g = chat.guion({"estado": "REQUERIMIENTO_APROBADO", "cliente": "ACME", "huecos": [],
                    "es_planificacion": True}, "preparador")
    texto = " ".join(m["texto"] for m in g["mensajes"]).lower()
    assert "independencia" in texto and ("autom" in texto or "política de la firma" in texto)


def test_en_una_prueba_del_catalogo_no_habla_de_gobierno_ni_de_planificacion():
    # La consola-chat de una herramienta del catálogo usa el nombre de la prueba y no
    # arrastra el texto de gobierno del encargo (independencia/enfoque), propio de la planificación.
    g = chat.guion({"estado": "REQUERIMIENTO_APROBADO", "cliente": "ACME", "prueba": "Efectivo y equivalentes",
                    "es_planificacion": False, "huecos": ["Conciliación bancaria"],
                    "pendientes": ["Conciliación bancaria"]}, "preparador")
    texto = " ".join(m["texto"] for m in g["mensajes"]).lower()
    assert "efectivo y equivalentes" in texto
    assert "independencia" not in texto and "planificación" not in texto
    assert g["siguiente"]["accion"] == "subir"


# --- endpoint HTTP -------------------------------------------------------------------------------------------

def _prueba_planificacion(client, estado="EN_REVISION", con_run=True):
    from backend.app.aud.niif.ciclo.models import Prueba

    tok, pid = _staff_con_proyecto(client)
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    reg = {
        "engagement": {"cutoff": pl.EJEMPLO["corte"], "framework": "NIIF completas", "edition": ""},
        "datasets": pl.EJEMPLO["datasets"],
        "parameters": {k: v for k, v in pl.EJEMPLO["parametros"].items() if not k.startswith("_")},
    }
    if con_run:
        reg["run"] = {"hojas": [{"name": "01_Resumen"}]}
    db = SessionLocal()
    try:
        p = Prueba(project_id=pid, version=1, estado=estado, origen="proc:planificacion_nia",
                   definicion=pl.definicion(), registro=reg, revision=1, creada_por="x")
        db.add(p)
        db.commit()
        prueba_id = p.id
    finally:
        db.close()
    return tok, prueba_id


def test_endpoint_chat_preparador_y_auditor(client):
    tok, prueba_id = _prueba_planificacion(client)
    # Preparador: la planificación está con el auditor.
    r = client.get(f"{BASE}/pruebas/{prueba_id}/consola-chat?rol=preparador", headers=_h(tok))
    assert r.status_code == 200, r.text
    assert r.json()["siguiente"]["rol"] == "auditor"
    # Auditor: trae el veredicto del recálculo independiente y puede aprobar.
    r = client.get(f"{BASE}/pruebas/{prueba_id}/consola-chat?rol=auditor", headers=_h(tok))
    assert r.status_code == 200, r.text
    g = r.json()
    assert g["fase"] == chat.FASE_REVISAR
    assert g["siguiente"]["accion"] in ("aprobar", "devolver")
    assert any("APTO" in m["texto"] or "OBSERVADO" in m["texto"] or "NO APTO" in m["texto"] for m in g["mensajes"])
