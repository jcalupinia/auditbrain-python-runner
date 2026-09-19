"""Tareas 1 y 2 del plan de Automatizaciones: catálogo y tabla ``aut_cuentas``."""

import pytest
from sqlalchemy.exc import IntegrityError

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


def test_aut_cuenta_unica_por_cliente_y_herramienta(db):
    from backend.app.automatizaciones.models import AutCuenta

    db.add(
        AutCuenta(
            client_id=1,
            herramienta="PRESUPUESTOS_IA",
            empresa_nombre="X",
            admin_email="a@x.ec",
            admin_nombre="A",
            creado_por="op@firma.ec",
        )
    )
    db.commit()
    db.add(
        AutCuenta(
            client_id=1,
            herramienta="PRESUPUESTOS_IA",
            empresa_nombre="Y",
            admin_email="b@y.ec",
            admin_nombre="B",
            creado_por="op@firma.ec",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()


def test_aut_cuenta_estado_por_defecto_activa(db):
    from backend.app.automatizaciones.models import AutCuenta

    cuenta = AutCuenta(
        client_id=1,
        herramienta="PLANIFICACION_IA",
        empresa_nombre="Z",
        admin_email="c@z.ec",
        admin_nombre="C",
        creado_por="op@firma.ec",
    )
    db.add(cuenta)
    db.commit()
    db.refresh(cuenta)
    assert cuenta.estado == "activa"


@pytest.fixture()
def db():
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()
