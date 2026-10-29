"""Cuentas de prueba de un Preview Environment (solo ``APP_ENV=preview``).

Reproduce en la base **aislada del PR** la configuración real verificada: 1 admin
(el jefe) y los operadores del equipo, cada uno con su correo real y rol ``user``.
Los correos **nunca** están en el repositorio ni en variables globales: se leen de
un **archivo de identidades** que vive solo en el volumen ``appdata`` (aislado por
preview) del preview autorizado, colocado por un operador de confianza.

Garantías (requisitos del dueño):
- **Solo preview.** ``seed_preview_users`` es un no-op fuera de ``APP_ENV=preview``.
  En producción no crea, no modifica, no borra. En preview, ``preview_bootstrap``
  exige que ``DATABASE_URL`` apunte al servicio interno ``db`` del propio PR.
- **Sin PII en Git ni en logs.** El repo no contiene correos reales; el seeder
  registra solo CONTEOS, nunca correos. Las claves por cuenta se guardan con nombre
  de archivo **hash** (no el correo) para no exponer PII en el volumen.
- **Admin:** si el archivo trae un correo de admin válido, se crea/asegura como
  ``admin`` con clave aleatoria propia y se **desactiva** (no se borra) el admin
  genérico de reserva, evitando dos admins activos o claves compartidas. Sin archivo
  válido, queda el admin genérico de reserva (lo crea ``ensure_bootstrap_admin``).
- **Operadores:** rol ``user``, activos, organización por defecto; clave aleatoria e
  independiente por cuenta (``secrets.token_urlsafe``), guardada 600 en el volumen RW
  del PR. Idempotente por correo; **no resetea** en el arranque; fallo de escritura →
  cuenta inactiva (nunca "provisionada"); recuperación explícita (``reissue_password``).
- **Sin credenciales de producción.** No copia contraseñas, hashes ni sesiones.
- **No debilita la autorización.** Roles reales; los guards siguen intactos.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import secrets

from sqlalchemy.orm import Session

from backend.app.auth import service as auth_service
from backend.app.auth.models import Role
from backend.app.core import preview
from backend.app.core import preview_users as cfg

log = logging.getLogger("auditbrain")

# token_urlsafe(24) ≈ 32 chars url-safe; supera el mínimo de 8 de reset_user_password.
_PASSWORD_ENTROPY_BYTES = 24


# --------------------------------------------------------------------------- #
# Rutas y utilidades (sin exponer PII)
# --------------------------------------------------------------------------- #
def _identities_file() -> pathlib.Path:
    return pathlib.Path(os.getenv(cfg.ENV_IDENTITIES_FILE, cfg.DEFAULT_IDENTITIES_FILE))


def _secrets_dir() -> pathlib.Path:
    return pathlib.Path(os.getenv(cfg.ENV_SECRETS_DIR, cfg.DEFAULT_SECRETS_DIR))


def _email_slug(email: str) -> str:
    """Nombre de archivo NO-PII: hash del correo (no revela la identidad en el volumen)."""
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:16]


def _valid_email(email: str) -> bool:
    return bool(email) and auth_service._email_valido(email)


def _new_password() -> str:
    return secrets.token_urlsafe(_PASSWORD_ENTROPY_BYTES)


def _ensure_dir() -> pathlib.Path:
    d = _secrets_dir()
    d.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(d, 0o700)
    except OSError:
        pass
    return d


def _store_password(email: str, password: str) -> None:
    """Escribe la clave (atómico, 600), con nombre = hash del correo. Propaga OSError."""
    d = _ensure_dir()
    slug = _email_slug(email)
    tmp = d / f".{slug}.tmp"
    final = d / slug
    tmp.write_text(password + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, final)


def _password_file_exists(email: str) -> bool:
    try:
        return (_secrets_dir() / _email_slug(email)).is_file()
    except OSError:
        return False


def _load_identities() -> dict:
    """Lee el archivo de identidades del volumen del PR. Devuelve
    ``{"admin": <correo|None>, "operators": [<correo>, …]}`` ya validado y normalizado.

    Nunca lanza ni registra el CONTENIDO (solo conteos): un archivo ausente,
    ilegible o inválido produce una configuración vacía (comportamiento seguro)."""
    vacio = {"admin": None, "operators": []}
    try:
        raw = _identities_file().read_text(encoding="utf-8")
    except OSError:
        return vacio  # ausente: sin configuración (se usa el admin genérico de reserva)
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        log.warning("PREVIEW seed: archivo de identidades ilegible (JSON inválido); se ignora")
        return vacio
    if not isinstance(data, dict):
        log.warning("PREVIEW seed: archivo de identidades con formato inesperado; se ignora")
        return vacio

    admin_raw = data.get("admin")
    admin = admin_raw.strip().lower() if isinstance(admin_raw, str) else None
    if admin is not None and not _valid_email(admin):
        log.warning("PREVIEW seed: correo de admin inválido en el archivo; se ignora el admin")
        admin = None

    operadores: list[str] = []
    descartados = 0
    for e in data.get("operators") or []:
        cand = e.strip().lower() if isinstance(e, str) else ""
        if _valid_email(cand) and cand not in operadores:
            operadores.append(cand)
        else:
            descartados += 1
    if descartados:
        log.warning("PREVIEW seed: %d entrada(s) de operador inválidas descartadas", descartados)
    return {"admin": admin, "operators": operadores}


# --------------------------------------------------------------------------- #
# Siembra
# --------------------------------------------------------------------------- #
def seed_preview_users(db: Session) -> dict:
    """Siembra admin + operadores en el preview. Idempotente y solo en preview.

    Devuelve un resumen con **conteos** (sin correos), p. ej.::

        {"skipped": False, "admin": "seeded"|"exists"|"failed"|"generic"|"none",
         "generic_desactivado": bool, "operadores_creados": int,
         "operadores_avisos": int, "operadores_fallidos": int, "reason": ""}

    Nunca lanza: cualquier problema se registra (sin PII) y el arranque continúa.
    """
    resumen: dict = {
        "skipped": True, "admin": "none", "generic_desactivado": False,
        "operadores_creados": 0, "operadores_avisos": 0, "operadores_fallidos": 0,
        "reason": "",
    }
    if not preview.is_preview():
        resumen["reason"] = "no es preview (APP_ENV!=preview)"
        return resumen

    resumen["skipped"] = False
    try:
        ident = _load_identities()
        _seed_admin(db, ident["admin"], resumen)
        _seed_operadores(db, ident["operators"], ident["admin"], resumen)
    except Exception:  # pragma: no cover - defensivo: el arranque no debe caer
        log.exception("PREVIEW seed: falló la siembra (ver log)")
        resumen["reason"] = "excepción durante la siembra"
    log.info(
        "PREVIEW seed: admin=%s genérico_desactivado=%s operadores creados=%d avisos=%d fallidos=%d",
        resumen["admin"], resumen["generic_desactivado"],
        resumen["operadores_creados"], resumen["operadores_avisos"], resumen["operadores_fallidos"],
    )
    return resumen


def _seed_admin(db: Session, admin_email: str | None, resumen: dict) -> None:
    """Crea/asegura el admin real del archivo y desactiva el admin genérico de reserva.

    Sin correo de admin válido → no hace nada (queda el genérico de reserva activo)."""
    if not admin_email:
        resumen["admin"] = "generic"
        return
    from backend.app.context.service import get_or_create_default_organization

    org = get_or_create_default_organization(db)
    existing = auth_service.get_user_by_email(db, admin_email)
    if existing is None:
        password = _new_password()
        user = auth_service.create_user(db, email=admin_email, password=password, role=Role.admin)
        user.organization_id = org.id
        db.add(user)
        db.commit()
        try:
            _store_password(admin_email, password)
        except OSError:
            auth_service.set_user_active(db, user=user, active=False)
            resumen["admin"] = "failed"
            log.error("PREVIEW seed: no se pudo guardar la clave del admin; cuenta inactiva")
            return
        resumen["admin"] = "seeded"
    else:
        resumen["admin"] = "exists"
        if not _password_file_exists(admin_email):
            log.warning("PREVIEW seed: el admin ya existe sin archivo de clave; recupérala explícitamente")

    # Desactivar (no borrar) el admin genérico de reserva si es OTRA cuenta activa:
    # evita dos admins activos y que compartan contraseña. Reversible.
    generico = auth_service.get_user_by_email(db, cfg.GENERIC_ADMIN_EMAIL)
    if (generico is not None and generico.email != admin_email.strip().lower()
            and generico.is_active):
        auth_service.set_user_active(db, user=generico, active=False)
        resumen["generic_desactivado"] = True


def _seed_operadores(db: Session, operadores: list[str], admin_email: str | None, resumen: dict) -> None:
    """Crea cada operador (rol user) con clave aleatoria propia. Idempotente por correo;
    NO resetea cuentas existentes. Excluye el correo del admin."""
    if not operadores:
        return
    from backend.app.context.service import get_or_create_default_organization

    org = get_or_create_default_organization(db)
    admin_norm = admin_email.strip().lower() if admin_email else None
    for email in operadores:
        if admin_norm and email == admin_norm:
            continue  # nunca como operador si es el admin
        existing = auth_service.get_user_by_email(db, email)
        if existing is not None:
            if not _password_file_exists(email):
                resumen["operadores_avisos"] += 1  # existe sin clave; recuperación explícita
            continue
        password = _new_password()
        user = auth_service.create_user(db, email=email, password=password, role=cfg.OPERATOR_ROLE)
        user.organization_id = org.id
        db.add(user)
        db.commit()
        try:
            _store_password(email, password)
        except OSError:
            auth_service.set_user_active(db, user=user, active=False)
            resumen["operadores_fallidos"] += 1
        else:
            resumen["operadores_creados"] += 1


def reissue_password(db: Session, email: str) -> str:
    """Recuperación administrativa EXPLÍCITA de la clave de una cuenta del preview.

    - Solo en preview (si no, ``RuntimeError``).
    - El correo debe estar en el archivo de identidades vigente (admin u operador);
      si no, ``KeyError``.
    - La cuenta debe existir; si no, ``LookupError``.
    - Genera una clave aleatoria nueva e independiente, la aplica y la guarda; reactiva
      la cuenta si estaba inactiva. Devuelve la clave UNA vez (no se registra)."""
    if not preview.is_preview():
        raise RuntimeError("reissue_password solo está permitido en previews.")
    email = email.strip().lower()
    ident = _load_identities()
    validos = set(ident["operators"]) | ({ident["admin"]} if ident["admin"] else set())
    if email not in validos:
        raise KeyError("el correo no está en el archivo de identidades del preview.")
    user = auth_service.get_user_by_email(db, email)
    if user is None:
        raise LookupError("la cuenta no existe en la base del preview.")
    password = _new_password()
    auth_service.reset_user_password(db, user=user, new_password=password)
    _store_password(email, password)
    log.info("PREVIEW seed: clave re-emitida (recuperación explícita) para una cuenta del preview")
    return password
