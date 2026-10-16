"""Emisión y validación de JWT (HS256, PyJWT)."""

import datetime
import os
from pathlib import Path

import jwt

_ALGO = "HS256"
_ACCESS_TTL_MIN = int(os.getenv("AUDITBRAIN_JWT_EXPIRE_MINUTES", "60"))

# Secreto del preview leído del volumen de secretos del PR; se cachea por proceso.
_PREVIEW_SECRET: str | None = None


def _preview_secret() -> str:
    """Secreto JWT de un Preview Environment: exclusivo del PR y persistente.

    Lo genera el servicio ``init`` del Compose dentro del volumen ``secrets`` del
    preview (``PREVIEW_SECRETS_DIR/jwt_secret``, modo 600). Persiste entre
    redespliegues del mismo PR (el volumen persiste) y es distinto en cada PR
    (volumen por PR). Nunca se usa el literal de desarrollo ni un secreto de
    producción. Si el archivo falta o es inválido, el preview NO arranca
    (``preview_bootstrap`` ya lo comprueba al importar la app; aquí se vuelve a
    exigir por si se llama fuera de ese flujo).
    """
    global _PREVIEW_SECRET
    if _PREVIEW_SECRET:
        return _PREVIEW_SECRET
    path = Path(os.getenv("PREVIEW_SECRETS_DIR", "/run/secrets")) / "jwt_secret"
    try:
        value = path.read_text(encoding="utf-8").strip()
    except OSError as e:
        import logging

        logging.getLogger("auditbrain").critical(
            "PREVIEW: no se puede leer el secreto JWT en %s (%s). El servicio no arranca.",
            path, e.__class__.__name__,
        )
        raise SystemExit(3) from e
    if len(value) < 32:
        import logging

        logging.getLogger("auditbrain").critical("PREVIEW: secreto JWT demasiado corto. El servicio no arranca.")
        raise SystemExit(3)
    _PREVIEW_SECRET = value
    return value


def _secret() -> str:
    """Secreto de firma. OBLIGATORIO en producción.

    - ``AUDITBRAIN_JWT_SECRET`` definido: se usa (producción).
    - Preview (``APP_ENV=preview``) sin esa variable: secreto del volumen del PR.
    - Otro entorno sin esa variable: valor de desarrollo con aviso (INSEGURO en
      producción; permitiría forjar tokens).
    """
    secret = os.getenv("AUDITBRAIN_JWT_SECRET", "").strip()
    if secret:
        return secret
    from backend.app.core.preview import is_preview

    if is_preview():
        return _preview_secret()
    import logging

    logging.getLogger("auditbrain").warning(
        "AUDITBRAIN_JWT_SECRET no definido: usando secreto de desarrollo "
        "INSEGURO. Definir en producción."
    )
    return "dev-insecure-secret-change-me"


def create_access_token(
    subject: str, role: str, extra_claims: dict | None = None
) -> str:
    now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + datetime.timedelta(minutes=_ACCESS_TTL_MIN),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_token(token: str) -> dict:
    """Devuelve el payload o lanza jwt.PyJWTError si es inválido/expirado."""
    return jwt.decode(token, _secret(), algorithms=[_ALGO])
