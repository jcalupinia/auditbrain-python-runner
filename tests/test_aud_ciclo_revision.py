"""E9 por HTTP: revisión, puntos, aprobación inmutable, papel final, versiones,
plantilla, contexto con alcance, bandejas, encerar y eliminar."""
import pytest

from tests.test_aud_ciclo_ejecucion import _navegador, _validada
from tests.test_aud_ciclo_evidencia import _leer
from tests.test_aud_ciclo_http import BASE, FICHA, _accion, _prueba_vnr
from tests.test_aud_niif_fichas import _h


@pytest.fixture(autouse=True)
def disco_temporal(tmp_path, monkeypatch):
    monkeypatch.setenv("AUD_CICLO_DIR", str(tmp_path / "aud_pruebas"))
    monkeypatch.setenv("AUD_CICLO_MIN_LIBRE_MB", "0")


def _analizada(client):
    tok, p = _validada(client)
    p = _accion(client, tok, p, "configure", {"basis": "Lista de precios vigente al corte."}).json()
    p = _accion(client, tok, p, "approve_methodology").json()
    p = _accion(client, tok, p, "execute", {"navegador": _navegador(p)}).json()
    p = _accion(client, tok, p, "analyze").json()
    assert p["estado"] == "RESULTADOS_ANALIZADOS", p
    return tok, p


def _papel(client, tok, p, xlsx=b"PK\x03\x04excel", html=b"<!doctype html><html><body>papel</body></html>"):
    return client.post(f"{BASE}/pruebas/{p['id']}/papel", headers=_h(tok), data={"revision": str(p["revision"])},
                       files={"xlsx": ("p.xlsx", xlsx), "html": ("p.html", html)})


def test_revision_aprobacion_y_papel_inmutable(client):
    tok, p = _analizada(client)

    r = _accion(client, tok, p, "submit", {"analysis": "Dos partidas bajo costo.", "conclusion": " "})
    assert r.status_code == 400 and "conclusión preliminar antes de enviar" in r.json()["detail"]
    p = _accion(client, tok, p, "submit", {"analysis": "Dos partidas bajo costo.", "conclusion": "Ajuste de 82,00."}).json()
    assert p["estado"] == "EN_REVISION"

    # Puntos de revisión: abrir, responder, resolver.
    assert _accion(client, tok, p, "add_note", {"comment": " "}).status_code == 400
    p = _accion(client, tok, p, "add_note", {"section": "Cálculos", "comment": "Sustente el precio de la partida 0003."}).json()
    nota = p["registro"]["notes"][0]
    assert nota["status"] == "ABIERTO"
    r = _accion(client, tok, p, "resolve_note", {"noteId": nota["id"]})
    assert r.status_code == 400 and "punto respondido" in r.json()["detail"]
    aprobar = {"conclusion": "Se propone ajuste de 82,00.", "conclusionReviewed": True,
               "exceptionReview": "Las dos excepciones son deterioro por precio; se registran."}
    r = _accion(client, tok, p, "approve", aprobar)
    assert r.status_code == 400 and "Cierre bloqueado" in r.json()["detail"]
    p = _accion(client, tok, p, "respond_note", {"noteId": nota["id"], "response": "Factura 1234 posterior al corte."}).json()
    p = _accion(client, tok, p, "resolve_note", {"noteId": nota["id"]}).json()
    assert p["registro"]["notes"][0]["status"] == "RESUELTO"

    # Aprobación: conclusión confirmada y excepciones evaluadas.
    r = _accion(client, tok, p, "approve", {**aprobar, "conclusionReviewed": False})
    assert r.status_code == 400 and "confirme la conclusión final" in r.json()["detail"]
    r = _accion(client, tok, p, "approve", {**aprobar, "exceptionReview": "ok"})
    assert r.status_code == 400 and "evaluación de excepciones" in r.json()["detail"]
    p = _accion(client, tok, p, "approve", aprobar).json()
    assert p["estado"] == "APROBADO" and p["registro"]["approvedBy"] and p["registro"]["approvedAt"]

    # Inmutable: ninguna acción del circuito ni la edición del contexto.
    r = _accion(client, tok, p, "save_analysis", {"analysis": "x"})
    assert r.status_code == 400 and "inmutable" in r.json()["detail"]
    r = _accion(client, tok, p, "edit_context", {"context": FICHA, "scope": "one"})
    assert r.status_code == 409 and "Cree otra versión" in r.json()["detail"]

    # Papel final: se guarda una sola vez, con su huella.
    assert _papel(client, tok, p, xlsx=b"no es excel").status_code == 400
    r = _papel(client, tok, p)
    assert r.status_code == 200, r.text
    p = _leer(client, tok, p)
    assert set(p["registro"]["artifacts"]) == {"xlsx", "html"}
    assert len(p["papeles"]) == 2 and all(len(x["sha256"]) == 64 for x in p["papeles"])
    assert all(a["requerimiento"] != "PAPEL" for a in p["archivos"]), "el papel no es evidencia del cliente"
    bajado = client.get(f"{BASE}/pruebas/{p['id']}/archivos/{p['registro']['artifacts']['xlsx']['id']}", headers=_h(tok))
    assert bajado.content == b"PK\x03\x04excel"
    r = _papel(client, tok, p)
    assert r.status_code == 400 and "no se reemplaza" in r.json()["detail"]

    # Bandeja: aparece como aprobada.
    fila = next(x for x in client.get(f"{BASE}/bandejas", headers=_h(tok)).json() if x["id"] == p["id"])
    assert fila["estado"] == "APROBADO" and fila["cliente"] and fila["notas_abiertas"] == 0

    # Nueva versión: solo una sucesora; no se elimina la madre antes que la hija.
    n = _accion(client, tok, p, "new_version").json()
    assert n["version"] == 2 and n["estado"] == "PRUEBA_SELECCIONADA" and n["id"] != p["id"]
    assert not any(s["verified"] for s in n["registro"]["sources"])
    p = _leer(client, tok, p)
    assert p["sucesora"] == n["id"]
    r = _accion(client, tok, p, "new_version")
    assert r.status_code == 400 and "sucesora" in r.json()["detail"]
    cliente = p["registro"]["engagement"]["client"]
    r = _accion(client, tok, p, "delete", {"confirmClient": cliente, "deleteConfirmed": True, "approvedConfirmed": True})
    assert r.status_code == 409 and "Elimine primero la más reciente" in r.json()["detail"]
    assert _accion(client, tok, n, "delete", {"confirmClient": cliente, "deleteConfirmed": True}).json()["deleted"] is True
    r = _accion(client, tok, p, "delete", {"confirmClient": cliente, "deleteConfirmed": True})
    assert r.status_code == 400 and "Confírmelo expresamente" in r.json()["detail"]
    r = _accion(client, tok, p, "delete", {"confirmClient": "Otro", "deleteConfirmed": True, "approvedConfirmed": True})
    assert r.status_code == 400 and "nombre del cliente" in r.json()["detail"]
    assert _accion(client, tok, p, "delete", {"confirmClient": cliente, "deleteConfirmed": True, "approvedConfirmed": True}).json()["deleted"]
    assert client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(tok)).status_code == 404


