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

ESTADO: IMPLEMENTADO a verde con TDD (Task P1-D). Pruebas en
tests/test_execution_*.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app.execution.models import (
    ExecutionRun,
    STATUS_DEAD_LETTER,
    STATUS_SUCCEEDED,
)


def _excepciones(run: ExecutionRun | None) -> list[dict]:
    """Excepciones persistidas de una corrida (de ``summary_json``).

    El diff NO recalcula reglas: consume el resumen ya sellado por el motor.
    """
    if run is None or not run.summary_json:
        return []
    exc = run.summary_json.get("excepciones") or run.summary_json.get("exceptions") or []
    return list(exc)


def _clave(exc: dict) -> str:
    """Clave estable de una excepción (record_key/rule_id), no por posición."""
    if exc.get("clave"):
        return str(exc["clave"])
    return f"{exc.get('rule_id') or exc.get('regla_id')}::{exc.get('record_key') or exc.get('entidad_id')}"


def _material(exc: dict) -> tuple:
    """Campos cuyo cambio hace que una excepción sea 'cambiada' (monto/severidad)."""
    monto = exc.get("monto", exc.get("monto_expuesto"))
    return (str(monto), exc.get("severidad"))


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
        return bool(self.nuevas or self.resueltas or self.cambiadas)

    def a_dict(self) -> dict:
        """Serialización para ``ExecutionRun.diff_json`` y el correo. Task 11."""
        return {
            "current_run_id": self.current_run_id,
            "previous_run_id": self.previous_run_id,
            "nuevas": self.nuevas,
            "resueltas": self.resueltas,
            "cambiadas": self.cambiadas,
            "conteos": {
                "nuevas": len(self.nuevas),
                "resueltas": len(self.resueltas),
                "cambiadas": len(self.cambiadas),
            },
        }


def diff_runs(current: ExecutionRun, previous: ExecutionRun | None) -> RunDiff:
    """Compara dos corridas y devuelve el ``RunDiff`` (AUT-008).

    Empareja excepciones por su clave estable (record_key/rule_id), no por
    orden. Si ``previous`` es None (primera corrida), todo es "nuevas". Pura:
    no toca DB ni red, testeable con dos ``ExecutionRun`` en memoria.
    Implementar en Task 11 del plan.
    """
    ahora = {_clave(e): e for e in _excepciones(current)}
    antes = {_clave(e): e for e in _excepciones(previous)}

    nuevas = [e for k, e in ahora.items() if k not in antes]
    resueltas = [e for k, e in antes.items() if k not in ahora]
    cambiadas = [
        ahora[k]
        for k in ahora
        if k in antes and _material(ahora[k]) != _material(antes[k])
    ]
    return RunDiff(
        current_run_id=current.run_id,
        previous_run_id=previous.run_id if previous is not None else None,
        nuevas=nuevas,
        resueltas=resueltas,
        cambiadas=cambiadas,
    )


def run_continuous(
    db: Session,
    *,
    engagement_id: int,
    app_id: str,
    app_version: str,
    engine_version: str,
    input_hashes: dict[str, str],
    parameter_snapshot: dict,
    executed_by: int | None = None,
) -> str:
    """Dispara una corrida de auditoría continua y encadena el diff.

    Pasos:
      1. Resuelve ``previous_run_id`` con ``run_history.latest_successful_run``.
      2. Encola con ``queue.enqueue(trigger_source="continuous",
         previous_run_id=...)`` usando el snapshot ya sellado por el llamador
         (``snapshots.build_snapshot`` con los parámetros vigentes y el
         ruleset activo) y los hashes de los insumos nuevos.
      3. El worker ejecuta como cualquier corrida; al terminar,
         ``on_run_finished`` calcula el diff y notifica.
    Devuelve el ``run_id`` encolado.
    """
    # Import diferido: evita ciclo queue↔continuo y mantiene el paquete
    # importable sin arrastrar toda la cola al cargar este módulo.
    from backend.app.execution import run_history
    from backend.app.execution.queue import EnqueueRequest, enqueue

    previa = run_history.latest_successful_run(
        db, engagement_id=engagement_id, app_id=app_id
    )
    req = EnqueueRequest(
        engagement_id=engagement_id,
        app_id=app_id,
        app_version=app_version,
        engine_version=engine_version,
        input_hashes=input_hashes,
        parameter_snapshot=parameter_snapshot,
        executed_by=executed_by,
        trigger_source="continuous",
        previous_run_id=previa.run_id if previa is not None else None,
    )
    return enqueue(db, req).run_id


def on_run_finished(db: Session, run: ExecutionRun, *, to: list[str] | None = None) -> None:
    """Hook a invocar cuando una corrida continua llega a estado terminal.

    Si ``succeeded``: calcula ``diff_runs`` contra ``run.previous_run_id``,
    persiste ``run.diff_json`` y llama a ``notify_success`` (AUT-011).
    Si ``dead_letter``: llama a ``notify_failure`` (AUT-012).
    Lo llama el worker tras ``queue.mark_succeeded`` / ``mark_failed`` cuando
    ``trigger_source == "continuous"``. Una corrida no continua no notifica.
    """
    if run.trigger_source != "continuous":
        return

    if run.status == STATUS_SUCCEEDED:
        from backend.app.execution import run_history

        previa = (
            run_history.get_run(db, run.previous_run_id)
            if run.previous_run_id
            else None
        )
        diff = diff_runs(run, previa)
        run.diff_json = diff.a_dict()
        db.commit()
        if to:
            notify_success(run, diff, to=to)
    elif run.status == STATUS_DEAD_LETTER:
        if to:
            notify_failure(run, to=to)


def notify_success(run: ExecutionRun, diff: RunDiff, *, to: list[str]) -> None:
    """Envía el correo de corrida exitosa con el resumen del diff (AUT-011)."""
    from backend.app.notifications import email

    c = diff.a_dict()["conteos"]
    asunto = f"[AUDIT-IA] Corrida {run.app_id} OK — {c['nuevas']} nuevas / {c['cambiadas']} cambiadas"
    html = (
        f"<p>La corrida <b>{_html_escape(run.run_id)}</b> de "
        f"<b>{_html_escape(run.app_id)}</b> terminó correctamente.</p>"
        f"<ul><li>Excepciones nuevas: {c['nuevas']}</li>"
        f"<li>Resueltas: {c['resueltas']}</li>"
        f"<li>Cambiadas: {c['cambiadas']}</li></ul>"
    )
    for destino in to:
        email.send_email(to=destino, subject=asunto, html=html)


def notify_failure(run: ExecutionRun, *, to: list[str]) -> None:
    """Envía el correo de corrida fallida / dead-letter (AUT-012).

    El fallo NUNCA es silencioso: un monitoreo continuo que se cae sin avisar
    es peor que no tenerlo.
    """
    from backend.app.notifications import email

    traza = (run.error_trace or "")[:2000]
    asunto = f"[AUDIT-IA] FALLO en corrida {run.app_id} ({run.run_id})"
    html = (
        f"<p>La corrida <b>{_html_escape(run.run_id)}</b> de "
        f"<b>{_html_escape(run.app_id)}</b> quedó en <b>{run.status}</b> tras "
        f"agotar los reintentos.</p>"
        f"<pre>{_html_escape(traza)}</pre>"
        f"<p>Revise la causa y reencole la corrida desde el dead-letter.</p>"
    )
    for destino in to:
        email.send_email(to=destino, subject=asunto, html=html)


def _html_escape(texto: str | None) -> str:
    import html as _html

    return _html.escape(str(texto or ""))
