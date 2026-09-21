"""Permiso firmado para el Motor de Auditoría Analítica (AUD, staff).

El motor corre en el servidor propio y el navegador le envía los datos
directamente (formulario AUT-2026-001, decisión X.2). Este endpoint solo
emite un permiso de vida corta firmado con MOTOR_TOKEN_SECRET, distinto
del secreto de sesiones del portal.
"""
from __future__ import annotations

import datetime
import os
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User

router = APIRouter(prefix="/aud/motor-analitico", tags=["aud-motor-analitico"])
VIDA_SEG = 300


class PermisoBody(BaseModel):
    encargo: str = Field(min_length=1, max_length=120)
    accion: Literal["leer", "ejecutar"]

    @field_validator("encargo")
    @classmethod
    def _encargo_no_vacio(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("encargo no puede estar vacío.")
        return v


@router.post("/permiso")
def emitir_permiso(body: PermisoBody, user: User = Depends(require_staff)) -> dict:
    secreto = os.getenv("MOTOR_TOKEN_SECRET", "").strip()
    url = os.getenv("MOTOR_ANALITICO_URL", "").strip().rstrip("/")
    if len(secreto) < 32 or not url:
        raise HTTPException(status_code=503,
                            detail="El Motor de Auditoría Analítica no está configurado.")
    ahora = datetime.datetime.now(datetime.timezone.utc)
    token = jwt.encode({
        "sub": user.email,
        "role": user.role.value,
        "encargo": body.encargo,
        "accion": body.accion,
        "aud": "motor-analitico",
        "iat": ahora,
        "exp": ahora + datetime.timedelta(seconds=VIDA_SEG),
    }, secreto, algorithm="HS256")
    return {"token": token, "url": url, "expira_en": VIDA_SEG}
