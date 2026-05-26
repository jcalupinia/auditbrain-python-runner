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
    """Crea las tablas si no existen y aplica migraciones ligeras.

    Migraciones formales (Alembic) quedan en el roadmap. Para Fase 2 · M1
    añadimos columnas de contexto operativo a ``users`` con ALTER TABLE
    idempotente (SQLite y Postgres lo soportan con la misma sintaxis).
    """
    from sqlalchemy import inspect, text

    # Registrar todas las tablas conocidas (orden importa: organizations y
    # projects deben existir antes de que users referencie sus columnas).
    from backend.app.auth import models as _auth_models  # noqa: F401
    from backend.app.aud.obligaciones_fiscales import models as _aud_of_models  # noqa: F401
    from backend.app.chat import models as _chat_models  # noqa: F401
    from backend.app.context import models as _context_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Migración aditiva en ``users``: añade columnas si faltan.
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    alters: list[str] = []
    if "organization_id" not in existing_cols:
        alters.append("ALTER TABLE users ADD COLUMN organization_id INTEGER")
    if "active_project_id" not in existing_cols:
        alters.append("ALTER TABLE users ADD COLUMN active_project_id INTEGER")
    if alters:
        with engine.begin() as conn:
            for stmt in alters:
                conn.execute(text(stmt))
