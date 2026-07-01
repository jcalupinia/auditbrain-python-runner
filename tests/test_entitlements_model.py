"""Tabla user_tool_entitlements: creación y unicidad (user_id, tool_code)."""
import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from backend.app.auth.models import Role, User, UserToolEntitlement
from backend.app.auth.service import create_user, get_user_by_email
from backend.app.db.session import SessionLocal


@pytest.fixture()
def db_session():
    db = SessionLocal()
    yield db
    db.close()


def _client_user(db):
    email = f"ent-{uuid.uuid4().hex[:8]}@example.com"
    return get_user_by_email(db, email) or create_user(
        db, email=email, password="x", role=Role.client
    )


def test_can_insert_entitlement(db_session):
    u = _client_user(db_session)
    ent = UserToolEntitlement(user_id=u.id, tool_code="ICT_2025", enabled=True)
    db_session.add(ent)
    db_session.commit()
    db_session.refresh(ent)
    assert ent.id is not None
    assert ent.enabled is True


def test_unique_user_tool(db_session):
    u = _client_user(db_session)
    db_session.add(UserToolEntitlement(user_id=u.id, tool_code="ICT_2025"))
    db_session.commit()
    db_session.add(UserToolEntitlement(user_id=u.id, tool_code="ICT_2025"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_delete_user_removes_entitlements(db_session):
    """Borrar el usuario elimina sus entitlements (cascada manual en
    delete_user_completely + ON DELETE CASCADE en Postgres). Sin huérfanos."""
    from sqlalchemy import select, func
    from backend.app.auth.service import delete_user_completely

    u = _client_user(db_session)
    db_session.add(UserToolEntitlement(user_id=u.id, tool_code="ICT_2025"))
    db_session.commit()
    uid = u.id

    delete_user_completely(db_session, user=u)

    remaining = db_session.execute(
        select(func.count()).select_from(UserToolEntitlement).where(
            UserToolEntitlement.user_id == uid
        )
    ).scalar_one()
    assert remaining == 0
