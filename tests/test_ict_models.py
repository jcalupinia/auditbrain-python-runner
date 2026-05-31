"""Tests for ICTSession + ICTAnexo models."""
from backend.app.ict.models import ICTSession, ICTAnexo


def test_ict_session_has_expected_columns():
    cols = {c.name for c in ICTSession.__table__.columns}
    expected = {
        "id", "user_id", "ejercicio_fiscal", "ruc", "razon_social",
        "numero_adhesivo", "status", "created_at", "last_activity_at",
        "expires_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_ict_anexo_has_expected_columns():
    cols = {c.name for c in ICTAnexo.__table__.columns}
    expected = {
        "id", "session_id", "anexo_code", "status",
        "extracted_data", "warnings", "uploaded_files", "last_updated_at",
    }
    assert expected.issubset(cols), f"missing: {expected - cols}"


def test_ict_anexo_has_unique_session_anexo_constraint():
    constraints = [c.name for c in ICTAnexo.__table__.constraints]
    assert "uq_session_anexo" in constraints
