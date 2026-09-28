"""Consola de comunicación por prueba (chat auditable).

Un comentario es un evento de la bitácora (``accion="comentario"``): queda en el
papel (cédula 12) y es trazable (NIA 230). El asistente responde en el mismo hilo
usando el servidor de IA local; si no hay proveedor, el comentario del usuario se
guarda igual y se avisa. Reutiliza el arnés HTTP del ciclo.
"""
from backend.app.aud.niif import consola
from backend.app.chat import providers
from tests.test_aud_ciclo_http import BASE, _h, _prueba_vnr, _staff_con_proyecto


def _prueba_id(client):
    tok, pid = _staff_con_proyecto(client)
    prueba = _prueba_vnr(client, tok, pid)
    return tok, prueba["id"]


def test_comentario_se_guarda_como_conversacion(client):
    tok, prueba_id = _prueba_id(client)
    r = client.post(f"{BASE}/pruebas/{prueba_id}/comentarios", headers=_h(tok),
                    json={"texto": "¿Por qué la cartera quedó con ajuste?"})
    assert r.status_code == 201, r.text
    conv = r.json()["conversacion"]
    comentarios = [e for e in conv if e["tipo"] == "comentario"]
    assert len(comentarios) == 1
    assert comentarios[0]["texto"] == "¿Por qué la cartera quedó con ajuste?"
    assert comentarios[0]["es_asistente"] is False

    g = client.get(f"{BASE}/pruebas/{prueba_id}/comentarios", headers=_h(tok))
    assert g.status_code == 200
    assert any(e["texto"] == "¿Por qué la cartera quedó con ajuste?" for e in g.json()["conversacion"])


def test_comentario_vacio_rechazado(client):
    tok, prueba_id = _prueba_id(client)
    r = client.post(f"{BASE}/pruebas/{prueba_id}/comentarios", headers=_h(tok), json={"texto": ""})
    assert r.status_code == 422  # min_length de pydantic


def test_asistente_sin_proveedor_no_rompe(client, monkeypatch):
    monkeypatch.setattr(providers, "available_provider", lambda: None)
    tok, prueba_id = _prueba_id(client)
    r = client.post(f"{BASE}/pruebas/{prueba_id}/comentarios", headers=_h(tok),
                    json={"texto": "Explícame el resultado", "asistente": True})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["asistente_error"]  # avisa que no hay proveedor
    assert data["respuesta_asistente"] is None
    # el comentario del usuario igual quedó guardado
    assert sum(1 for e in data["conversacion"] if e["tipo"] == "comentario") == 1


def test_asistente_responde_en_el_hilo(client, monkeypatch):
    monkeypatch.setattr(providers, "available_provider", lambda: "local")
    monkeypatch.setattr(
        consola.providers, "chat_complete",
        lambda mensajes, system=None: providers.LLMResponse(
            content="El ajuste surge del recálculo del deterioro.", model="auditia-local",
            tokens_in=10, tokens_out=8),
    )
    tok, prueba_id = _prueba_id(client)
    r = client.post(f"{BASE}/pruebas/{prueba_id}/comentarios", headers=_h(tok),
                    json={"texto": "¿De dónde sale el ajuste?", "asistente": True})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["asistente_error"] is None
    assert data["respuesta_asistente"]["modelo"] == "auditia-local"
    comentarios = [e for e in data["conversacion"] if e["tipo"] == "comentario"]
    assert len(comentarios) == 2  # pregunta del usuario + respuesta del asistente
    asistente = comentarios[-1]
    assert asistente["es_asistente"] is True
    assert "El ajuste surge del recálculo" in asistente["texto"]
    assert consola.DISCLAIMER in asistente["texto"]  # disclaimer obligatorio
