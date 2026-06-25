"""Lógica de usuarios: alta, autenticación y bootstrap del admin."""

import datetime
import os
import uuid

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


def list_operators(db: Session) -> list[User]:
    """Operadores del Command Center (roles admin/user), excluye clientes de portal."""
    return list(
        db.execute(
            select(User).where(User.role != Role.client).order_by(User.email)
        ).scalars()
    )


def reset_user_password(db: Session, *, user: User) -> str:
    """Genera una clave temporal para un operador y la devuelve en claro (una sola vez)."""
    from backend.app.client_portal.service import _generate_temp_password

    temp = _generate_temp_password()
    user.hashed_password = hash_password(temp)
    user.password_reset_required = True
    user.is_active = True
    db.add(user)
    db.commit()
    return temp


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def start_new_session(db: Session, *, user: User) -> str:
    """Genera nuevo session_id, lo guarda en User, retorna el sid.
    Invalida cualquier sesión anterior (last-login-wins).
    """
    sid = str(uuid.uuid4())
    user.current_session_id = sid
    user.session_started_at = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    db.add(user)
    db.commit()
    return sid


def invalidate_session(db: Session, *, user: User) -> None:
    """Limpia el session_id activo (logout o force-logout admin)."""
    user.current_session_id = None
    user.session_started_at = None
    db.add(user)
    db.commit()


def ensure_bootstrap_admin(db: Session) -> None:
    """Crea el admin inicial desde el entorno si no existe (idempotente)."""
    email = os.getenv("AUDITBRAIN_BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    password = os.getenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not email or not password:
        return
    if get_user_by_email(db, email):
        return
    create_user(db, email=email, password=password, role=Role.admin)
