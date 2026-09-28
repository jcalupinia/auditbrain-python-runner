"""Endpoints HTTP del Motor de balances (AUD, staff)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User
from backend.app.aud.motor_balances import analisis as analisis_estados
from backend.app.aud.motor_balances.papel_estados import (
    generar_html_estados, generar_papel_estados,
)
from backend.app.client_portal.flujo import catalogos, motor_balances

router = APIRouter(prefix="/aud/motor-balances", tags=["aud-motor-balances"])
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


class AnalisisBody(BaseModel):
    esf: dict
    eri: dict
    umbral_pct: float = 0.10


def _analisis(body: AnalisisBody) -> dict:
    homologado = motor_balances.estados_superintendencia(body.esf, body.eri)
    return analisis_estados.analizar(homologado, body.umbral_pct)


@router.post("/analisis")
def analisis(body: AnalisisBody, _user: User = Depends(require_staff)) -> dict:
    """Análisis de estados financieros (NIA 315/520): horizontal, vertical,
    ratios y expectativa vs. real, sobre los estados homologados."""
    return _analisis(body)


@router.post("/analisis/papel")
def analisis_papel(body: AnalisisBody, formato: str = "xlsx",
                   _user: User = Depends(require_staff)) -> Response:
    """Papel de trabajo del análisis de estados financieros. ``formato=xlsx``
    (fórmulas) o ``formato=html`` (autónomo, Excel embebido, imprimible a PDF)."""
    res = _analisis(body)
    if formato == "html":
        return Response(generar_html_estados(res), media_type="text/html; charset=utf-8")
    return Response(generar_papel_estados(res), media_type=_XLSX, headers={
        "Content-Disposition": 'attachment; filename="papel-estados-financieros.xlsx"'})


@router.get("/plan")
def plan(_user: User = Depends(require_staff)) -> dict:
    return catalogos.cargar_mapa_super_sri()
