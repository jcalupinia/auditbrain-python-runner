"""F2b.2 — La API de gobernanza de punta a punta (el gate que IMPIDE).

Criterios del diseño F2b probados aquí, vía HTTP:
- **P1**  el gate: ``export`` sin aprobar ⇒ 409 y el body NO trae el artefacto.
- **P3**  aislamiento: el usuario B no ve ni toca los planes de A ⇒ 404.
- **P5**  irreversible: aprobar algo ya rechazado ⇒ 409.
- **P6**  rechazo con motivo: ``reject`` sin ``reason`` ⇒ 422.
- **P9**  deny-by-default: sin ``FORGE_CONSOLE`` (y sin ser operador) ⇒ 403.
- Idempotencia de ``POST /plans`` (mismo ⇒ 200; distinto ⇒ 409).

Se autentica como **operador** (admin), que entra al router cliente sin device y
bypasea el entitlement — el mismo camino que usará el CLI en F2b.3.
"""

import uuid

from backend.app.auth import service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db

BASE = "/api/v1/client/forge"


def _mk_operator():
    init_db()
    email = f"gov-op-{uuid.uuid4().hex[:8]}@example.com"
    pwd = "Sup3rSecret!"
    db = SessionLocal()
    try:
        service.create_user(db, email=email, password=pwd, role=Role.admin)
    finally:
        db.close()
    return email, pwd


def _login(client, email, pwd):
    r = client.post("/api/v1/auth/login", data={"username": email, "password": pwd})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _auth(client):
    email, pwd = _mk_operator()
    return _login(client, email, pwd)


def _plan_payload():
    return {
        "plan_id": f"plan-{uuid.uuid4().hex[:12]}",
        "goal": "añadir login",
        "confidence": "alta",
        "model": "fallback",
        "ai_invoked": False,
        "tasks": [
            {"id": "t1", "description": "crear endpoint", "acceptance": "responde 200"},
            {"id": "t2", "description": "tests", "acceptance": "verdes"},
        ],
    }


# --- Flujo completo + el gate ---------------------------------------------------


