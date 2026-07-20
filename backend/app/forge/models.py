"""Modelos SQLAlchemy del módulo Forge.

El cerebro se persiste por tenant. Las colecciones (rules, memory, skills…) se
guardan como JSON en la fila del cerebro (MVP); la normalización a tablas
separadas es una mejora posterior. Aislamiento por ``owner_user_id``.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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


class ForgeSubscription(Base):
    """Suscripción de Forge de un usuario (tenant). Una por usuario."""

    __tablename__ = "forge_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        unique=True,
        nullable=False,
    )
    plan: Mapped[str] = mapped_column(String(40), default="free", nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="none", nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(120), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )


class ForgePlan(Base):
    """Un ``TaskPlan`` registrado desde el CLI (``forge push``).

    El plan es un **dato revisable**: se registra tal cual lo generó el Planner
    local (BYOK, §1 del diseño F2b). La aprobación/rechazo vive en
    ``ForgeDecision``, no aquí. Aislamiento por ``owner_user_id``.
    """

    __tablename__ = "forge_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    #: **RESTRICT**: no se puede borrar al dueño de un plan sin tratar su rastro.
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    #: El ``uuid4`` que generó el CLI. Único: reintentar el mismo plan es idempotente.
    plan_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    goal: Mapped[str] = mapped_column(Text, default="", nullable=False)
    schema_version: Mapped[str] = mapped_column(String(16), default="1", nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), default="media", nullable=False)
    model: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ai_invoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    #: El ``TaskPlan.tasks`` serializado. El tope de tamaño (≤ 64 KB) se valida en
    #: el esquema Pydantic de la API (§3.3), no en la columna.
    tasks: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )


class ForgeDecision(Base):
    """Una decisión (aprobar/rechazar) sobre una tarea. La cadena. **APPEND-ONLY.**

    Append-only garantizado por un **trigger de BD** (``init_db()``), no por
    ``REVOKE`` (que en Postgres es no-op para el dueño de la tabla). Ver §3.2 del
    diseño. El ``hash`` se calcula con el ``compute_hash`` vendorizado, byte-idéntico
    al del CLI, para que la traza verifique con ``forge audit verify`` (P7/P8).
    """

    __tablename__ = "forge_decisions"
    __table_args__ = (
        # El (plan, seq) es único: la cadena de un plan no puede tener dos "seq=3".
        UniqueConstraint("plan_row_id", "seq", name="uq_forge_decision_plan_seq"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    #: **RESTRICT**: no se borra un plan que tenga decisiones colgando.
    plan_row_id: Mapped[int] = mapped_column(
        ForeignKey("forge_plans.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    #: Snapshot denormalizado (no FK): la traza no debe romperse si se toca la org.
    organization_id: Mapped[int | None] = mapped_column(
        Integer, index=True, nullable=True
    )
    #: **RESTRICT** + identidad REAL: quién aprobó, autenticado (no autodeclarado).
    actor_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    #: Snapshot del email/nombre EN EL MOMENTO. Es lo que se **firma** como ``actor``,
    #: para que la traza siga siendo legible aunque el usuario cambie o se dé de baja.
    actor_label: Mapped[str] = mapped_column(String(200), nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    task_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    #: Huella del contenido de la tarea aprobada (cierra el content-swap). Firmado.
    content_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    #: ISO 8601 en texto: es exactamente lo que se firma, byte-estable.
    ts: Mapped[str] = mapped_column(String(40), nullable=False)
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
