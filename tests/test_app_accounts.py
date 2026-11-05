"""Tests de las Cuentas de Aplicaciones AUDIT-IA (tipo de cuenta dedicado + apps)."""
import uuid

import pytest

from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.db.session import SessionLocal

PREFIX = "/api/v1"


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture()
def admin_headers(db_session):
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="AdminPass1!", role=Role.admin,
    )
    return {"Authorization": f"Bearer {create_access_token(subject=u.email, role='admin')}"}


def _login(client, email, password, app=None):
    url = f"{PREFIX}/apps/auth/login" + (f"?app={app}" if app else "")
    return client.post(url, data={"username": email, "password": password})


def test_catalogo_requiere_admin(client, admin_headers):
    assert client.get(f"{PREFIX}/apps/catalog").status_code in (401, 403)
    r = client.get(f"{PREFIX}/apps/catalog", headers=admin_headers)
    assert r.status_code == 200
    keys = [a["key"] for a in r.json()]
    assert "audit_sound" in keys


def test_alta_y_login_con_permiso_de_app(client, admin_headers):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    # Alta (admin) con acceso a audit_sound
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": email, "display_name": "DJ Uno", "client_label": "Cliente X",
                          "apps": ["audit_sound"]})
    assert r.status_code == 201, r.text
    body = r.json()
    temp = body["temp_password"]
    assert body["account"]["apps"] == ["audit_sound"]
    assert temp and len(temp) >= 10

    # Login con clave mala → 401
    assert _login(client, email, "incorrecta").status_code == 401
    # Login correcto (sin app) → 200 + token + apps
    r = _login(client, email, temp)
    assert r.status_code == 200, r.text
    assert r.json()["apps"] == ["audit_sound"]
    assert r.json()["password_reset_required"] is True
    token = r.json()["access_token"]
    # Login validando acceso a la app concreta → 200
    assert _login(client, email, temp, app="audit_sound").status_code == 200
    # Login pidiendo una app sin permiso → 403
    assert _login(client, email, temp, app="otra_app").status_code == 403

    # /apps/auth/me con el token → apps
    me = client.get(f"{PREFIX}/apps/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["apps"] == ["audit_sound"]


def test_cuenta_sin_la_app_no_entra_a_esa_app(client, admin_headers):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": email, "apps": []})  # sin apps
    temp = r.json()["temp_password"]
    # Login general funciona (cuenta válida)
    assert _login(client, email, temp).status_code == 200
    # Pero no puede entrar a audit_sound
    assert _login(client, email, temp, app="audit_sound").status_code == 403


def test_reset_clave_permisos_y_desactivar(client, admin_headers):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    acc = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                      json={"email": email, "apps": ["audit_sound"]}).json()["account"]
    aid = acc["id"]

    # Reset de clave → nueva temporal, la vieja deja de servir
    new_temp = client.post(f"{PREFIX}/apps/accounts/{aid}/reset-password", headers=admin_headers).json()["temp_password"]
    assert _login(client, email, new_temp).status_code == 200

    # Quitar el permiso de la app (PATCH apps=[])
    r = client.patch(f"{PREFIX}/apps/accounts/{aid}", headers=admin_headers, json={"apps": []})
    assert r.status_code == 200 and r.json()["apps"] == []
    assert _login(client, email, new_temp, app="audit_sound").status_code == 403

    # Desactivar la cuenta → no puede iniciar sesión
    client.patch(f"{PREFIX}/apps/accounts/{aid}", headers=admin_headers, json={"is_active": False})
    assert _login(client, email, new_temp).status_code == 401


def test_gestion_requiere_admin(client):
    # Sin admin no se puede listar ni crear
    assert client.get(f"{PREFIX}/apps/accounts").status_code in (401, 403)
    assert client.post(f"{PREFIX}/apps/accounts", json={"email": "x@y.com"}).status_code in (401, 403)


def test_correo_duplicado_y_app_invalida(client, admin_headers):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    assert client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                       json={"email": email, "apps": ["audit_sound"]}).status_code == 201
    # Duplicado → 400
    assert client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                       json={"email": email}).status_code == 400
    # App inexistente → 400
    assert client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                       json={"email": f"z-{uuid.uuid4().hex[:6]}@y.com", "apps": ["no_existe"]}).status_code == 400
