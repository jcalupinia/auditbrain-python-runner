"""Service layer del portal cliente: creación de cuentas, autenticación,
operaciones específicas del rol client.
"""

from __future__ import annotations

import secrets
import string

from sqlalchemy.orm import Session

from backend.app.auth.models import Role, User
from backend.app.auth.password import hash_password, verify_password
from backend.app.context.models import Client


def _generate_temp_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
        ):
            return pwd


def create_portal_user(
    db: Session, *, client_id: int, email: str
) -> tuple[User, str]:
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError(f"Client {client_id} no existe.")

    temp_pwd = _generate_temp_password()
    user = User(
        email=email.lower(),
        hashed_password=hash_password(temp_pwd),
        role=Role.client,
        is_active=True,
        client_id=client.id,
        organization_id=client.organization_id,
        password_reset_required=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, temp_pwd


def authenticate_portal_user(db: Session, email: str, password: str) -> User | None:
    from sqlalchemy import select

    user = db.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if user.role != Role.client:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def change_password(
    db: Session, *, user: User, new_password: str
) -> None:
    if len(new_password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")
    user.hashed_password = hash_password(new_password)
    user.password_reset_required = False
    db.add(user)
    db.commit()
