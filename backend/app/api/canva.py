"""Endpoints REST para generación de designs Canva via MCP."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.security.api_key import require_api_key
from backend.app.utils import canva_mcp

log = logging.getLogger(__name__)

router = APIRouter(prefix="/canva", tags=["canva"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CanvaGenerateRequest(BaseModel):
    """Solicitud genérica de generación de design Canva."""
    topic: str = Field(..., description="Tema principal del design (ej. 'Reporte ejecutivo Q1 2026')")
    design_type: str = Field(
        default="report",
        description="Tipo de design Canva: report, proposal, doc, infographic, flyer, poster, etc.",
    )
    audience: str | None = Field(
        default=None,
        description="Audiencia objetivo (ej. 'Board of Directors')",
    )
    style: str | None = Field(
        default=None,
        description="Directrices visuales (ej. 'corporativo formal paleta sobria')",
    )
    content: dict | None = Field(
        default=None,
        description="Contenido estructurado a incluir en el design",
    )
    brand_kit_id: str | None = Field(
        default=None,
        description="ID del brand kit Canva a aplicar (opcional)",
    )
    export_formats: list[str] = Field(
        default_factory=lambda: ["pdf", "pptx"],
        description="Formatos a exportar. Valores: pdf, pptx, png, jpg",
    )
    extra_instructions: str | None = Field(
        default=None,
        description="Instrucciones adicionales para el modelo",
    )


class CanvaAuditReportRequest(BaseModel):
    """Atajo para reporte ejecutivo de auditoría."""
    client_name: str
    period: str = Field(..., description="Período auditado (ej. '2026', 'Q1 2026')")
    findings: list[dict] = Field(
        default_factory=list,
        description="Lista de hallazgos. Cada uno: {titulo, descripcion, riesgo, recomendacion}",
    )
    kpis: dict | None = Field(
        default=None,
        description="KPIs financieros (ej. {ingresos: '12.5M', ebitda_pct: 18})",
    )
    recommendations: list[str] = Field(default_factory=list)
    brand_kit_id: str | None = None


class CanvaResponse(BaseModel):
    """Respuesta normalizada de generación Canva."""
    status: str
    design_id: str | None = None
    edit_url: str | None = None
    view_url: str | None = None
    title: str | None = None
    page_count: int | None = None
    exports: dict[str, str] = Field(default_factory=dict)
    tokens_in: int | None = None
    tokens_out: int | None = None
    warnings: list[str] = Field(default_factory=list)
    error: str | None = None


class CanvaStatusResponse(BaseModel):
    """Estado del MCP de Canva."""
    available: bool
    engine: str = "anthropic-mcp-canva"
    model: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=CanvaStatusResponse)
async def status():
    """Verifica si el MCP de Canva está configurado y operativo."""
    import os

    available = canva_mcp.is_available()
    notes = None
    if not available:
        missing = []
        if not os.getenv("ANTHROPIC_API_KEY", "").strip():
            missing.append("ANTHROPIC_API_KEY")
        if not os.getenv("CANVA_MCP_OAUTH_TOKEN", "").strip():
            missing.append("CANVA_MCP_OAUTH_TOKEN")
        try:
            import anthropic  # noqa: F401
        except ImportError:
            missing.append("anthropic (pip)")
        notes = (
            "Variables/dependencias faltantes: " + ", ".join(missing)
            if missing
            else "MCP no inicializado por error desconocido."
        )
    return CanvaStatusResponse(
        available=available,
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        notes=notes,
    )


@router.post(
    "/generate",
    response_model=CanvaResponse,
    summary="Genera un design Canva genérico via MCP",
    description=(
        "Orquesta Claude API con MCP de Canva para crear un design en la "
        "cuenta del operador. Devuelve URLs editables y exports (PDF/PPTX)."
    ),
)
async def generate(
    body: CanvaGenerateRequest,
    _auth: None = Depends(require_api_key),
):
    try:
        result = canva_mcp.generate_design(
            topic=body.topic,
            design_type=body.design_type,
            audience=body.audience,
            style=body.style,
            content=body.content,
            brand_kit_id=body.brand_kit_id,
            export_formats=body.export_formats,
            extra_instructions=body.extra_instructions,
        )
    except canva_mcp.CanvaMCPUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except canva_mcp.CanvaMCPError as exc:
        return CanvaResponse(status="error", error=str(exc))

    return CanvaResponse(
        status="ok" if result.design_id else "partial",
        design_id=result.design_id,
        edit_url=result.edit_url,
        view_url=result.view_url,
        title=result.title,
        page_count=result.page_count,
        exports=result.exports,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        warnings=result.warnings,
    )


@router.post(
    "/audit-report",
    response_model=CanvaResponse,
    summary="Genera un reporte ejecutivo de auditoría",
    description=(
        "Atajo opinated: produce un reporte profesional para Board/Comité con "
        "hallazgos, KPIs y recomendaciones. Estructura estándar AuditBrain."
    ),
)
async def audit_report(
    body: CanvaAuditReportRequest,
    _auth: None = Depends(require_api_key),
):
    try:
        result = canva_mcp.generate_executive_audit_report(
            client_name=body.client_name,
            period=body.period,
            findings=body.findings,
            kpis=body.kpis,
            recommendations=body.recommendations,
            brand_kit_id=body.brand_kit_id,
        )
    except canva_mcp.CanvaMCPUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except canva_mcp.CanvaMCPError as exc:
        return CanvaResponse(status="error", error=str(exc))

    return CanvaResponse(
        status="ok" if result.design_id else "partial",
        design_id=result.design_id,
        edit_url=result.edit_url,
        view_url=result.view_url,
        title=result.title,
        page_count=result.page_count,
        exports=result.exports,
        tokens_in=result.tokens_in,
        tokens_out=result.tokens_out,
        warnings=result.warnings,
    )
