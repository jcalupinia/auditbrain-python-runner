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


def _ensure_forge_append_only_triggers() -> None:
    """Hace ``forge_decisions`` **append-only a nivel de motor** (F2b, §3.2).

    Un trigger, no ``REVOKE``: en el Postgres de Render la app es **dueña** de la
    tabla y el dueño conserva todos los privilegios (``REVOKE`` sería no-op). El
    trigger bloquea UPDATE/DELETE **independientemente de la propiedad**, y tiene la
    misma semántica en SQLite, así que la garantía se prueba en CI (que corre sobre
    SQLite). Idempotente.

    Si algo falla aquí, se registra pero **no se tumba el arranque** (misma filosofía
    que F2b.0): el servicio nunca emite UPDATE/DELETE sobre la cadena, así que el
    trigger es la garantía dura contra un bug o código rogue, no la única barrera.
    """
    from sqlalchemy import text

    dialect = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dialect == "postgresql":
                conn.execute(
                    text(
                        "CREATE OR REPLACE FUNCTION forge_decisions_append_only() "
                        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                        "RAISE EXCEPTION 'forge_decisions es append-only'; "
                        "END; $$;"
                    )
                )
                conn.execute(
                    text(
                        "DROP TRIGGER IF EXISTS forge_decisions_no_mutate "
                        "ON forge_decisions;"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TRIGGER forge_decisions_no_mutate "
                        "BEFORE UPDATE OR DELETE ON forge_decisions "
                        "FOR EACH ROW EXECUTE FUNCTION forge_decisions_append_only();"
                    )
                )
            elif dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS forge_decisions_no_update "
                        "BEFORE UPDATE ON forge_decisions BEGIN "
                        "SELECT RAISE(ABORT, 'forge_decisions es append-only'); END;"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS forge_decisions_no_delete "
                        "BEFORE DELETE ON forge_decisions BEGIN "
                        "SELECT RAISE(ABORT, 'forge_decisions es append-only'); END;"
                    )
                )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "No se pudieron crear los triggers append-only de forge_decisions"
        )


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
    from backend.app.ict import models as _ict_models  # noqa: F401
    from backend.app.events import models as _events_models  # noqa: F401
    from backend.app.forge import models as _forge_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    _ensure_forge_append_only_triggers()

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

    # Portal cliente (M2): nuevas columnas en users
    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    for col_def in [
        ("client_id", "INTEGER"),
        ("password_reset_required", "BOOLEAN DEFAULT FALSE NOT NULL"),
        ("current_session_id", "VARCHAR(64)"),
        ("session_started_at", "TIMESTAMP"),
    ]:
        col_name, col_type = col_def
        if col_name not in existing_cols:
            with engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}"))

    # Portal cliente (M2): ensanchar ``users.role`` para acomodar ``Role.client``
    # (6 chars). SQLAlchemy ``Enum(..., native_enum=False)`` infiere el VARCHAR
    # como max(len(value)); antes de añadir el rol ``client``, el max era
    # ``admin``/``user`` => VARCHAR(5), y la inserción del primer cliente
    # falla con ``StringDataRightTruncation`` en Postgres. SQLite no enforce
    # length, así que sólo importa en producción. Idempotente: si la columna
    # ya es VARCHAR(>=16) (o el dialecto no expone ``length``), no-op.
    role_col = next(
        (c for c in inspector.get_columns("users") if c["name"] == "role"), None
    )
    if role_col is not None:
        col_type = role_col.get("type")
        current_len = getattr(col_type, "length", None)
        if current_len is not None and current_len < 16:
            with engine.begin() as conn:
                try:
                    conn.execute(
                        text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(16)")
                    )
                except Exception:
                    # SQLite no soporta ALTER COLUMN TYPE; se ignora.
                    pass

    # Migración destructiva en ``event_registrations``: eliminar columna
    # ``whatsapp_enviado`` (WhatsApp Cloud API eliminado, reemplazado por QR).
    if "event_registrations" in inspector.get_table_names():
        ev_cols = {c["name"] for c in inspector.get_columns("event_registrations")}
        if "whatsapp_enviado" in ev_cols:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE event_registrations DROP COLUMN whatsapp_enviado"))

    # Migración aditiva en ``tool_jobs``: firma_auditora (M1+), portal cliente (M2).
    if "tool_jobs" in inspector.get_table_names():
        existing_cols = {c["name"] for c in inspector.get_columns("tool_jobs")}
        for col_def in [
            ("firma_auditora", "VARCHAR(32)"),
            ("initiated_from", "VARCHAR(16) DEFAULT 'staff' NOT NULL"),
            ("notify_email", "VARCHAR(320)"),
        ]:
            col_name, col_type = col_def
            if col_name not in existing_cols:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE tool_jobs ADD COLUMN {col_name} {col_type}"))

    # Backfill de entitlements: concede la sección Tributarias a los clientes
    # existentes en el primer arranque tras activar el gating comercial.
    try:
        from backend.app.client_portal.entitlements import backfill_tributarias
        _bf_db = SessionLocal()
        try:
            backfill_tributarias(_bf_db)
        finally:
            _bf_db.close()
    except Exception:
        # El backfill nunca debe impedir el arranque de la app, pero un fallo
        # silencioso dejaría a los clientes sin acceso sin dejar rastro: logueamos.
        import logging
        logging.getLogger(__name__).exception("backfill_tributarias falló en init_db")
