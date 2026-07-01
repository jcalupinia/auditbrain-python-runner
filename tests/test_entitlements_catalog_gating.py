"""El catálogo del portal filtra por los entitlements del usuario."""
import uuid
import pytest
from backend.app.client_portal.service import create_portal_user
from backend.app.client_portal import entitlements as ent
from backend.app.context.models import Organization, Client
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _login(client, db, granted):
    suffix = uuid.uuid4().hex[:8]
    org = Organization(name=f"ACG-gate-{suffix}", slug=f"acg-gate-{suffix}", is_active=True)
    db.add(org); db.commit(); db.refresh(org)
    cli = Client(organization_id=org.id, name=f"CL-gate-{suffix}", is_active=True)
    db.add(cli); db.commit(); db.refresh(cli)
    user, pwd = create_portal_user(db, client_id=cli.id, email=f"gate-{suffix}@example.com")
    if granted:
        ent.set_user_entitlements(db, user.id, set(granted))
    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    return {"headers": {"Authorization": f"Bearer {token}"},
            "cookies": {"device_id": device_id} if device_id else {}}


def _codes_by_cat(body):
    return {c["id"]: [t["code"] for t in c["tools"]] for c in body["categories"]}


def test_catalog_empty_when_client_has_nothing(client, db_session):
    """Cliente sin nada asignado: catálogo vacío (ninguna sección aparece)."""
    auth = _login(client, db_session, granted=set())
    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = _codes_by_cat(r.json())
    assert by_cat == {}  # ni una sola sección


def test_catalog_shows_only_granted_section(client, db_session):
    """Cliente con ICT_2025: ve SOLO la sección Tributarias; las demás secciones
    (sin herramientas asignadas) NO aparecen."""
    auth = _login(client, db_session, granted={"ICT_2025"})
    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = _codes_by_cat(r.json())
    assert set(by_cat.keys()) == {"TRIBUTARIAS"}  # solo esa sección
    assert by_cat["TRIBUTARIAS"] == ["ICT_2025"]


def test_catalog_operator_sees_all_sections(client, db_session):
    """Un operador (admin/user) ve TODAS las secciones (incl. vacías como
    'Próximamente') y las herramientas, sin depender de entitlements."""
    from backend.app.auth.models import Role
    from backend.app.auth.service import create_user, get_user_by_email
    from backend.app.auth.jwt_tokens import create_access_token

    email = f"op-gate-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.admin
    )
    token = create_access_token(subject=u.email, role="admin")
    r = client.get(
        "/api/v1/client/catalog",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    by_cat = _codes_by_cat(r.json())
    # Ve ICT_2025 y además las secciones vacías siguen presentes (p. ej. NIIF).
    assert "ICT_2025" in by_cat["TRIBUTARIAS"]
    assert "NIIF" in by_cat  # sección vacía visible para operadores
    assert by_cat["NIIF"] == []
