"""Tests for new User columns and Role.client enum."""
from backend.app.auth.models import Role, User


def test_role_client_exists():
    assert Role.client.value == "client"


def test_user_has_new_columns(client):
    # Smoke test: User model has the new columns we added
    cols = {c.name for c in User.__table__.columns}
    assert "client_id" in cols
    assert "password_reset_required" in cols
    assert "current_session_id" in cols
    assert "session_started_at" in cols


def test_client_role_jwt_rejected_by_get_current_user(client, db_session=None):
    """Defense-in-depth: a JWT minted for Role.client must NOT pass through
    the staff get_current_user dependency."""
    import uuid
    from backend.app.auth.jwt_tokens import create_access_token, decode_token
    from backend.app.auth.models import Role
    from backend.app.auth.service import create_user, get_user_by_email
    from backend.app.db.session import SessionLocal

    # Use unique email per run to avoid UNIQUE constraint failure on shared test DB.
    email = f"defense-test-{uuid.uuid4().hex[:8]}@example.com"
    db = SessionLocal()
    try:
        u = get_user_by_email(db, email) or create_user(
            db, email=email, password="x", role=Role.client
        )
        token = create_access_token(subject=u.email, role=u.role.value)
    finally:
        db.close()

    # /auth/me uses get_current_user → must reject
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 401


def test_jwt_carries_sid_and_did():
    from backend.app.auth.jwt_tokens import create_access_token, decode_token

    token = create_access_token(
        subject="cliente@example.com",
        role="client",
        extra_claims={"sid": "abc123", "did": "device-xyz"},
    )
    payload = decode_token(token)
    assert payload["sub"] == "cliente@example.com"
    assert payload["role"] == "client"
    assert payload["sid"] == "abc123"
    assert payload["did"] == "device-xyz"


def test_jwt_backward_compatible_without_extra_claims():
    from backend.app.auth.jwt_tokens import create_access_token, decode_token

    # Old call signature still works for existing staff login
    token = create_access_token(subject="admin@example.com", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "admin@example.com"
    assert "sid" not in payload


import pytest
from backend.app.auth.service import (
    start_new_session,
    invalidate_session,
    create_user,
    get_user_by_email,
)
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _unique_email(prefix: str) -> str:
    import uuid as _uuid
    return f"{prefix}-{_uuid.uuid4().hex[:8]}@x.com"


def test_start_new_session_assigns_sid(db_session):
    email = _unique_email("sess-start")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    sid = start_new_session(db_session, user=u)
    db_session.refresh(u)
    assert u.current_session_id == sid
    assert u.session_started_at is not None
    assert len(sid) == 36  # UUID4


def test_second_session_replaces_first(db_session):
    email = _unique_email("sess-replace")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    sid_a = start_new_session(db_session, user=u)
    sid_b = start_new_session(db_session, user=u)
    db_session.refresh(u)
    assert sid_b != sid_a
    assert u.current_session_id == sid_b


def test_invalidate_session_clears_sid(db_session):
    email = _unique_email("sess-invalidate")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    start_new_session(db_session, user=u)
    invalidate_session(db_session, user=u)
    db_session.refresh(u)
    assert u.current_session_id is None


# ---------------------------------------------------------------------------
# Sesión única "el primero gana" (first-wins) + auto-liberación por inactividad
# ---------------------------------------------------------------------------
import datetime as _dt


def test_has_active_session_true_when_recent(db_session):
    from backend.app.auth.service import has_active_session
    email = _unique_email("active-recent")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    start_new_session(db_session, user=u)
    db_session.refresh(u)
    assert has_active_session(u) is True


def test_has_active_session_false_when_no_session(db_session):
    from backend.app.auth.service import has_active_session
    email = _unique_email("active-none")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    invalidate_session(db_session, user=u)
    db_session.refresh(u)
    assert has_active_session(u) is False


def test_has_active_session_false_when_stale(db_session):
    """Tras > timeout de inactividad la sesión se considera libre (liberación
    automática para no bloquear la cuenta si alguien cerró sin 'Salir')."""
    from backend.app.auth.service import has_active_session
    email = _unique_email("active-stale")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    start_new_session(db_session, user=u)
    u.session_started_at = (
        _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
        - _dt.timedelta(minutes=11)
    )
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    assert has_active_session(u) is False


def test_touch_session_refreshes_activity(db_session):
    """touch_session (heartbeat) refresca la última actividad → la sesión
    vuelve a contar como viva aunque estuviera por expirar."""
    from backend.app.auth.service import has_active_session, touch_session
    email = _unique_email("touch")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    start_new_session(db_session, user=u)
    u.session_started_at = (
        _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None)
        - _dt.timedelta(minutes=8)
    )
    db_session.add(u)
    db_session.commit()
    touch_session(db_session, user=u)
    db_session.refresh(u)
    assert has_active_session(u) is True


def test_touch_session_noop_without_active_session(db_session):
    """Si no hay sesión activa, touch_session no reactiva nada."""
    from backend.app.auth.service import has_active_session, touch_session
    email = _unique_email("touch-noop")
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="pwd123!", role=Role.client
    )
    invalidate_session(db_session, user=u)
    touch_session(db_session, user=u)
    db_session.refresh(u)
    assert has_active_session(u) is False
