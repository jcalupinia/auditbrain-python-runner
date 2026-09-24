"""Entrypoint del Render Cron: un tick de mantenimiento de la cola (AUT-003).

Uso (Render Cron Job, p. ej. ``*/5 * * * *``):

    python -m backend.app.execution.scheduler.tick

Abre una sesión, ejecuta el mantenimiento (recupera leases vencidos) y cierra.
Cuando exista una fuente de schedules persistente, este tick también llamará a
``run_due_schedules`` con su ``build_request``. No requiere proceso siempre
activo ni la dependencia APScheduler (ese backend es el alternativo in-process).
"""

from __future__ import annotations

import logging


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger("execution.tick")
    from backend.app.db.session import SessionLocal, init_db
    from backend.app.execution.scheduler.planificador import run_maintenance

    # Autosuficiente: si corre como proceso separado del cron contra una base
    # aún sin migrar, crea las tablas (idempotente). En producción la app ya
    # las creó en su arranque; aquí es una salvaguarda barata.
    init_db()

    db = SessionLocal()
    try:
        resumen = run_maintenance(db)
        log.info("tick de mantenimiento: %s", resumen)
    finally:
        db.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
