"""Tests de Fase 2 · M1 — Contexto operativo (orgs, clientes, proyectos).

Cubre:
- Bootstrap de organización por defecto y asignación legacy.
- GET /me/context devuelve la org y la lista de proyectos visibles.
- PUT /me/context fija el proyecto activo (admin todo, user sólo sus
  proyectos como member).
- Aislamiento estricto entre organizaciones (no leak entre tenants).
- Solo admin crea clientes y proyectos.
"""

import uuid

import pytest

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.context import service as ctx_service
from backend.app.context.models import Organization
from backend.app.db.session import SessionLocal, init_db


@pytest.fixture(autouse=True)
def _db():
    init_db()
    yield


def _mk_user(role: Role = Role.user, organization_id: int | None = None):
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        u = auth_service.create_user(db, email=email, password=password, role=role)
        if organization_id is not None:
            u.organization_id = organization_id
            db.add(u)
            db.commit()
    finally:
        db.close()
    return email, password


def _login(client, email, password):
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def test_default_org_bootstrap_idempotent():
    db = SessionLocal()
    try:
        org1 = ctx_service.get_or_create_default_organization(db)
        org2 = ctx_service.get_or_create_default_organization(db)
        assert isinstance(org1, Organization)
        assert org1.id == org2.id
        assert org1.slug == ctx_service.DEFAULT_ORG_SLUG
    finally:
        db.close()


def test_legacy_users_assigned_to_default_org(client):
    """Cualquier usuario sin organization_id se migra al bootstrap."""
    email, pw = _mk_user(Role.user)
    db = SessionLocal()
    try:
        org = ctx_service.get_or_create_default_organization(db)
        n = ctx_service.assign_legacy_users_to_default_org(db)
        # El usuario recién creado no tenía org -> al menos 1 migrado.
        assert n >= 1
        from backend.app.auth.service import get_user_by_email

        u = get_user_by_email(db, email)
        assert u.organization_id == org.id
    finally:
        db.close()


def test_me_context_returns_org_and_projects_list(client):
    email, pw = _mk_user(Role.user)
    tok = _login(client, email, pw)
    r = client.get("/api/v1/me/context", headers=_h(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["organization"] is not None
    assert body["organization"]["slug"] == ctx_service.DEFAULT_ORG_SLUG
    # Política de firma: los operadores (rol user) ven los proyectos de su
    # organización (igual que el admin). No hay activo por defecto.
    assert isinstance(body["projects"], list)
    assert body["active_project"] is None


def test_operator_can_create_clients(client):
    # Nueva política de firma: los operadores (rol user) pueden crear clientes
    # y proyectos, igual que el admin. La excepción admin-only es crear
    # usuarios de portal de clientes y operadores (staff_portal / auth).
    user_email, user_pw = _mk_user(Role.user)
    user_tok = _login(client, user_email, user_pw)
    r = client.post(
        "/api/v1/context/clients",
        headers=_h(user_tok),
        json={"name": "Cliente Demo"},
    )
    assert r.status_code == 201, r.text


def test_admin_creates_client_and_project_and_user_is_scoped(client):
    admin_email, admin_pw = _mk_user(Role.admin)
    admin_tok = _login(client, admin_email, admin_pw)

    # Crear cliente
    r = client.post(
        "/api/v1/context/clients",
        headers=_h(admin_tok),
        json={"name": "ACME Corp", "tax_id": "B-0000", "sector": "Industria"},
    )
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    # Crear proyecto
    r = client.post(
        "/api/v1/context/projects",
        headers=_h(admin_tok),
        json={
            "client_id": client_id,
            "name": "Auditoría 2026",
            "module_code": "AUD",
            "period_label": "AF 2026",
        },
    )
    assert r.status_code == 201, r.text
    project = r.json()
    assert project["client_id"] == client_id
    assert project["module_code"] == "AUD"

    # Admin lo ve en su lista de proyectos
    r = client.get("/api/v1/context/projects", headers=_h(admin_tok))
    assert r.status_code == 200
    assert any(p["id"] == project["id"] for p in r.json())

    # Un operador (rol user) en la MISMA org VE el proyecto aunque no sea
    # miembro (nueva política: operadores = admin para acceso a proyectos).
    user_email, user_pw = _mk_user(Role.user)
    user_tok = _login(client, user_email, user_pw)
    r = client.get("/api/v1/context/projects", headers=_h(user_tok))
    assert r.status_code == 200
    assert any(p["id"] == project["id"] for p in r.json())


def test_operator_can_set_same_org_but_not_cross_org_project_active(client):
    # Admin de la org por defecto crea un proyecto (sin invitar al operador).
    admin_email, admin_pw = _mk_user(Role.admin)
    admin_tok = _login(client, admin_email, admin_pw)
    r = client.post(
        "/api/v1/context/clients", headers=_h(admin_tok), json={"name": "X"}
    )
    cid = r.json()["id"]
    r = client.post(
        "/api/v1/context/projects",
        headers=_h(admin_tok),
        json={"client_id": cid, "name": "Privado"},
    )
    same_org_pid = r.json()["id"]

    # Operador de la MISMA org: SÍ puede fijarlo activo (nueva política).
    user_email, user_pw = _mk_user(Role.user)
    user_tok = _login(client, user_email, user_pw)
    r = client.put(
        "/api/v1/me/context", headers=_h(user_tok),
        json={"project_id": same_org_pid},
    )
    assert r.status_code == 200, r.text

    # Proyecto de OTRA organización: el operador NO puede fijarlo activo (403).
    db = SessionLocal()
    try:
        org_b = Organization(name="Org B", slug=f"orgb-{uuid.uuid4().hex[:6]}")
        db.add(org_b)
        db.commit()
        db.refresh(org_b)
        org_b_id = org_b.id
    finally:
        db.close()
    admin_b_email, admin_b_pw = _mk_user(Role.admin, organization_id=org_b_id)
    b_tok = _login(client, admin_b_email, admin_b_pw)
    r = client.post("/api/v1/context/clients", headers=_h(b_tok), json={"name": "CB"})
    cb = r.json()["id"]
    r = client.post(
        "/api/v1/context/projects", headers=_h(b_tok),
        json={"client_id": cb, "name": "Ajeno"},
    )
    cross_pid = r.json()["id"]
    r = client.put(
        "/api/v1/me/context", headers=_h(user_tok),
        json={"project_id": cross_pid},
    )
    assert r.status_code == 403


def test_cross_org_isolation(client):
    """Un cliente creado en org A no es visible para un admin de org B."""
    # Org A: admin por defecto
    admin_a_email, admin_a_pw = _mk_user(Role.admin)
    a_tok = _login(client, admin_a_email, admin_a_pw)
    r = client.post(
        "/api/v1/context/clients", headers=_h(a_tok), json={"name": "Cliente A"}
    )
    assert r.status_code == 201

    # Org B: crear org distinta y asignar a un admin B
    db = SessionLocal()
    try:
        org_b = Organization(name="Org B", slug=f"orgb-{uuid.uuid4().hex[:6]}")
        db.add(org_b)
        db.commit()
        db.refresh(org_b)
        org_b_id = org_b.id
    finally:
        db.close()
    admin_b_email, admin_b_pw = _mk_user(Role.admin, organization_id=org_b_id)
    b_tok = _login(client, admin_b_email, admin_b_pw)

    r = client.get("/api/v1/context/clients", headers=_h(b_tok))
    assert r.status_code == 200
    names = [c["name"] for c in r.json()]
    assert "Cliente A" not in names
