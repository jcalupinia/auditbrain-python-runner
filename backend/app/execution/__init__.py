"""Paquete ``execution`` — Motor de ejecución (Agente D, P0/P1).

Cierra las capacidades de orquestación/automatización del benchmark:
cola persistente con reintentos idempotentes, historial de corridas,
snapshots inmutables de parámetros/engine_version/ruleset y scheduler
(cron + continuous auditing con diff vs corrida previa y notificación de
éxito y fallo).

Contrato canónico: ``ExecutionRun`` (ver
``docs/ARQUITECTURA_CONVERGENCIA_v1.md`` §2 en el repo del motor).

ESTADO: SCAFFOLD tipado. La lógica real se implementa en el servidor
siguiendo ``docs/superpowers/plans/2026-09-24-p1d-execution-engine.md``
(las dependencias FastAPI/SQLAlchemy/APScheduler no corren en este
contenedor). Cada punto sin lógica levanta ``NotImplementedError`` con la
referencia a la task del plan que lo implementa.

Capacidades cubiertas: AUT-003/004/005/006/007/008/009/010/011/012,
DATA-011/012.
"""

from __future__ import annotations

# NOTE: los imports de submódulos NO se re-exportan a nivel de paquete de
# forma perezosa aquí porque ``models`` importa SQLAlchemy (no disponible en
# este contenedor). El consumidor importa el símbolo concreto del submódulo
# concreto (``from backend.app.execution.models import ExecutionRun``), igual
# que el resto de paquetes del repo (forge, ict, ...).

__all__ = [
    "models",
    "queue",
    "run_history",
    "snapshots",
    "scheduler",
]
