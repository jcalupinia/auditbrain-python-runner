"""Lógica de negocio de los registros de recursos."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.recursos.models import RecursoLead, _utcnow
from backend.app.recursos.schemas import LeadCreate

# Versión del texto de public/politica-datos/ del mini-sitio.
POLITICA_VERSION = "v1"


def buscar(db: Session, slug: str, email: str) -> RecursoLead | None:
    return db.execute(
        select(RecursoLead).where(
            RecursoLead.recurso_slug == slug,
            RecursoLead.email == email.strip().lower(),
        )
    ).scalar_one_or_none()


def registrar(db: Session, *, slug: str, data: LeadCreate, ip: str) -> RecursoLead:
    """Alta idempotente. Si el (slug, email) ya existe, lo devuelve sin tocarlo."""
    email = str(data.email).strip().lower()
    lead = buscar(db, slug, email)
    if lead is not None:
        return lead
    lead = RecursoLead(
        recurso_slug=slug,
        email=email,
        ip=ip[:64],
        nombre=data.nombre,
        empresa=data.empresa,
        consentimiento_at=_utcnow(),
        consentimiento_version=POLITICA_VERSION,
    )
    db.add(lead)
    try:
        db.commit()
    except IntegrityError:
        # Carrera: otra request insertó el mismo (slug, email) en paralelo.
        db.rollback()
        lead = buscar(db, slug, email)
        if lead is None:
            raise
        return lead
    db.refresh(lead)
    return lead


def marcar_verificado(db: Session, lead: RecursoLead) -> None:
    if lead.verificado_at is None:
        lead.verificado_at = _utcnow()
        db.commit()


def listar(db: Session, *, slug: str | None = None, limit: int = 200) -> list[RecursoLead]:
    q = select(RecursoLead)
    if slug:
        q = q.where(RecursoLead.recurso_slug == slug)
    q = q.order_by(RecursoLead.created_at.desc(), RecursoLead.id.desc()).limit(limit)
    return list(db.execute(q).scalars())
