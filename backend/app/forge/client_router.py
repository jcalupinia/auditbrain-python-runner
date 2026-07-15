"""Endpoints de Forge para el PORTAL DE CLIENTES (rol client).

Mismos datos que ``router.py`` (staff) pero autenticados con
``require_client_with_device`` — la Console (auditbrain-clientes) los consume.
Delegan en el mismo ``service``/``plans`` (una sola fuente de lógica).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.auth.deps import require_client_with_device
from backend.app.auth.models import User
from backend.app.client_portal.entitlements import can_access_tool, is_operator
from backend.app.db.session import get_db

from . import plans, service
from .engine.adapters import list_adapters
from .schemas import BrainCreate, BrainOut, CompileOut, CompileRequest, SubscriptionOut

client_router = APIRouter(prefix="/client/forge", tags=["forge-client"])

TOOL_CODE = "FORGE_CONSOLE"


def require_forge_client(
    user: User = Depends(require_client_with_device),
    db: Session = Depends(get_db),
) -> User:
    """Cliente autenticado CON acceso a Forge (entitlement o operador)."""
    if not is_operator(user) and not can_access_tool(db, user.id, TOOL_CODE):
        raise HTTPException(
            status_code=403,
            detail="No tienes acceso a Forge. Contacta a tu administrador.",
        )
    return user


@client_router.get("/targets")
def targets() -> list[str]:
    return list_adapters()


@client_router.get("/subscription", response_model=SubscriptionOut)
def subscription(
    db: Session = Depends(get_db), user: User = Depends(require_forge_client)
) -> SubscriptionOut:
    plan = plans.get_user_plan(db, user.id)
    allowed = plans.PLANS[plan]["targets"]
    tgts = sorted(list_adapters()) if allowed is None else sorted(allowed)
    return SubscriptionOut(
        plan=plan, targets=tgts, max_brains=plans.plan_brain_limit(plan)
    )


@client_router.get("/brains", response_model=list[BrainOut])
def list_brains(
    db: Session = Depends(get_db), user: User = Depends(require_forge_client)
) -> list[BrainOut]:
    return [service.to_out(r) for r in service.list_brains(db, user.id)]


@client_router.post("/brains", response_model=BrainOut, status_code=201)
def create_brain(
    payload: BrainCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> BrainOut:
    plans.check_can_create_brain(db, user)
    return service.to_out(service.create_brain(db, user, payload))


@client_router.get("/brains/{brain_id}", response_model=BrainOut)
def get_brain(
    brain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> BrainOut:
    return service.to_out(service.get_owned_brain(db, user.id, brain_id))


@client_router.post("/brains/{brain_id}/compile", response_model=CompileOut)
def compile_brain(
    brain_id: int,
    payload: CompileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_forge_client),
) -> CompileOut:
    row = service.get_owned_brain(db, user.id, brain_id)
    plans.check_can_compile(db, user, payload.target)
    try:
        files = service.compile_brain(row, payload.target)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Cerebro inválido: {exc}") from exc
    return CompileOut(target=payload.target, files=files, count=len(files))
