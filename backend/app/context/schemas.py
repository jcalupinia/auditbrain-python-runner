"""Schemas Pydantic del contexto operativo."""

import datetime

from pydantic import BaseModel, Field


class OrganizationOut(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    tax_id: str | None = Field(default=None, max_length=64)
    sector: str | None = Field(default=None, max_length=120)


class ClientOut(BaseModel):
    id: int
    organization_id: int
    name: str
    tax_id: str | None
    sector: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class ProjectCreate(BaseModel):
    client_id: int
    name: str = Field(min_length=1, max_length=200)
    module_code: str | None = Field(default=None, max_length=8)
    period_label: str | None = Field(default=None, max_length=64)
    period_start: datetime.date | None = None
    period_end: datetime.date | None = None


class ProjectOut(BaseModel):
    id: int
    organization_id: int
    client_id: int
    name: str
    module_code: str | None
    period_label: str | None
    period_start: datetime.date | None
    period_end: datetime.date | None
    is_active: bool

    model_config = {"from_attributes": True}


class ProjectMemberAdd(BaseModel):
    user_id: int
    project_role: str = Field(default="member", max_length=24)


class ProjectMemberOut(BaseModel):
    id: int
    project_id: int
    user_id: int
    project_role: str

    model_config = {"from_attributes": True}


class ContextOut(BaseModel):
    """Estado de contexto del usuario actual."""

    organization: OrganizationOut | None
    active_project: ProjectOut | None
    active_client: ClientOut | None
    projects: list[ProjectOut]


class SetActiveContext(BaseModel):
    project_id: int | None = None
