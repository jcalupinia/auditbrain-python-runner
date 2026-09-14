"""Clave personal de recursos: legible, sin caracteres ambiguos."""

from __future__ import annotations

import secrets

ALFABETO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generar_clave() -> str:
    c = "".join(secrets.choice(ALFABETO) for _ in range(9))
    return f"{c[:3]}-{c[3:6]}-{c[6:]}"


def normalizar(clave: str) -> str:
    """Forma canónica de una clave GENERADA: sin guiones/espacios, mayúsculas."""
    return "".join(ch for ch in clave if ch.isalnum()).upper()
