"""E6 por HTTP: ficha del encargo, crear una prueba y llevar su programa a aprobado.

Las reglas en sí están en ``test_aud_ciclo_reglas.py`` (contra el sitio). Aquí se
prueba lo que añade el portal: permisos, pertenencia del proyecto, concurrencia,
bitácora, y que la ficha NIIF solo se pueda usar con una definición que corrió.
"""
import uuid

from backend.app.auth.models import Role
from backend.app.context import service as ctx
from backend.app.db.session import SessionLocal
from tests.test_aud_niif_fichas import _crear, _h, _mk_user, _login
from tests.test_aud_niif_motor import FILA, NIIF16

BASE = "/api/v1/aud/ciclo"

FICHA = {
    "client": "Empresa Ejemplo S.A.", "ruc": "1791961048001", "activity": "Comercio", "year": 2025,
    "cutoff": "2025-12-31", "preparer": "Ana Preparadora", "reviewer": "Luis Revisor",
    "firm": "Audit Consulting", "framework": "NIIF completas", "country": "Ecuador",
    "currency": "USD", "visit": "Final", "edition": "2025", "adoption": "", "reuseScope": "one",
}


def _staff_con_proyecto(client, modulo="AUD", organizacion_propia=False):
    """Operador con un proyecto. Por defecto el portal pone a todos en la
    organización por defecto; ``organizacion_propia`` crea otra, para probar el
    aislamiento entre organizaciones."""
    email, pw = _mk_user(Role.user)
    db = SessionLocal()
    try:
        from backend.app.auth.models import User
        from backend.app.context.models import Organization
        u = db.query(User).filter(User.email == email).one()
        if organizacion_propia:
            tag = uuid.uuid4().hex[:8]
            org = Organization(name=f"Otra firma {tag}", slug=f"otra-{tag}")
            db.add(org)
            db.commit()
            u.organization_id = org.id
            db.commit()
        else:
            ctx.ensure_user_has_organization(db, u)
        db.refresh(u)
        c = ctx.create_client(db, name=f"Cliente {uuid.uuid4().hex[:6]}", organization_id=u.organization_id)
        p = ctx.create_project(db, client_id=c.id, name="Auditoría 2025", module_code=modulo, organization_id=u.organization_id)
        pid = p.id
    finally:
        db.close()
    return _login(client, email, pw), pid


def _prueba_vnr(client, tok, pid):
    assert client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA).status_code == 200
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "vnr"})
    assert r.status_code == 201, r.text
    return r.json()


def _accion(client, tok, prueba, accion, datos=None):
    return client.post(f"{BASE}/pruebas/{prueba['id']}/acciones", headers=_h(tok),
                       json={"accion": accion, "revision": prueba["revision"], "datos": datos or {}})


# --- permisos y pertenencia --------------------------------------------------

def test_sin_sesion_no_hay_acceso(client):
    assert client.get(f"{BASE}/herramientas").status_code in (401, 403)
    assert client.get(f"{BASE}/proyectos/1/ficha").status_code in (401, 403)


def test_un_proyecto_de_otra_organizacion_no_existe_para_mi(client):
    tok_a, pid_a = _staff_con_proyecto(client)
    tok_b, _ = _staff_con_proyecto(client, organizacion_propia=True)
    assert client.get(f"{BASE}/proyectos/{pid_a}/ficha", headers=_h(tok_b)).status_code == 404


def test_solo_proyectos_aud(client):
    tok, pid = _staff_con_proyecto(client, modulo="TAX")
    r = client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA)
    assert r.status_code == 400 and "módulo AUD" in r.json()["detail"]


# --- ficha del encargo -------------------------------------------------------

def test_la_ficha_se_valida_con_la_regla_del_sitio(client):
    tok, pid = _staff_con_proyecto(client)
    assert client.get(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok)).json() == {"ficha": None}
    r = client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json={**FICHA, "ruc": "123"})
    assert r.status_code == 400 and "RUC de 13 dígitos" in r.json()["detail"]
    r = client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA)
    assert r.status_code == 200 and r.json()["ficha"]["year"] == 2025


def test_sin_ficha_no_se_crea_la_prueba(client):
    tok, pid = _staff_con_proyecto(client)
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "vnr"})
    assert r.status_code == 400 and "ficha del encargo" in r.json()["detail"]


def test_pce_solo_con_niif_completas(client):
    tok, pid = _staff_con_proyecto(client)
    client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json={**FICHA, "framework": "NIIF para las PYMES"})
    r = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": "pce"})
    assert r.status_code == 400 and "NIIF completas" in r.json()["detail"]


# --- creación y programa -----------------------------------------------------

