"""L6 en la plataforma — escribe y verifica la cadena de gobernanza en PostgreSQL.

Es el equivalente de servidor de ``forge/governance/audit.py`` y ``approval.py``
del CLI, pero el estado vive donde el cliente **no manda** (la BD), y el aprobador
es un **usuario autenticado**, no autodeclarado. El ``hash`` se calcula con el
``compute_hash`` vendorizado (byte-idéntico al CLI) para que la traza verifique con
``forge audit verify`` (P7/P8).

Este módulo **nunca** emite ``UPDATE``/``DELETE`` sobre ``forge_decisions``: la
cadena es append-only. El trigger de BD (``init_db``) es la garantía dura; esto es
la defensa en profundidad del lado del código.
"""

from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .engine.governance import GENESIS, compute_hash, task_content_hash
from .models import ForgeDecision, ForgePlan


class GovernanceError(RuntimeError):
    """La operación de gobernanza no se puede completar. El caller debe denegar."""


class ChainError(RuntimeError):
    """La cadena guardada no cuadra: manipulación o corrupción. Denegar."""


class PlanConflictError(GovernanceError):
    """Se reenvió un ``plan_id`` ya registrado con **contenido distinto** (409)."""


class TaskNotFoundError(GovernanceError):
    """La tarea referida no existe en el plan (404)."""


class NotApprovedError(GovernanceError):
    """El gate: no hay nada aprobado que exportar (409, sin artefacto)."""


class AlreadyDecidedError(GovernanceError):
    """Se intentó aprobar una tarea ya **rechazada**: el rechazo es terminal (409)."""


