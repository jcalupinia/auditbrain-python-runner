"""L6 (vendorizado) — El hash de la cadena de auditoría, byte-idéntico al CLI.

Esto es una **copia deliberada** de la parte pura de
``src/forge/governance/audit.py`` del repo ``auditbrain-forge``. La plataforma
escribe la cadena contra PostgreSQL (no contra un archivo), pero el **hash** debe
calcularse **exactamente igual** que en el CLI: solo así una traza exportada por la
API verifica con ``forge audit verify`` en la máquina del cliente (criterio P7).

**No es reutilización, es vendoring con contrato.** El núcleo de Forge (L1-L3) es
neutral y no importable desde este backend; se copia la función pura y se blinda la
copia con un **test de conformidad de vectores fijos** (P8,
``tests/test_forge_governance_hash.py``). Si esta copia diverge del CLI, ese test
falla — la divergencia no puede pasar en silencio y romper P7.

``_CAMPOS_FIRMADOS`` y su orden son un **contrato**: cambiarlos invalida las cadenas
ya escritas y rompe la verificación cruzada con el CLI. ``content_hash`` entró en la
cadena con el fix del agujero content-swap (auditbrain-forge PR #9).
"""

from __future__ import annotations

import hashlib
from typing import Any

#: Campos que entran en el hash, en orden fijo. **Contrato con el CLI.** Debe
#: coincidir byte a byte con ``forge.governance.audit._CAMPOS_FIRMADOS``.
_CAMPOS_FIRMADOS = (
    "seq",
    "ts",
    "actor",
    "action",
    "plan_id",
    "task_id",
    "content_hash",
    "decision",
    "rationale",
)

#: Hash "cero" del que cuelga la primera decisión de una cadena.
GENESIS = "0" * 64


def compute_hash(entrada: dict[str, Any], prev_hash: str) -> str:
    """Hash de una entrada. Función pura: mismos datos, mismo hash.

    Idéntica a ``forge.governance.audit.compute_hash``. Un campo ausente cuenta
    como cadena vacía (``str("")``), igual que en el CLI.
    """
    material = "|".join(str(entrada.get(c, "")) for c in _CAMPOS_FIRMADOS)
    return hashlib.sha256(f"{material}|{prev_hash}".encode()).hexdigest()
