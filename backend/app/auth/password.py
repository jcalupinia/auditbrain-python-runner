"""Hashing de contraseñas con bcrypt (sin passlib para evitar problemas
de compatibilidad de versiones)."""

import bcrypt

# bcrypt trunca a 72 bytes; lo recortamos explícitamente para evitar
# comportamiento dependiente de versión.
_MAX_BYTES = 72


def _norm(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_norm(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_norm(password), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False