def test_papel_declarativo_guarda_tambien_word_y_powerpoint(client):
    """Una prueba declarativa guarda su papel completo: Excel, HTML, Word y PowerPoint."""
    tok, p = _analizada(client)
    p = _accion(client, tok, p, "submit", {"analysis": "Dos partidas bajo costo.", "conclusion": "Ajuste de 82,00."}).json()
    p = _accion(client, tok, p, "approve", {"conclusion": "Se propone ajuste de 82,00.", "conclusionReviewed": True,
                                             "exceptionReview": "Las dos excepciones son deterioro por precio; se registran."}).json()
    assert p["estado"] == "APROBADO", p

    def subir(docx=b"PK\x03\x04word", pptx=b"PK\x03\x04ppt"):
        return client.post(f"{BASE}/pruebas/{p['id']}/papel", headers=_h(tok), data={"revision": str(p["revision"])},
                           files={"xlsx": ("p.xlsx", b"PK\x03\x04excel"), "html": ("p.html", b"<!doctype html><html></html>"),
                                  "docx": ("p.docx", docx), "pptx": ("p.pptx", pptx)})

    r = subir(docx=b"no es word")
    assert r.status_code == 400 and "Word" in r.json()["detail"]
    r = subir(pptx=b"no es ppt")
    assert r.status_code == 400 and "PowerPoint" in r.json()["detail"]
    assert subir().status_code == 200
    p = _leer(client, tok, p)
    arts = p["registro"]["artifacts"]
    assert set(arts) == {"xlsx", "html", "docx", "pptx"}
    assert len(p["papeles"]) == 4 and all(len(x["sha256"]) == 64 for x in p["papeles"])
    for ext, esperado in (("docx", b"PK\x03\x04word"), ("pptx", b"PK\x03\x04ppt")):
        bajado = client.get(f"{BASE}/pruebas/{p['id']}/archivos/{arts[ext]['id']}", headers=_h(tok))
        assert bajado.content == esperado and arts[ext]["nombre"].endswith(f".{ext}")


