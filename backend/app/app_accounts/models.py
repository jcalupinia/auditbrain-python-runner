"""Modelos de las Cuentas de Aplicaciones AUDIT-IA.

Tipo de cuenta dedicado para el login de las aplicaciones de la plataforma (AUDIT SOUND
y futuras), independiente de la tabla `users` (operadores y portal de auditoría). Así los
clientes nuevos de las apps se administran en su propia sección sin mezclarse con las
cuentas del portal de auditoría.
"""

import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.session import Base


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class AppAccount(Base):
    __tablename__ = "app_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    client_label: Mapped[str | None] = mapped_column(String(200), nullable=True)  # cliente/empresa (texto)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    password_reset_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(320), nullable=True)   # email del admin
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, nullable=False)


class AppAccountEntitlement(Base):
    """Permiso de una cuenta de aplicación para acceder a una app del catálogo.
    Una fila = una app concedida."""

    __tablename__ = "app_account_entitlements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    app_account_id: Mapped[int] = mapped_column(
        ForeignKey("app_accounts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    app_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("app_account_id", "app_key", name="uq_appacct_app"),
    )
