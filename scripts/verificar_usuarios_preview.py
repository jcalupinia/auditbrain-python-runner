#!/usr/bin/env python3
"""Verificador read-only de las cuentas de prueba del preview.

Compara la BD del preview contra el archivo de identidades del PR y reporta
diferencias. SOLO lee (SELECT); no crea, no modifica, no borra. No imprime
contraseñas.

Uso (dentro del contenedor backend del preview):

    python scripts/verificar_usuarios_preview.py

Sale 0 si «DIFERENCIAS: 0», 1 si hay diferencias, 2 si no es preview.
"""
from __future__ import annotations

import sys

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.core import preview, preview_seed
from backend.app.core import preview_users as cfg
from backend.app.db.session import SessionLocal


def main() -> int:
    if not preview.is_preview():
        print("No es un preview (APP_ENV!=preview); nada que verificar.")
        return 2

    ident = preview_seed._load_identities()
    db = SessionLocal()
    diffs: list[str] = []
    try:
        # Admin: si hay admin en el archivo, debe existir como admin activo y el
        # genérico de reserva debe estar inactivo.
        if ident["admin"]:
            u = auth_service.get_user_by_email(db, ident["admin"])
            if u is None or u.role != Role.admin or not u.is_active:
                diffs.append("ADMIN: el correo de admin del archivo no está como admin activo")
            else:
                print("OK? admin real activo")
            g = auth_service.get_user_by_email(db, cfg.GENERIC_ADMIN_EMAIL)
            if g is not None and g.is_active and g.email != ident["admin"]:
                diffs.append("ADMIN: el admin genérico de reserva sigue ACTIVO (debería estar inactivo)")
        else:
            print("Sin admin en el archivo: se espera el admin genérico de reserva.")

        # Operadores: rol user, activos, con organización.
        for email in ident["operators"]:
            if ident["admin"] and email == ident["admin"]:
                continue
            u = auth_service.get_user_by_email(db, email)
            if u is None:
                diffs.append("FALTA un operador configurado en el archivo")
            elif u.role != Role.user or not u.is_active or u.organization_id is None:
                diffs.append("OPERADOR con rol/estado/organización incorrectos")
            else:
                print("OK? operador user activo")
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
