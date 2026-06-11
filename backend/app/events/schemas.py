"""Schemas Pydantic del módulo de eventos."""

from __future__ import annotations

import datetime
import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

_E164 = re.compile(r"^\+\d{8,15}$")
_PAIS = re.compile(r"^\+\d{1,4}$")


class RegistrationCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=160)
    email: EmailStr
    telefono: str = Field(min_length=6, max_length=20)
    telefono_pais: str = Field(default="+593", max_length=5)
    documento: str = Field(min_length=8, max_length=20)
    empresa: str = Field(min_length=1, max_length=200)
    # Calculado en el validador a partir de telefono + telefono_pais.
    telefono_e164: str = Field(default="", exclude=True)

    @field_validator("documento")
    @classmethod
    def _validate_documento(cls, v: str) -> str:
        digits = re.sub(r"\D", "", v)
        if len(digits) not in (10, 13):
            raise ValueError("La cédula debe tener 10 dígitos o el RUC 13 dígitos.")
        return digits

    @field_validator("telefono_pais")
    @classmethod
    def _validate_pais(cls, v: str) -> str:
        v = v.strip()
        if not _PAIS.match(v):
            raise ValueError("Código de país inválido (ej. +593).")
        return v

    @model_validator(mode="after")
    def _normalize_phone(self) -> "RegistrationCreate":
        local = re.sub(r"\D", "", self.telefono).lstrip("0")
        pais = self.telefono_pais.lstrip("+")
        e164 = f"+{pais}{local}"
        if not _E164.match(e164):
            raise ValueError("Número de teléfono inválido.")
        self.telefono_e164 = e164
        return self


class RegistrationResponse(BaseModel):
    ok: bool
    estado: str
    ya_inscrito: bool
    mensaje: str


class RegistrationOut(BaseModel):
    id: int
    event_slug: str
    nombre: str
    email: str
    telefono_e164: str
    documento: str
    empresa: str
    estado: str
    email_enviado: bool
    aviso_interno_enviado: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
