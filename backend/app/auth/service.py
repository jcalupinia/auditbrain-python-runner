"""Lógica de usuarios: alta, autenticación y bootstrap del admin."""

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import Role, User
from backend.app.auth.password import hash_password, verify_password


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()


def create_user(
    db: Session, email: str, password: str, role: Role = Role.user
) -> User:
    user = User(
        email=email.lower(),
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def ensure_bootstrap_admin(db: Session) -> None:
    """Crea el admin inicial desde el entorno si no existe (idempotente)."""
    email = os.getenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not email or not password:
        return
    if get_user_by_email(db, email):
        return
    create_user(db, email=email, password=password, role=Role.admin)