def test_la_prueba_nace_como_en_el_sitio(client):
    tok, pid = _staff_con_proyecto(client)
    p = _prueba_vnr(client, tok, pid)
    assert p["estado"] == "PRUEBA_SELECCIONADA"
    assert p["registro"]["methodologyVersion"] == "1.3.2"
    assert [s["category"] for s in p["registro"]["sources"]] == ["NIIF", "NIA"]
    lista = client.get(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok)).json()
    assert [x["id"] for x in lista] == [p["id"]]


def test_programa_de_punta_a_punta(client):
    tok, pid = _staff_con_proyecto(client)
    p = _prueba_vnr(client, tok, pid)

    r = _accion(client, tok, p, "generate_program")
    assert r.status_code == 400 and "fuentes oficiales" in r.json()["detail"]

    p = _accion(client, tok, p, "research").json()
    p = _accion(client, tok, p, "generate_program").json()
    assert p["estado"] == "PROGRAMA_PROPUESTO"
    assert [x["code"] for x in p["registro"]["program"]] == ["VNR-01", "VNR-02", "VNR-03"]

    programa, fuentes = p["registro"]["program"], p["registro"]["sources"]
    # Sin verificar las fuentes no se aprueba.
    r = _accion(client, tok, p, "approve_program", {"program": programa, "sources": fuentes})
    assert r.status_code == 400 and "vigencia de la fuente NIIF" in r.json()["detail"]

    fuentes[0].update(verified=True, section="par. 9 y 28-33", date="vigente 2025", procedures=["VNR-01", "VNR-02"])
    fuentes[1].update(verified=True, document="NIA 540", section="par. 13", date="vigente 2025", procedures=["VNR-03"])
    p = _accion(client, tok, p, "approve_program", {"program": programa, "sources": fuentes}).json()
    assert p["estado"] == "PROGRAMA_APROBADO"
    assert all(x["state"] == "APROBADO" and x["source"]["verified"] for x in p["registro"]["program"])

    detalle = client.get(f"{BASE}/pruebas/{p['id']}", headers=_h(tok)).json()
    assert [e["accion"] for e in detalle["eventos"]] == ["create", "research", "generate_program", "approve_program"]
    assert detalle["eventos"][-1]["estado_nuevo"] == "PROGRAMA_APROBADO"


def test_una_revision_vieja_no_pisa_el_trabajo(client):
    tok, pid = _staff_con_proyecto(client)
    p = _prueba_vnr(client, tok, pid)
    assert _accion(client, tok, p, "research").status_code == 200
    r = _accion(client, tok, p, "research")  # misma revisión, ya usada
    assert r.status_code == 409


def test_procedimiento_sin_fuente_verificada(client):
    tok, pid = _staff_con_proyecto(client)
    p = _prueba_vnr(client, tok, pid)
    p = _accion(client, tok, p, "research").json()
    p = _accion(client, tok, p, "generate_program").json()
    fuentes = p["registro"]["sources"]
    fuentes[0].update(verified=True, section="par. 9", date="vigente", procedures=["VNR-01"])
    fuentes[1].update(verified=True, document="NIA 540", section="par. 13", date="vigente", procedures=["VNR-02"])
    r = _accion(client, tok, p, "approve_program", {"program": p["registro"]["program"], "sources": fuentes})
    assert r.status_code == 400 and "procedimiento VNR-03" in r.json()["detail"]


# --- fichas NIIF como herramienta ---------------------------------------------

def test_una_ficha_solo_se_usa_con_definicion_que_corrio(client):
    tok, pid = _staff_con_proyecto(client)
    ficha = _crear(client, tok)
    client.post(f"/api/v1/aud/niif/fichas/{ficha['id']}/estado", headers=_h(tok), json={"estado": "probada"})
    origenes = [h["origen"] for h in client.get(f"{BASE}/herramientas", headers=_h(tok)).json()]
    assert f"ficha:{ficha['id']}" not in origenes, "sin definición guardada no debe ofrecerse"

    rota = dict(NIIF16, rules=[{"key": "x", "label": "x", "op": "potencia", "a": "pago", "b": "#2", "precision": 2}])
    r = client.put(f"{BASE}/fichas/{ficha['id']}/definicion", headers=_h(tok), json={"definicion": rota, "filas": [FILA]})
    assert r.status_code == 400

    r = client.put(f"{BASE}/fichas/{ficha['id']}/definicion", headers=_h(tok), json={"definicion": NIIF16, "filas": [FILA]})
    assert r.status_code == 200
    origenes = [h["origen"] for h in client.get(f"{BASE}/herramientas", headers=_h(tok)).json()]
    assert f"ficha:{ficha['id']}" in origenes

    client.put(f"{BASE}/proyectos/{pid}/ficha", headers=_h(tok), json=FICHA)
    p = client.post(f"{BASE}/proyectos/{pid}/pruebas", headers=_h(tok), json={"origen": f"ficha:{ficha['id']}"}).json()
    assert p["definicion"]["id"] == "custom"
    assert p["definicion"]["name"] == NIIF16["name"]
