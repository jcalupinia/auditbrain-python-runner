"""Modelo SQLAlchemy de la ficha de diseño de una herramienta NIIF."""

import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class NiifFicha(Base):
    """Ficha de diseño de una prueba de auditoría NIIF.

    ``items`` y ``salidas`` van como JSON porque son listas de longitud libre
    cuya forma la fija la ficha (bloques 2 y 4 de la estructura), no el
    esquema: normalizarlas en tablas hijas no compraría ninguna consulta que
    el portal necesite hoy.
    """

    __tablename__ = "niif_fichas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # --- Identificación -------------------------------------------------
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    rubro: Mapped[str] = mapped_column(String(64), nullable=False)
    norma: Mapped[str] = mapped_column(String(160), nullable=False)
    parrafo: Mapped[str] = mapped_column(String(160), nullable=False)

    # --- Contenido de la ficha -----------------------------------------
    items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    salidas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    # --- Ciclo de vida ---------------------------------------------------
    # "en_diseño" -> "probada" -> "enviada". Sin saltos (ver service.py).
    estado: Mapped[str] = mapped_column(String(16), default="en_diseño", nullable=False)

    autor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    autor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)

    # Quién verificó que la prueba funciona, y cuándo. Queda registrado
    # igual que el resto del portal registra sus revisiones.
    probada_por_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    probada_por_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    probada_en: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    enviada_por_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    enviada_por_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    enviada_en: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora, nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora, onupdate=_ahora, nullable=False
    )
