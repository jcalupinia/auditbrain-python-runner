"""Cuentas de las herramientas de Automatizaciones (Presupuestos IA, Planificación IA).

Una fila por cliente + herramienta: la firma crea la empresa cliente y su
administrador en el Supabase de la app de presupuestos; ese administrador
crea después las cuentas de su propio personal (fuera de esta tabla).
"""

import datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class AutCuenta(Base):
    __tablename__ = "aut_cuentas"
    __table_args__ = (
        UniqueConstraint("client_id", "herramienta", name="uq_aut_cuenta_cliente_herramienta"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # "PRESUPUESTOS_IA" / "PLANIFICACION_IA" (códigos de TOOLS en tool_registry).
    herramienta: Mapped[str] = mapped_column(String(32), nullable=False)
    empresa_nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    # UUID de la empresa en la app de presupuestos; nulo hasta que se completa el alta.
    empresa_id_app: Mapped[str | None] = mapped_column(String(36), nullable=True)
    admin_email: Mapped[str] = mapped_column(String(255), nullable=False)
    admin_nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    # UUID del usuario administrador en la app de presupuestos.
    admin_user_id_app: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # "activa" / "suspendida"
    estado: Mapped[str] = mapped_column(String(16), default="activa", nullable=False)
    vigencia_hasta: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # Correo del operador de la firma que dio de alta la cuenta.
    creado_por: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow, nullable=False
    )
