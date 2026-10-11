"""Validador de coherencia SRI — endpoint del portal del cliente (Fase 9).

El cliente sube sus F-101/F-103/F-104 y recibe un reporte de cruces ANTES de
generar el ICT. **No crea sesión ICT, no genera Excel y no toca el flujo ICT.**
Reutiliza el Motor de Ingesta (`ingerir`, que delega en los parsers del ICT en
solo lectura) y la lógica de cruces (`validador_sri.validar_coherencia`).

Acceso: rol `client` vía `require_client_with_device` (la misma dependencia que
el resto del portal; refresca el heartbeat de sesión y valida el dispositivo).
Es stateless: no escribe nada en disco ni en la base.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.app.auth.deps import require_client_with_device
from backend.app.auth.models import User
from backend.app.ingesta import ingerir
from backend.app.ingesta.validador_sri import ReporteCoherencia, validar_coherencia

router = APIRouter(prefix="/client/validador-sri", tags=["client-validador-sri"])

# Mismo tope por archivo que el resto del portal cliente (client_portal/router).
_MAX_BYTES = 50 * 1024 * 1024
_MAX_MENSUALES = 12


async def _leer(file: UploadFile) -> bytes:
    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail=f"Archivo vacío: {file.filename}.")
    if len(contenido) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail=f"{file.filename} supera 50 MB.")
    return contenido


@router.post("/coherencia", response_model=ReporteCoherencia)
async def coherencia(
    f101: UploadFile = File(...),
    f103: list[UploadFile] = File(default=[]),
    f104: list[UploadFile] = File(default=[]),
    user: User = Depends(require_client_with_device),
) -> ReporteCoherencia:
    """Ingiere los formularios y devuelve el reporte de cruces (sin generar ICT)."""
    if len(f103) > _MAX_MENSUALES or len(f104) > _MAX_MENSUALES:
        raise HTTPException(
            status_code=400,
            detail=f"Máximo {_MAX_MENSUALES} archivos mensuales por formulario.",
        )

    datasets = [ingerir(f101.filename or "F101.pdf", await _leer(f101), tipo_declarado="f101")]
    for f in f103:
        datasets.append(ingerir(f.filename or "F103.pdf", await _leer(f), tipo_declarado="f103"))
    for f in f104:
        datasets.append(ingerir(f.filename or "F104.pdf", await _leer(f), tipo_declarado="f104"))

    return validar_coherencia(datasets)
