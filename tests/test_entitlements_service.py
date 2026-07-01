"""Servicio de entitlements: set/list/can_access."""
import uuid
import pytest
from backend.app.auth.models import Role
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.client_portal import entitlements as ent
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _client_user(db):
    email = f"entsvc-{uuid.uuid4().hex[:8]}@example.com"
    return get_user_by_email(db, email) or create_user(
        db, email=email, password="x", role=Role.client
    )


def test_default_no_access(db_session):
    u = _client_user(db_session)
    assert ent.list_user_tool_codes(db_session, u.id) == set()
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is False


def test_set_grants_only_valid_codes(db_session):
    u = _client_user(db_session)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025", "NO_EXISTE"})
    codes = ent.list_user_tool_codes(db_session, u.id)
    assert codes == {"ICT_2025"}  # código inexistente ignorado
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is True


def test_set_replaces_full_set(db_session):
    u = _client_user(db_session)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    ent.set_user_entitlements(db_session, u.id, set())  # revoca todo
    assert ent.list_user_tool_codes(db_session, u.id) == set()
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is False


def test_set_is_idempotent(db_session):
    u = _client_user(db_session)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    assert ent.list_user_tool_codes(db_session, u.id) == {"ICT_2025"}


def test_set_partial_overlap_replace(db_session):
    """Caso más común en producción: reemplazo con solapamiento parcial.
    Ejercita en una sola llamada las tres ramas: mantener una fila existente,
    insertar una nueva y borrar una sobrante."""
    u = _client_user(db_session)
    # A = {ICT_2025}
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})
    # A→B: mantiene ICT_2025 (ya existía) e inserta STUB_ECHO
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025", "STUB_ECHO"})
    assert ent.list_user_tool_codes(db_session, u.id) == {"ICT_2025", "STUB_ECHO"}
    # B→C: mantiene STUB_ECHO y borra ICT_2025 (sobrante)
    ent.set_user_entitlements(db_session, u.id, {"STUB_ECHO"})
    assert ent.list_user_tool_codes(db_session, u.id) == {"STUB_ECHO"}
    assert ent.can_access_tool(db_session, u.id, "ICT_2025") is False
    assert ent.can_access_tool(db_session, u.id, "STUB_ECHO") is True
