"""Schemas Pydantic de los endpoints de cuentas de Automatizaciones (Tarea 6)."""

from __future__ import annotations

import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from backend.app.client_portal.tool_registry import TOOLS

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CuentaCreate(BaseModel):
    client_id: int
    herramienta: str = Field(max_length=32)
    empresa_nombre: Nombre
    admin_nombre: Nombre
    admin_email: EmailStr
    vigencia_hasta: datetime.date | None = None

    @field_validator("herramienta")
    @classmethod
    def _herramienta_de_automatizaciones(cls, v: str) -> str:
        tool = TOOLS.get(v)
        if tool is None or tool.category != "AUTOMATIZACIONES":
            raise ValueError(f"«{v}» no es una herramienta de Automatizaciones válida.")
        return v

    @field_validator("vigencia_hasta")
    @classmethod
    def _vigencia_no_pasada(cls, v: datetime.date | None) -> datetime.date | None:
        if v is not None and v < datetime.date.today():
            raise ValueError("La vigencia no puede ser una fecha pasada.")
        return v


class CuentaOut(BaseModel):
    id: int
    client_id: int
    client_nombre: str
    herramienta: str
    herramienta_label: str
    empresa_nombre: str
    empresa_id_app: str | None
    admin_email: str
    admin_nombre: str
    estado: str
    vencida: bool
    vigencia_hasta: datetime.date | None
    creado_por: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
