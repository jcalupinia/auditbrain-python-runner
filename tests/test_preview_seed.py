"""Siembra de cuentas de operador del preview (``core/preview_seed``).

Verifica: (1) fuera de preview es un no-op total; (2) en preview crea las 8
cuentas de la matriz con rol ``user`` y clave propia recuperable; (3) cada cuenta
tiene una contraseña aleatoria DISTINTA (no compartida) que autentica por el flujo
real; (4) es idempotente (no duplica); (5) re-emite la clave si su archivo se
perdió; (6) no toca usuarios existentes ajenos a la matriz. No depende de Postgres:
corre sobre la base hermética de la suite (ver conftest) y un directorio temporal
para las claves.
"""
import uuid

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role, User
from backend.app.core import preview_seed
from backend.app.core.preview_users import PREVIEW_ACCOUNTS
from backend.app.db.session import SessionLocal

ALIASES = [a["alias"] for a in PREVIEW_ACCOUNTS]


def _borrar_sembrados() -> None:
    s = SessionLocal()
    try:
        for alias in ALIASES:
            u = auth_service.get_user_by_email(s, alias)
            if u:
                s.delete(u)
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _aislar(tmp_path, monkeypatch):
    """Base sin las cuentas de la matriz y claves en un directorio temporal."""
    monkeypatch.setenv("PREVIEW_USER_SECRETS_DIR", str(tmp_path / "preview-users"))
    _borrar_sembrados()
    yield
    _borrar_sembrados()


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def preview_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")


def test_fuera_de_preview_es_no_op(db, monkeypatch):
    """APP_ENV=production: no crea NADA (garantía de aislamiento con producción)."""
    monkeypatch.setenv("APP_ENV", "production")
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is True and r["seeded"] == []
    for alias in ALIASES:
        assert auth_service.get_user_by_email(db, alias) is None


def test_siembra_los_operadores_con_rol_y_clave_recuperable(db, preview_env):
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is False
    assert len(r["seeded"]) == len(PREVIEW_ACCOUNTS) == 8

    claves = {}
    import pathlib, os
    secrets_dir = pathlib.Path(os.environ["PREVIEW_USER_SECRETS_DIR"])
    for acc in PREVIEW_ACCOUNTS:
        alias = acc["alias"]
        u = auth_service.get_user_by_email(db, alias)
        assert u is not None and u.role == Role.user and u.is_active
        assert u.organization_id is not None
        # La clave quedó guardada con nombre = parte local del alias.
        f = secrets_dir / preview_seed._alias_slug(alias)
        assert f.is_file(), f"falta la clave de {alias}"
        pw = f.read_text(encoding="utf-8").strip()
        assert pw  # no vacía
        claves[alias] = pw
        # Autentica por el flujo real con su propia clave; una mala NO autentica.
        assert auth_service.authenticate_user(db, alias, pw)
        assert auth_service.authenticate_user(db, alias, "mala") is None

    # Claves ALEATORIAS e INDEPENDIENTES: todas distintas entre sí.
    assert len(set(claves.values())) == len(claves)


def test_idempotente_no_duplica(db, preview_env):
    preview_seed.seed_preview_users(db)
    ids1 = {
        u.email: u.id
        for u in db.execute(select(User).where(User.email.in_(ALIASES))).scalars()
    }
    r2 = preview_seed.seed_preview_users(db)
    assert r2["seeded"] == []  # segunda pasada no crea nada
    ids2 = {
        u.email: u.id
        for u in db.execute(select(User).where(User.email.in_(ALIASES))).scalars()
    }
    assert ids1 == ids2 and len(ids1) == len(PREVIEW_ACCOUNTS)


def test_reemite_clave_si_se_perdio_el_archivo(db, preview_env):
    """Si la cuenta existe pero su clave no es recuperable, se re-emite."""
    import pathlib, os
    preview_seed.seed_preview_users(db)
    secrets_dir = pathlib.Path(os.environ["PREVIEW_USER_SECRETS_DIR"])
    alias = ALIASES[0]
    (secrets_dir / preview_seed._alias_slug(alias)).unlink()

    r = preview_seed.seed_preview_users(db)
    assert r["seeded"] == []  # no recrea
    assert alias in r["reissued"]
    nueva = (secrets_dir / preview_seed._alias_slug(alias)).read_text().strip()
    assert auth_service.authenticate_user(db, alias, nueva)


def test_no_modifica_usuarios_existentes(db, preview_env):
    """Una cuenta ajena a la matriz (p. ej. un admin) no se toca al sembrar."""
    email = f"existente-{uuid.uuid4().hex[:8]}@example.com"
    pre = auth_service.create_user(db, email=email, password="original-pw", role=Role.admin)
    hash_antes, rol_antes = pre.hashed_password, pre.role
    try:
        preview_seed.seed_preview_users(db)
        db.refresh(pre)
        assert pre.hashed_password == hash_antes and pre.role == rol_antes and pre.is_active
    finally:
        db.delete(pre)
        db.commit()
