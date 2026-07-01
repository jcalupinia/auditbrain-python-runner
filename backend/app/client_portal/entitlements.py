"""Servicio de permisos herramienta↔usuario (gating comercial del portal).

Una cuenta de portal (rol client) solo puede ver/ejecutar las herramientas
que tenga concedidas aquí. El set se administra desde el Command Center.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import UserToolEntitlement
from backend.app.client_portal.tool_registry import TOOLS


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
