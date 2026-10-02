"""API v1 del Motor de Ingesta y Normalización (Fase 7).

Expone el motor transversal (clasificación → extracción determinista →
normalización → confianza) por HTTP, con subida de archivos. Reutiliza
`backend/app/ingesta` sin modificar nada de las fases anteriores.

Acceso: admin (JWT) o X-API-Key (server-to-server), igual que `/python` y
`/router` (``require_runner_access``). Determinístico primero: el OCR y la IA
no se disparan salvo que haga falta / se pidan.
"""
# Sin `from __future__ import annotations`: los modelos de respuesta
# (IngerirResponse) referencian DatasetNormalizado/ItemRevision como tipos
# reales para que Pydantic los resuelva al definir la clase (si fueran strings
# diferidas requeriría model_rebuild()).
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.app.auth.deps import require_runner_access
from backend.app.ingesta import (
    DatasetNormalizado,
    ItemRevision,
    ResultadoClasificacion,
    TipoDocumento,
    clasificar_documento,
    cola_de_revision,
    ingerir,
)

router = APIRouter(
    prefix="/ingesta",
    tags=["ingesta"],
    dependencies=[Depends(require_runner_access)],
)

# Tamaño máximo del archivo aceptado (MB). Barrera simple contra abusos.
_MAX_MB = 25


class TiposResponse(BaseModel):
    tipos: list[str]
    nota: str


class IngerirResponse(BaseModel):
    dataset: DatasetNormalizado
    cola_revision: list[ItemRevision]


async def _leer(file: UploadFile) -> bytes:
    contenido = await file.read()
    if not contenido:
        raise HTTPException(status_code=400, detail="Archivo vacío.")
    if len(contenido) > _MAX_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413, detail=f"Archivo supera el límite de {_MAX_MB} MB."
        )
    return contenido


@router.get("/tipos", response_model=TiposResponse)
def tipos() -> TiposResponse:
    """Lista los tipos de documento que el clasificador reconoce."""
    return TiposResponse(
        tipos=[t.value for t in TipoDocumento],
        nota=(
            "El tipo se puede declarar en 'tipo_declarado' (manda) o se detecta "
            "automáticamente por firma de contenido y nombre del archivo."
        ),
    )


@router.post("/clasificar", response_model=ResultadoClasificacion)
async def clasificar(
    file: UploadFile = File(...),
    tipo_declarado: Optional[str] = Form(default=None),
) -> ResultadoClasificacion:
    """Clasifica el documento sin extraer (determinista, barato)."""
    contenido = await _leer(file)
    return clasificar_documento(
        file.filename or "documento",
        contenido=contenido,
        tipo_declarado=tipo_declarado,
    )


@router.post("/ingerir", response_model=IngerirResponse)
async def ingerir_endpoint(
    file: UploadFile = File(...),
    tipo_declarado: Optional[str] = Form(default=None),
    ocr: bool = Form(default=True),
    consolidar: bool = Form(default=True),
) -> IngerirResponse:
    """Ingiere el documento y devuelve el dataset normalizado + cola de revisión.

    La IA (AI Semantic Resolver) NO se dispara aquí: es un paso aparte y opcional.
    """
    contenido = await _leer(file)
    ds = ingerir(
        file.filename or "documento",
        contenido,
        tipo_declarado=tipo_declarado,
        ocr=ocr,
        consolidar=consolidar,
    )
    return IngerirResponse(dataset=ds, cola_revision=cola_de_revision([ds]))
