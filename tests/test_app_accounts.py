"""Tests de las Cuentas de Aplicaciones AUDIT-IA (tipo de cuenta dedicado + apps)."""
import uuid

import pytest

import backend.app.app_accounts.router as app_router
from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.db.session import SessionLocal

PREFIX = "/api/v1"


@pytest.fixture(autouse=True)
def email_spy(monkeypatch):
    """Evita enviar correos reales en toda la suite y registra las llamadas."""
    sent = []
    monkeypatch.setattr(
        app_router.email_svc, "send_app_account_access",
        lambda **kw: (sent.append(kw) or {"id": "test"}),
    )
    return sent


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


def test_alta_envia_el_acceso_por_correo(client, admin_headers, email_spy):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": email, "apps": ["audit_sound"]})  # send_email default True
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["email_sent"] is True
    assert len(email_spy) == 1
    assert email_spy[0]["to"] == email and email_spy[0]["clave"] == body["temp_password"]


def test_alta_sin_correo_no_envia(client, admin_headers, email_spy):
    # send_email=False -> no se envía, email_sent None (clave generada o fija).
    e1 = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": e1, "apps": ["audit_sound"], "send_email": False})
    assert r.json()["email_sent"] is None
    e2 = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": e2, "apps": ["audit_sound"], "password": "ClaveFija123", "send_email": False})
    assert r.json()["email_sent"] is None
    assert email_spy == []


def test_reset_reenvia_el_acceso_por_correo(client, admin_headers, email_spy):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    aid = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                      json={"email": email, "apps": ["audit_sound"], "send_email": False}).json()["account"]["id"]
    email_spy.clear()
    r = client.post(f"{PREFIX}/apps/accounts/{aid}/reset-password", headers=admin_headers)
    assert r.status_code == 200 and r.json()["email_sent"] is True
    assert len(email_spy) == 1 and email_spy[0]["to"] == email


def test_alta_con_clave_manual(client, admin_headers, email_spy):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    # El admin fija la clave -> se usa esa, no se fuerza cambio, y se envía por correo.
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": email, "apps": ["audit_sound"], "password": "ClaveManual123", "send_email": True})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["temp_password"] == "ClaveManual123"
    assert body["account"]["password_reset_required"] is False
    assert body["email_sent"] is True and len(email_spy) == 1 and email_spy[0]["clave"] == "ClaveManual123"
    # Entra con la clave fijada
    assert _login(client, email, "ClaveManual123").status_code == 200


def test_alta_con_clave_manual_corta_falla(client, admin_headers):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                    json={"email": email, "password": "corta"})
    assert r.status_code == 400


def test_cliente_cambia_su_propia_clave(client, admin_headers):
    email = f"dj-{uuid.uuid4().hex[:8]}@example.com"
    temp = client.post(f"{PREFIX}/apps/accounts", headers=admin_headers,
                       json={"email": email, "apps": ["audit_sound"], "send_email": False}).json()["temp_password"]
    token = _login(client, email, temp).json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}

    # Clave actual incorrecta -> 400
    assert client.post(f"{PREFIX}/apps/auth/change-password", headers=H,
                       json={"current_password": "mala", "new_password": "NuevaClave123"}).status_code == 400
    # Nueva demasiado corta -> 400
    assert client.post(f"{PREFIX}/apps/auth/change-password", headers=H,
                       json={"current_password": temp, "new_password": "corta"}).status_code == 400
    # Correcto -> 200 y ya no exige reset
    r = client.post(f"{PREFIX}/apps/auth/change-password", headers=H,
                    json={"current_password": temp, "new_password": "NuevaClave123"})
    assert r.status_code == 200 and r.json()["password_reset_required"] is False
    # La vieja ya no entra; la nueva sí
    assert _login(client, email, temp).status_code == 401
    assert _login(client, email, "NuevaClave123").status_code == 200


def test_change_password_requiere_token_de_cuenta_de_app(client, admin_headers):
    # Sin token -> 401; con token de operador (no 'app') -> 403
    assert client.post(f"{PREFIX}/apps/auth/change-password",
                       json={"current_password": "x", "new_password": "NuevaClave123"}).status_code == 401
    assert client.post(f"{PREFIX}/apps/auth/change-password", headers=admin_headers,
                       json={"current_password": "x", "new_password": "NuevaClave123"}).status_code == 403


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
