"""Backfill: concede la sección Tributarias a clientes sin entitlements
cuando la tabla está globalmente vacía; idempotente en el segundo arranque."""
import uuid
import pytest
from sqlalchemy import delete
from backend.app.auth.models import Role, UserToolEntitlement
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.client_portal import entitlements as ent
from backend.app.client_portal.tool_registry import TOOLS
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _tributarias_codes():
    return {c for c, t in TOOLS.items() if t.category == "TRIBUTARIAS" and t.enabled}


def test_backfill_grants_tributarias_when_table_empty(db_session):
    # Estado controlado: vaciar la tabla y crear un cliente sin entitlements.
    db_session.execute(delete(UserToolEntitlement))
    db_session.commit()
    email = f"bf-{uuid.uuid4().hex[:8]}@example.com"
    u = get_user_by_email(db_session, email) or create_user(
        db_session, email=email, password="x", role=Role.client
    )

    granted = ent.backfill_tributarias(db_session)

    assert granted >= 1
    assert ent.list_user_tool_codes(db_session, u.id) == _tributarias_codes()


def test_backfill_noop_when_table_not_empty(db_session):
    # Con al menos una fila, el backfill no debe tocar nada.
    db_session.execute(delete(UserToolEntitlement))
    db_session.commit()
    email = f"bf2-{uuid.uuid4().hex[:8]}@example.com"
    u = create_user(db_session, email=email, password="x", role=Role.client)
    ent.set_user_entitlements(db_session, u.id, {"ICT_2025"})  # deja 1 fila

    email2 = f"bf3-{uuid.uuid4().hex[:8]}@example.com"
    u2 = create_user(db_session, email=email2, password="x", role=Role.client)

    granted = ent.backfill_tributarias(db_session)

    assert granted == 0  # tabla no vacía → no corre
    assert ent.list_user_tool_codes(db_session, u2.id) == set()  # u2 sigue sin nada
