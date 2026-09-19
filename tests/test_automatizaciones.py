"""Tarea 1 del plan de Automatizaciones: categoría y herramientas del catálogo."""

from backend.app.db.session import SessionLocal


def test_categoria_automatizaciones_y_herramientas():
    from backend.app.client_portal.tool_registry import CATEGORIES, TOOLS

    assert any(c["id"] == "AUTOMATIZACIONES" for c in CATEGORIES)
    assert TOOLS["PRESUPUESTOS_IA"].category == "AUTOMATIZACIONES"
    assert TOOLS["PLANIFICACION_IA"].enabled is False


def test_catalog_endpoint_no_muestra_automatizaciones_sin_entitlement(client):
    """Un cliente sin entitlement de AUTOMATIZACIONES no ve esa sección en /catalog,
    aunque el catálogo global ya la registre (calca el patrón de
    test_entitlements_catalog_gating.py)."""
    import uuid

    from backend.app.client_portal.service import create_portal_user
    from backend.app.context.models import Client, Organization

    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        org = Organization(name=f"ACG-aut-{suffix}", slug=f"acg-aut-{suffix}", is_active=True)
        db.add(org)
        db.commit()
        db.refresh(org)
        cli = Client(organization_id=org.id, name=f"CL-aut-{suffix}", is_active=True)
        db.add(cli)
        db.commit()
        db.refresh(cli)
        user, pwd = create_portal_user(db, client_id=cli.id, email=f"aut-{suffix}@example.com")
    finally:
        db.close()

    r = client.post("/api/v1/client/auth/login", data={"username": user.email, "password": pwd})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    device_id = r.cookies.get("device_id")
    auth = {
        "headers": {"Authorization": f"Bearer {token}"},
        "cookies": {"device_id": device_id} if device_id else {},
    }

    r = client.get("/api/v1/client/catalog", **auth)
    assert r.status_code == 200
    by_cat = {c["id"]: c for c in r.json()["categories"]}
    assert "AUTOMATIZACIONES" not in by_cat
