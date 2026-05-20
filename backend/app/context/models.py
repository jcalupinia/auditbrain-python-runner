"""Modelos SQLAlchemy del contexto operativo (multi-tenant)."""

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.session import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    tax_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_client_org_name"),
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Módulo principal del proyecto (ADV, AUD, TAX, LEG, FIN, ...). En Fase 3
    # se vincula al registry de módulos sectoriales; aquí es solo un código.
    module_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    period_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    period_start: Mapped[datetime.date | None] = mapped_column(nullable=True)
    period_end: Mapped[datetime.date | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Rol del usuario DENTRO del proyecto. No reemplaza al rol global
    # (admin/user) sino que da granularidad por proyecto.
    project_role: Mapped[str] = mapped_column(
        String(24), default="member", nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_member_project_user"),
    )
