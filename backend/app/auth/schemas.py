"""Schemas Pydantic para auth."""

from pydantic import BaseModel, EmailStr, Field

from backend.app.auth.models import Role


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.user


class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: Role
    is_active: bool

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
