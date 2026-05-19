"""Capa de base de datos (SQLAlchemy 2.0).

DATABASE_URL desde el entorno. Si no está definida, usa SQLite local
(dev/test) para no exigir Postgres en entornos sin él. En Render se
inyecta la DATABASE_URL del Postgres administrado.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./auditbrain.db").strip()

# Render entrega a veces "postgres://"; SQLAlchemy 2 requiere "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_connect_args = (
    {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency FastAPI: sesión por request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Crea las tablas si no existen.

    Migraciones formales (Alembic) quedan en el roadmap; create_all es
    suficiente para el esquema inicial de usuarios.
    """
    from backend.app.auth import models  # noqa: F401  (registra tablas)

    Base.metadata.create_all(bind=engine)
