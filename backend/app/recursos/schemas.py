"""Schemas Pydantic de recursos gratuitos."""

from __future__ import annotations

import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=160)]
Empresa = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LeadCreate(BaseModel):
    nombre: Nombre
    empresa: Empresa
    email: EmailStr
    acepta_politica: bool
    # Campo trampa: invisible para personas; si llega con texto es un bot.
    website: str = Field(default="", max_length=200)

    @field_validator("acepta_politica")
    @classmethod
    def _debe_aceptar(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Debe aceptar la política de protección de datos.")
        return v


class ReenvioIn(BaseModel):
    email: EmailStr


class LeadResponse(BaseModel):
    ok: bool
    ya_registrado: bool
    mensaje: str


class MensajeOut(BaseModel):
    ok: bool
    mensaje: str


class AccesoOut(BaseModel):
    ok: bool
    nombre: str


class LeadOut(BaseModel):
    id: int
    recurso_slug: str
    nombre: str
    empresa: str
    email: str
    consentimiento_at: datetime.datetime
    consentimiento_version: str
    email_enviado: bool
    verificado_at: datetime.datetime | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
