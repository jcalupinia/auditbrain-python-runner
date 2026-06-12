"""Lógica de negocio de inscripciones."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.events.models import EventRegistration
from backend.app.events.schemas import RegistrationCreate


def _find(db: Session, event_slug: str, email: str) -> EventRegistration | None:
    return db.execute(
        select(EventRegistration).where(
            EventRegistration.event_slug == event_slug,
            EventRegistration.email == email,
        )
    ).scalar_one_or_none()


def create_registration(
    db: Session, *, event_slug: str, data: RegistrationCreate
) -> tuple[EventRegistration, bool]:
    """Crea (o reusa) una inscripción. Devuelve (registro, ya_inscrito)."""
    email = data.email.lower()
    existing = _find(db, event_slug, email)
    if existing is not None:
        return existing, True

    reg = EventRegistration(
        event_slug=event_slug,
        nombre=data.nombre.strip(),
        email=email,
        telefono_e164=data.telefono_e164,
        documento=data.documento,
        empresa=data.empresa.strip(),
    )
    db.add(reg)
    try:
        db.commit()
    except IntegrityError:
        # Carrera: otra request insertó el mismo (slug,email) en paralelo.
        db.rollback()
        existing = _find(db, event_slug, email)
        if existing is not None:
            return existing, True
        raise
    db.refresh(reg)
    return reg, False


def list_registrations(
    db: Session, *, event_slug: str, limit: int = 100
) -> list[EventRegistration]:
    return list(
        db.execute(
            select(EventRegistration)
            .where(EventRegistration.event_slug == event_slug)
            .order_by(EventRegistration.created_at.desc(), EventRegistration.id.desc())
            .limit(limit)
        ).scalars()
    )
