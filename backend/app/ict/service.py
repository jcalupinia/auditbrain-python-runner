"""Service layer for ICT 2025: sessions, anexos, Excel generation."""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.ict.models import ICTAnexo, ICTSession

SESSION_TTL_DAYS = 90
ANEXOS_CATALOG = ["INDICE", "A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]


def _now() -> datetime.datetime:
    return datetime.datetime.utcnow()


def _expires_at(from_dt: datetime.datetime | None = None) -> datetime.datetime:
    base = from_dt or _now()
    return base + datetime.timedelta(days=SESSION_TTL_DAYS)


def create_session(
    db: Session,
    *,
    user: User,
    ejercicio_fiscal: str,
    ruc: str,
    razon_social: str,
    numero_adhesivo: str | None,
) -> ICTSession:
    """Create new ICT session or return existing in_progress (idempotent)."""
    existing = get_active_session(db, user=user)
    if existing is not None:
        return existing

    now = _now()
    session = ICTSession(
        user_id=user.id,
        ejercicio_fiscal=ejercicio_fiscal,
        ruc=ruc,
        razon_social=razon_social,
        numero_adhesivo=numero_adhesivo,
        status="in_progress",
        created_at=now,
        last_activity_at=now,
        expires_at=_expires_at(now),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    for anexo_code in ANEXOS_CATALOG:
        db.add(ICTAnexo(
            session_id=session.id,
            anexo_code=anexo_code,
            status="empty",
            extracted_data=None,
            warnings=None,
            uploaded_files=None,
            last_updated_at=now,
        ))
    db.commit()
    db.refresh(session)
    return session


def get_active_session(db: Session, *, user: User) -> ICTSession | None:
    """Return user's in_progress session or None."""
    return db.execute(
        select(ICTSession)
        .where(ICTSession.user_id == user.id, ICTSession.status == "in_progress")
        .order_by(ICTSession.created_at.desc())
    ).scalars().first()


def get_session(db: Session, *, session_id: int, user: User) -> ICTSession:
    """Get session by id, validates ownership. Raises PermissionError if not owner."""
    s = db.get(ICTSession, session_id)
    if s is None or s.user_id != user.id:
        raise PermissionError("Session not found or not owned by user")
    return s


def touch_session(db: Session, *, session: ICTSession) -> None:
    """Update last_activity_at + extend expires_at."""
    now = _now()
    session.last_activity_at = now
    session.expires_at = _expires_at(now)
    db.add(session)
    db.commit()


def update_session(
    db: Session,
    *,
    session: ICTSession,
    ruc: str | None = None,
    razon_social: str | None = None,
    numero_adhesivo: str | None = None,
) -> ICTSession:
    """Update session contribuyente data and touch activity."""
    if ruc is not None:
        session.ruc = ruc
    if razon_social is not None:
        session.razon_social = razon_social
    if numero_adhesivo is not None:
        session.numero_adhesivo = numero_adhesivo
    now = _now()
    session.last_activity_at = now
    session.expires_at = _expires_at(now)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def expire_session(db: Session, *, session: ICTSession) -> None:
    """Mark session as expired (user-initiated close)."""
    session.status = "expired"
    db.add(session)
    db.commit()
