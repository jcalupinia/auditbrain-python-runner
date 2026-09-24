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

# Parámetros de pool EXPLÍCITOS para Postgres (2026-08-04).
#
# Antes se dependía de los defaults implícitos de SQLAlchemy (pool_size=5,
# max_overflow=10). Se fijan aquí por tres motivos:
#
#  1. `pool_recycle`: Render cierra conexiones ociosas por su lado. Una
#     conexión reciclada por el servidor pero viva en el pool provoca un
#     error en la primera consulta que la use. `pool_pre_ping` ya lo
#     detectaba (a costa de un SELECT 1 extra), pero reciclar a los 30 min
#     evita llegar a ese punto.
#  2. `pool_timeout`: con el default de 30s, una petición que no consigue
#     conexión se queda ocupando un hilo del threadpool medio minuto. 10s
#     falla antes y libera el hilo, que es lo que interesa en un servicio de
#     1 CPU.
#  3. Visibilidad: los valores quedan a la vista y ajustables por entorno sin
#     tocar código. Los defaults se dejan en 5/10 —los mismos que ya había—
#     para NO alterar el comportamiento actual: el diagnóstico mostró 3
#     conexiones en uso sobre un máximo de 103, así que el pool no es el
#     cuello de botella y no hay motivo para ampliarlo a ciegas.
#
# Solo se aplican a Postgres: SQLite (dev/tests) usa clases de pool distintas
# que no aceptan `max_overflow`.
_pool_kwargs: dict = {}
if not DATABASE_URL.startswith("sqlite"):
    _pool_kwargs = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": int(os.getenv("DB_POOL_TIMEOUT", "10")),
        "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "1800")),
    }

engine = create_engine(
    DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args, **_pool_kwargs
)
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


def _ensure_bitacora_append_only_trigger() -> None:
    """Hace ``aud_prueba_eventos`` **inmutable a nivel de motor** (P2-G, ENG-020).

    A diferencia de ``forge_decisions`` (que bloquea UPDATE y DELETE), aquí el
    trigger bloquea **solo UPDATE**: el DELETE es legítimo en dos lugares del
    ciclo —``servicio.encerar`` (reinicia la prueba) y ``servicio.eliminar``
    (quita la prueba con su historial)—, ambos operaciones de ciclo de vida
    confirmadas por el usuario. El vector de manipulación real es *alterar en
    sitio* el contenido de un evento ya escrito, y eso es lo que el UPDATE
    imposibilita a nivel de motor, aun contra SQL crudo. El borrado parcial de un
    evento intermedio lo delata ``gobernanza.verificar_cadena`` (rompe la
    contigüidad de ``seq`` y el ``prev_hash``).

    Misma filosofía que los triggers de Forge: idempotente, misma semántica en
    Postgres y SQLite (se prueba en CI sobre SQLite) y falla suave —si algo
    revienta se registra pero no se tumba el arranque; el servicio nunca emite
    UPDATE sobre la bitácora, así que el trigger es la garantía dura contra un
    bug o código rogue, no la única barrera.
    """
    from sqlalchemy import text

    dialect = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dialect == "postgresql":
                conn.execute(
                    text(
                        "CREATE OR REPLACE FUNCTION aud_prueba_eventos_append_only() "
                        "RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                        "RAISE EXCEPTION 'aud_prueba_eventos es append-only: los eventos no se modifican'; "
                        "END; $$;"
                    )
                )
                conn.execute(
                    text(
                        "DROP TRIGGER IF EXISTS aud_prueba_eventos_no_update "
                        "ON aud_prueba_eventos;"
                    )
                )
                conn.execute(
                    text(
                        "CREATE TRIGGER aud_prueba_eventos_no_update "
                        "BEFORE UPDATE ON aud_prueba_eventos "
                        "FOR EACH ROW EXECUTE FUNCTION aud_prueba_eventos_append_only();"
                    )
                )
            elif dialect == "sqlite":
                conn.execute(
                    text(
                        "CREATE TRIGGER IF NOT EXISTS aud_prueba_eventos_no_update "
                        "BEFORE UPDATE ON aud_prueba_eventos BEGIN "
                        "SELECT RAISE(ABORT, 'aud_prueba_eventos es append-only: los eventos no se modifican'); END;"
                    )
                )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "No se pudo crear el trigger append-only de aud_prueba_eventos"
        )


