"""Endpoints HTTP de TAX.PLANIFICACION_UTILIDADES (ingesta + exportación).

Stateless: no hay jobs ni base de datos. El frontend mantiene el estado y
recalcula en vivo; aquí solo parseamos archivos y armamos el Excel.
"""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse

from backend.app.auth.deps import get_current_user
from backend.app.auth.models import User
from backend.app.core.config import settings
from backend.app.tax.planificacion_utilidades import exporter
from backend.app.tax.planificacion_utilidades.parsers import (
    balance_resumido,
    f101,
)
from backend.app.tax.planificacion_utilidades import pptx_builder
import json
import urllib.request

from backend.app.tax.planificacion_utilidades.schemas import (
    ExportRequest,
    ExtractResponse,
    PresentacionRequest,
    SriRucResponse,
)

router = APIRouter(
    prefix="/tax/planificacion-utilidades",
    tags=["tax-planificacion-utilidades"],
)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_ALLOWED = {
    "f101": {"application/pdf"},
    "resumido": {XLSX_MIME, "application/vnd.ms-excel"},
}


@router.post("/extract", response_model=ExtractResponse)
async def extract_endpoint(
    kind: str = Form(...),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
):
    if kind not in _ALLOWED:
        raise HTTPException(400, detail="kind debe ser 'f101' o 'resumido'.")
    allowed = _ALLOWED[kind]
    if file.content_type and file.content_type not in allowed:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Tipo {file.content_type} no permitido para {kind}.",
        )
    data = await file.read()
    max_bytes = settings.AUD_OF_MAX_FILE_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archivo excede {settings.AUD_OF_MAX_FILE_MB} MB.",
        )
    if not data:
        raise HTTPException(400, detail="Archivo vacío.")

    if kind == "f101":
        result = f101.extract_f101(data)
    else:
        result = balance_resumido.extract_balance_resumido(data)
    return ExtractResponse(**result)


@router.post("/export")
def export_endpoint(
    body: ExportRequest,
    current: User = Depends(get_current_user),
):
    ctrl = [c.model_dump() for c in body.ctrl]
    xlsx = exporter.build_workbook(body.data, ctrl, body.params)
    empresa = str(body.params.get("empresa", "cliente")) or "cliente"
    safe = empresa.replace(" ", "_").replace("/", "_")
    filename = f"Planificacion_Utilidades_{safe}.xlsx"
    return StreamingResponse(
        BytesIO(xlsx),
        media_type=XLSX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_SRI_URL = (
    "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/"
    "rest/ConsolidadoContribuyente/obtenerPorNumerosRuc?ruc="
)


@router.get("/sri/{ruc}", response_model=SriRucResponse)
def consultar_sri(ruc: str, current: User = Depends(get_current_user)):
    """Consulta el SRI (oficial, sin captcha) y devuelve razón social + actividad.

    Se usa para auto-poblar el cliente y sugerir el sector (CIIU) del que sale la
    tasa de crecimiento sectorial cuando el histórico no crece.
    """
    digits = "".join(ch for ch in (ruc or "") if ch.isdigit())
    if len(digits) != 13:
        raise HTTPException(400, "RUC inválido (deben ser 13 dígitos).")
    try:
        req = urllib.request.Request(
            _SRI_URL + digits, headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"No se pudo consultar el SRI: {exc}") from exc
    if not data:
        raise HTTPException(404, "RUC no encontrado en el SRI.")
    c = data[0] if isinstance(data, list) else data
    return SriRucResponse(
        ruc=c.get("numeroRuc"),
        razon_social=c.get("razonSocial"),
        actividad=c.get("actividadEconomicaPrincipal"),
        estado=c.get("estadoContribuyenteRuc"),
        tipo=c.get("tipoContribuyente"),
        regimen=c.get("regimen"),
    )


@router.get("/plantilla")
def plantilla_endpoint(current: User = Depends(get_current_user)):
    xlsx = exporter.build_plantilla()
    return StreamingResponse(
        BytesIO(xlsx),
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": 'attachment; filename="Balance_resumido_plantilla.xlsx"'
        },
    )


PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)


@router.post("/presentacion")
def presentacion_endpoint(
    body: PresentacionRequest,
    current: User = Depends(get_current_user),
):
    """Genera la presentación ejecutiva (.pptx) premium. Requiere JWT.

    Se construye en el servidor con python-pptx replicando la estética aprobada
    (tema oscuro, DM Sans, KPIs grandes). No depende de servicios externos.
    """
    try:
        pptx = pptx_builder.build_deck(body.content)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, detail=f"Error generando la presentación: {exc}") from exc

    empresa = str(body.content.get("empresa", "cliente")) or "cliente"
    safe = empresa.replace(" ", "_").replace("/", "_")
    filename = f"Presentacion_Utilidades_{safe}.pptx"
    return StreamingResponse(
        BytesIO(pptx),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
