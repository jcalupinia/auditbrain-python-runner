"""Servicio de permisos herramienta↔usuario (gating comercial del portal).

Una cuenta de portal (rol client) solo puede ver/ejecutar las herramientas
que tenga concedidas aquí. El set se administra desde el Command Center.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import Role, User, UserToolEntitlement
from backend.app.client_portal.tool_registry import TOOLS


def is_operator(user: User) -> bool:
    """True si el usuario es operador (admin/user) y por tanto hace BYPASS del
    gating comercial: entra al portal con su mismo usuario para QA/soporte y ve
    todo. Fuente única de esa decisión, usada en el catálogo y en crear job.

    Fail-closed a propósito: solo admin/user hacen bypass; cualquier otro rol
    (incluido uno nuevo que se agregara en el futuro) queda gateado por defecto,
    en vez de obtener acceso total por accidente."""
    return user.role in (Role.admin, Role.user)


def list_user_tool_codes(db: Session, user_id: int) -> set[str]:
    """Códigos de herramienta habilitados para el usuario."""
    rows = db.execute(
        select(UserToolEntitlement.tool_code).where(
            UserToolEntitlement.user_id == user_id,
            UserToolEntitlement.enabled.is_(True),
        )
    ).scalars()
    return set(rows)


def can_access_tool(db: Session, user_id: int, tool_code: str) -> bool:
    """True si el usuario tiene la herramienta concedida y habilitada."""
    row = db.execute(
        select(UserToolEntitlement.id).where(
            UserToolEntitlement.user_id == user_id,
            UserToolEntitlement.tool_code == tool_code,
            UserToolEntitlement.enabled.is_(True),
        )
    ).first()
    return row is not None


def set_user_entitlements(db: Session, user_id: int, tool_codes: set[str]) -> None:
    """Reemplaza el conjunto completo de herramientas del usuario.

    - Ignora códigos que no existen en el registry.
    - Inserta/habilita las del set; borra las filas que ya no están en el set.
    """
    valid = {c for c in tool_codes if c in TOOLS}
    existing = {
        e.tool_code: e
        for e in db.execute(
            select(UserToolEntitlement).where(
                UserToolEntitlement.user_id == user_id
            )
        ).scalars()
    }
    for code in valid:
        if code in existing:
            existing[code].enabled = True
        else:
            db.add(UserToolEntitlement(user_id=user_id, tool_code=code, enabled=True))
    for code, row in existing.items():
        if code not in valid:
            db.delete(row)
    db.commit()


def backfill_tributarias(db: Session) -> int:
    """Concede las herramientas de la sección TRIBUTARIAS a todas las cuentas
    de rol client, SOLO si la tabla de entitlements está globalmente vacía.
    Devuelve el número de concesiones creadas (0 si no corrió)."""
    already = db.execute(select(UserToolEntitlement.id).limit(1)).first()
    if already is not None:
        return 0  # ya inicializado; nunca re-aplicar

    trib_codes = [
        code for code, t in TOOLS.items()
        if t.category == "TRIBUTARIAS" and t.enabled
    ]
    if not trib_codes:
        return 0

    client_ids = db.execute(
        select(User.id).where(User.role == Role.client)
    ).scalars().all()

    created = 0
    for uid in client_ids:
        for code in trib_codes:
            db.add(UserToolEntitlement(user_id=uid, tool_code=code, enabled=True))
            created += 1
    db.commit()
    return created
