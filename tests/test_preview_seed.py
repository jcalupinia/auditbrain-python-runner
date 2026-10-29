"""Siembra de cuentas de prueba del preview (``core/preview_seed``).

Verifica: (1) fuera de preview es un no-op total; (2) sin la clave del preview
no siembra; (3) en preview crea una cuenta por rol (user/client) con sus datos;
(4) es idempotente (no duplica); (5) no toca usuarios existentes. No depende de
Postgres: corre sobre la base hermética de la suite (ver conftest).
"""
import uuid

import pytest
from sqlalchemy import select

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role, User, UserToolEntitlement
from backend.app.client_portal.entitlements import list_user_tool_codes
from backend.app.client_portal.tool_registry import TOOLS
from backend.app.context.models import Client
from backend.app.core import preview_seed
from backend.app.db.session import SessionLocal

EMAILS = [preview_seed.PREVIEW_OPERADOR_EMAIL, preview_seed.PREVIEW_CLIENTE_EMAIL]
TEST_PW = "preview-pw-12345678"


def _borrar_sembrados() -> None:
    s = SessionLocal()
    try:
        for email in EMAILS:
            u = auth_service.get_user_by_email(s, email)
            if u:
                for e in s.execute(
                    select(UserToolEntitlement).where(UserToolEntitlement.user_id == u.id)
                ).scalars():
                    s.delete(e)
                s.delete(u)
        cli = s.execute(
            select(Client).where(Client.name == preview_seed.PREVIEW_CLIENTE_NOMBRE)
        ).scalar_one_or_none()
        if cli:
            s.delete(cli)
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _aislar():
    """Deja la base sin las cuentas de prueba antes y después de cada test."""
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
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", TEST_PW)


def test_fuera_de_preview_es_no_op(db, monkeypatch):
    """APP_ENV=production: no crea NADA (garantía de aislamiento con producción)."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", TEST_PW)
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is True and r["seeded"] == []
    assert auth_service.get_user_by_email(db, preview_seed.PREVIEW_OPERADOR_EMAIL) is None
    assert auth_service.get_user_by_email(db, preview_seed.PREVIEW_CLIENTE_EMAIL) is None


def test_sin_clave_del_preview_no_siembra(db, monkeypatch):
    monkeypatch.setenv("APP_ENV", "preview")
    monkeypatch.delenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    r = preview_seed.seed_preview_users(db)
    assert r["seeded"] == []
    assert auth_service.get_user_by_email(db, preview_seed.PREVIEW_OPERADOR_EMAIL) is None


def test_siembra_una_cuenta_por_rol_con_sus_datos(db, preview_env):
    r = preview_seed.seed_preview_users(db)
    assert r["skipped"] is False and len(r["seeded"]) == 2

    op = auth_service.get_user_by_email(db, preview_seed.PREVIEW_OPERADOR_EMAIL)
    assert op is not None and op.role == Role.user and op.is_active
    assert op.organization_id is not None

    cl = auth_service.get_user_by_email(db, preview_seed.PREVIEW_CLIENTE_EMAIL)
    assert cl is not None and cl.role == Role.client and cl.is_active
    assert cl.organization_id is not None and cl.client_id is not None

    # Entitlements = subconjunto válido del catálogo real (nunca códigos inventados).
    esperado = {c for c in preview_seed.PREVIEW_CLIENTE_TOOL_CODES if c in TOOLS}
    assert list_user_tool_codes(db, cl.id) == esperado

    # Las credenciales exclusivas del preview autentican por el flujo real.
    assert auth_service.authenticate_user(db, preview_seed.PREVIEW_OPERADOR_EMAIL, TEST_PW)
    assert auth_service.authenticate_user(db, preview_seed.PREVIEW_CLIENTE_EMAIL, TEST_PW)
    # Y una clave incorrecta NO autentica (no se debilitó la autenticación).
    assert auth_service.authenticate_user(db, preview_seed.PREVIEW_OPERADOR_EMAIL, "mala") is None


def test_idempotente_no_duplica(db, preview_env):
    preview_seed.seed_preview_users(db)
    ids1 = {
        u.email: u.id
        for u in db.execute(select(User).where(User.email.in_(EMAILS))).scalars()
    }
    r2 = preview_seed.seed_preview_users(db)
    assert r2["seeded"] == []  # segunda pasada no crea nada
    ids2 = {
        u.email: u.id
        for u in db.execute(select(User).where(User.email.in_(EMAILS))).scalars()
    }
    assert ids1 == ids2 and len(ids1) == 2  # mismos ids, sin duplicar
    # Un único Client de prueba (no se duplica entre despliegues).
    clientes = db.execute(
        select(Client).where(Client.name == preview_seed.PREVIEW_CLIENTE_NOMBRE)
    ).scalars().all()
    assert len(clientes) == 1


def test_no_modifica_usuarios_existentes(db, preview_env):
    """Una cuenta preexistente (p. ej. un admin) no se toca al sembrar."""
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