def _drop_bitacora_append_only_trigger() -> None:
    """Quita el trigger append-only de ``aud_prueba_eventos`` (idempotente).

    El sellado histórico (``servicio.sellar_bitacora_historica``) hace UPDATE
    sobre filas viejas, así que si en un arranque anterior ya se creó el trigger,
    hay que retirarlo mientras se sella y volver a crearlo justo después. Falla
    suave, igual que el resto de la orquestación de arranque.
    """
    from sqlalchemy import text

    dialect = engine.dialect.name
    try:
        with engine.begin() as conn:
            if dialect == "postgresql":
                conn.execute(text(
                    "DROP TRIGGER IF EXISTS aud_prueba_eventos_no_update ON aud_prueba_eventos;"
                ))
            elif dialect == "sqlite":
                conn.execute(text("DROP TRIGGER IF EXISTS aud_prueba_eventos_no_update;"))
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "No se pudo retirar el trigger append-only de aud_prueba_eventos para sellar"
        )


def _ensure_execution_idempotency_index() -> None:
    """Índice único PARCIAL de idempotencia de ``execution_runs`` (AUT-004).

    No puede haber DOS corridas "vivas" con la misma ``idempotency_key``. La
    garantía dura se expresa como índice único parcial en Postgres (no
    portable a ``__table_args__``); en SQLite (CI/tests) se emula dentro de
    ``execution.queue.enqueue`` con un SELECT previo en la misma transacción,
    así que aquí es un no-op. Falla suave: si algo revienta se registra pero
    no se tumba el arranque (patrón de ``_ensure_forge_append_only_triggers``).
    """
    from sqlalchemy import text

    if engine.dialect.name != "postgresql":
        return
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_runs_idem_live "
                    "ON execution_runs (idempotency_key) "
                    "WHERE status NOT IN ('canceled', 'dead_letter');"
                )
            )
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "No se pudo crear el índice parcial de idempotencia de execution_runs"
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
    from backend.app.aud.obligaciones_fiscales.mayor import models as _mayor_models  # noqa: F401
    from backend.app.aud.niif import models as _aud_niif_models  # noqa: F401
    from backend.app.aud.niif.ciclo import models as _aud_ciclo_models  # noqa: F401
    from backend.app.chat import models as _chat_models  # noqa: F401
    from backend.app.context import models as _context_models  # noqa: F401
    from backend.app.ict import models as _ict_models  # noqa: F401
    from backend.app.events import models as _events_models  # noqa: F401
    from backend.app.recursos import models as _recursos_models  # noqa: F401
    from backend.app.forge import models as _forge_models  # noqa: F401
    from backend.app.execution import models as _execution_models  # noqa: F401
    from backend.app.audit_apps import models as _audit_apps_models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    _ensure_forge_append_only_triggers()
    # Sellado histórico de la bitácora del ciclo: numera y encadena los eventos
    # previos a P2-G. Corre ANTES del trigger append-only porque hace UPDATE
    # sobre esas filas. Falla suave (no tumba el arranque); si algo revienta, la
    # cadena sin sellar la delata luego ``verificar_bitacora``.
    try:
        from backend.app.aud.niif.ciclo import servicio as _ciclo_srv
        # Retirar el trigger (si un arranque previo lo creó) para poder sellar con
        # UPDATE; se recrea inmediatamente después con _ensure_...().
        _drop_bitacora_append_only_trigger()
        _seal_db = SessionLocal()
        try:
            if _ciclo_srv.sellar_bitacora_historica(_seal_db):
                _seal_db.commit()
        finally:
            _seal_db.close()
    except Exception:
        import logging
        logging.getLogger(__name__).exception("sellar_bitacora_historica falló en init_db")
    _ensure_bitacora_append_only_trigger()
    _ensure_execution_idempotency_index()

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
    # Migración aditiva en ``niif_fichas``: la definición que corrió en el
    # Estudio se guarda al marcar la ficha como probada (diseño 2026-09-21,
    # §4). Sin ella, una ficha «enviada» no se puede aplicar a un cliente.
    if "niif_fichas" in inspector.get_table_names():
        if "definicion" not in {c["name"] for c in inspector.get_columns("niif_fichas")}:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE niif_fichas ADD COLUMN definicion JSON"))

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

    # Migración aditiva en ``tool_jobs``: modalidad manual del mayor.
    if "tool_jobs" in inspector.get_table_names():
        cols_jobs = {c["name"] for c in inspector.get_columns("tool_jobs")}
        if "mayor_especifico_categoria" not in cols_jobs:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE tool_jobs ADD COLUMN mayor_especifico_categoria VARCHAR(32)")
                )

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
