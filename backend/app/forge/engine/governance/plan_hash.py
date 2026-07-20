"""Huella del **contenido** de una tarea — byte-idéntica a ``Task.content_hash``.

Copia deliberada de ``forge.planner.model.Task.content_hash`` del CLI. La usa el
gate de exportación: al aprobar se firma este hash, y al exportar se re-verifica.
Si el contenido de una tarea cambió tras aprobarse, deja de estar aprobada (cierra
el content-swap, igual que en el CLI).

**Excluye ``id`` y ``status``**: el ``id`` es el ancla (ya va en la cadena) y el
``status`` es la vista, no el contenido. El orden de los campos es un **contrato**:
cambiarlo invalida las firmas ya escritas. Blindado con vectores fijos (P8).
"""

from __future__ import annotations

import hashlib
from typing import Any


def task_content_hash(task: dict[str, Any]) -> str:
    """Huella de 16 hex del contenido de una tarea (un dict del ``TaskPlan.tasks``).

    Réplica exacta de ``Task.content_hash`` del CLI: mismos campos, mismo orden,
    mismo separador, ``sha256(...).hexdigest()[:16]``.
    """
    material = "|".join(
        [
            str(task.get("description", "")),
            str(task.get("acceptance", "")),
            ",".join(sorted(task.get("capabilities", []) or [])),
            str(task.get("target", "") or ""),
            ",".join(sorted(task.get("deps", []) or [])),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
