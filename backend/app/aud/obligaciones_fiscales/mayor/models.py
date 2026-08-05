"""Persistencia del motor de mayores.

Tres tablas:
  · mayor_categorias        — catálogo configurable (semilla global + por organización)
  · mayor_homologaciones    — lo que el auditor confirmó, POR CLIENTE
  · mayor_clasificacion_job — foto inmutable de lo clasificado en cada job
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from backend.app.db.session import Base


def _ahora() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class MayorCategoria(Base):
    """Categoría fiscal. organization_id NULL = categoría de sistema."""

    __tablename__ = "mayor_categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=True
    )
    codigo: Mapped[str] = mapped_column(String(32), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    naturaleza_esperada: Mapped[str] = mapped_column(String(16), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    es_sistema: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "codigo", name="uq_mayor_categoria_org_codigo"),
    )


class MayorHomologacion(Base):
    """Lo aprendido de un cliente: esta cuenta es de esta categoría.

    La clave es client_id (NO project_id) para que el aprendizaje sobreviva
    de un ejercicio fiscal al siguiente.
    """

    __tablename__ = "mayor_homologaciones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    codigo_cuenta: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre_norm: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    categoria: Mapped[str] = mapped_column(String(32), nullable=False)
    tarifa: Mapped[float | None] = mapped_column(Float, nullable=True)
    veces_usada: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    creada_por_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_ahora, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=_ahora, nullable=False)

    __table_args__ = (
        UniqueConstraint("client_id", "codigo_cuenta", name="uq_mayor_homologacion_cliente_cuenta"),
    )


class MayorClasificacionJob(Base):
    """Qué se clasificó en un job y por qué. Alimenta la hoja de trazabilidad."""

    __tablename__ = "mayor_clasificacion_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(
        ForeignKey("tool_jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    codigo_cuenta: Mapped[str] = mapped_column(String(64), nullable=False)
    nombre_cuenta: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    n_movimientos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    debe: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    haber: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    por_mes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    categoria_sugerida: Mapped[str | None] = mapped_column(String(32), nullable=True)
    categoria_final: Mapped[str | None] = mapped_column(String(32), nullable=True)
    tarifa: Mapped[float | None] = mapped_column(Float, nullable=True)
    confianza: Mapped[str] = mapped_column(String(8), default="baja", nullable=False)
    origen: Mapped[str] = mapped_column(String(16), default="reglas", nullable=False)
    senales_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    corregida: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    aprobada_por_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aprobada_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