def _iso_now() -> str:
    """ISO 8601 en UTC. Es exactamente el texto que se firma (byte-estable)."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _entrada_firmada(
    *,
    seq: int,
    ts: str,
    actor_label: str,
    action: str,
    plan_id: str,
    task_id: str,
    content_hash: str,
    decision: str,
    rationale: str,
) -> dict:
    """Arma el dict que entra en ``compute_hash``, con el mapeo hacia el CLI.

    El CLI firma ``actor`` (el identificador humano) y ``plan_id`` (el uuid4), no
    los ids numéricos de la BD. Aquí ``actor`` = ``actor_label`` y ``plan_id`` = el
    ``plan_id`` del CLI. Cambiar este mapeo rompe la verificación cruzada (P7).
    """
    return {
        "seq": seq,
        "ts": ts,
        "actor": actor_label,
        "action": action,
        "plan_id": plan_id,
        "task_id": task_id,
        "content_hash": content_hash,
        "decision": decision,
        "rationale": rationale,
    }


def _decisiones_de(db: Session, plan_row_id: int) -> list[ForgeDecision]:
    return list(
        db.execute(
            select(ForgeDecision)
            .where(ForgeDecision.plan_row_id == plan_row_id)
            .order_by(ForgeDecision.seq.asc())
        )
        .scalars()
        .all()
    )


def append_decision(
    db: Session,
    plan: ForgePlan,
    *,
    actor_user_id: int,
    actor_label: str,
    action: str,
    decision: str,
    rationale: str,
    task_id: str = "",
    content_hash: str = "",
) -> ForgeDecision:
    """Añade una decisión a la cadena del plan y devuelve la fila escrita.

    ``actor_user_id`` es la identidad **autenticada** (de la sesión, nunca de un
    parámetro del cliente); ``actor_label`` es su snapshot legible y es lo que se
    firma. No hace ``commit`` — lo hace el caller (la request), para que la
    decisión y sus efectos entren en una sola transacción.
    """
    previas = _decisiones_de(db, plan.id)
    seq = len(previas) + 1
    prev_hash = previas[-1].hash if previas else GENESIS
    ts = _iso_now()

    entrada = _entrada_firmada(
        seq=seq,
        ts=ts,
        actor_label=actor_label,
        action=action,
        plan_id=plan.plan_id,
        task_id=task_id,
        content_hash=content_hash,
        decision=decision,
        rationale=rationale,
    )
    fila = ForgeDecision(
        seq=seq,
        plan_row_id=plan.id,
        organization_id=plan.organization_id,
        actor_user_id=actor_user_id,
        actor_label=actor_label,
        action=action,
        task_id=task_id,
        content_hash=content_hash,
        decision=decision,
        rationale=rationale,
        ts=ts,
        prev_hash=prev_hash,
        hash=compute_hash(entrada, prev_hash),
    )
    db.add(fila)
    db.flush()  # asigna id y dispara la unicidad (plan_row_id, seq) sin commitear
    return fila


def verify_chain(db: Session, plan: ForgePlan) -> list[ForgeDecision]:
    """Verifica la cadena entera del plan y la devuelve. Lanza ``ChainError``.

    Recalcula cada ``hash`` desde ``GENESIS`` con el ``compute_hash`` vendorizado:
    detecta una fila alterada, un ``seq`` fuera de orden o un ``prev_hash`` roto.
    Es lo que hace verificable la traza sin confiar en la BD.
    """
    filas = _decisiones_de(db, plan.id)
    prev_hash = GENESIS
    for i, fila in enumerate(filas, start=1):
        if fila.seq != i:
            raise ChainError(
                f"cadena manipulada: se esperaba seq={i} y hay seq={fila.seq}"
            )
        if fila.prev_hash != prev_hash:
            raise ChainError(f"cadena manipulada: la fila {i} no encadena")
        entrada = _entrada_firmada(
            seq=fila.seq,
            ts=fila.ts,
            actor_label=fila.actor_label,
            action=fila.action,
            plan_id=plan.plan_id,
            task_id=fila.task_id,
            content_hash=fila.content_hash,
            decision=fila.decision,
            rationale=fila.rationale,
        )
        if compute_hash(entrada, prev_hash) != fila.hash:
            raise ChainError(f"cadena manipulada: la fila {i} fue alterada")
        prev_hash = fila.hash
    return filas


def estado_por_tarea(db: Session, plan: ForgePlan) -> dict[str, ForgeDecision]:
    """Última decisión por ``task_id`` (la que vale). Base del gate y del review."""
    ultimo: dict[str, ForgeDecision] = {}
    for fila in _decisiones_de(db, plan.id):
        ultimo[fila.task_id] = fila
    return ultimo


def usuario_tiene_decisiones(db: Session, user_id: int) -> bool:
    """¿El usuario firmó alguna decisión? Lo consulta el borrado de cuenta (P12):
    no se puede borrar a quien tiene rastro de aprobaciones en la traza."""
    row = db.execute(
        select(ForgeDecision.id)
        .where(ForgeDecision.actor_user_id == user_id)
        .limit(1)
    ).first()
    return row is not None


# --- Registro idempotente del plan (POST /plans) --------------------------------


def _tarea_de(plan: ForgePlan, task_id: str) -> dict:
    for t in plan.tasks or []:
        if t.get("id") == task_id:
            return t
    raise TaskNotFoundError(f"el plan no tiene la tarea '{task_id}'")


def register_plan(
    db: Session,
    *,
    owner_user_id: int,
    organization_id: int | None,
    plan_id: str,
    goal: str,
    schema_version: str,
    confidence: str,
    model: str,
    ai_invoked: bool,
    tasks: list[dict],
) -> tuple[ForgePlan, bool]:
    """Registra un plan. **Idempotente** por ``plan_id`` (contrato con ``forge push``).

    - No existe          → se crea. Devuelve ``(plan, True)``.
    - Existe e **idéntico** → se devuelve el guardado. ``(plan, False)`` (⇒ 200).
    - Existe y **difiere**  → ``PlanConflictError`` (⇒ 409). Un reintento de red no
      puede pisar un plan con contenido distinto ni dar un 500.

    ``owner_user_id`` sale de la sesión autenticada, **nunca de un parámetro** del
    cliente: es el aislamiento multi-tenant (P3).
    """
    existente = db.execute(
        select(ForgePlan).where(ForgePlan.plan_id == plan_id)
    ).scalar_one_or_none()
    if existente is not None:
        mismo = (
            existente.owner_user_id == owner_user_id
            and existente.goal == goal
            and list(existente.tasks or []) == list(tasks or [])
        )
        if not mismo:
            raise PlanConflictError(
                f"el plan '{plan_id}' ya existe con contenido distinto"
            )
        return existente, False

    plan = ForgePlan(
        owner_user_id=owner_user_id,
        organization_id=organization_id,
        plan_id=plan_id,
        goal=goal,
        schema_version=schema_version,
        confidence=confidence,
        model=model,
        ai_invoked=ai_invoked,
        tasks=list(tasks or []),
    )
    db.add(plan)
    db.flush()
    return plan, True


# --- Aprobar / rechazar ----------------------------------------------------------


def approve_task(
    db: Session,
    plan: ForgePlan,
    task_id: str,
    *,
    actor_user_id: int,
    actor_label: str,
    rationale: str = "aprobada por una persona",
) -> ForgeDecision:
    """Aprueba una tarea, firmando el hash de su **contenido actual**.

    Firmar el ``content_hash`` es lo que cierra el content-swap: si la tarea cambia
    después, el gate lo detecta (su hash deja de coincidir con el firmado).

    **El rechazo es terminal** (P5): aprobar una tarea ya rechazada ⇒
    ``AlreadyDecidedError`` (409). Re-aprobar una ya aprobada sí se permite (p. ej.
    tras editar y re-subir): la cadena es append-only y la última decisión manda."""
    tarea = _tarea_de(plan, task_id)
    ultimo = estado_por_tarea(db, plan).get(task_id)
    if ultimo is not None and ultimo.decision == "rejected":
        raise AlreadyDecidedError(
            f"la tarea '{task_id}' ya fue rechazada; el rechazo es terminal"
        )
    return append_decision(
        db, plan,
        actor_user_id=actor_user_id, actor_label=actor_label,
        action="approve", decision="approved", rationale=rationale,
        task_id=task_id, content_hash=task_content_hash(tarea),
    )


def reject_task(
    db: Session,
    plan: ForgePlan,
    task_id: str,
    *,
    actor_user_id: int,
    actor_label: str,
    reason: str,
) -> ForgeDecision:
    """Rechaza una tarea. El motivo es obligatorio (el router devuelve 422 si falta)."""
    tarea = _tarea_de(plan, task_id)
    return append_decision(
        db, plan,
        actor_user_id=actor_user_id, actor_label=actor_label,
        action="reject", decision="rejected", rationale=reason,
        task_id=task_id, content_hash=task_content_hash(tarea),
    )


# --- Review y el GATE de exportación --------------------------------------------


def review_state(db: Session, plan: ForgePlan) -> list[dict]:
    """Estado por tarea **según la BD**: pending / approved / rejected (+ si se
    modificó tras aprobarse). Base del ``GET /plans/{id}/review`` y del gate."""
    ultimo = estado_por_tarea(db, plan)
    filas = []
    for t in plan.tasks or []:
        tid = t.get("id", "")
        d = ultimo.get(tid)
        if d is None:
            estado = "pending"
        elif d.decision == "approved":
            estado = (
                "approved"
                if d.content_hash == task_content_hash(t)
                else "modified"  # aprobada, pero el contenido cambió después
            )
        else:
            estado = "rejected"
        filas.append(
            {
                "task_id": tid,
                "description": t.get("description", ""),
                "estado": estado,
                "actor": d.actor_label if d else None,
                "ts": d.ts if d else None,
                "rationale": d.rationale if d else None,
            }
        )
    return filas


def export_gate(db: Session, plan: ForgePlan) -> tuple[list[dict], list[dict]]:
    """**El gate.** Devuelve ``(tareas_aprobadas, excluidas)``.

    Una tarea sale solo si su última decisión es ``approved`` **y** el
    ``content_hash`` firmado coincide con el contenido actual (si se editó tras
    aprobarse, no sale: cierre del content-swap). El router traduce "no hay nada
    aprobado" en **409 sin artefacto** (P1)."""
    estados = {f["task_id"]: f["estado"] for f in review_state(db, plan)}
    aprobadas, excluidas = [], []
    for t in plan.tasks or []:
        tid = t.get("id", "")
        if estados.get(tid) == "approved":
            aprobadas.append(t)
        else:
            excluidas.append({"task_id": tid, "estado": estados.get(tid, "pending")})
    return aprobadas, excluidas
