"""Siembra de cuentas de operador del preview (``core/preview_seed``).

Cubre: (1) fuera de preview es un no-op total; (2) arranque normal: crea las 8
cuentas con rol ``user`` y clave propia recuperable y distinta por cuenta;
(3) idempotencia (no duplica); (4) falta el archivo de clave de una cuenta
existente → NO cambia la contraseña, solo avisa; (5) error de escritura → la
cuenta NO se presenta como provisionada (queda inactiva, va a ``failed``);
(6) recuperación explícita (``reissue_password``) genera clave nueva e
independiente y solo en preview; (7) no modifica usuarios ajenos a la matriz.
No depende de Postgres: corre sobre la base hermética de la suite (ver conftest)
y un directorio temporal para las claves.
"""
import os
import pathlib
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


def _secrets_dir() -> pathlib.Path:
    return pathlib.Path(os.environ["PREVIEW_USER_SECRETS_DIR"])


def _leer_clave(alias: str) -> str:
    return (_secrets_dir() / preview_seed._alias_slug(alias)).read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
# (1) Fuera de preview
# --------------------------------------------------------------------------- #
def test_fuera_de_preview_es_no_op(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is True and r["seeded"] == []
    for alias in ALIASES:
        assert auth_service.get_user_by_email(db, alias) is None


# --------------------------------------------------------------------------- #
# (2) Arranque normal
# --------------------------------------------------------------------------- #
def test_arranque_normal_crea_operadores_con_clave_propia(db, preview_env):
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is False
    assert len(r["seeded"]) == len(PREVIEW_ACCOUNTS) == 8
    assert r["warnings"] == [] and r["failed"] == []

    claves = {}
    for acc in PREVIEW_ACCOUNTS:
        alias = acc["alias"]
        u = auth_service.get_user_by_email(db, alias)
        assert u is not None and u.role == Role.user and u.is_active
        assert u.organization_id is not None
        f = _secrets_dir() / preview_seed._alias_slug(alias)
        assert f.is_file(), f"falta la clave de {alias}"
        # Permisos restrictivos (600).
        assert (f.stat().st_mode & 0o777) == 0o600
        pw = _leer_clave(alias)
        assert pw
        claves[alias] = pw
        assert auth_service.authenticate_user(db, alias, pw)
        assert auth_service.authenticate_user(db, alias, "mala") is None

    # Claves ALEATORIAS e INDEPENDIENTES: todas distintas.
    assert len(set(claves.values())) == len(claves)


# --------------------------------------------------------------------------- #
# (3) Idempotencia
# --------------------------------------------------------------------------- #
def test_idempotente_no_duplica(db, preview_env):
    preview_seed.seed_preview_users(db)
    ids1 = {
        u.email: u.id
        for u in db.execute(select(User).where(User.email.in_(ALIASES))).scalars()
    }
    r2 = preview_seed.seed_preview_users(db)
    assert r2["seeded"] == [] and r2["warnings"] == [] and r2["failed"] == []
    ids2 = {
        u.email: u.id
        for u in db.execute(select(User).where(User.email.in_(ALIASES))).scalars()
    }
    assert ids1 == ids2 and len(ids1) == len(PREVIEW_ACCOUNTS)


# --------------------------------------------------------------------------- #
# (4) Falta el archivo de clave de una cuenta existente → NO se resetea
# --------------------------------------------------------------------------- #
def test_falta_archivo_no_cambia_la_contrasena_solo_avisa(db, preview_env):
    preview_seed.seed_preview_users(db)
    alias = ALIASES[0]
    pw_original = _leer_clave(alias)
    u_antes = auth_service.get_user_by_email(db, alias)
    hash_antes = u_antes.hashed_password

    # Se pierde el archivo de la clave.
    (_secrets_dir() / preview_seed._alias_slug(alias)).unlink()

    r = preview_seed.seed_preview_users(db)
    assert alias in r["warnings"]
    assert r["seeded"] == []  # no recrea
    # La contraseña y el hash NO cambian; el archivo NO se regenera solo.
    db.refresh(u_antes)
    assert u_antes.hashed_password == hash_antes
    assert auth_service.authenticate_user(db, alias, pw_original)
    assert not (_secrets_dir() / preview_seed._alias_slug(alias)).exists()


# --------------------------------------------------------------------------- #
# (5) Error de escritura → la cuenta no se presenta como provisionada
# --------------------------------------------------------------------------- #
def test_error_de_escritura_no_provisiona_la_cuenta(db, preview_env, monkeypatch):
    def _falla(alias, password):
        raise OSError("disco lleno (simulado)")

    monkeypatch.setattr(preview_seed, "_store_password", _falla)

    r = preview_seed.seed_preview_users(db)
    # Ninguna cuenta se reporta como provisionada; todas van a failed.
    assert r["seeded"] == []
    assert set(r["failed"]) == set(ALIASES)
    for alias in ALIASES:
        u = auth_service.get_user_by_email(db, alias)
        assert u is not None and u.is_active is False  # inactiva = no usable
        # Sin clave guardada y, al estar inactiva, no autentica con nada.
        assert auth_service.authenticate_user(db, alias, "lo-que-sea") is None


# --------------------------------------------------------------------------- #
# (6) Recuperación explícita
# --------------------------------------------------------------------------- #
def test_reissue_password_genera_clave_nueva_independiente(db, preview_env):
    preview_seed.seed_preview_users(db)
    alias = ALIASES[0]
    pw_vieja = _leer_clave(alias)
    (_secrets_dir() / preview_seed._alias_slug(alias)).unlink()

    pw_nueva = preview_seed.reissue_password(db, alias)
    assert pw_nueva and pw_nueva != pw_vieja
    # Nueva autentica; vieja ya no.
    assert auth_service.authenticate_user(db, alias, pw_nueva)
    assert auth_service.authenticate_user(db, alias, pw_vieja) is None
    # Queda guardada de nuevo con permisos 600.
    f = _secrets_dir() / preview_seed._alias_slug(alias)
    assert f.is_file() and (f.stat().st_mode & 0o777) == 0o600
    assert _leer_clave(alias) == pw_nueva


def test_reissue_reactiva_una_cuenta_inactiva(db, preview_env, monkeypatch):
    # Provoca una cuenta en estado failed (inactiva, sin clave).
    real_store = preview_seed._store_password
    monkeypatch.setattr(preview_seed, "_store_password",
                        lambda a, p: (_ for _ in ()).throw(OSError("fallo")))
    preview_seed.seed_preview_users(db)
    # Restaura SOLO _store_password (sin tocar los setenv de APP_ENV/dir).
    monkeypatch.setattr(preview_seed, "_store_password", real_store)

    alias = ALIASES[0]
    assert auth_service.get_user_by_email(db, alias).is_active is False
    pw = preview_seed.reissue_password(db, alias)
    u = auth_service.get_user_by_email(db, alias)
    assert u.is_active is True
    assert auth_service.authenticate_user(db, alias, pw)


def test_reissue_fuera_de_preview_falla(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        preview_seed.reissue_password(db, ALIASES[0])


def test_reissue_alias_fuera_de_matriz_falla(db, preview_env):
    with pytest.raises(KeyError):
        preview_seed.reissue_password(db, "cualquiera@example.com")


def test_reissue_cuenta_inexistente_falla(db, preview_env):
    # Alias válido de la matriz pero no sembrado aún.
    with pytest.raises(LookupError):
        preview_seed.reissue_password(db, ALIASES[0])


# --------------------------------------------------------------------------- #
# (7) No modifica usuarios ajenos a la matriz
# --------------------------------------------------------------------------- #
def test_no_modifica_usuarios_existentes(db, preview_env):
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
