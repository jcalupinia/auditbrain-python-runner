"""Matriz de cuentas de prueba del Preview Environment (datos versionados).

Reproduce en el preview los **permisos efectivos** de las cuentas de OPERADOR
reales del entorno de producción, obtenidos con una exportación de solo lectura
(SQL `SELECT` + control cruzado por los endpoints admin). Aquí vive **solo** la
autorización seudonimizada: un alias exclusivo del preview por persona y su rol.
El mapa alias → persona real lo conserva el dueño **fuera del repositorio**.

Garantías de privacidad:
- **Sin PII real.** No hay correos reales, nombres, RUC ni datos de clientes.
  Cada entrada es un alias ``pr-*@preview.audit-ia.ec`` + su rol.
- **Sin secretos.** No hay contraseñas, hashes ni tokens. Las claves del preview
  se generan aleatorias por cuenta en runtime (ver ``preview_seed``).
- **Sin inventar permisos.** El rol de cada cuenta es el verificado en la BD de
  producción; no se deduce del correo.

Decisión del dueño (2026-10-29): se reproducen **solo los operadores** (rol
``user``). El admin del preview ya existe (es el admin del bootstrap,
``preview-admin@audit-ia.ec``) y **no** se recrea aquí. Las cuentas de rol
``client`` **no** se reproducen.

Correspondencia (privada, fuera del repo) con los ids de producción:
    pr-op-01 → 59   pr-op-02 → 60   pr-op-03 → 61   pr-op-04 → 62
    pr-op-05 → 63   pr-op-06 → 64   pr-op-07 → 70   pr-op-08 → 72
"""

from __future__ import annotations

# Organización por defecto del preview (en producción era organization_id=1).
PREVIEW_ORG_PSEUDO = "ORG1"

# Cuentas que SIEMBRA el seeder. El admin NO está aquí a propósito (lo crea el
# bootstrap). Cada dict es autorización pura: alias de login + rol real.
PREVIEW_ACCOUNTS: list[dict[str, str]] = [
    {"alias": "pr-op-01@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-02@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-03@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-04@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-05@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-06@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-07@preview.audit-ia.ec", "role": "user"},
    {"alias": "pr-op-08@preview.audit-ia.ec", "role": "user"},
]
