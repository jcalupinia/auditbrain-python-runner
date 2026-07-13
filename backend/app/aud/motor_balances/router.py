"""Endpoints HTTP del Motor de balances (AUD, staff)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.client_portal.flujo import catalogos, motor_balances

router = APIRouter(prefix="/aud/motor-balances", tags=["aud-motor-balances"])


@router.post("/homologar")
async def homologar(archivos: list[UploadFile] = File(...),
                    _user: User = Depends(require_staff)) -> dict:
    leidos = [(f.filename or "", await f.read()) for f in archivos]
    return motor_balances.homologar_archivos(leidos)


class RecalcularBody(BaseModel):
    esf: dict
    eri: dict


class EstadosBody(BaseModel):
    esf: dict
    eri: dict


@router.post("/recalcular")
def recalcular(body: RecalcularBody, _user: User = Depends(require_staff)) -> dict:
    return motor_balances.recalcular_homologado(body.esf, body.eri)


@router.post("/estados")
def estados(body: EstadosBody, _user: User = Depends(require_staff)) -> dict:
    return motor_balances.estados_superintendencia(body.esf, body.eri)


@router.get("/plan")
def plan(_user: User = Depends(require_staff)) -> dict:
    return catalogos.cargar_mapa_super_sri()
