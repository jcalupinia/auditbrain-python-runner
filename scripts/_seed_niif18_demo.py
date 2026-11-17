#!/usr/bin/env python3
"""Siembra datos de prueba para verificar el NIIF 18 Studio en un navegador.

Crea una organización, un cliente, una cuenta de portal CON la herramienta
``NIIF_18_STUDIO`` concedida y un operador admin, e imprime en JSON los tokens
que usará el verificador. NO es parte del producto: solo lo invoca
``scripts/verificar_niif18_portal.mjs``.

Uso:  python scripts/_seed_niif18_demo.py
"""
from __future__ import annotations

import json
import uuid

from backend.app.auth.jwt_tokens import create_access_token
from backend.app.auth.models import Role
from backend.app.auth.service import create_user
from backend.app.client_portal import entitlements as ent
from backend.app.client_portal.service import create_portal_user
from backend.app.context.models import Client, Organization
from backend.app.db.session import SessionLocal, init_db


def main() -> None:
    init_db()  # idempotente: create_all + migraciones aditivas
    db = SessionLocal()
    try:
        suf = uuid.uuid4().hex[:8]
        org = Organization(name=f"Verif-{suf}", slug=f"verif-{suf}", is_active=True)
        db.add(org)
        db.commit()
        db.refresh(org)

        cli = Client(organization_id=org.id, name=f"Cliente Verif {suf}", is_active=True)
        db.add(cli)
        db.commit()
        db.refresh(cli)

        portal_user, _pwd = create_portal_user(
            db, client_id=cli.id, email=f"cliente-{suf}@verificacion.local"
        )
        ent.set_user_entitlements(db, portal_user.id, {"NIIF_18_STUDIO"})

        operador = create_user(
            db,
            email=f"operador-{suf}@verificacion.local",
            password=uuid.uuid4().hex,
            role=Role.admin,
        )

        print(
            json.dumps(
                {
                    "cliente": {
                        "email": portal_user.email,
                        "token": create_access_token(subject=portal_user.email, role="client"),
                    },
                    "operador": {
                        "email": operador.email,
                        "token": create_access_token(subject=operador.email, role="admin"),
                    },
                }
            )
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
