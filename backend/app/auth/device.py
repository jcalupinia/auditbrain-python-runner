"""Helpers para vinculación dispositivo-cliente (capa 2 de seguridad)."""

from __future__ import annotations

import datetime
import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import ClientDevice, User


def generate_device_id() -> str:
    """Genera UUID4 string para identificar dispositivo en cookie."""
    return str(uuid.uuid4())


def compute_fingerprint_hash(
    user_agent: str = "",
    accept_language: str = "",
    accept_encoding: str = "",
) -> str:
    """Hash determinístico del navegador para segunda capa de validación."""
    raw = f"{user_agent}|{accept_language}|{accept_encoding}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def register_device(
    db: Session,
    *,
    user: User,
    fingerprint_hash: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> ClientDevice:
    """Crea ClientDevice nuevo para el usuario. Devuelve la instancia."""
    now = datetime.datetime.utcnow()
    device = ClientDevice(
        user_id=user.id,
        device_id=generate_device_id(),
        fingerprint_hash=fingerprint_hash,
        user_agent=user_agent,
        ip_first_seen=ip,
        is_active=True,
        registered_at=now,
        last_seen_at=now,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


def validate_device(
    db: Session,
    *,
    user: User,
    device_id: str,
    fingerprint_hash: str,
) -> ClientDevice | None:
    """Devuelve ClientDevice si es válido (activo, dueño, fingerprint coincide).
    Devuelve None si cualquier validación falla.
    """
    device = db.execute(
        select(ClientDevice).where(ClientDevice.device_id == device_id)
    ).scalar_one_or_none()
    if device is None:
        return None
    if device.user_id != user.id:
        return None
    if not device.is_active:
        return None
    if device.fingerprint_hash != fingerprint_hash:
        return None
    # Touch last_seen
    device.last_seen_at = datetime.datetime.utcnow()
    db.add(device)
    db.commit()
    return device


def revoke_device(
    db: Session, *, device: ClientDevice, revoked_by: User
) -> None:
    """Marca el dispositivo como revocado (no se borra para auditoría)."""
    device.is_active = False
    device.revoked_at = datetime.datetime.utcnow()
    device.revoked_by_user_id = revoked_by.id
    db.add(device)
    db.commit()


def revoke_all_devices_for_user(
    db: Session, *, user: User, revoked_by: User
) -> int:
    """Revoca todos los dispositivos activos del usuario. Retorna count."""
    devices = db.execute(
        select(ClientDevice).where(
            ClientDevice.user_id == user.id,
            ClientDevice.is_active.is_(True),
        )
    ).scalars().all()
    now = datetime.datetime.utcnow()
    for d in devices:
        d.is_active = False
        d.revoked_at = now
        d.revoked_by_user_id = revoked_by.id
        db.add(d)
    db.commit()
    return len(devices)
