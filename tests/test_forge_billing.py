"""Tests de facturación y gating por plan de Forge (Stripe mockeado, sin claves).

Verifica: plan por defecto free, límite de cerebros y de destinos por plan, y que
el webhook de Stripe activa el plan. No requiere claves de Stripe (el webhook sin
``STRIPE_WEBHOOK_SECRET`` acepta el payload sin verificar firma).
"""

import json
import uuid

from backend.app.auth import service
from backend.app.auth.models import Role
from backend.app.db.session import SessionLocal, init_db


def _admin(client):
    init_db()
    email = f"forgebill-{uuid.uuid4().hex[:8]}@example.com"
    password = "Sup3rSecret!"
    db = SessionLocal()
    try:
        service.create_user(db, email=email, password=password, role=Role.admin)
    finally:
        db.close()
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    uid = client.get("/api/v1/auth/me", headers=h).json()["id"]
    return h, uid


def _brain():
    return {"name": "P", "slug": "p", "rules": [{"id": "g", "title": "G", "body": "b"}]}


def test_plan_por_defecto_free(client):
    h, _ = _admin(client)
    r = client.get("/api/v1/forge/subscription", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["plan"] == "free"
    assert data["targets"] == ["claude-code"]
    assert data["max_brains"] == 1


# Nota: el gating por plan (límite de cerebros / destinos) aplica a CLIENTES, no
# a operadores admin/user (que hacen bypass). Su verificación vive en
# tests/test_forge_client.py con un usuario de rol client.


def test_webhook_activa_pro(client):
    h, uid = _admin(client)
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"forge_user_id": str(uid), "forge_plan": "pro"},
                "client_reference_id": str(uid),
                "customer": "cus_test",
                "subscription": "sub_test",
            }
        },
    }
    r = client.post("/api/v1/forge/billing/webhook", content=json.dumps(event))
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "activated"

    # ahora el plan es pro: compila a cursor y crea varios cerebros
    sub = client.get("/api/v1/forge/subscription", headers=h).json()
    assert sub["plan"] == "pro"
    assert "cursor" in sub["targets"]
    bid = client.post("/api/v1/forge/brains", json=_brain(), headers=h).json()["id"]
    r = client.post(
        f"/api/v1/forge/brains/{bid}/compile", json={"target": "cursor"}, headers=h
    )
    assert r.status_code == 200, r.text


def test_checkout_sin_claves_da_503(client):
    h, _ = _admin(client)
    r = client.post("/api/v1/forge/billing/checkout", json={"plan": "pro"}, headers=h)
    assert r.status_code == 503, r.text
