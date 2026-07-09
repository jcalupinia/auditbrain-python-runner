"""Endpoints /api/v1/context/*  ·  /me/context."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.auth.deps import get_current_user, require_staff
from backend.app.auth.models import User
from backend.app.context import service
from backend.app.context.schemas import (
    ClientCreate,
    ClientOut,
    ContextOut,
    ProjectCreate,
    ProjectMemberAdd,
    ProjectMemberOut,
    ProjectOut,
    SetActiveContext,
)
from backend.app.db.session import get_db

router = APIRouter(tags=["context"])


# ----- /me/context ---------------------------------------------------------

@router.get("/me/context", response_model=ContextOut)
def my_context(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ctx = service.get_user_context(db, current)
    return ContextOut(**ctx)


@router.put("/me/context", response_model=ContextOut)
def set_my_context(
    payload: SetActiveContext,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = service.ensure_user_has_organization(db, current)
    try:
        service.set_active_project(db, current, payload.project_id)
    except PermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    ctx = service.get_user_context(db, current)
    return ContextOut(**ctx)


# ----- Clients -------------------------------------------------------------

@router.get("/context/clients", response_model=list[ClientOut])
def list_clients_endpoint(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = service.ensure_user_has_organization(db, current)
    return service.list_clients(db, current.organization_id)


@router.post(
    "/context/clients",
    response_model=ClientOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
)
def create_client_endpoint(
    payload: ClientCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = service.ensure_user_has_organization(db, current)
    return service.create_client(
        db,
        organization_id=current.organization_id,
        name=payload.name,
        tax_id=payload.tax_id,
        sector=payload.sector,
    )


# ----- Projects ------------------------------------------------------------

@router.get("/context/projects", response_model=list[ProjectOut])
def list_projects_endpoint(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = service.ensure_user_has_organization(db, current)
    return service.list_user_projects(db, current)


@router.post(
    "/context/projects",
    response_model=ProjectOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
)
def create_project_endpoint(
    payload: ProjectCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = service.ensure_user_has_organization(db, current)
    client = service.get_client(db, payload.client_id, current.organization_id)
    if not client:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Cliente no encontrado en la organización."
        )
    proj = service.create_project(
        db,
        organization_id=current.organization_id,
        client_id=client.id,
        name=payload.name,
        module_code=payload.module_code,
        period_label=payload.period_label,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    # El admin que crea el proyecto se auto-añade como member para verlo.
    service.add_project_member(db, proj.id, current.id, "lead")
    return proj


@router.post(
    "/context/projects/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_staff)],
)
def add_project_member_endpoint(
    project_id: int,
    payload: ProjectMemberAdd,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current = service.ensure_user_has_organization(db, current)
    proj = service.get_project(db, project_id, current.organization_id)
    if not proj:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Proyecto no encontrado en la organización."
        )
    target = db.get(User, payload.user_id)
    if not target or target.organization_id != current.organization_id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Usuario no pertenece a la organización."
        )
    return service.add_project_member(
        db, proj.id, target.id, payload.project_role
    )