def test_devolver_a_datos_reabre_los_puntos(client):
    tok, p = _analizada(client)
    p = _accion(client, tok, p, "submit", {"analysis": "a", "conclusion": "c"}).json()
    p = _accion(client, tok, p, "add_note", {"comment": "Revise el mapeo."}).json()
    r = _accion(client, tok, p, "return_to_data", {"comment": "corto"})
    assert r.status_code == 400 and "motivo de reapertura" in r.json()["detail"]
    p = _accion(client, tok, p, "return_to_data", {"comment": "El mapeo tomó la hoja equivocada."}).json()
    assert p["estado"] == "DOCUMENTACION_RECIBIDA"
    assert p["registro"]["run"] is None and p["registro"]["reconciliation"] is None
    assert p["registro"]["notes"][0]["status"] == "ABIERTO" and p["registro"]["notes"][0]["reopenedAt"]


def test_encerar_deja_la_prueba_limpia(client):
    tok, p = _analizada(client)
    cliente = p["registro"]["engagement"]["client"]
    r = _accion(client, tok, p, "erase", {"confirmClient": cliente})
    assert r.status_code == 400 and "Confirme el cliente" in r.json()["detail"]
    p = _accion(client, tok, p, "erase", {"confirmClient": cliente, "downloadConfirmed": True}).json()
    assert p["estado"] == "PRUEBA_SELECCIONADA" and p["registro"]["rows"] == [] and p["registro"]["erasedAt"]
    p = _leer(client, tok, p)
    assert p["archivos"] == [] and [e["accion"] for e in p["eventos"]] == ["erase"]


def test_plantilla_exige_programa_aprobado_y_sustento(client):
    tok, p = _validada(client)
    r = _accion(client, tok, p, "approve_template", {"basis": " "})
    assert r.status_code == 400 and "Sustente la metodología" in r.json()["detail"]
    p = _accion(client, tok, p, "approve_template", {"basis": "Metodología VNR de la firma, lista de precios."}).json()
    assert p["registro"]["templateApproved"]["parameters"]["basis"].startswith("Metodología")
    assert p["estado"] == "DOCUMENTACION_VALIDADA", "la plantilla no mueve el circuito"


def test_editar_la_ficha_con_alcance(client):
    tok, a = _validada(client)
    pid = a["project_id"]
    # Las pruebas creadas con la ficha compartida («all») reciben los cambios de alcance «todas».
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json={**FICHA, "reuseScope": "all"}).status_code == 200
    b = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "vnr"}).json()
    c = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "pce"}).json()
    nueva = {**FICHA, "preparer": "Carla Nueva", "reuseScope": "one"}

    # Solo esta: vuelve a empezar; las demás no cambian.
    r = _accion(client, tok, a, "edit_context", {"context": nueva, "scope": "one"})
    assert r.status_code == 200, r.text
    a = _leer(client, tok, a)
    assert a["estado"] == "PRUEBA_SELECCIONADA" and a["registro"]["engagement"]["preparer"] == "Carla Nueva"
    assert a["registro"]["rows"] == [] and a["registro"]["contextOverride"] is True
    assert _leer(client, tok, b)["registro"]["engagement"]["preparer"] != "Carla Nueva"

    # Varias: la selección debe incluir esta prueba y ser del encargo.
    r = _accion(client, tok, a, "edit_context", {"context": nueva, "scope": "selected", "toolIds": [b["id"]]})
    assert r.status_code == 400 and "esta prueba y las adicionales" in r.json()["detail"]
    r = _accion(client, tok, a, "edit_context", {"context": nueva, "scope": "selected", "toolIds": [a["id"], 999999]})
    assert r.status_code == 400 and "de este encargo" in r.json()["detail"]
    # Una PCE no admite PYMES.
    pymes = {**nueva, "framework": "NIIF para las PYMES"}
    r = _accion(client, tok, a, "edit_context", {"context": pymes, "scope": "selected", "toolIds": [a["id"], c["id"]]})
    assert r.status_code == 400 and "PCE" in r.json()["detail"]

    # Todas: incluye las que no tienen ficha propia y actualiza la ficha del proyecto.
    a = _leer(client, tok, a)
    r = _accion(client, tok, a, "edit_context", {"context": {**nueva, "reviewer": "Rita Todas"}, "scope": "all"})
    assert r.status_code == 200, r.text
    assert _leer(client, tok, b)["registro"]["engagement"]["reviewer"] == "Rita Todas"
    assert client.get(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok)).json()["ficha"]["reviewer"] == "Rita Todas"
