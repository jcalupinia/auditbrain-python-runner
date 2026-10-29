"""Cuentas de prueba de un Preview Environment (solo ``APP_ENV=preview``).

Un preview nace con UNA sola cuenta: el admin del bootstrap
(``ensure_bootstrap_admin``). Para poder probar AuditBrain como la aplicación
real —entrar con cada tipo de usuario, ver sus permisos y que cada uno trabaje
con sus propios datos— aquí se siembran, **de forma idempotente y solo en
previews**, una cuenta por cada rol real del sistema (``admin``/``user``/
``client``; ver ``auth.models.Role``). No se inventan roles.

Garantías de aislamiento y seguridad (requisitos del dueño):
- **Solo preview.** ``seed_preview_users`` es un no-op fuera de ``APP_ENV=preview``
  (``preview.is_preview()``). En producción no crea, no modifica y no borra nada.
  Además, en preview ``preview_bootstrap`` ya exige que ``DATABASE_URL`` apunte al
  servicio interno ``db`` del propio PR, así que esto nunca toca la base productiva.
- **Base aislada por PR.** Usa la ``SessionLocal`` del backend, que en preview es la
  Postgres exclusiva del PR.
- **Sin secretos de producción.** La contraseña de las cuentas de prueba es la
  MISMA clave exclusiva del preview que ya usa el admin
  (``AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD``, derivada de ``/run/secrets/admin_password``,
  única por PR). No se hardcodea ninguna clave, hash, token ni PII.
- **Idempotente.** Cada cuenta se crea solo si su email no existe; nunca se
  modifican ni borran usuarios existentes. No duplica en cada despliegue.
- **No debilita la autorización.** Crea usuarios con sus roles reales; los guards
  (``require_admin``/``require_staff``/``require_client_with_device``) siguen intactos.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy.orm import Session

from backend.app.auth.models import Role, User
from backend.app.auth import service as auth_service
from backend.app.core import preview

log = logging.getLogger("auditbrain")

# Emails de las cuentas de prueba del preview. El dominio audit-ia.ec pasa el
# validador EmailStr de la API (igual que el admin del bootstrap). No son
# identidades productivas: viven solo en la base aislada del PR.
PREVIEW_OPERADOR_EMAIL = "preview-operador@audit-ia.ec"
PREVIEW_CLIENTE_EMAIL = "preview-cliente@audit-ia.ec"

# Cliente de prueba al que se liga la cuenta de rol ``client``.
PREVIEW_CLIENTE_NOMBRE = "Cliente de prueba (preview)"

# Herramientas del catálogo que se conceden a la cuenta client de prueba, para
# que el portal muestre contenido. ``set_user_entitlements`` ignora cualquier
# código que no exista en ``tool_registry.TOOLS``, así que esto nunca falla
# aunque el catálogo cambie.
PREVIEW_CLIENTE_TOOL_CODES = {"ICT_2025"}


def _preview_test_password() -> str:
    """La clave exclusiva del preview (la del admin). Vacía => no se siembra."""
    return os.getenv("AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD", "").strip()


def seed_preview_users(db: Session) -> dict:
    """Siembra las cuentas de prueba por rol. Idempotente y solo en preview.

    Devuelve un resumen ``{"seeded": [...], "skipped": bool, "reason": str}``.
    Nunca lanza: cualquier problema se registra y el arranque continúa.
    """
    resumen: dict = {"seeded": [], "skipped": True, "reason": ""}
    if not preview.is_preview():
        resumen["reason"] = "no es preview (APP_ENV!=preview)"
        return resumen

    password = _preview_test_password()
    if not password:
        resumen["reason"] = "sin AUDITBRAIN_BOOTSTRAP_ADMIN_PASSWORD; no se siembran cuentas de prueba"
        log.warning("PREVIEW seed: %s", resumen["reason"])
        return resumen

    resumen["skipped"] = False
    try:
        _seed_operador(db, password, resumen)
        _seed_cliente(db, password, resumen)
    except Exception:  # pragma: no cover - defensivo: el arranque no debe caer
        log.exception("PREVIEW seed: falló la siembra de cuentas de prueba")
        resumen["reason"] = "excepción durante la siembra (ver log)"
    if resumen["seeded"]:
        log.info("PREVIEW seed: cuentas de prueba creadas: %s", ", ".join(resumen["seeded"]))
    return resumen


def _seed_operador(db: Session, password: str, resumen: dict) -> None:
    """Rol ``user`` (operador del Command Center), en la organización por defecto."""
    if auth_service.get_user_by_email(db, PREVIEW_OPERADOR_EMAIL):
        return
    from backend.app.context.service import get_or_create_default_organization

    user = auth_service.create_user(
        db, email=PREVIEW_OPERADOR_EMAIL, password=password, role=Role.user
    )
    org = get_or_create_default_organization(db)
    user.organization_id = org.id
    db.add(user)
    db.commit()
    resumen["seeded"].append(f"{PREVIEW_OPERADOR_EMAIL} (user)")


def _seed_cliente(db: Session, password: str, resumen: dict) -> None:
    """Rol ``client`` (portal), ligado a un Client de prueba con entitlements."""
    if auth_service.get_user_by_email(db, PREVIEW_CLIENTE_EMAIL):
        return
    from backend.app.client_portal.entitlements import set_user_entitlements
    from backend.app.context.models import Client
    from backend.app.context.service import get_or_create_default_organization
    from sqlalchemy import select

    org = get_or_create_default_organization(db)
    # Client idempotente por (organization_id, name) — su constraint único.
    client = db.execute(
        select(Client).where(
            Client.organization_id == org.id, Client.name == PREVIEW_CLIENTE_NOMBRE
        )
    ).scalar_one_or_none()
    if client is None:
        client = Client(organization_id=org.id, name=PREVIEW_CLIENTE_NOMBRE, sector="Preview")
        db.add(client)
        db.commit()
        db.refresh(client)

    user = auth_service.create_user(
        db, email=PREVIEW_CLIENTE_EMAIL, password=password, role=Role.client
    )
    user.organization_id = org.id
    user.client_id = client.id
    db.add(user)
    db.commit()
    set_user_entitlements(db, user.id, set(PREVIEW_CLIENTE_TOOL_CODES))
    resumen["seeded"].append(f"{PREVIEW_CLIENTE_EMAIL} (client)")
