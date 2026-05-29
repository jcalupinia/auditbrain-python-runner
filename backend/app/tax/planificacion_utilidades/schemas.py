"""Esquemas Pydantic de entrada/salida de TAX.PLANIFICACION_UTILIDADES."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExtractResponse(BaseModel):
    """Resultado de la ingesta (F-101 o balance resumido)."""

    data: dict[str, list[float | None]] = Field(
        description="Valores por clave ESF/ER: [2023, 2024, 2025] (None = sin dato)."
    )
    params: dict[str, str] = Field(
        default_factory=dict,
        description="Datos del cliente detectados (empresa, ruc, ...).",
    )
    warnings: list[str] = Field(default_factory=list)
    source: str = Field(description="'f101' | 'resumido'")
    casilleros_leidos: dict[str, float] = Field(
        default_factory=dict,
        description="Casilleros F-101 efectivamente leídos (auditoría humana).",
    )
    anio_detectado: int | None = None


class CtrlYear(BaseModel):
    g: float = 0.0
    div: float = 0.0
    cap: float = 0.0


class ExportRequest(BaseModel):
    """Modelo actual del frontend para exportar a Excel con fórmulas nativas."""

    data: dict[str, list[float | None]]
    ctrl: list[CtrlYear] = Field(default_factory=list)
    params: dict[str, str | float] = Field(default_factory=dict)
