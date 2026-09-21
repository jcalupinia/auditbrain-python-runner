"""Tablas del ciclo real de una prueba (diseño 2026-09-21, §4).

El «encargo» es el proyecto AUD del portal (`projects`); aquí solo se guarda lo
que el proyecto no tiene. `registro` va como JSON porque es la forma del
registro de una prueba en el sitio (programa, fuentes, requerimiento,
parámetros, ejecución, análisis, puntos de revisión) y las consultas solo
filtran por proyecto y estado: normalizarlo no compra nada hoy.

La tabla de archivos de evidencia llega con E7.
"""
import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class FichaEncargo(Base):
    """Datos del encargo que el proyecto del portal no tiene (RUC, marco, corte…).

    Validados con la regla portada de `parseEngagement` del sitio.
    """

    __tablename__ = "aud_ficha_encargo"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    datos: Mapped[dict] = mapped_column(JSON, nullable=False)
    actualizada_por: Mapped[str | None] = mapped_column(String(320), nullable=True)
    actualizada_en: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora, onupdate=_ahora, nullable=False
    )


class Prueba(Base):
    """Una prueba aplicada a un encargo, en uno de los 13 estados del sitio."""

    __tablename__ = "aud_pruebas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Versión anterior: una prueba aprobada es inmutable y se corrige con otra.
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("aud_pruebas.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estado: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    # Origen de la definición: "vnr", "pce" o "ficha:<id>".
    origen: Mapped[str] = mapped_column(String(40), nullable=False)
    definicion: Mapped[dict] = mapped_column(JSON, nullable=False)
    registro: Mapped[dict] = mapped_column(JSON, nullable=False)
    # Concurrencia optimista, como `revision` en el sitio: dos personas no pisan
    # el trabajo de la otra sin enterarse.
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    creada_por: Mapped[str | None] = mapped_column(String(320), nullable=True)
    creada_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=_ahora, nullable=False)
    actualizada_en: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=_ahora, onupdate=_ahora, nullable=False
    )
    aprobada_por: Mapped[str | None] = mapped_column(String(320), nullable=True)
    aprobada_en: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class PruebaEvento(Base):
    """Bitácora: quién hizo qué y cuándo. Alimenta la cédula 12."""

    __tablename__ = "aud_prueba_eventos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prueba_id: Mapped[int] = mapped_column(
        ForeignKey("aud_pruebas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    accion: Mapped[str] = mapped_column(String(40), nullable=False)
    estado_anterior: Mapped[str | None] = mapped_column(String(32), nullable=True)
    estado_nuevo: Mapped[str | None] = mapped_column(String(32), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(320), nullable=True)
    comentario: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime.datetime] = mapped_column(DateTime, default=_ahora, nullable=False)
