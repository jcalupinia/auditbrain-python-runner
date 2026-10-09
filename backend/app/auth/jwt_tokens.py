"""Emisión y validación de JWT (HS256, PyJWT)."""

import datetime
import os

import jwt

_ALGO = "HS256"
_ACCESS_TTL_MIN = int(os.getenv("AUDITBRAIN_JWT_EXPIRE_MINUTES", "60"))


# Secreto efímero de los Preview Environments de Render (ver _secret()).
# Se genera UNA vez por proceso y se cachea aquí.
_PREVIEW_SECRET: str | None = None


def _preview_secret() -> str:
    """Secreto aleatorio por proceso para un preview sin AUDITBRAIN_JWT_SECRET.

    Las variables ``sync: false`` NO se copian a los Preview Environments del
    Blueprint, así que el secreto de producción nunca llega a un preview (y no
    debe llegar). Un preview tampoco puede usar el literal de desarrollo: sería
    público y permitiría forjar tokens. Se genera un secreto de 384 bits con
    ``secrets`` al primer uso y se reutiliza mientras viva el proceso: los
    tokens valen solo en esa instancia del preview y caducan con cada
    redeploy, lo que es aceptable para un entorno temporal. Si el equipo define
    AUDITBRAIN_JWT_SECRET en el preview (grupo de variables de entorno), ese
    valor tiene prioridad (ver _secret()).
    """
    global _PREVIEW_SECRET
    if _PREVIEW_SECRET is None:
        import logging
        import secrets

        _PREVIEW_SECRET = secrets.token_urlsafe(48)
        logging.getLogger("auditbrain").warning(
            "APP_ENV=preview sin AUDITBRAIN_JWT_SECRET: se generó un secreto "
            "JWT aleatorio para este proceso (los tokens caducan al redesplegar)."
        )
    return _PREVIEW_SECRET


def _secret() -> str:
    """Secreto de firma. OBLIGATORIO en producción.

    Si no está definido: en un Preview Environment (APP_ENV=preview) se usa un
    secreto aleatorio por proceso, NUNCA el literal de desarrollo; fuera de
    preview se usa el valor de desarrollo y se avisa: NO es seguro en
    producción (permitiría forjar tokens).
    """
    secret = os.getenv("AUDITBRAIN_JWT_SECRET", "").strip()
    if not secret:
        from backend.app.core.preview import is_preview

        if is_preview():
            return _preview_secret()
        import logging

        logging.getLogger("auditbrain").warning(
            "AUDITBRAIN_JWT_SECRET no definido: usando secreto de desarrollo "
            "INSEGURO. Definir en producción."
        )
        return "dev-insecure-secret-change-me"
    return secret


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
