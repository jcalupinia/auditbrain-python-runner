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

from .engine.governance import GENESIS, compute_hash
from .models import ForgeDecision, ForgePlan


class GovernanceError(RuntimeError):
    """La operación de gobernanza no se puede completar. El caller debe denegar."""


class ChainError(RuntimeError):
    """La cadena guardada no cuadra: manipulación o corrupción. Denegar."""


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
