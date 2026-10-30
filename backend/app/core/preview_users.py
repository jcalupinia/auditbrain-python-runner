"""Configuración de las cuentas de prueba del Preview Environment.

**Sin PII.** Este módulo versionado NO contiene ningún correo real. Las identidades
(correo del admin y correos de los operadores) se suministran **en tiempo de
ejecución** mediante un archivo de identidades que vive **solo en el volumen
aislado del preview autorizado** (ver ``preview_seed``), nunca en Git, nunca en
variables globales de Coolify (que se heredarían en todos los previews).

Aquí solo viven constantes de configuración no sensibles:
- el correo **genérico NO-PII** del admin de reserva (fallback),
- los roles reproducidos (``admin`` para el jefe, ``user`` para los operadores),
- las rutas/nombres de env por defecto.
"""

from __future__ import annotations

from backend.app.auth.models import Role

# Admin genérico de RESERVA (no es una persona real; puede ir en el repo).
# Se usa solo cuando NO hay un archivo de identidades válido en el preview.
GENERIC_ADMIN_EMAIL = "preview-admin@audit-ia.ec"

# Roles reproducidos (verificados en la BD de producción). No se inventan.
ADMIN_ROLE = Role.admin
OPERATOR_ROLE = Role.user

# Archivo de identidades por-PR (JSON {"admin": <correo>, "operators": [<correo>, …]}).
# Vive en el volumen `appdata` (/var/data), aislado por preview; lo coloca un
# operador de confianza por terminal, solo en el preview autorizado. Configurable.
ENV_IDENTITIES_FILE = "PREVIEW_IDENTITIES_FILE"
DEFAULT_IDENTITIES_FILE = "/var/data/preview-seed/identidades.json"

# Directorio donde se guardan las claves aleatorias por cuenta (volumen RW del PR).
ENV_SECRETS_DIR = "PREVIEW_USER_SECRETS_DIR"
DEFAULT_SECRETS_DIR = "/var/data/preview-users"
