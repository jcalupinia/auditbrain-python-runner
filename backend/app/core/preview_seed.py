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
- **Idempotente y NO destructivo en el arranque.** Cada cuenta se crea solo si su
  alias no existe. Si la cuenta YA existe pero su archivo de clave se perdió, el
  arranque **solo registra una advertencia** y NO cambia la contraseña ni el hash;
  la recuperación es un acto administrativo explícito (``reissue_password`` /
  ``scripts/recuperar_clave_preview.py``), nunca automática en cada boot.
- **Los fallos de escritura no se ocultan.** Si no se puede guardar el archivo de
  una clave recién creada, se registra el error (sin revelar el secreto), la cuenta
  se deja **inactiva** y se reporta en ``failed`` — nunca como una cuenta bien
  provisionada.
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


def _matrix_aliases() -> set[str]:
    return {a["alias"] for a in PREVIEW_ACCOUNTS}


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


def _ensure_dir() -> pathlib.Path:
    """Crea el directorio de claves con permisos 700. Propaga OSError si falla."""
    d = _secrets_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        # El chmod puede no ser soportado por el FS; no es fatal si el dir existe.
        pass
    return d


def _store_password(alias: str, password: str) -> None:
    """Escribe la clave en un archivo propio (atómico, permisos 600).

    Propaga ``OSError`` si no puede escribir: el fallo NO se oculta; el llamador
    decide cómo reportarlo. Nunca registra ni devuelve el secreto."""
    d = _ensure_dir()
    slug = _alias_slug(alias)
    tmp = d / f".{slug}.tmp"
    final = d / slug
    tmp.write_text(password + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, final)


def _password_file_exists(alias: str) -> bool:
    try:
        return (_secrets_dir() / _alias_slug(alias)).is_file()
    except OSError:
        return False


def seed_preview_users(db: Session) -> dict:
    """Siembra las cuentas de operador del preview. Idempotente y solo en preview.

    Devuelve ``{"seeded": [...], "warnings": [...], "failed": [...],
    "skipped": bool, "reason": str}``. Nunca lanza: cualquier problema se registra
    y el arranque continúa.

    - ``seeded``:   cuentas creadas Y con su clave guardada correctamente.
    - ``warnings``: cuentas que ya existían pero cuyo archivo de clave falta
                    (NO se tocó la contraseña; requieren recuperación explícita).
    - ``failed``:   cuentas creadas pero cuya clave NO pudo guardarse (quedan
                    INACTIVAS; no son usables hasta recuperarlas).
    """
    resumen: dict = {
        "seeded": [], "warnings": [], "failed": [], "skipped": True, "reason": ""
    }
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
    if resumen["warnings"]:
        log.warning(
            "PREVIEW seed: cuentas existentes SIN archivo de clave (no se cambió la "
            "contraseña; recupérala con scripts/recuperar_clave_preview.py): %s",
            ", ".join(resumen["warnings"]),
        )
    if resumen["failed"]:
        log.error(
            "PREVIEW seed: cuentas creadas pero SIN poder guardar su clave "
            "(quedaron inactivas): %s", ", ".join(resumen["failed"]),
        )
    return resumen


def _seed_operadores(db: Session, resumen: dict) -> None:
    """Crea cada operador de la matriz (rol de la matriz), en la organización por
    defecto, con una clave aleatoria propia. Idempotente por alias. NO resetea
    contraseñas de cuentas ya existentes."""
    from backend.app.context.service import get_or_create_default_organization

    org = get_or_create_default_organization(db)
    for acc in PREVIEW_ACCOUNTS:
        alias = acc["alias"]
        role = Role(acc["role"])  # valida contra el enum real; no inventa roles
        existing = auth_service.get_user_by_email(db, alias)

        if existing is not None:
            # Idempotente: no se recrea NI se resetea. Si falta la clave, solo se
            # avisa; la recuperación es un acto administrativo explícito.
            if not _password_file_exists(alias):
                resumen["warnings"].append(alias)
            continue

        password = _new_password()
        user = auth_service.create_user(
            db, email=alias, password=password, role=role
        )
        user.organization_id = org.id
        db.add(user)
        db.commit()
        try:
            _store_password(alias, password)
        except OSError:
            # No ocultar el fallo: la cuenta NO queda usable (se desactiva) y se
            # reporta como failed, nunca como provisionada. Sin exponer el secreto.
            auth_service.set_user_active(db, user=user, active=False)
            resumen["failed"].append(alias)
        else:
            resumen["seeded"].append(f"{alias} ({role.value})")


def reissue_password(db: Session, alias: str) -> str:
    """Recuperación administrativa EXPLÍCITA de la clave de una cuenta de prueba.

    - Solo en preview (``is_preview``); fuera de preview lanza ``RuntimeError``.
    - Solo para un alias de la matriz; otro alias lanza ``KeyError``.
    - La cuenta debe existir; si no, lanza ``LookupError``.
    - Genera una contraseña ALEATORIA e INDEPENDIENTE nueva, la aplica y la guarda.
      Reactiva la cuenta si estaba inactiva (``reset_user_password`` pone
      ``is_active=True``). Devuelve la clave en claro UNA sola vez (para mostrarla
      por canal seguro); el llamador no debe registrarla.

    No usa ninguna variable persistente: no se dispara sola en cada arranque.
    """
    if not preview.is_preview():
        raise RuntimeError("reissue_password solo está permitido en previews.")
    if alias not in _matrix_aliases():
        raise KeyError(f"{alias} no es una cuenta de prueba de la matriz.")
    user = auth_service.get_user_by_email(db, alias)
    if user is None:
        raise LookupError(f"{alias} no existe en la base del preview.")
    password = _new_password()
    auth_service.reset_user_password(db, user=user, new_password=password)
    _store_password(alias, password)  # propaga OSError si no puede guardar
    log.info("PREVIEW seed: clave re-emitida (recuperación explícita) para %s", alias)
    return password
