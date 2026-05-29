"""Schemas Pydantic del portal cliente."""

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
