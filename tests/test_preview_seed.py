"""Siembra de cuentas de prueba del preview desde el archivo de identidades.

Cubre: no-op fuera de preview; admin real desde el archivo + desactivación del
admin genérico de reserva; operadores rol user activos con claves independientes;
exclusión del admin de la lista de operadores; archivo ausente/ilegible/ inválido
→ configuración segura (sin operadores, admin genérico intacto); idempotencia;
no-reset con aviso; error de escritura → cuenta inactiva; recuperación explícita;
fallback de ``ensure_bootstrap_admin`` en preview; y la guarda anti-PII (ningún
correo real en archivos versionados). Base hermética de la suite (ver conftest).
"""
import json
import os
import pathlib

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role, User
from backend.app.core import preview_seed
from backend.app.core import preview_users as cfg
from backend.app.db.session import SessionLocal

ADMIN = "jefe.prueba@example.com"
OPERADORES = [f"op{i}.prueba@example.com" for i in range(1, 9)]  # 8 ficticios
TODOS = [ADMIN, cfg.GENERIC_ADMIN_EMAIL] + OPERADORES


def _borrar() -> None:
    s = SessionLocal()
    try:
        for email in TODOS:
            u = auth_service.get_user_by_email(s, email)
            if u:
                s.delete(u)
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _aislar(tmp_path, monkeypatch):
    monkeypatch.setenv(cfg.ENV_SECRETS_DIR, str(tmp_path / "preview-users"))
    monkeypatch.setenv(cfg.ENV_IDENTITIES_FILE, str(tmp_path / "identidades.json"))
    _borrar()
    yield
    _borrar()


