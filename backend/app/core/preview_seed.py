"""Cuentas de prueba de un Preview Environment (solo ``APP_ENV=preview``).

Un preview nace con UNA sola cuenta: el admin del bootstrap
(``ensure_bootstrap_admin``, ``preview-admin@audit-ia.ec``). Para poder probar
AUDIT-IA como la aplicación real —entrar como cada operador del equipo y ver sus
permisos— aquí se siembran, **de forma idempotente y solo en previews**, las
cuentas de OPERADOR de la matriz ``preview_users.PREVIEW_ACCOUNTS`` (reproducción
seudonimizada de los operadores reales de producción; ver ese módulo). No se
inventan roles ni se reproducen cuentas de rol ``client``.

Garantías de aislamiento y seguridad (requisitos del dueño):
- **Solo preview.** ``seed_preview_users`` es un no-op fuera de ``APP_ENV=preview``
  (``preview.is_preview()``). En producción no crea, no modifica y no borra nada.
  En preview ``preview_bootstrap`` ya exige que ``DATABASE_URL`` apunte al servicio
  interno ``db`` del propio PR, así que esto nunca toca la base productiva.
- **Base aislada por PR.** Usa la ``SessionLocal`` del backend, que en preview es la
  Postgres exclusiva del PR.
- **Contraseñas aleatorias e independientes por cuenta.** Cada cuenta recibe una
  clave aleatoria propia (``secrets.token_urlsafe``), NO derivada de la del admin
  ni compartida entre cuentas. Se guarda, con permisos 600, en el volumen de datos
  del preview (``PREVIEW_USER_SECRETS_DIR``, por defecto ``/var/data/preview-users``,
  que es read-write y persistente por PR). NUNCA va al repositorio, a variables de
  Coolify ni a los logs. Recuperación: ``docker exec <backend-pr-N> sh -c 'cat
  /var/data/preview-users/<alias-localpart>'``.
- **Sin PII ni secretos de producción.** La matriz solo tiene alias + rol; no hay
  correos reales, hashes, tokens ni datos de clientes.
- **Idempotente.** Cada cuenta se crea solo si su alias no existe. Si la cuenta ya
  existe pero su archivo de clave se perdió (p. ej. se recreó el volumen), se
  **re-emite** la clave para que siga siendo recuperable — solo para las cuentas
  que gestiona este seeder, nunca para el admin u otras cuentas.
- **No debilita la autorización.** Crea usuarios con sus roles reales; los guards
  (``require_admin``/``require_staff``/``require_client_with_device``) siguen intactos.
"""

from __future__ import annotations

import logging
import os
import pathlib
import re
import secrets

from sqlalchemy.orm import Session

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.core import preview
from backend.app.core.preview_users import PREVIEW_ACCOUNTS

log = logging.getLogger("auditbrain")

# Longitud (en bytes de entropía) de cada clave aleatoria. token_urlsafe(24) da
# ~32 caracteres url-safe; supera el mínimo de 8 que valida reset_user_password.
_PASSWORD_ENTROPY_BYTES = 24

# Directorio (read-write, persistente por PR) donde se guardan las claves por
# cuenta. El volumen `secrets` del compose está montado read-only en el backend,
# por eso NO se usa /run/secrets aquí; `appdata` (/var/data) sí es escribible.
_DEFAULT_SECRETS_DIR = "/var/data/preview-users"


def _secrets_dir() -> pathlib.Path:
    return pathlib.Path(
        os.getenv("PREVIEW_USER_SECRETS_DIR", _DEFAULT_SECRETS_DIR)
    )


def _alias_slug(alias: str) -> str:
    """Nombre de archivo seguro a partir del alias (parte local del correo)."""
    local = alias.split("@", 1)[0]
    return re.sub(r"[^A-Za-z0-9._-]", "_", local)


def _new_password() -> str:
    return secrets.token_urlsafe(_PASSWORD_ENTROPY_BYTES)


def _store_password(alias: str, password: str) -> None:
    """Escribe la clave en un archivo propio con permisos 600. Best-effort: si el
    directorio no es escribible, lo registra y sigue (la cuenta ya quedó creada)."""
    try:
        d = _secrets_dir()
        d.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(d, 0o700)
        except OSError:
            pass
        f = d / _alias_slug(alias)
        tmp = d / f".{_alias_slug(alias)}.tmp"
        tmp.write_text(password + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, f)
    except OSError:
        log.warning(
            "PREVIEW seed: no se pudo guardar la clave de %s en %s "
            "(cuenta creada; recupérala re-sembrando)", alias, _secrets_dir()
        )


def _password_file_exists(alias: str) -> bool:
    try:
        return (_secrets_dir() / _alias_slug(alias)).is_file()
    except OSError:
        return False


def seed_preview_users(db: Session) -> dict:
    """Siembra las cuentas de operador del preview. Idempotente y solo en preview.

    Devuelve un resumen ``{"seeded": [...], "reissued": [...], "skipped": bool,
    "reason": str}``. Nunca lanza: cualquier problema se registra y el arranque
    continúa.
    """
    resumen: dict = {"seeded": [], "reissued": [], "skipped": True, "reason": ""}
    if not preview.is_preview():
        resumen["reason"] = "no es preview (APP_ENV!=preview)"
        return resumen

    resumen["skipped"] = False
    try:
        _seed_operadores(db, resumen)
    except Exception:  # pragma: no cover - defensivo: el arranque no debe caer
        log.exception("PREVIEW seed: falló la siembra de cuentas de prueba")
        resumen["reason"] = "excepción durante la siembra (ver log)"
    if resumen["seeded"]:
        log.info("PREVIEW seed: cuentas creadas: %s", ", ".join(resumen["seeded"]))
    if resumen["reissued"]:
        log.info("PREVIEW seed: claves re-emitidas: %s", ", ".join(resumen["reissued"]))
    return resumen


def _seed_operadores(db: Session, resumen: dict) -> None:
    """Crea cada operador de la matriz (rol de la matriz), en la organización por
    defecto, con una clave aleatoria propia. Idempotente por alias."""
    from backend.app.context.service import get_or_create_default_organization

    org = get_or_create_default_organization(db)
    for acc in PREVIEW_ACCOUNTS:
        alias = acc["alias"]
        role = Role(acc["role"])  # valida contra el enum real; no inventa roles
        existing = auth_service.get_user_by_email(db, alias)
        if existing is None:
            password = _new_password()
            user = auth_service.create_user(
                db, email=alias, password=password, role=role
            )
            user.organization_id = org.id
            db.add(user)
            db.commit()
            _store_password(alias, password)
            resumen["seeded"].append(f"{alias} ({role.value})")
        elif not _password_file_exists(alias):
            # La cuenta existe pero su clave no es recuperable: re-emitir para no
            # dejar la cuenta de QA inutilizable. Solo cuentas de esta matriz.
            password = _new_password()
            auth_service.reset_user_password(db, user=existing, new_password=password)
            _store_password(alias, password)
            resumen["reissued"].append(alias)
