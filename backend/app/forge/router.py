"""Router del módulo Forge (bajo /api/v1/forge).

Autenticado con ``get_current_user``. Aislamiento por ``owner_user_id``: cada
usuario solo ve y compila sus propios cerebros.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.db.session import get_db

from . import service
from .engine.adapters import list_adapters
from .schemas import BrainCreate, BrainOut, CompileOut, CompileRequest

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
    try:
        files = service.compile_brain(row, payload.target)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=400, detail=f"Cerebro inválido: {exc}"
        ) from exc
    return CompileOut(target=payload.target, files=files, count=len(files))
