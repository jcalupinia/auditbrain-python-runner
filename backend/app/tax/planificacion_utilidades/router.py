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
from backend.app.tax.planificacion_utilidades.schemas import (
    ExportRequest,
    ExtractResponse,
    PresentacionRequest,
    PresentacionResponse,
)
from backend.app.utils import canva_mcp

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


_DECK_INSTRUCTIONS = (
    "Crea una PRESENTACIÓN EJECUTIVA PREMIUM en español para Gerencia General y "
    "Accionistas sobre planificación del pago a cuenta de utilidades no "
    "distribuidas (Ecuador). Audiencia no técnica: prioriza claridad y narrativa "
    "de negocio sobre tecnicismos.\n"
    "Estructura sugerida (~{slides} slides):\n"
    "1) Portada (empresa, RUC, representante, fecha).\n"
    "2) Resumen ejecutivo con los KPIs clave (números grandes y legibles).\n"
    "3) El problema: por qué nace la obligación y cuánto cuesta no actuar.\n"
    "4) Diagnóstico financiero (1 slide, con gráfico de indicadores).\n"
    "5) Diagnóstico tributario y societario.\n"
    "6) Las 4 alternativas antes del 31 de julio.\n"
    "7) Matriz de decisión: tabla comparativa de los 4 escenarios (pago, crédito "
    "recuperable, costo muerto, patrimonio) con gráfico de barras del pago por "
    "escenario.\n"
    "8) Recomendación y ahorro (destácalo visualmente).\n"
    "9) Modelación 2026–2028 (gráfico de pago/crédito/riesgo por año).\n"
    "10) Plan de acción con responsables y plazos.\n"
    "11) Cierre/contacto.\n"
    "Requisitos visuales: incluye GRÁFICOS (barras/líneas) y, donde aporte, un "
    "mini-dashboard de KPIs; usa imágenes/íconos corporativos sobrios; storytelling "
    "claro (problema → diagnóstico → escenarios → recomendación → plan). "
    "Mantén consistencia de marca. Exporta en los formatos pedidos y devuelve el "
    "JSON con design_id, edit_url, view_url, page_count y exports."
)


@router.post("/presentacion", response_model=PresentacionResponse)
def presentacion_endpoint(
    body: PresentacionRequest,
    current: User = Depends(get_current_user),
):
    """Genera una presentación ejecutiva (Canva via MCP). Requiere JWT.

    La API Key nunca se expone al navegador: este endpoint usa el token JWT del
    usuario y orquesta Canva en el servidor.
    """
    emp = str(body.content.get("empresa", "la Compañía")) or "la Compañía"
    topic = (
        f"Planificación tributaria sobre utilidades no distribuidas — {emp}"
    )
    style = body.style or (
        "Estética AuditBrain aprobada (referencia PoC): tema OSCURO premium y "
        "minimalista, tipografía DM Sans, texto claro sobre fondos oscuros, "
        "KPIs con números grandes y legibles, mucho espacio en blanco, acentos "
        "en Gold #C7A83C sobre Deep Blue #071B2F / Navy #0A2342. Look ejecutivo "
        "de agencia, sobrio y elegante; jerarquía visual clara."
    )
    extra = _DECK_INSTRUCTIONS.format(slides=body.slides)
    try:
        result = canva_mcp.generate_design(
            topic=topic,
            design_type="presentation",
            audience=body.audience,
            style=style,
            content=body.content,
            brand_kit_id=body.brand_kit_id,
            export_formats=body.export_formats,
            extra_instructions=extra,
        )
    except canva_mcp.CanvaMCPUnavailable as exc:
        raise HTTPException(
            503,
            detail=(
                "Canva no está configurado en el servidor "
                f"(falta token/credenciales). {exc}"
            ),
        ) from exc
    except canva_mcp.CanvaMCPError as exc:
        raise HTTPException(502, detail=f"Error generando la presentación: {exc}") from exc

    return PresentacionResponse(
        status="ok" if result.design_id else "partial",
        design_id=result.design_id,
        edit_url=result.edit_url,
        view_url=result.view_url,
        title=result.title,
        page_count=result.page_count,
        exports=result.exports,
        warnings=result.warnings,
    )
