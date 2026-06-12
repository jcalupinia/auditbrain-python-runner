"""Modelo de inscripción a eventos."""

import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class EventRegistration(Base):
    __tablename__ = "event_registrations"
    __table_args__ = (
        UniqueConstraint("event_slug", "email", name="uq_event_registration_slug_email"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_slug: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    telefono_e164: Mapped[str] = mapped_column(String(20), nullable=False)
    documento: Mapped[str] = mapped_column(String(20), nullable=False)
    empresa: Mapped[str] = mapped_column(String(200), nullable=False)
    estado: Mapped[str] = mapped_column(String(16), default="registrado", nullable=False)
    email_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    aviso_interno_enviado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
