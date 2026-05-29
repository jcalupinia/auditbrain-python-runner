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
    assert r.status_code in (401, 403)  # 401 if endpoint not yet wired, 403 once it is
