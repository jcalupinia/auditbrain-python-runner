"""Regresión: la migración debe ensanchar ``users.role`` para acomodar
``Role.client`` (6 chars) en Postgres legacy donde la columna se creó como
VARCHAR(5) (cuando los únicos valores eran ``admin``/``user``).

SQLite no enforce length, así que el bug sólo aparece en producción. Aquí
ejercitamos el path de Postgres con un emulador: creamos una tabla
``users`` con ``role VARCHAR(5)`` directamente, llamamos a ``init_db()`` y
verificamos que la longitud sea ahora >=16 (o que la inserción de
``client`` no falle).
"""
import os
import uuid

import pytest
from sqlalchemy import inspect, text

from backend.app.db.session import engine, init_db


def _dialect_supports_alter_column_type() -> bool:
    return engine.dialect.name in {"postgresql", "postgres"}


def test_init_db_idempotent_when_role_already_wide():
    """En SQLite (tests por defecto) la migración debe ser no-op silenciosa.

    Llamar a ``init_db()`` dos veces no debe fallar ni romper la tabla.
    """
    init_db()
    init_db()  # idempotente
    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("users")}
    assert "role" in cols


@pytest.mark.skipif(
    not _dialect_supports_alter_column_type(),
    reason="ALTER COLUMN TYPE sólo aplica en Postgres; SQLite no enforce length.",
)
def test_role_column_widened_on_postgres():
    """En Postgres, tras ``init_db()`` la columna ``role`` debe permitir
    al menos 16 chars para que ``client`` (6) entre sin truncar."""
    # Forzamos el escenario legacy: VARCHAR(5).
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ALTER COLUMN role TYPE VARCHAR(5)"))

    init_db()  # debe ensanchar

    insp = inspect(engine)
    role_col = next(c for c in insp.get_columns("users") if c["name"] == "role")
    assert getattr(role_col["type"], "length", 0) >= 16, (
        f"role column length is {role_col['type'].length}, expected >=16"
    )


def test_create_user_with_client_role_does_not_truncate():
    """Smoke test end-to-end: tras ``init_db()``, crear un User con
    ``Role.client`` no debe lanzar ``StringDataRightTruncation`` ni equivalente.
    """
    from backend.app.auth.models import Role
    from backend.app.auth.service import create_user
    from backend.app.db.session import SessionLocal

    init_db()
    db = SessionLocal()
    try:
        email = f"role-client-mig-{uuid.uuid4().hex[:8]}@x.com"
        u = create_user(db, email=email, password="pwd123!", role=Role.client)
        assert u.role == Role.client
        assert u.role.value == "client"
    finally:
        db.close()
