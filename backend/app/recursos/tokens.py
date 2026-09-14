"""Token del enlace de acceso a un recurso (JWT HS256, audiencia propia).

Lleva ``aud="recurso-acceso"``: ``auth.jwt_tokens.decode_token`` (consola) no
pasa ``audience``, así que PyJWT rechaza estos tokens allí. Un enlace de
recurso nunca sirve para entrar a la consola.
"""

from __future__ import annotations

import datetime

import jwt

from backend.app.auth.jwt_tokens import _ALGO, _secret

AUDIENCIA = "recurso-acceso"
TTL_DIAS = 30


def crear_token(lead_id: int, slug: str, *, dias: int = TTL_DIAS) -> str:
    ahora = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "sub": str(lead_id),
        "rs": slug,
        "aud": AUDIENCIA,
        "iat": ahora,
        "exp": ahora + datetime.timedelta(days=dias),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def leer_token(token: str, slug: str) -> int | None:
    """Id del lead si el token es válido, vigente y de este recurso; si no, None."""
    try:
        payload = jwt.decode(token, _secret(), algorithms=[_ALGO], audience=AUDIENCIA)
    except jwt.PyJWTError:
        return None
    if payload.get("rs") != slug:
        return None
    try:
        return int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        return None
