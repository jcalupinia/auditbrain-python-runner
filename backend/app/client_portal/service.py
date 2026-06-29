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
    db: Session, *, client_id: int, email: str, password: str | None = None
) -> tuple[User, str]:
    client = db.get(Client, client_id)
    if client is None:
        raise ValueError(f"Client {client_id} no existe.")

    # Si se pasa una contraseña explícita (p. ej. la regla dominio+RUC de la
    # carga masiva) se usa esa; si no, se genera una aleatoria segura.
    temp_pwd = password or _generate_temp_password()
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
    """Autentica para el portal cliente. Acepta clientes (rol client) y también
    operadores del staff (rol admin/user) para que entren con su mismo usuario,
    sin necesidad de una cuenta cliente aparte. (Un cliente NUNCA accede al
    staff: esa separación se mantiene en las dependencias de staff.)"""
    from sqlalchemy import select

    user = db.execute(
        select(User).where(User.email == email.lower())
    ).scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if user.role not in (Role.client, Role.admin, Role.user):
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


def reset_portal_user_password(
    db: Session, *, user: User, new_password: str | None = None
) -> str:
    """Resetea la clave de un usuario de portal cliente (devuelta en claro una vez).

    - Si el admin provee ``new_password``: esa queda como clave DEFINITIVA
      (``password_reset_required=False``); el cliente entra directo con ella.
    - Si no la provee: clave temporal aleatoria + ``password_reset_required=True``
      (comportamiento histórico). Siempre reactiva la cuenta.
    """
    if new_password is not None:
        if len(new_password) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres.")
        temp_pwd = new_password
        user.password_reset_required = False
    else:
        temp_pwd = _generate_temp_password()
        user.password_reset_required = True
    user.hashed_password = hash_password(temp_pwd)
    user.is_active = True
    db.add(user)
    db.commit()
    return temp_pwd


# ---------------------------------------------------------------------------
# Job management
# ---------------------------------------------------------------------------

import datetime  # noqa: E402

from sqlalchemy import select  # noqa: E402

from backend.app.aud.obligaciones_fiscales.models import ToolJob  # noqa: E402


def create_client_job(
    db: Session, *, user: User, tool_code: str
) -> ToolJob:
    """Crea ToolJob para un cliente. Verifica que no haya otro job activo."""
    active = db.execute(
        select(ToolJob).where(
            ToolJob.user_id == user.id,
            ToolJob.status.in_(["pending", "processing"]),
        )
    ).scalars().first()
    if active:
        raise PermissionError(
            "Tiene otro trabajo en proceso. Espere a que termine."
        )

    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    project_id = _ensure_client_project(db, user=user)

    job = ToolJob(
        user_id=user.id,
        project_id=project_id,
        tool_code=tool_code,
        status="pending",
        cliente_name=str(user.client_id or user.email),
        period_label=datetime.date.today().isoformat(),
        created_at=now,
        expires_at=now + datetime.timedelta(hours=24),
        initiated_from="client",
        notify_email=user.email,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _ensure_client_project(db: Session, *, user: User) -> int:
    """Devuelve project_id 'stub' para jobs del cliente. Crea uno si no existe."""
    from backend.app.context.models import Project

    if user.active_project_id:
        return user.active_project_id
    # Crear proyecto stub vinculado a su client_id
    proj = Project(
        organization_id=user.organization_id,
        client_id=user.client_id,
        name=f"PortalCliente-{user.email}",
        module_code="CP",
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    user.active_project_id = proj.id
    db.add(user)
    db.commit()
    return proj.id


def get_client_job(db: Session, *, user: User, job_id: int) -> ToolJob:
    """Obtiene job verificando ownership del cliente."""
    job = db.get(ToolJob, job_id)
    if not job or job.user_id != user.id:
        raise PermissionError("Job no encontrado o sin acceso.")
    return job
