"""Endpoints del agente guía «NIIF Piloto» en la plataforma AUDIT-IA.

Un solo router para TODAS las pruebas NIIF: la plataforma pregunta qué pruebas hay,
qué datos necesita cada una, y ejecuta la prueba con los datos del cliente para
descargar el papel de trabajo en cualquier formato. Toda la lógica vive en el
servicio ``piloto`` (misma fuente de verdad que la CLI). Permisos: ``require_staff``,
igual que el resto del módulo AUD.
"""
from __future__ import annotations

import io
import zipfile

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.app.aud.niif import piloto
from backend.app.aud.niif.procesadores import libro
from backend.app.auth.deps import require_staff
from backend.app.auth.models import User

router = APIRouter(prefix="/aud/niif/piloto", tags=["aud-niif-piloto"])


class EjecutarIn(BaseModel):
    corte: str = Field(..., description="Fecha de corte de la prueba (AAAA-MM-DD).")
    datasets: dict = Field(default_factory=dict, description="{anexo: [fila, ...]} con los datos del cliente.")
    parametros: dict = Field(default_factory=dict, description="Parámetros del auditor (sobre los del defecto).")
    encargo: dict | None = Field(default=None, description="Datos del encargo: client, ruc, framework, preparer, reviewer.")


@router.get("/pruebas")
def pruebas(user: User = Depends(require_staff)) -> dict:
    """Todas las pruebas disponibles (id, rubro, marcos, datasets, si trae ejemplo)."""
    return {"pruebas": piloto.listar()}


@router.get("/pruebas/{prueba_id}/requisitos")
def requisitos(prueba_id: str, user: User = Depends(require_staff)) -> dict:
    """Qué datos necesita una prueba: datasets con columnas, parámetros y requerimientos."""
    try:
        return piloto.requisitos(prueba_id)
    except piloto.PruebaDesconocida as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/pruebas/{prueba_id}/plantilla")
def plantilla(prueba_id: str, user: User = Depends(require_staff)) -> dict:
    """El ejemplo realista {corte, parametros, datasets} para precargar un molde."""
    try:
        molde = piloto.plantilla(prueba_id)
    except piloto.PruebaDesconocida as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    if molde is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="La prueba no trae ejemplo de manifiesto.")
    return molde


def _preparar(prueba_id: str, body: EjecutarIn):
    try:
        return piloto.preparar(prueba_id, body.datasets, body.parametros, body.corte, body.encargo)
    except piloto.PruebaDesconocida as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:  # noqa: BLE001 — el procesador rechaza datos inválidos con mensaje claro
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"El procesador no pudo calcular: {e}")


@router.post("/pruebas/{prueba_id}/ejecutar")
def ejecutar(prueba_id: str, body: EjecutarIn, formato: str = "json", user: User = Depends(require_staff)) -> Response:
    """Ejecuta la prueba con los datos del cliente.

    - ``formato=json`` (defecto): metadata + resultado + verificación del Excel (que reabre sin «reparaciones»).
    - ``formato=xlsx|html|docx|pptx|pdf``: descarga ese papel.
    - ``formato=zip``: descarga todos los formatos disponibles en un ZIP.
    """
    from fastapi.responses import JSONResponse

    d, reg = _preparar(prueba_id, body)

    if formato == "json":
        try:
            verificacion = piloto.verificar_excel(piloto.papel(d, reg, "xlsx"))
        except libro.PDFNoDisponible as e:  # xlsx nunca la lanza, pero por robustez
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
        return JSONResponse({"id": prueba_id, "corte": body.corte,
                             "resultado": piloto.resumen_run(reg), "verificacion_excel": verificacion})

    if formato == "zip":
        buffer = io.BytesIO()
        omitidos = []
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for ext, _fn, _etq, _mime in piloto.FORMATOS:
                try:
                    zf.writestr(f"{prueba_id}.{ext}", piloto.papel(d, reg, ext))
                except libro.PDFNoDisponible:
                    omitidos.append(ext)
        headers = {"Content-Disposition": f'attachment; filename="{prueba_id}_papeles.zip"'}
        if omitidos:
            headers["X-Formatos-Omitidos"] = ",".join(omitidos)
        return Response(buffer.getvalue(), media_type="application/zip", headers=headers)

    if formato not in piloto.TIPOS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"Formato no disponible: {formato}.")
    try:
        contenido = piloto.papel(d, reg, formato)
    except libro.PDFNoDisponible as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    return Response(contenido, media_type=piloto.TIPOS[formato],
                    headers={"Content-Disposition": f'attachment; filename="{prueba_id}.{formato}"'})