def test_flujo_push_review_approve_export(client):
    h = _auth(client)
    payload = _plan_payload()
    pid = payload["plan_id"]

    r = client.post(f"{BASE}/plans", json=payload, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["created"] is True

    # review: todo pendiente
    r = client.get(f"{BASE}/plans/{pid}/review", headers=h)
    assert r.status_code == 200
    assert {t["estado"] for t in r.json()["tasks"]} == {"pending"}

    # P1: el gate impide exportar sin nada aprobado (409, sin artefacto)
    r = client.post(f"{BASE}/plans/{pid}/export", headers=h)
    assert r.status_code == 409
    assert "approved" not in r.json()  # no viene el artefacto

    # aprobar t1
    r = client.post(f"{BASE}/plans/{pid}/tasks/t1/approve", json={}, headers=h)
    assert r.status_code == 200, r.text

    # export: sale t1, t2 queda excluida
    r = client.post(f"{BASE}/plans/{pid}/export", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [t["id"] for t in body["approved"]] == ["t1"]
    assert [e["task_id"] for e in body["excluded"]] == ["t2"]

    # audit: la cadena verifica y guarda identidad real
    r = client.get(f"{BASE}/plans/{pid}/audit", headers=h)
    assert r.status_code == 200
    a = r.json()
    assert a["verified"] is True
    assert a["decisions"][0]["action"] == "approve"
    assert "@" in a["decisions"][0]["actor"]  # actor real (email), no autodeclarado


# --- Idempotencia ---------------------------------------------------------------


def test_idempotencia_mismo_plan_devuelve_200(client):
    h = _auth(client)
    payload = _plan_payload()
    assert client.post(f"{BASE}/plans", json=payload, headers=h).status_code == 201
    r = client.post(f"{BASE}/plans", json=payload, headers=h)
    assert r.status_code == 200  # ya existía, idéntico
    assert r.json()["created"] is False


def test_idempotencia_mismo_id_distinto_contenido_409(client):
    h = _auth(client)
    payload = _plan_payload()
    assert client.post(f"{BASE}/plans", json=payload, headers=h).status_code == 201
    payload2 = {**payload, "goal": "otra cosa distinta"}
    r = client.post(f"{BASE}/plans", json=payload2, headers=h)
    assert r.status_code == 409


# --- P6: rechazo con motivo obligatorio ----------------------------------------


def test_p6_reject_sin_reason_es_422(client):
    h = _auth(client)
    payload = _plan_payload()
    pid = payload["plan_id"]
    client.post(f"{BASE}/plans", json=payload, headers=h)
    r = client.post(f"{BASE}/plans/{pid}/tasks/t1/reject", json={}, headers=h)
    assert r.status_code == 422  # falta 'reason'
    r = client.post(
        f"{BASE}/plans/{pid}/tasks/t1/reject", json={"reason": "faltan pruebas"}, headers=h
    )
    assert r.status_code == 200, r.text


# --- P5: aprobar algo ya rechazado ⇒ 409 ---------------------------------------


def test_p5_aprobar_una_tarea_rechazada_es_409(client):
    h = _auth(client)
    payload = _plan_payload()
    pid = payload["plan_id"]
    client.post(f"{BASE}/plans", json=payload, headers=h)
    assert client.post(
        f"{BASE}/plans/{pid}/tasks/t1/reject", json={"reason": "no"}, headers=h
    ).status_code == 200
    r = client.post(f"{BASE}/plans/{pid}/tasks/t1/approve", json={}, headers=h)
    assert r.status_code == 409  # el rechazo es terminal


# --- P3: aislamiento por dueño --------------------------------------------------


def test_p3_un_operador_no_ve_por_owner_pero_el_cliente_si_se_aisla(client):
    """Dos clientes distintos: B no ve el plan de A (404)."""
    from backend.app.client_portal.service import create_portal_user
    from backend.app.client_portal import entitlements as ent
    from backend.app.context.models import Client, Organization

    init_db()
    db = SessionLocal()
    try:
        def _mk_client():
            sfx = uuid.uuid4().hex[:10]  # único: el test debe ser hermético
            org = Organization(name=f"O{sfx}", slug=f"o-{sfx}", is_active=True)
            db.add(org); db.commit(); db.refresh(org)
            cli = Client(organization_id=org.id, name=f"C{sfx}", is_active=True)
            db.add(cli); db.commit(); db.refresh(cli)
            u, pwd = create_portal_user(db, client_id=cli.id, email=f"c-{sfx}@ex.com")
            ent.set_user_entitlements(db, u.id, {"FORGE_CONSOLE"})
            return u.email, pwd
        a_email, a_pwd = _mk_client()
        b_email, b_pwd = _mk_client()
    finally:
        db.close()

    def _client_auth(email, pwd):
        r = client.post("/api/v1/client/auth/login", data={"username": email, "password": pwd})
        assert r.status_code == 200, r.text
        did = r.cookies.get("device_id")
        return {"Authorization": f"Bearer {r.json()['access_token']}"}, (
            {"device_id": did} if did else {}
        )

    ha, ca = _client_auth(a_email, a_pwd)
    payload = _plan_payload()
    pid = payload["plan_id"]
    r = client.post(f"{BASE}/plans", json=payload, headers=ha, cookies=ca)
    assert r.status_code == 201, r.text

    hb, cb = _client_auth(b_email, b_pwd)
    # B no ve el plan de A: 404, no 403 (no se filtra la existencia)
    assert client.get(f"{BASE}/plans/{pid}/review", headers=hb, cookies=cb).status_code == 404
    assert client.post(
        f"{BASE}/plans/{pid}/tasks/t1/approve", json={}, headers=hb, cookies=cb
    ).status_code == 404


# --- P9: deny-by-default --------------------------------------------------------


def test_p9_sin_entitlement_forge_console_es_403(client):
    from backend.app.client_portal.service import create_portal_user
    from backend.app.context.models import Client, Organization

    init_db()
    db = SessionLocal()
    try:
        sfx = uuid.uuid4().hex[:8]
        org = Organization(name=f"O{sfx}", slug=f"o-{sfx}", is_active=True)
        db.add(org); db.commit(); db.refresh(org)
        cli = Client(organization_id=org.id, name=f"C{sfx}", is_active=True)
        db.add(cli); db.commit(); db.refresh(cli)
        u, pwd = create_portal_user(db, client_id=cli.id, email=f"noent-{sfx}@ex.com")
        # SIN conceder FORGE_CONSOLE
    finally:
        db.close()

    r = client.post("/api/v1/client/auth/login", data={"username": u.email, "password": pwd})
    assert r.status_code == 200, r.text
    did = r.cookies.get("device_id")
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    c = {"device_id": did} if did else {}
    assert client.get(f"{BASE}/plans", headers=h, cookies=c).status_code == 403
