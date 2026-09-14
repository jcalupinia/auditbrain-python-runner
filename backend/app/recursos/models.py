"""Registros (leads) de recursos gratuitos."""

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class RecursoLead(Base):
    __tablename__ = "recurso_leads"
    __table_args__ = (
        UniqueConstraint("recurso_slug", "email", name="uq_recurso_lead_slug_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recurso_slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    empresa: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    consentimiento_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    consentimiento_version: Mapped[str] = mapped_column(String(16), nullable=False)
    ip: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verificado_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
