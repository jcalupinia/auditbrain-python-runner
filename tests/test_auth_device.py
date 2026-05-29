"""Tests for ClientDevice model."""
from backend.app.auth.models import ClientDevice


def test_client_device_model_exists():
    cols = {c.name for c in ClientDevice.__table__.columns}
    assert "user_id" in cols
    assert "device_id" in cols
    assert "fingerprint_hash" in cols
    assert "is_active" in cols
    assert "revoked_at" in cols
    assert "revoked_by_user_id" in cols
