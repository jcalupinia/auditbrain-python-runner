"""Tests for client portal login + 3-layer security guard."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.auth import device as device_mod
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture()
def client_user(db_session):
    email = _unique_email("client-user")
    return get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="ClientPass1!", role=Role.client,
    )


def test_guard_rejects_when_role_is_not_client(client, client_user, db_session):
    from backend.app.auth.jwt_tokens import create_access_token
    token = create_access_token(subject=client_user.email, role="admin")
    r = client.get(
        "/api/v1/client/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code in (401, 403)  # 403 because role=admin is rejected by require_client_with_device


# ---------------------------------------------------------------------------
# Task 8: client_portal service layer tests
# ---------------------------------------------------------------------------

from backend.app.client_portal.service import (
    create_portal_user,
    authenticate_portal_user,
)
from backend.app.context.models import Organization, Client


@pytest.fixture()
def org_and_client(db_session):
    slug_unique = f"acg-{uuid.uuid4().hex[:6]}"
    org = Organization(name=f"ACG-{slug_unique}", slug=slug_unique, is_active=True)
    db_session.add(org); db_session.commit(); db_session.refresh(org)
    cli = Client(
        organization_id=org.id, name=f"CL-{slug_unique}", is_active=True
    )
    db_session.add(cli); db_session.commit(); db_session.refresh(cli)
    return org, cli


def test_create_portal_user_returns_temp_password(db_session, org_and_client):
    org, cli = org_and_client
    email = _unique_email("newclient")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    assert user.role == Role.client
    assert user.client_id == cli.id
    assert user.password_reset_required is True
    assert user.organization_id == org.id
    assert len(temp_pwd) >= 12


def test_authenticate_portal_user_with_wrong_password(db_session, org_and_client):
    _, cli = org_and_client
    email = _unique_email("auth1")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    assert authenticate_portal_user(db_session, email, "wrong") is None
    auth_result = authenticate_portal_user(db_session, email, temp_pwd)
    assert auth_result is not None
    assert auth_result.email == user.email


# ---------------------------------------------------------------------------
# Task 9: router endpoint tests
# ---------------------------------------------------------------------------


def test_first_login_returns_password_reset_required(client, db_session, org_and_client):
    _, cli = org_and_client
    email = _unique_email("first")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["password_reset_required"] is True
    assert "access_token" in body
    # device_id cookie should be set (via Set-Cookie header)
    assert "device_id" in r.cookies or "device_id" in r.headers.get("set-cookie", "")


def test_login_with_wrong_credentials_returns_401(client, db_session, org_and_client):
    r = client.post(
        "/api/v1/client/auth/login",
        data={"username": "nobody@example.com", "password": "x"},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Sesión única "el primero gana" (first-wins): el segundo login se BLOQUEA
# mientras el primero tiene una sesión viva; el primero NO es expulsado.
# ---------------------------------------------------------------------------


def test_second_login_blocked_while_first_active(client, db_session, org_and_client):
    """Regla 'el primero gana': si ya hay una sesión viva, el segundo login
    recibe 409 session_in_use y el primero sigue dentro."""
    _, cli = org_and_client
    email = _unique_email("dual")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)

    r_a = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
    )
    assert r_a.status_code == 200, r_a.json()
    token_a = r_a.json()["access_token"]
    device_id_cookie = r_a.cookies.get("device_id")

    # Segundo login (misma cuenta, sesión A viva) → 409 bloqueado.
    r_b = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
        cookies={"device_id": device_id_cookie} if device_id_cookie else {},
    )
    assert r_b.status_code == 409, r_b.json()
    detail = r_b.json()["detail"]
    assert isinstance(detail, dict) and detail["code"] == "session_in_use"

    # El primero SIGUE dentro: /me con token_a → 200.
    r_check = client.get(
        "/api/v1/client/auth/me",
        headers={"Authorization": f"Bearer {token_a}"},
        cookies={"device_id": device_id_cookie} if device_id_cookie else {},
    )
    assert r_check.status_code == 200, r_check.json()


def test_login_allowed_after_logout(client, db_session, org_and_client):
    """Tras 'Salir' (logout) la cuenta queda libre para que otro entre."""
    _, cli = org_and_client
    email = _unique_email("after-logout")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)

    r_a = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
    )
    assert r_a.status_code == 200, r_a.json()
    token_a = r_a.json()["access_token"]
    device_id_cookie = r_a.cookies.get("device_id")

    r_logout = client.post(
        "/api/v1/client/auth/logout",
        headers={"Authorization": f"Bearer {token_a}"},
        cookies={"device_id": device_id_cookie} if device_id_cookie else {},
    )
    assert r_logout.status_code == 200, r_logout.json()

    # Ahora un nuevo login debe ser permitido (sesión liberada).
    r_b = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
        cookies={"device_id": device_id_cookie} if device_id_cookie else {},
    )
    assert r_b.status_code == 200, r_b.json()


def test_login_allowed_after_inactivity_timeout(client, db_session, org_and_client):
    """Si la sesión queda 'colgada' (sin logout) pero pasa el timeout de
    inactividad, otra persona puede ingresar (auto-liberación)."""
    import datetime
    _, cli = org_and_client
    email = _unique_email("after-timeout")
    user, temp_pwd = create_portal_user(db_session, client_id=cli.id, email=email)

    r_a = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
    )
    assert r_a.status_code == 200, r_a.json()
    device_id_cookie = r_a.cookies.get("device_id")

    # Simular inactividad: última actividad hace 11 min (> timeout de 10).
    db_session.refresh(user)
    user.session_started_at = (
        datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        - datetime.timedelta(minutes=11)
    )
    db_session.add(user)
    db_session.commit()

    r_b = client.post(
        "/api/v1/client/auth/login",
        data={"username": email, "password": temp_pwd},
        cookies={"device_id": device_id_cookie} if device_id_cookie else {},
    )
    assert r_b.status_code == 200, r_b.json()
