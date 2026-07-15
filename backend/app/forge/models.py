"""Modelos SQLAlchemy del módulo Forge.

El cerebro se persiste por tenant. Las colecciones (rules, memory, skills…) se
guardan como JSON en la fila del cerebro (MVP); la normalización a tablas
separadas es una mejora posterior. Aislamiento por ``owner_user_id``.
"""

from __future__ import annotations

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class ForgeBrain(Base):
    __tablename__ = "forge_brains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    organization: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(40), default="python", nullable=False)
    version: Mapped[str] = mapped_column(String(40), default="0.1.0", nullable=False)

    targets: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    rules: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    memory: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    agents: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    personas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    connectors: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    capabilities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
