#!/usr/bin/env python3
"""Verificador read-only de las cuentas de prueba del preview.

Compara la BD del preview contra la matriz ``preview_users.PREVIEW_ACCOUNTS`` y
reporta cualquier diferencia. SOLO lee (SELECT); no crea, no modifica, no borra.

Uso (dentro del contenedor backend del preview, que ya tiene DATABASE_URL al
Postgres aislado del PR):

    python scripts/verificar_usuarios_preview.py

Sale con código 0 si «DIFERENCIAS: 0», 1 si hay diferencias, 2 si no es preview.
"""
from __future__ import annotations

import sys

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.core import preview
from backend.app.core.preview_users import PREVIEW_ACCOUNTS
from backend.app.db.session import SessionLocal


def main() -> int:
    if not preview.is_preview():
        print("No es un preview (APP_ENV!=preview); nada que verificar.")
        return 2

    db = SessionLocal()
    diffs: list[str] = []
    try:
        for acc in PREVIEW_ACCOUNTS:
            alias = acc["alias"]
            esperado_rol = Role(acc["role"])
            u = auth_service.get_user_by_email(db, alias)
            if u is None:
                diffs.append(f"FALTA   {alias}: no existe en la BD del preview")
                continue
            if u.role != esperado_rol:
                diffs.append(
                    f"ROL     {alias}: esperado {esperado_rol.value}, hay {u.role.value}"
                )
            if not u.is_active:
                diffs.append(f"ESTADO  {alias}: is_active=False (se esperaba activo)")
            if u.organization_id is None:
                diffs.append(f"ORG     {alias}: sin organización asignada")
            print(
                f"OK?     {alias}: role={u.role.value} "
                f"activo={u.is_active} org={u.organization_id}"
            )
    finally:
        db.close()

    print()
    if diffs:
        print("\n".join(diffs))
        print(f"DIFERENCIAS: {len(diffs)}")
        return 1
    print("DIFERENCIAS: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
