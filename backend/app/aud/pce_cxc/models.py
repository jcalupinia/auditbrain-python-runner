"""Corridas del papel de trabajo de pérdidas esperadas (AUD.PCE_CXC).

Se guardan los parámetros y el resultado completo: el papel de trabajo debe poder
reproducirse tal como se emitió, sin volver a cargar los archivos.
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.app.db.session import Base


class CorridaPCE(Base):
    __tablename__ = "aud_pce_corridas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    entidad: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    fecha_corte: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    parametros: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resultado: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))


def guardar_corrida(db: Session, **campos) -> CorridaPCE:
    corrida = CorridaPCE(**campos)
    db.add(corrida)
    db.commit()
    db.refresh(corrida)
    return corrida
