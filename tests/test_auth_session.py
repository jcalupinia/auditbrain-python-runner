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
    from backend.app.auth.jwt_tokens import create_access_token
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
