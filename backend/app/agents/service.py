"""Ejecución de agentes especializados con persistencia."""

from __future__ import annotations

import datetime
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.models import AgentRun
from backend.app.agents.registry import AgentDef, get_agent
from backend.app.auth.models import User
from backend.app.chat.providers import ProviderUnavailable, chat_complete
from backend.app.context.service import ensure_user_has_organization
from backend.app.db.session import SessionLocal


def create_run(
    db: Session,
    user: User,
    agent: AgentDef,
    project_id: int | None,
    inputs: dict,
) -> AgentRun:
    user = ensure_user_has_organization(db, user)
    run = AgentRun(
        organization_id=user.organization_id,
        user_id=user.id,
        project_id=project_id,
        agent_code=agent.code,
        module_code=agent.module_code,
        status="queued",
        inputs=inputs or {},
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_user_runs(db: Session, user: User, limit: int = 50) -> list[AgentRun]:
    user = ensure_user_has_organization(db, user)
    return list(
        db.execute(
            select(AgentRun)
            .where(
                AgentRun.organization_id == user.organization_id,
                AgentRun.user_id == user.id,
            )
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        ).scalars()
    )


def get_run(db: Session, run_id: int, user: User) -> AgentRun | None:
    user = ensure_user_has_organization(db, user)
    return db.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.organization_id == user.organization_id,
            AgentRun.user_id == user.id,
        )
    ).scalar_one_or_none()


def _validate_inputs(agent: AgentDef, inputs: dict) -> str | None:
    """Devuelve un mensaje de error si falta algún input requerido."""
    for inp in agent.inputs:
        if inp.required and not str(inputs.get(inp.name, "")).strip():
            return f"Falta el input requerido: '{inp.label}' ({inp.name})."
    return None


def _build_user_message(agent: AgentDef, inputs: dict) -> str:
    """Serializa los inputs en un mensaje legible para el modelo."""
    lines = [f"Inputs del agente '{agent.label}':"]
    for inp in agent.inputs:
        v = inputs.get(inp.name)
        if v is None or (isinstance(v, str) and not v.strip()):
            continue
        lines.append(f"- {inp.label}: {v}")
    return "\n".join(lines)


def execute_run(run_id: int) -> None:
    """Ejecuta un run en background. Abre su propia sesión de BD para no
    depender del scope HTTP. Idempotente: si el run ya no está queued, no
    lo re-ejecuta."""
    db = SessionLocal()
    try:
        run = db.get(AgentRun, run_id)
        if not run or run.status != "queued":
            return
        agent = get_agent(run.agent_code)
        if not agent:
            run.status = "failed"
            run.error = f"Agente desconocido: {run.agent_code}"
            run.finished_at = datetime.datetime.utcnow()
            db.add(run); db.commit()
            return

        run.status = "running"
        run.started_at = datetime.datetime.utcnow()
        db.add(run); db.commit()

        try:
            inputs = run.inputs or {}
            user_msg = _build_user_message(agent, inputs)
            llm = chat_complete(
                messages=[{"role": "user", "content": user_msg}],
                system=agent.system_prompt,
            )
            run.output = llm.content
            run.model = llm.model
            run.tokens_in = llm.tokens_in
            run.tokens_out = llm.tokens_out
            run.status = "succeeded"
        except ProviderUnavailable as exc:
            run.status = "failed"
            run.error = f"Proveedor LLM no disponible: {exc}"
        except Exception as exc:
            run.status = "failed"
            run.error = f"Error ejecutando el agente: {exc}"
        finally:
            run.finished_at = datetime.datetime.utcnow()
            db.add(run); db.commit()
    finally:
        db.close()


def execute_inline(db: Session, run: AgentRun) -> AgentRun:
    """Ejecución sincrónica (para tests). Reutiliza execute_run."""
    db.commit()  # asegúrate de que el run está visible para otra sesión
    execute_run(run.id)
    db.refresh(run)
    return run


def validate_and_create(
    db: Session,
    user: User,
    agent: AgentDef,
    project_id: int | None,
    inputs: dict,
) -> AgentRun:
    err = _validate_inputs(agent, inputs)
    if err:
        raise ValueError(err)
    return create_run(db, user, agent, project_id, inputs)
