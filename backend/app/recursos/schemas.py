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


class OlvideIn(BaseModel):
    email: EmailStr


class IngresarIn(BaseModel):
    email: EmailStr
    clave: str = Field(min_length=1, max_length=128)


class LeadResponse(BaseModel):
    ok: bool
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


class CuentaOut(BaseModel):
    id: int
    email: str
    nombre: str
    empresa: str
    activo: bool
    accesos: list[str]
    ultimo_ingreso_at: datetime.datetime | None
    created_at: datetime.datetime
    consentimiento_at: datetime.datetime | None
    email_enviado: bool


class AccesosOut(BaseModel):
    ok: bool
    accesos: list[str]


class ResetClaveIn(BaseModel):
    # Clave que escribe el admin (se compara exacta). Ausente: se genera una.
    new_password: str | None = Field(default=None, min_length=8, max_length=72)
    enviar_correo: bool = False

    @field_validator("new_password")
    @classmethod
    def _limite_bcrypt(cls, v: str | None) -> str | None:
        # bcrypt solo usa los primeros 72 bytes: más largo, el resto se ignoraría.
        if v is not None and len(v.encode("utf-8")) > 72:
            raise ValueError("La clave no puede superar 72 bytes (las tildes y la ñ ocupan 2).")
        return v


class ResetClaveOut(BaseModel):
    email: str
    temp_password: str
    note: str = "Comparta esta clave con la persona por un canal seguro. No se vuelve a mostrar."


class ActivoIn(BaseModel):
    activo: bool


class ActivoOut(BaseModel):
    ok: bool
    activo: bool
