"""Endpoints de agentes: catálogo, ejecución y consulta de runs."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.agents import service
from backend.app.agents.registry import get_agent, list_agents
from backend.app.agents.schemas import (
    AgentInputSchema,
    AgentOut,
    AgentRunCreate,
    AgentRunOut,
)
from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.context.models import Project
from backend.app.context.service import (
    ensure_user_has_organization,
    user_can_access_project,
)
from backend.app.db.session import get_db

router = APIRouter(tags=["agents"])


def _serialize(a) -> AgentOut:
    return AgentOut(
        code=a.code,
        module_code=a.module_code,
        label=a.label,
        description=a.description,
        inputs=[
            AgentInputSchema(
                name=i.name, label=i.label, kind=i.kind, required=i.required,
                options=list(i.options), placeholder=i.placeholder,
            )
            for i in a.inputs
        ],
        output_hint=a.output_hint,
    )


@router.get("/agents", response_model=list[AgentOut])
def list_agents_endpoint(
    module: str | None = None,
    _: User = Depends(get_current_user),
):
    return [_serialize(a) for a in list_agents(module)]


@router.get("/agents/{code}", response_model=AgentOut)
def get_agent_endpoint(code: str, _: User = Depends(get_current_user)):
    a = get_agent(code)
    if not a:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agente no encontrado.")
    return _serialize(a)


@router.post(
    "/agents/{code}/runs",
    response_model=AgentRunOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def execute_agent_endpoint(
    code: str,
    payload: AgentRunCreate,
    background: BackgroundTasks,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = get_agent(code)
    if not agent:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Agente no encontrado.")
    current = ensure_user_has_organization(db, current)
    if payload.project_id is not None:
        proj = db.get(Project, payload.project_id)
        if not proj or not user_can_access_project(db, current, proj):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Proyecto no accesible para este usuario.",
            )
    try:
        run = service.validate_and_create(
            db, current, agent, payload.project_id, payload.inputs
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    background.add_task(service.execute_run, run.id)
    return run


@router.get("/runs", response_model=list[AgentRunOut])
def list_runs_endpoint(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service.list_user_runs(db, current)


@router.get("/runs/{run_id}", response_model=AgentRunOut)
def get_run_endpoint(
    run_id: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = service.get_run(db, run_id, current)
    if not run:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run no encontrado.")
    return run
