"""El admin de bootstrap no debe crearse con un email inválido.

Detectado el 2026-08-05 levantando el entorno local: con
AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL="admin@local.test" el usuario se creaba sin
problema y el login devolvía 200, pero cualquier endpoint que serializara el
usuario reventaba con 500 (`ResponseValidationError`), porque el schema usa
`EmailStr` y `.test` es un TLD reservado. El fallo aparecía lejos de su
causa, que es lo que lo hace caro de diagnosticar.
"""

from __future__ import annotations

import uuid

from backend.app.auth import service as auth_service
from backend.app.db.session import SessionLocal, init_db


def _sin_usuario(email: str) -> bool:
    db = SessionLocal()
    try:
        return auth_service.get_user_by_email(db, email) is None
    finally:
        db.close()


def test_un_email_de_dominio_reservado_no_crea_admin(monkeypatch):
    init_db()
    email = f"admin-{uuid.uuid4().hex[:6]}@local.test"
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "Sup3rSecret!")

    db = SessionLocal()
    try:
        auth_service.ensure_bootstrap_admin(db)
    finally:
        db.close()

    assert _sin_usuario(email), (
        "Se creó un admin con email inválido: el login funcionaría pero "
        "cualquier endpoint que lo serialice devolvería 500."
    )


def test_un_email_valido_si_crea_el_admin(monkeypatch):
    init_db()
    email = f"admin-{uuid.uuid4().hex[:6]}@auditconsulting.ec"
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "Sup3rSecret!")

    db = SessionLocal()
    try:
        auth_service.ensure_bootstrap_admin(db)
    finally:
        db.close()

    assert not _sin_usuario(email)


def test_es_idempotente_con_un_email_valido(monkeypatch):
    """Llamarlo dos veces no debe fallar ni duplicar."""
    init_db()
    email = f"admin-{uuid.uuid4().hex[:6]}@auditconsulting.ec"
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", email)
    monkeypatch.setenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "Sup3rSecret!")

    db = SessionLocal()
    try:
        auth_service.ensure_bootstrap_admin(db)
        auth_service.ensure_bootstrap_admin(db)
    finally:
        db.close()

    assert not _sin_usuario(email)
