"""Continuous auditing: reejecuta, compara con la corrida previa y notifica.

Cierra el ciclo de la auditoría continua sobre la cola persistente:

  * **AUT-008** — Diff contra la corrida previa: tras una corrida
    ``succeeded``, compara sus excepciones/resultados con los de la última
    corrida comparable (``run_history.latest_successful_run``) y clasifica en
    NUEVAS, RESUELTAS y CAMBIADAS. Ese diff es lo que le importa al auditor en
    monitoreo continuo (no la foto completa cada vez).
  * **AUT-011** — Notificación de ÉXITO: cuando una corrida programada termina
    bien, avisa (con el resumen del diff) a los responsables.
  * **AUT-012** — Notificación de FALLO: cuando una corrida va a
    ``dead_letter`` (o falla de forma relevante), avisa igual. El fallo NUNCA
    es silencioso: un monitoreo que se cae sin avisar es peor que no tenerlo.

Reutiliza ``backend/app/notifications/email.py`` (Resend + retry): no se
reimplementa el envío; se agrega el render del correo de corrida (éxito y
fallo) siguiendo el patrón de ``render_job_ready`` / ``send_job_ready_email``.

El diff se calcula sobre las excepciones del motor. El motor determinista
(Agente A) sella cada excepción con su clave estable
(``motor/nucleo.py::Excepcion`` + ``run_id``/``source_refs``); el diff empareja
por esa clave, no por posición. Este módulo consume el resumen ya persistido
de cada corrida (``ExecutionRun.summary_json`` / los artefactos sellados por
hash), no recalcula reglas.

ESTADO: SCAFFOLD. Firmas + docstrings; lógica levanta NotImplementedError.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app.execution.models import ExecutionRun


@dataclass(frozen=True)
class RunDiff:
    """Resultado de comparar una corrida contra su previa (AUT-008)."""

    current_run_id: str
    previous_run_id: str | None
    #: Claves de excepción presentes ahora y no antes.
    nuevas: list[dict] = field(default_factory=list)
    #: Presentes antes y ya no (resueltas/desaparecidas).
    resueltas: list[dict] = field(default_factory=list)
    #: Presentes en ambas pero con cambio material (monto/severidad).
    cambiadas: list[dict] = field(default_factory=list)

    def hay_cambios(self) -> bool:
        """True si el diff tiene algo que reportar. Task 11."""
        raise NotImplementedError("RunDiff.hay_cambios: implementar en Task 11.")

    def a_dict(self) -> dict:
        """Serialización para ``ExecutionRun.diff_json`` y el correo. Task 11."""
        raise NotImplementedError("RunDiff.a_dict: implementar en Task 11.")


def diff_runs(current: ExecutionRun, previous: ExecutionRun | None) -> RunDiff:
    """Compara dos corridas y devuelve el ``RunDiff`` (AUT-008).

    Empareja excepciones por su clave estable (record_key/rule_id), no por
    orden. Si ``previous`` es None (primera corrida), todo es "nuevas". Pura:
    no toca DB ni red, testeable con dos ``ExecutionRun`` en memoria.
    Implementar en Task 11 del plan.
    """
    raise NotImplementedError("diff_runs: implementar el emparejamiento en Task 11.")


def run_continuous(
    db: Session,
    *,
    engagement_id: int,
    app_id: str,
    app_version: str,
    executed_by: int | None = None,
) -> str:
    """Dispara una corrida de auditoría continua y encadena el diff.

    Pasos:
      1. Resuelve ``previous_run_id`` con ``run_history.latest_successful_run``.
      2. Construye el snapshot vigente (``snapshots.build_snapshot``) y encola
         con ``queue.enqueue(trigger_source="continuous", previous_run_id=...)``.
      3. El worker ejecuta como cualquier corrida; al terminar,
         ``on_run_finished`` calcula el diff y notifica.
    Devuelve el ``run_id`` encolado. Implementar en Task 11.
    """
    raise NotImplementedError("run_continuous: implementar el encadenado en Task 11.")


def on_run_finished(db: Session, run: ExecutionRun) -> None:
    """Hook a invocar cuando una corrida continua llega a estado terminal.

    Si ``succeeded``: calcula ``diff_runs`` contra ``run.previous_run_id``,
    persiste ``run.diff_json`` y llama a ``notify_success`` (AUT-011).
    Si ``dead_letter``: llama a ``notify_failure`` (AUT-012).
    Lo llama el worker tras ``queue.mark_succeeded`` / ``mark_failed`` cuando
    ``trigger_source == "continuous"``. Implementar en Task 12.
    """
    raise NotImplementedError("on_run_finished: implementar el hook terminal en Task 12.")


def notify_success(run: ExecutionRun, diff: RunDiff, *, to: list[str]) -> None:
    """Envía el correo de corrida exitosa con el resumen del diff (AUT-011).

    Usa ``backend.app.notifications.email.send_email`` con un template nuevo
    (``run_success.html``, análogo a ``job_ready.html``). Implementar en
    Task 12.
    """
    raise NotImplementedError("notify_success: implementar el correo de éxito en Task 12.")


def notify_failure(run: ExecutionRun, *, to: list[str]) -> None:
    """Envía el correo de corrida fallida / dead-letter (AUT-012).

    Incluye ``error_trace`` recortado y el link a la corrida para reencolar
    tras corregir. Usa el mismo wrapper de email. Implementar en Task 12.
    """
    raise NotImplementedError("notify_failure: implementar el correo de fallo en Task 12.")
