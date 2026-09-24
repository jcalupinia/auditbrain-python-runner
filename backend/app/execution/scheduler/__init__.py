"""Subpaquete ``scheduler`` — disparo temporizado y continuous auditing.

  * ``planificador.py`` — scheduler (APScheduler o Render Cron) que dispara
    corridas programadas y las tareas de mantenimiento de la cola (AUT-003).
  * ``continuo.py`` — continuous auditing: reejecuta, compara contra la
    corrida previa (diff) y notifica éxito Y fallo (AUT-008/011/012).

ESTADO: SCAFFOLD. Ver el plan
``docs/superpowers/plans/2026-09-24-p1d-execution-engine.md``.
"""

from __future__ import annotations

__all__ = ["planificador", "continuo"]
