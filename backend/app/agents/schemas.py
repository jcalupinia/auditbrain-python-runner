"""Schemas Pydantic de agentes y runs."""

import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentInputSchema(BaseModel):
    name: str
    label: str
    kind: str
    required: bool
    options: list[str] = []
    placeholder: str = ""


class AgentOut(BaseModel):
    code: str
    module_code: str
    label: str
    description: str
    inputs: list[AgentInputSchema]
    output_hint: str = ""


class AgentRunCreate(BaseModel):
    project_id: int | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)


class AgentRunOut(BaseModel):
    id: int
    organization_id: int
    user_id: int
    project_id: int | None
    agent_code: str
    module_code: str | None
    status: str
    inputs: dict[str, Any] | None
    output: str | None
    error: str | None
    model: str | None
    tokens_in: int | None
    tokens_out: int | None
    created_at: datetime.datetime
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None

    model_config = {"from_attributes": True}
