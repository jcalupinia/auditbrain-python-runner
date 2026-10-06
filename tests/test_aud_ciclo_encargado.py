"""Encargado (dueño) del encargo y anti-duplicado de empresa (2026-10-06).

- El encargo es colaborativo: los asistentes del mismo equipo acceden a la misma prueba.
- PERO las acciones que afectan a TODO el encargo (reiniciar/encerar, eliminar, editar el
  contexto que resetea las pruebas) y modificar la ficha ya existente son SOLO del encargado
  (quien creó el encargo) o de un admin. Evita que un asistente borre/resetee el trabajo de todos.
- Anti-duplicado: crear un encargo reutiliza la empresa existente si coincide el RUC (o el
  nombre), para que no se repliquen clientes al tipearlos distinto.
"""
import uuid

from backend.app.auth.models import Role
from backend.app.context import service as ctx
from backend.app.context.models import Client
from backend.app.db.session import SessionLocal

from tests.test_aud_ciclo_http import BASE, FICHA
from tests.test_aud_niif_fichas import _h, _mk_user, _login


def _operador(client, role=Role.user):
    """Usuario operador con organización (la por defecto, compartida)."""
    email, pw = _mk_user(role)
    db = SessionLocal()
    try:
        from backend.app.auth.models import User
        u = db.query(User).filter(User.email == email).one()
        ctx.ensure_user_has_organization(db, u)
        db.commit()
    finally:
        db.close()
    return _login(client, email, pw), email


def _crear_encargo(client, tok, ficha=None):
    f = ficha or FICHA
    r = client.post(f"{BASE}/encargos", headers=_h(tok), json={"ficha": f, "cliente": f["client"]})
    assert r.status_code == 201, r.text
    return r.json()


def _crear_prueba(client, tok, pid, origen="vnr"):
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": origen})
    assert r.status_code == 201, r.text
    return r.json()


def test_crear_encargo_fija_encargado(client):
    tok, email = _operador(client)
    enc = _crear_encargo(client, tok)
    r = client.get(f"{BASE}/proyectos/{enc['id']}/ficha", headers=_h(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["encargado"] == email
    assert body["es_encargado"] is True


def test_anti_duplicado_por_ruc(client):
    tok, _ = _operador(client)
    enc1 = _crear_encargo(client, tok, {**FICHA, "client": "ACME Original S.A."})
    # Mismo RUC, nombre tipeado distinto → NO debe crear otra empresa.
    enc2 = _crear_encargo(client, tok, {**FICHA, "client": "ACME tipeada distinta"})
    assert enc1["client_id"] == enc2["client_id"], "mismo RUC debe reutilizar la misma empresa"
    db = SessionLocal()
    try:
        n = db.query(Client).filter(Client.tax_id == FICHA["ruc"]).count()
        assert n == 1, "no debe haber empresas duplicadas con el mismo RUC"
    finally:
        db.close()


def test_asistente_no_puede_encerar_ni_eliminar(client):
    due_tok, _ = _operador(client)
    enc = _crear_encargo(client, due_tok)
    p = _crear_prueba(client, due_tok, enc["id"])
    asis_tok, _ = _operador(client)  # otro operador de la misma organización (asistente)
    # El asistente ve la prueba (colabora)…
    assert client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(asis_tok)).status_code == 200
    # …pero no puede encerar/eliminar/editar contexto.
    for accion in ("erase", "delete", "edit_context"):
        r = client.post(f"{BASE}/pruebas/{p['id']}/acciones", headers=_h(asis_tok),
                        json={"accion": accion, "revision": p["revision"], "datos": {}})
        assert r.status_code == 403, f"{accion}: {r.status_code} {r.text}"


def test_lectura_expone_es_encargado_por_usuario(client):
    due_tok, due_email = _operador(client)
    enc = _crear_encargo(client, due_tok)
    p = _crear_prueba(client, due_tok, enc["id"])
    asis_tok, _ = _operador(client)
    r_due = client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(due_tok)).json()
    r_asis = client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(asis_tok)).json()
    assert r_due["es_encargado"] is True and r_due["encargado"] == due_email
    assert r_asis["es_encargado"] is False and r_asis["encargado"] == due_email


def test_encargado_si_puede_encerar(client):
    due_tok, _ = _operador(client)
    enc = _crear_encargo(client, due_tok)
    p = _crear_prueba(client, due_tok, enc["id"])
    datos = {"confirmClient": FICHA["client"], "downloadConfirmed": True}
    r = client.post(f"{BASE}/pruebas/{p['id']}/acciones", headers=_h(due_tok),
                    json={"accion": "erase", "revision": p["revision"], "datos": datos})
    assert r.status_code == 200, r.text  # el encargado sí puede


def test_admin_puede_aunque_no_sea_encargado(client):
    due_tok, _ = _operador(client)
    enc = _crear_encargo(client, due_tok)
    p = _crear_prueba(client, due_tok, enc["id"])
    admin_tok, _ = _operador(client, role=Role.admin)
    datos = {"confirmClient": FICHA["client"], "downloadConfirmed": True}
    r = client.post(f"{BASE}/pruebas/{p['id']}/acciones", headers=_h(admin_tok),
                    json={"accion": "erase", "revision": p["revision"], "datos": datos})
    assert r.status_code == 200, r.text  # admin override


def test_modificar_ficha_existente_solo_encargado(client):
    due_tok, _ = _operador(client)
    enc = _crear_encargo(client, due_tok)
    asis_tok, _ = _operador(client)
    # El asistente intenta modificar la ficha ya existente → 403.
    r = client.put(f"{BASE}/proyectos/{enc['id']}/ficha", headers=_h(asis_tok), json=FICHA)
    assert r.status_code == 403, r.text
    # El encargado sí puede.
    assert client.put(f"{BASE}/proyectos/{enc['id']}/ficha", headers=_h(due_tok), json=FICHA).status_code == 200
