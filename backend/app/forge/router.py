"""Router del módulo Forge (bajo /api/v1/forge).

Autenticado con ``get_current_user``. Aislamiento por ``owner_user_id``: cada
usuario solo ve y compila sus propios cerebros.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.db.session import get_db

from . import billing, plans, service
from .engine.adapters import list_adapters
from .schemas import (
    BrainCreate,
    BrainOut,
    CheckoutRequest,
    CompileOut,
    CompileRequest,
    MemoryCreate,
    MemoryOut,
    SubscriptionOut,
)


def _memory_out(m: dict) -> MemoryOut:
    return MemoryOut(
        slug=m.get("slug", ""),
        name=m.get("name", ""),
        description=m.get("description", ""),
        type=m.get("type", "project"),
    )

router = APIRouter(prefix="/forge", tags=["forge"])


@router.get("/targets")
def get_targets() -> list[str]:
    """Lista los destinos (adaptadores) disponibles."""
    return list_adapters()


@router.get("/brains", response_model=list[BrainOut])
def list_brains(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[BrainOut]:
    return [service.to_out(r) for r in service.list_brains(db, user.id)]


@router.post("/brains", response_model=BrainOut, status_code=201)
def create_brain(
    payload: BrainCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BrainOut:
    plans.check_can_create_brain(db, user)
    return service.to_out(service.create_brain(db, user, payload))


@router.get("/brains/{brain_id}", response_model=BrainOut)
def get_brain(
    brain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BrainOut:
    return service.to_out(service.get_owned_brain(db, user.id, brain_id))


@router.post("/brains/{brain_id}/compile", response_model=CompileOut)
def compile_brain(
    brain_id: int,
    payload: CompileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CompileOut:
    row = service.get_owned_brain(db, user.id, brain_id)
    plans.check_can_compile(db, user, payload.target)
    try:
        files = service.compile_brain(row, payload.target)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=f"Cerebro inválido: {exc}"
        ) from exc
    return CompileOut(target=payload.target, files=files, count=len(files))


# --- Memoria (L8) -----------------------------------------------------------

@router.get("/brains/{brain_id}/memory", response_model=list[MemoryOut])
def list_memory(
    brain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MemoryOut]:
    row = service.get_owned_brain(db, user.id, brain_id)
    return [_memory_out(m) for m in service.list_memory(row)]


@router.post("/brains/{brain_id}/memory", response_model=MemoryOut, status_code=201)
def add_memory(
    brain_id: int,
    payload: MemoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MemoryOut:
    row = service.get_owned_brain(db, user.id, brain_id)
    entry = service.add_memory(
        db, row, payload.name, payload.description, payload.body, payload.type
    )
    return _memory_out(entry)


# --- Facturación (Stripe) ---------------------------------------------------

@router.get("/subscription", response_model=SubscriptionOut)
def get_subscription(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> SubscriptionOut:
    plan = plans.get_user_plan(db, user.id)
    allowed = plans.PLANS[plan]["targets"]
    targets = sorted(list_adapters()) if allowed is None else sorted(allowed)
    return SubscriptionOut(
        plan=plan, targets=targets, max_brains=plans.plan_brain_limit(plan)
    )


@router.post("/billing/checkout")
def create_checkout(
    payload: CheckoutRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Crea una sesión de pago de Stripe y devuelve la URL de checkout."""
    return {"url": billing.create_checkout_url(user, payload.plan)}


@router.post("/billing/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Webhook de Stripe (sin auth: lo llama Stripe). Verifica firma si hay secret."""
    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    return billing.handle_webhook(db, payload, signature)
