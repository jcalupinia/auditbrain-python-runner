"""Registros (leads), cuentas y accesos de recursos gratuitos."""

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
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


class RecursoCuenta(Base):
    """Una por persona (correo). Solo guarda el hash de la clave."""

    __tablename__ = "recurso_cuentas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_clave: Mapped[str] = mapped_column(String(255), nullable=False)
    # True: clave generada (se compara normalizada). False: escrita por el admin (exacta).
    clave_generada: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_ingreso_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    clave_actualizada_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )


class RecursoAcceso(Base):
    __tablename__ = "recurso_accesos"
    __table_args__ = (
        UniqueConstraint("cuenta_id", "recurso_slug", name="uq_recurso_acceso_cuenta_slug"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cuenta_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recurso_cuentas.id"), nullable=False
    )
    recurso_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    # "registro" o el correo del admin que lo otorgó.
    otorgado_por: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
