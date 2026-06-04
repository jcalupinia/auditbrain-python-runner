"""Pydantic schemas for the ICT audit subsystem.

These models are the contract between data computation (metrics.py,
interpreter.py) and presentation (fillers/). They are also the public
JSON shape sent to the frontend.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Status(str, Enum):
    """Visual status for a metric or an anexo."""

    OK = "ok"
    REVISAR = "revisar"
    CRITICO = "critico"
    NA = "na"


class A1Metrics(BaseModel):
    """Quantitative metrics for the A1 mapeo balance sheet."""

    activo_total: Decimal
    pasivo_patrimonio_total: Decimal
    diferencia: Decimal
    status_cuadre: Status
    cobertura_mapeo_pct: float = Field(ge=0, le=100)
    cas_mapeados: int = Field(ge=0)
    cas_total: int = Field(ge=0)
    cas_sin_contrapartida: list[str] = Field(default_factory=list)


class AnexoStatus(BaseModel):
    """Status snapshot for one of the 9 anexos."""

    codigo: str
    nombre: str
    status: Status
    observacion_corta: str = Field(max_length=120)
    monto_principal: Optional[Decimal] = None


class AnexosMetrics(BaseModel):
    """Aggregate metrics across all 9 anexos."""

    anexos: list[AnexoStatus]
    resumen_global: dict[Status, int]


SeverityLevel = Literal["critico", "material", "leve", "informativo"]

FindingCategoria = Literal[
    "subdeclaracion_ventas", "sobredeclaracion_ventas",
    "gasto_no_deducible", "depreciacion_irregular",
    "credito_iva_irrecuperable", "retencion_inconsistente",
    "impuesto_a_pagar_anomalo", "exportacion_sin_respaldo",
    "inventario_variacion_atipica", "beneficio_mal_aplicado",
    "conciliacion_inconsistente", "otra",
]


class AnexoFinding(BaseModel):
    """A single audit finding identified by the LLM interpreter."""

    severity: SeverityLevel
    categoria: FindingCategoria
    titulo: str = Field(max_length=120)
    descripcion_tecnica: str
    implicacion_tributaria: str
    recomendacion: str
    monto_disputa: Optional[Decimal] = None
    casilleros_afectados: list[str] = Field(default_factory=list)


class AnexoInterpretation(BaseModel):
    """LLM-generated interpretation of an anexo's status."""

    anexo_codigo: str
    anexo_nombre: str
    resumen_ejecutivo: str = Field(max_length=500)
    findings: list[AnexoFinding] = Field(default_factory=list)
    confianza_modelo: Literal["alta", "media", "baja"]
    requiere_revision_humana: bool
    timestamp_analisis: datetime
    modelo_usado: str
    tokens_consumidos: int = Field(ge=0)
