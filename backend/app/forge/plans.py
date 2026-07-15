"""Planes de Forge y gating por plan (destinos permitidos + límite de cerebros).

El plan vigente de un usuario sale de su ``ForgeSubscription`` activa; sin
suscripción activa, el plan es ``free``. La lógica no depende de Stripe (Stripe
solo actualiza la suscripción vía webhook), por lo que es testeable en aislado.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .engine.adapters import list_adapters
from .models import ForgeBrain, ForgeSubscription

# targets=None → todos los destinos; max_brains=None → ilimitado.
PLANS: dict[str, dict] = {
    "free": {"targets": {"claude-code"}, "max_brains": 1},
    "pro": {"targets": None, "max_brains": 10},
    "team": {"targets": None, "max_brains": None},
}
DEFAULT_PLAN = "free"
PAID_PLANS = ("pro", "team")


def get_user_plan(db: Session, user_id: int) -> str:
    sub = db.execute(
        select(ForgeSubscription).where(ForgeSubscription.user_id == user_id)
    ).scalar_one_or_none()
    if sub and sub.status == "active" and sub.plan in PLANS:
        return sub.plan
    return DEFAULT_PLAN


def plan_allows_target(plan: str, target: str) -> bool:
    allowed = PLANS[plan]["targets"]
    if allowed is None:
        return target in set(list_adapters())
    return target in allowed


def plan_brain_limit(plan: str) -> int | None:
    return PLANS[plan]["max_brains"]


def check_can_create_brain(db: Session, user_id: int) -> None:
    plan = get_user_plan(db, user_id)
    limit = plan_brain_limit(plan)
    if limit is None:
        return
    count = db.execute(
        select(func.count())
        .select_from(ForgeBrain)
        .where(ForgeBrain.owner_user_id == user_id)
    ).scalar_one()
    if count >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"Tu plan '{plan}' permite hasta {limit} cerebro(s). Mejora tu plan.",
        )


def check_can_compile(db: Session, user_id: int, target: str) -> None:
    plan = get_user_plan(db, user_id)
    if not plan_allows_target(plan, target):
        raise HTTPException(
            status_code=402,
            detail=(
                f"Tu plan '{plan}' no incluye el destino '{target}'. Mejora tu plan."
            ),
        )
