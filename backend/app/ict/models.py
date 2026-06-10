"""SQLAlchemy models for ICT 2025 sessions and anexos.

ICTSession: persistent 90-day project per client, holds contribuyente data.
ICTAnexo: per-anexo extracted data (survives 24h file deletion).
"""

import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.app.db.session import Base


class ICTSession(Base):
    """Persistent ICT project. 90 days inactivity → expired."""

    __tablename__ = "ict_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    ejercicio_fiscal: Mapped[str] = mapped_column(String(4), nullable=False)
    ruc: Mapped[str] = mapped_column(String(20), nullable=False)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    numero_adhesivo: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress", nullable=False
    )  # in_progress | completed | expired
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None), nullable=False
    )
    last_activity_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None), nullable=False
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)

    anexos: Mapped[list["ICTAnexo"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ICTAnexo(Base):
    """Per-anexo extracted data. Persists 90 days with the session."""

    __tablename__ = "ict_anexos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("ict_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    anexo_code: Mapped[str] = mapped_column(String(16), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="empty", nullable=False)

    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    uploaded_files: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None), nullable=False
    )

    session: Mapped["ICTSession"] = relationship(back_populates="anexos")

    __table_args__ = (
        UniqueConstraint("session_id", "anexo_code", name="uq_session_anexo"),
    )
