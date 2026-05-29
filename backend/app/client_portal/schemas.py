"""Schemas Pydantic del portal cliente."""

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class ClientLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    password_reset_required: bool


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)


class ClientMeResponse(BaseModel):
    email: EmailStr
    client_id: int | None
    organization_id: int | None
    password_reset_required: bool


class SlotOut(BaseModel):
    name: str
    mimes_allowed: list[str]
    required: bool
    multi: bool


class ToolOut(BaseModel):
    code: str
    label: str
    description: str
    category: str
    slots: list[SlotOut]


class CategoryOut(BaseModel):
    id: str
    label: str
    tools: list[ToolOut]


class ClientCatalogResponse(BaseModel):
    categories: list[CategoryOut]
