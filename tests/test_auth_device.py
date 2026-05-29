"""Tests for ClientDevice model + device.py helpers."""
from backend.app.auth.models import ClientDevice
from backend.app.auth.device import (
    generate_device_id,
    compute_fingerprint_hash,
    register_device,
    validate_device,
    revoke_device,
)


def test_client_device_model_exists():
    cols = {c.name for c in ClientDevice.__table__.columns}
    assert "user_id" in cols
    assert "device_id" in cols
    assert "fingerprint_hash" in cols
    assert "is_active" in cols
    assert "revoked_at" in cols
    assert "revoked_by_user_id" in cols


def test_generate_device_id_unique():
    a = generate_device_id()
    b = generate_device_id()
    assert a != b
    assert len(a) == 36  # UUID4 string


def test_fingerprint_hash_deterministic():
    h1 = compute_fingerprint_hash(
        user_agent="Mozilla/5.0 Chrome/120",
        accept_language="en-US",
        accept_encoding="gzip",
    )
    h2 = compute_fingerprint_hash(
        user_agent="Mozilla/5.0 Chrome/120",
        accept_language="en-US",
        accept_encoding="gzip",
    )
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_fingerprint_hash_changes_with_input():
    h1 = compute_fingerprint_hash(user_agent="Firefox", accept_language="en")
    h2 = compute_fingerprint_hash(user_agent="Chrome", accept_language="en")
    assert h1 != h2
