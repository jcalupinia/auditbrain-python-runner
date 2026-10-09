"""Detección de Preview Environments de Render y valores que NUNCA deben
apuntar a producción desde un preview.

Render marca los previews del Blueprint con ``APP_ENV=preview`` (previewValue
en render.yaml) y nombra cada servicio del preview con el sufijo ``-pr-<n>``
(mismo ``n`` para backend y frontends del mismo PR); el hostname público del
servicio llega en ``RENDER_EXTERNAL_HOSTNAME`` (p. ej.
``auditbrain-python-runner-pr-123.onrender.com``). El patrón ``-pr-<n>`` debe
CONFIRMARSE en el primer preview (misma salvedad que el CORS de app.py).

Fuera de preview (``APP_ENV`` distinto de "preview") todo devuelve lo mismo
que antes: producción no cambia de comportamiento.
"""

from __future__ import annotations

import logging
import os
import re

log = logging.getLogger("auditbrain")

# URL del portal de clientes en producción (default histórico de CLIENT_PORTAL_URL).
PRODUCTION_PORTAL_URL = "https://auditbrain-clientes.onrender.com"

# Centinela para un preview cuyo número de PR no se pudo leer: dominio
# ``.invalid`` (RFC 6761), no resuelve. Un enlace roto es preferible a un
# enlace hacia producción.
PREVIEW_PORTAL_UNRESOLVED = "https://preview-portal-no-resuelto.invalid"

_PR_SUFFIX_RE = re.compile(r"-pr-(\d+)\.onrender\.com$")


def is_preview() -> bool:
    """True solo si ``APP_ENV`` vale exactamente "preview" (tras strip/lower)."""
    return os.getenv("APP_ENV", "production").strip().lower() == "preview"


def preview_pr_number() -> str | None:
    """Número de PR leído de ``RENDER_EXTERNAL_HOSTNAME`` (…-pr-<n>.onrender.com) o None."""
    host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "").strip().lower()
    m = _PR_SUFFIX_RE.search(host)
    return m.group(1) if m else None


def client_portal_url() -> str:
    """URL base del portal de clientes para enlaces y redirecciones.

    - Producción / dev: ``CLIENT_PORTAL_URL`` o el default histórico (idéntico
      al comportamiento previo).
    - Preview: el portal del MISMO preview (``auditbrain-clientes-pr-<n>``),
      ignorando ``CLIENT_PORTAL_URL`` (que en preview lleva un centinela). Si no
      se puede leer el número de PR, devuelve el centinela ``.invalid`` y avisa:
      nunca la URL de producción.
    """
    if not is_preview():
        return os.getenv("CLIENT_PORTAL_URL", PRODUCTION_PORTAL_URL)
    pr = preview_pr_number()
    if pr:
        return f"https://auditbrain-clientes-pr-{pr}.onrender.com"
    log.warning(
        "APP_ENV=preview pero RENDER_EXTERNAL_HOSTNAME=%r no termina en "
        "-pr-<n>.onrender.com: los enlaces al portal usan el centinela %s "
        "(nunca producción).",
        os.getenv("RENDER_EXTERNAL_HOSTNAME", ""),
        PREVIEW_PORTAL_UNRESOLVED,
    )
    return PREVIEW_PORTAL_UNRESOLVED
