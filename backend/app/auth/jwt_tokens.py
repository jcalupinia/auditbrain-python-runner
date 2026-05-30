"""Emisión y validación de JWT (HS256, PyJWT)."""

import datetime
import os

import jwt

_ALGO = "HS256"
_ACCESS_TTL_MIN = int(os.getenv("AUDITBRAIN_JWT_EXPIRE_MINUTES", "60"))


def _secret() -> str:
    """Secreto de firma. OBLIGATORIO en producción.

    Si no está definido se usa un valor de desarrollo y se avisa: NO es
    seguro en producción (permitiría forjar tokens).
    """
    secret = os.getenv("AUDITBRAIN_JWT_SECRET", "").strip()
    if not secret:
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
    now = datetime.datetime.utcnow()
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
