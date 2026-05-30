"""Service layer del staff portal: gestión de cuentas y dispositivos cliente."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth import device as device_mod
from backend.app.auth.models import ClientDevice, Role, User
from backend.app.auth.service import invalidate_session


def list_portal_users(db: Session, *, client_id: int) -> list[User]:
    return list(
        db.execute(
            select(User).where(User.client_id == client_id, User.role == Role.client)
        ).scalars()
    )


def disable_portal_user(db: Session, *, user: User) -> None:
    user.is_active = False
    db.add(user)
    db.commit()


def list_devices(db: Session, *, user_id: int) -> list[ClientDevice]:
    return list(
        db.execute(
            select(ClientDevice).where(ClientDevice.user_id == user_id)
            .order_by(ClientDevice.registered_at.desc())
        ).scalars()
    )


def reset_all_devices(db: Session, *, user: User, revoked_by: User) -> int:
    return device_mod.revoke_all_devices_for_user(db, user=user, revoked_by=revoked_by)


def force_logout(db: Session, *, user: User) -> None:
    invalidate_session(db, user=user)
