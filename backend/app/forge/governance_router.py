"""F2b.2 — La API de gobernanza: registrar, revisar, aprobar/rechazar, **el gate**.

Es donde la gobernanza pasa de *detectar* a **impedir**: ``POST /export`` solo
devuelve lo aprobado, o 409 sin artefacto. El estado vive en la BD (el cliente no
manda) y el aprobador es el **usuario autenticado** de la sesión.

Se monta bajo ``/api/v1/client/forge`` y reutiliza ``require_forge_client``: lo
consume la Console (rol client con ``FORGE_CONSOLE``) y, más adelante, el CLI
(``forge push/pull``, F2b.3) autenticado como operador. El montaje va dentro del
aislamiento de F2b.0: un fallo aquí no tumba ``/api/v1``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.auth.models import User
from backend.app.client_portal.entitlements import is_operator
from backend.app.client_portal.rate_limit import check_and_record
from backend.app.db.session import get_db

from . import governance_service as gov
from .client_router import require_forge_client
from .models import ForgePlan
from .schemas import (
    AuditOut,
    DecisionCreate,
    DecisionOut,
    ExportOut,
    PlanCreate,
    PlanOut,
    RejectCreate,
    ReviewOut,
    TaskStateOut,
)

governance_router = APIRouter(prefix="/client/forge", tags=["forge-governance"])


def _rate_limit(user: User, bucket: str) -> None:
    if not check_and_record(
        f"forge-gov:{bucket}:{user.id}", max_hits=60, window_seconds=60
    ):
        raise HTTPException(
            status_code=429, detail="Demasiadas peticiones; intenta en un momento."
        )


def _plan_or_404(db: Session, user: User, plan_id: str) -> ForgePlan:
    """Trae el plan **aislado por dueño** (P3). 404 —no 403— si no es tuyo: no se
    filtra ni la existencia de planes ajenos. Los operadores ven cualquiera."""
    plan = db.execute(
        select(ForgePlan).where(ForgePlan.plan_id == plan_id)
    ).scalar_one_or_none()
    if plan is None or (not is_operator(user) and plan.owner_user_id != user.id):
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    return plan


@governance_router.post("/plans", response_model=PlanOut)
def create_plan(
    payload: PlanCreate,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> PlanOut:
    """Registra un plan (``forge push``). **Idempotente** por ``plan_id``: mismo
    contenido ⇒ 200; contenido distinto ⇒ 409; nuevo ⇒ 201. El dueño sale de la
    sesión, nunca del payload."""
    _rate_limit(user, "plans")
    try:
        plan, created = gov.register_plan(
            db,
            owner_user_id=user.id,
            organization_id=getattr(user, "organization_id", None),
            plan_id=payload.plan_id,
            goal=payload.goal,
            schema_version=payload.schema_version,
            confidence=payload.confidence,
            model=payload.model,
            ai_invoked=payload.ai_invoked,
            tasks=payload.tasks,
        )
    except gov.PlanConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    response.status_code = 201 if created else 200
    return PlanOut(
        plan_id=plan.plan_id,
        goal=plan.goal,
        confidence=plan.confidence,
        model=plan.model,
        ai_invoked=plan.ai_invoked,
        tasks=list(plan.tasks or []),
        created=created,
    )


@governance_router.get("/plans", response_model=list[PlanOut])
def list_plans(
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> list[PlanOut]:
    q = select(ForgePlan).order_by(ForgePlan.id.desc())
    if not is_operator(user):
        q = q.where(ForgePlan.owner_user_id == user.id)
    return [
        PlanOut(
            plan_id=p.plan_id,
            goal=p.goal,
            confidence=p.confidence,
            model=p.model,
            ai_invoked=p.ai_invoked,
            tasks=list(p.tasks or []),
            created=False,
        )
        for p in db.execute(q).scalars().all()
    ]


@governance_router.get("/plans/{plan_id}/review", response_model=ReviewOut)
def review_plan(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> ReviewOut:
    plan = _plan_or_404(db, user, plan_id)
    return ReviewOut(
        plan_id=plan.plan_id,
        goal=plan.goal,
        tasks=[TaskStateOut(**f) for f in gov.review_state(db, plan)],
    )


@governance_router.post("/plans/{plan_id}/tasks/{task_id}/approve")
def approve(
    plan_id: str,
    task_id: str,
    payload: DecisionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> dict:
    _rate_limit(user, "approve")
    plan = _plan_or_404(db, user, plan_id)
    try:
        gov.approve_task(
            db, plan, task_id,
            actor_user_id=user.id, actor_label=user.email, rationale=payload.rationale,
        )
    except gov.TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except gov.AlreadyDecidedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "task_id": task_id, "estado": "approved"}


@governance_router.post("/plans/{plan_id}/tasks/{task_id}/reject")
def reject(
    plan_id: str,
    task_id: str,
    payload: RejectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> dict:
    """Rechaza una tarea. ``reason`` es obligatorio (Pydantic ⇒ 422 si falta)."""
    _rate_limit(user, "reject")
    plan = _plan_or_404(db, user, plan_id)
    try:
        gov.reject_task(
            db, plan, task_id,
            actor_user_id=user.id, actor_label=user.email, reason=payload.reason,
        )
    except gov.TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.commit()
    return {"ok": True, "task_id": task_id, "estado": "rejected"}


@governance_router.post("/plans/{plan_id}/export", response_model=ExportOut)
def export(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> ExportOut:
    """**El gate.** Devuelve solo las tareas aprobadas; si no hay ninguna, **409 sin
    artefacto** (P1). Una tarea editada tras aprobarse no sale (content-swap)."""
    _rate_limit(user, "export")
    plan = _plan_or_404(db, user, plan_id)
    approved, excluded = gov.export_gate(db, plan)
    if not approved:
        raise HTTPException(
            status_code=409,
            detail="No hay tareas aprobadas para exportar. Aprueba primero en la revisión.",
        )
    return ExportOut(plan_id=plan.plan_id, approved=approved, excluded=excluded)


@governance_router.get("/plans/{plan_id}/audit", response_model=AuditOut)
def audit(
    plan_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> AuditOut:
    """La traza, verificable. ``verified`` dice si la cadena cuadra de punta a punta."""
    plan = _plan_or_404(db, user, plan_id)
    try:
        filas = gov.verify_chain(db, plan)
        verified = True
    except gov.ChainError:
        filas = gov._decisiones_de(db, plan.id)
        verified = False
    return AuditOut(
        plan_id=plan.plan_id,
        verified=verified,
        decisions=[
            DecisionOut(
                seq=f.seq, actor=f.actor_label, action=f.action, task_id=f.task_id,
                decision=f.decision, rationale=f.rationale, ts=f.ts, hash=f.hash,
            )
            for f in filas
        ],
    )
