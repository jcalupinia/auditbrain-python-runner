"""Catálogo de aplicaciones AUDIT-IA.

Las «Cuentas de Aplicaciones AUDIT-IA» son un tipo de cuenta DEDICADO (aparte de los
operadores y de los usuarios del portal de auditoría) que inician sesión en las
aplicaciones de la plataforma AUDIT-IA (p. ej. AUDIT SOUND). Cada cuenta tiene acceso a
una o varias apps de este catálogo.

Para agregar una app nueva, añade un AppInfo aquí; no hace falta tocar nada más.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AppInfo:
    key: str          # identificador estable (se guarda en la BD y lo envía la app)
    label: str        # nombre visible
    description: str = ""


AUDIT_IA_APPS: list[AppInfo] = [
    AppInfo("audit_sound", "AUDIT SOUND", "Consola DJ profesional con IA"),
]

APP_KEYS: set[str] = {a.key for a in AUDIT_IA_APPS}


def app_catalog() -> list[dict]:
    return [{"key": a.key, "label": a.label, "description": a.description} for a in AUDIT_IA_APPS]


def is_valid_app(key: str) -> bool:
    return key in APP_KEYS
