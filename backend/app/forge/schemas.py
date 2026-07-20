"""Schemas Pydantic v2 del módulo Forge."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class BrainCreate(BaseModel):
    name: str
    slug: str
    organization: str = ""
    language: str = "python"
    version: str = "0.1.0"
    targets: list[str] = Field(default_factory=lambda: ["claude-code"])
    rules: list[dict] = Field(default_factory=list)
    memory: list[dict] = Field(default_factory=list)
    skills: list[dict] = Field(default_factory=list)
    agents: list[dict] = Field(default_factory=list)
    personas: list[dict] = Field(default_factory=list)
    connectors: list[dict] = Field(default_factory=list)
    capabilities: list[dict] = Field(default_factory=list)


class BrainOut(BaseModel):
    id: int
    name: str
    slug: str
    organization: str
    language: str
    version: str
    targets: list[str]


class CompileRequest(BaseModel):
    target: str = "claude-code"


class CompileOut(BaseModel):
    target: str
    files: dict[str, str]
    count: int


class CheckoutRequest(BaseModel):
    plan: str


class SubscriptionOut(BaseModel):
    plan: str
    targets: list[str]
    max_brains: int | None


class MemoryCreate(BaseModel):
    name: str
    description: str
    body: str = ""
    type: str = "project"


class MemoryOut(BaseModel):
    slug: str
    name: str
    description: str
    type: str


# --- F2b.2 · Gobernanza: planes y decisiones ------------------------------------

#: Tope del payload de tareas (§3.3): un CLI con un bug no puede inflar la BD que
#: sirve al ICT y al portal. Se mide sobre el JSON serializado.
MAX_TASKS_BYTES = 64 * 1024


class PlanCreate(BaseModel):
    """El ``TaskPlan`` que sube ``forge push``. Se registra tal cual (dato revisable)."""

    plan_id: str = Field(min_length=1, max_length=64)
    goal: str = ""
    schema_version: str = "1"
    confidence: str = "media"
    model: str = ""
    ai_invoked: bool = False
    tasks: list[dict] = Field(default_factory=list)

    @field_validator("tasks")
    @classmethod
    def _tasks_bajo_tope(cls, v: list[dict]) -> list[dict]:
        import json

        if len(json.dumps(v, ensure_ascii=False).encode("utf-8")) > MAX_TASKS_BYTES:
            raise ValueError(
                f"'tasks' supera el tope de {MAX_TASKS_BYTES} bytes"
            )
        for t in v:
            if not isinstance(t, dict) or not t.get("id"):
                raise ValueError("cada tarea debe ser un objeto con 'id'")
        return v


class PlanOut(BaseModel):
    plan_id: str
    goal: str
    confidence: str
    model: str
    ai_invoked: bool
    tasks: list[dict]
    created: bool = True  # ¿se creó ahora (True) o ya existía idéntico (False)?


class DecisionCreate(BaseModel):
    """Motivo de una aprobación. Opcional: si falta, se usa una nota estándar."""

    rationale: str = "aprobada por una persona"


class RejectCreate(BaseModel):
    """Motivo de un rechazo. **Obligatorio** (sin él no hay auditoría) ⇒ 422."""

    reason: str = Field(min_length=1)


class TaskStateOut(BaseModel):
    task_id: str
    description: str
    estado: str  # pending | approved | rejected | modified
    actor: str | None = None
    ts: str | None = None
    rationale: str | None = None


class ReviewOut(BaseModel):
    plan_id: str
    goal: str
    tasks: list[TaskStateOut]


class ExportOut(BaseModel):
    plan_id: str
    approved: list[dict]  # solo las tareas aprobadas (el artefacto)
    excluded: list[dict]  # las que NO salen, con su estado


class DecisionOut(BaseModel):
    seq: int
    actor: str
    action: str
    task_id: str
    decision: str
    rationale: str
    ts: str
    hash: str


class AuditOut(BaseModel):
    plan_id: str
    verified: bool  # ¿la cadena verifica de punta a punta?
    decisions: list[DecisionOut]
