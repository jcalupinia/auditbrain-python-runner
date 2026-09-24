"""Modelo SQLAlchemy del catálogo de Audit Apps (AUT-002).

Persiste el manifest versionado de cada Audit App. Patrón de ``ForgePlan``:
alta idempotente por ``(app_id, version)``, contenido inmutable (una versión
publicada no se edita, se sube otra), aislamiento por tenant.

Registrar el import de este módulo en ``db/session.py::init_db`` para que
``Base.metadata.create_all`` cree la tabla ``audit_apps``.
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
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


class AuditApp(Base):
    """Una versión publicada de una Audit App en el catálogo."""

    __tablename__ = "audit_apps"
    __table_args__ = (
        UniqueConstraint("app_id", "version", name="uq_audit_apps_id_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Id de la app (AUD-INV-VNR o slug); una app tiene varias versiones.
    app_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    #: Versión semver (MAJOR.MINOR.PATCH). El registro ordena por ella.
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: El manifest completo (``AuditAppManifest.to_dict()``), fuente de verdad.
    manifest: Mapped[dict] = mapped_column(JSON, nullable=False)
    #: Huella del contenido; distingue "misma versión, otro contenido" (409).
    manifest_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    #: Aislamiento multi-tenant: salen de la sesión, nunca del cliente.
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), index=True, nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    notas: Mapped[str | None] = mapped_column(Text, nullable=True)
