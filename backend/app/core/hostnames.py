"""Normalización de hostnames para comparaciones seguras (previews, CORS).

Regla: antes de comparar un hostname con un patrón se canoniza (minúsculas, sin
esquema, sin ruta, sin puerto, sin espacios ni punto final) y se valida que sea
un nombre DNS plausible. Lo que no supera la validación se descarta (None).
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*$")
_IP_RE = re.compile(r"^[\d.]+$")


def normalize_host(value: str | None) -> str | None:
    """Hostname canónico o None si no es un hostname DNS válido.

    Acepta URLs completas (se toma el host), ``host:puerto`` y valores con
    espacios o punto final. Rechaza IPs literales, guiones bajos, IDN y cadenas
    vacías o demasiado largas.
    """
    if not value:
        return None
    v = value.strip()
    if "://" in v:
        v = urlsplit(v).hostname or ""
    else:
        v = v.split("/", 1)[0].split("@")[-1]
        if v.count(":") == 1:  # host:puerto (no IPv6)
            v = v.split(":", 1)[0]
    v = v.rstrip(".").lower()
    if not v or len(v) > 253 or not _HOST_RE.match(v) or _IP_RE.fullmatch(v):
        return None
    return v


def split_hosts(value: str | None) -> list[str]:
    """Lista de hostnames normalizados a partir de un valor separado por comas o espacios.

    Coolify puede entregar varios dominios en una sola variable (``COOLIFY_FQDN``).
    """
    out: list[str] = []
    for tok in re.split(r"[,\s]+", value or ""):
        h = normalize_host(tok)
        if h and h not in out:
            out.append(h)
    return out
