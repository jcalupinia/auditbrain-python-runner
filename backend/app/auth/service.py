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


def reset_user_password(
    db: Session, *, user: User, new_password: str | None = None
) -> str:
    """Resetea la clave de un operador y la devuelve en claro (una sola vez).

    - Si el admin provee ``new_password``: esa queda como clave DEFINITIVA
      (``password_reset_required=False``); el operador entra directo con ella.
    - Si no la provee: se genera una clave temporal aleatoria y se marca
      ``password_reset_required=True`` (comportamiento histórico).
    """
    from backend.app.client_portal.service import _generate_temp_password

    if new_password is not None:
        if len(new_password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        temp = new_password
        user.password_reset_required = False
    else:
        temp = _generate_temp_password()
        user.password_reset_required = True
    user.hashed_password = hash_password(temp)
    user.is_active = True
    db.add(user)
    db.commit()
    return temp


def count_active_admins(db: Session) -> int:
    from sqlalchemy import func

    return int(
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.role == Role.admin, User.is_active.is_(True))
        ).scalar()
        or 0
    )


def set_user_active(db: Session, *, user: User, active: bool) -> None:
    """Habilita/deshabilita una cuenta (baja reversible)."""
    user.is_active = active
    db.add(user)
    db.commit()


def delete_user_completely(db: Session, *, user: User) -> None:
    """Borrado DURO e irreversible: elimina al usuario y sus registros
    dependientes en orden hijo→padre (robusto aunque la BD no tenga ON DELETE
    CASCADE). Preserva ``tool_jobs`` como historial (SET NULL). Para una baja
    reversible usar ``disable``.
    """
    from sqlalchemy import text

    uid = user.id
    statements = [
        "DELETE FROM messages WHERE conversation_id IN "
        "(SELECT id FROM conversations WHERE user_id = :uid)",
        "DELETE FROM conversations WHERE user_id = :uid",
        "DELETE FROM ict_anexos WHERE session_id IN "
        "(SELECT id FROM ict_sessions WHERE user_id = :uid)",
        "DELETE FROM ict_sessions WHERE user_id = :uid",
        "DELETE FROM project_members WHERE user_id = :uid",
        "UPDATE client_devices SET revoked_by_user_id = NULL "
        "WHERE revoked_by_user_id = :uid",
        "DELETE FROM client_devices WHERE user_id = :uid",
        "UPDATE tool_jobs SET user_id = NULL WHERE user_id = :uid",
        "DELETE FROM user_tool_entitlements WHERE user_id = :uid",
        "DELETE FROM users WHERE id = :uid",
    ]
    for stmt in statements:
        db.execute(text(stmt), {"uid": uid})
    db.commit()


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


# ---------------------------------------------------------------------------
# Sesión única "el primero gana" (first-wins) + auto-liberación por inactividad
# ---------------------------------------------------------------------------
# Regla de negocio: una cuenta de cliente solo puede estar en uso por UNA
# persona a la vez. Si ya hay una sesión viva, el segundo login se rechaza
# (ver client_portal.router). La sesión se considera "viva" mientras la
# ÚLTIMA ACTIVIDAD (campo session_started_at, que se refresca en cada request
# del cliente vía touch_session) sea más reciente que el timeout de
# inactividad. Así, si alguien cierra el navegador sin "Salir", la cuenta se
# libera sola pasado el timeout. Default: 10 minutos.
DEFAULT_SESSION_TIMEOUT_MINUTES = 10


def _session_timeout_minutes() -> int:
    try:
        return int(os.getenv("CLIENT_PORTAL_SESSION_TIMEOUT_MINUTES",
                             str(DEFAULT_SESSION_TIMEOUT_MINUTES)))
    except (TypeError, ValueError):
        return DEFAULT_SESSION_TIMEOUT_MINUTES


def has_active_session(user: User) -> bool:
    """True si el usuario tiene una sesión viva (no expirada por inactividad).

    Viva = current_session_id seteado Y última actividad dentro del timeout.
    """
    if not user.current_session_id or not user.session_started_at:
        return False
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    return (now - user.session_started_at) < datetime.timedelta(
        minutes=_session_timeout_minutes()
    )


def touch_session(db: Session, *, user: User) -> None:
    """Heartbeat: refresca la marca de última actividad de la sesión activa.

    Se llama en cada request autenticado del cliente para mantener viva la
    sesión mientras la persona está usando el sistema. No hace nada si no hay
    sesión activa (evita "revivir" una sesión ya cerrada).
    """
    if not user.current_session_id:
        return
    user.session_started_at = datetime.datetime.now(
        datetime.timezone.utc
    ).replace(tzinfo=None)
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