@pytest.fixture()
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture()
def preview_env(monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")


def _escribir_identidades(admin=ADMIN, operators=None):
    operators = OPERADORES if operators is None else operators
    pathlib.Path(os.environ[cfg.ENV_IDENTITIES_FILE]).write_text(
        json.dumps({"admin": admin, "operators": operators}), encoding="utf-8"
    )


def _clave(email: str) -> str:
    f = pathlib.Path(os.environ[cfg.ENV_SECRETS_DIR]) / preview_seed._email_slug(email)
    return f.read_text(encoding="utf-8").strip()


# --------------------------------------------------------------------------- #
def test_fuera_de_preview_es_no_op(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    _escribir_identidades()
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is True
    assert auth_service.get_user_by_email(db, ADMIN) is None
    for e in OPERADORES:
        assert auth_service.get_user_by_email(db, e) is None


def test_admin_real_y_operadores_desde_el_archivo(db, preview_env):
    # Simula el admin genérico de reserva ya creado por ensure_bootstrap_admin.
    generico = auth_service.create_user(db, email=cfg.GENERIC_ADMIN_EMAIL, password="x" * 12, role=Role.admin)
    _escribir_identidades()

    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is False and r["admin"] == "seeded"
    assert r["operadores_creados"] == 8 and r["generic_desactivado"] is True

    adm = auth_service.get_user_by_email(db, ADMIN)
    assert adm is not None and adm.role == Role.admin and adm.is_active and adm.organization_id is not None

    # El admin genérico queda INACTIVO (no borrado) para no tener dos admins activos.
    db.refresh(generico)
    assert generico.is_active is False

    claves = {}
    for e in OPERADORES:
        u = auth_service.get_user_by_email(db, e)
        assert u is not None and u.role == Role.user and u.is_active and u.organization_id is not None
        f = pathlib.Path(os.environ[cfg.ENV_SECRETS_DIR]) / preview_seed._email_slug(e)
        assert f.is_file() and (f.stat().st_mode & 0o777) == 0o600
        pw = _clave(e)
        claves[e] = pw
        assert auth_service.authenticate_user(db, e, pw)
        assert auth_service.authenticate_user(db, e, "mala") is None
    # El admin también autentica con su propia clave, distinta de todas.
    claves[ADMIN] = _clave(ADMIN)
    assert auth_service.authenticate_user(db, ADMIN, claves[ADMIN])
    assert len(set(claves.values())) == len(claves)  # todas independientes


def test_admin_no_se_duplica_como_operador(db, preview_env):
    _escribir_identidades(admin=ADMIN, operators=[ADMIN] + OPERADORES)
    r = preview_seed.seed_preview_users(db)
    # El correo del admin no se crea además como operador.
    assert auth_service.get_user_by_email(db, ADMIN).role == Role.admin
    assert r["operadores_creados"] == 8


def test_sin_archivo_no_siembra_operadores_y_conserva_generico(db, preview_env):
    generico = auth_service.create_user(db, email=cfg.GENERIC_ADMIN_EMAIL, password="x" * 12, role=Role.admin)
    r = preview_seed.seed_preview_users(db)  # no se escribió el archivo
    assert r["admin"] == "generic" and r["operadores_creados"] == 0
    db.refresh(generico)
    assert generico.is_active is True  # el genérico de reserva se mantiene


def test_json_invalido_es_seguro(db, preview_env):
    pathlib.Path(os.environ[cfg.ENV_IDENTITIES_FILE]).write_text("{roto", encoding="utf-8")
    r = preview_seed.seed_preview_users(db)
    assert r["operadores_creados"] == 0 and r["admin"] == "generic"


def test_correos_invalidos_se_descartan(db, preview_env):
    _escribir_identidades(admin="no-es-correo", operators=["tampoco", OPERADORES[0]])
    r = preview_seed.seed_preview_users(db)
    assert r["admin"] == "generic"  # admin inválido → se ignora
    assert r["operadores_creados"] == 1  # solo el válido
    assert auth_service.get_user_by_email(db, OPERADORES[0]) is not None


def test_idempotente(db, preview_env):
    _escribir_identidades()
    preview_seed.seed_preview_users(db)
    r2 = preview_seed.seed_preview_users(db)
    assert r2["operadores_creados"] == 0 and r2["admin"] == "exists"
    ids = {u.email for u in db.execute(select(User).where(User.email.in_(OPERADORES))).scalars()}
    assert len(ids) == 8


def test_falta_archivo_de_clave_no_resetea(db, preview_env):
    _escribir_identidades()
    preview_seed.seed_preview_users(db)
    pw_orig = _clave(OPERADORES[0])
    hash_antes = auth_service.get_user_by_email(db, OPERADORES[0]).hashed_password
    (pathlib.Path(os.environ[cfg.ENV_SECRETS_DIR]) / preview_seed._email_slug(OPERADORES[0])).unlink()

    r = preview_seed.seed_preview_users(db)
    assert r["operadores_avisos"] >= 1 and r["operadores_creados"] == 0
    u = auth_service.get_user_by_email(db, OPERADORES[0])
    assert u.hashed_password == hash_antes
    assert auth_service.authenticate_user(db, OPERADORES[0], pw_orig)  # clave intacta


def test_error_de_escritura_deja_cuenta_inactiva(db, preview_env, monkeypatch):
    _escribir_identidades(admin=None, operators=OPERADORES)
    monkeypatch.setattr(preview_seed, "_store_password",
                        lambda e, p: (_ for _ in ()).throw(OSError("disco lleno")))
    r = preview_seed.seed_preview_users(db)
    assert r["operadores_creados"] == 0 and r["operadores_fallidos"] == 8
    for e in OPERADORES:
        u = auth_service.get_user_by_email(db, e)
        assert u is not None and u.is_active is False
        assert auth_service.authenticate_user(db, e, "lo-que-sea") is None


def test_reissue_por_correo(db, preview_env):
    _escribir_identidades()
    preview_seed.seed_preview_users(db)
    vieja = _clave(OPERADORES[0])
    (pathlib.Path(os.environ[cfg.ENV_SECRETS_DIR]) / preview_seed._email_slug(OPERADORES[0])).unlink()
    nueva = preview_seed.reissue_password(db, OPERADORES[0])
    assert nueva != vieja
    assert auth_service.authenticate_user(db, OPERADORES[0], nueva)
    assert auth_service.authenticate_user(db, OPERADORES[0], vieja) is None


def test_reissue_correo_fuera_del_archivo_falla(db, preview_env):
    _escribir_identidades()
    with pytest.raises(KeyError):
        preview_seed.reissue_password(db, "ajeno@example.com")


def test_reissue_fuera_de_preview_falla(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(RuntimeError):
        preview_seed.reissue_password(db, ADMIN)


# --------------------------------------------------------------------------- #
# ensure_bootstrap_admin: fallback genérico solo en preview
# --------------------------------------------------------------------------- #
def test_bootstrap_fallback_generico_en_preview(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.delenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "clave-preview-123456")
    try:
        auth_service.ensure_bootstrap_admin(db)
        g = auth_service.get_user_by_email(db, cfg.GENERIC_ADMIN_EMAIL)
        assert g is not None and g.role == Role.admin
    finally:
        g = auth_service.get_user_by_email(db, cfg.GENERIC_ADMIN_EMAIL)
        if g:
            db.delete(g)
            db.commit()


def test_bootstrap_sin_fallback_en_produccion(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "clave-prod-123456")
    auth_service.ensure_bootstrap_admin(db)
    # En producción, sin correo, NO se crea el admin genérico.
    assert auth_service.get_user_by_email(db, cfg.GENERIC_ADMIN_EMAIL) is None


# --------------------------------------------------------------------------- #
# Guarda anti-PII: ningún correo real en archivos versionados
# --------------------------------------------------------------------------- #
def test_sin_pii_en_archivos_versionados():
    raiz = pathlib.Path(__file__).resolve().parents[1]
    archivos = [
        "backend/app/core/preview_users.py",
        "backend/app/core/preview_seed.py",
        "docker-compose.preview.yml",
        "docs/preview-usuarios-prueba.md",
        "tests/test_preview_seed.py",
        "scripts/recuperar_clave_preview.py",
        "scripts/verificar_usuarios_preview.py",
    ]
    for rel in archivos:
        p = raiz / rel
        if not p.exists():
            continue
        texto = p.read_text(encoding="utf-8")
        # El dominio REAL de la firma no debe aparecer en archivos versionados.
        # Se arma por partes para que ESTE archivo no contenga el literal contiguo.
        dominio_real = "auditconsulting" + "." + "ec"
        assert dominio_real not in texto, f"PII (dominio real) en {rel}"
