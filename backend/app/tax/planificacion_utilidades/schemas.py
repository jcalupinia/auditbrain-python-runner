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
    anios_detectados: list[int] = Field(default_factory=list)
    # Etiquetas (fechas de corte) por estado — pueden diferir entre ESF y ER.
    labels_esf: list[str] = Field(default_factory=list)
    labels_er: list[str] = Field(default_factory=list)
    # Detalle por cuenta-hoja (drill-down). Cada item:
    # {sec, key (rubro), codigo, nombre, vals:[por período]}.
    detalle: list[dict] = Field(default_factory=list)
    # Comparaciones período-a-período (extractor resumido por nombre). Sin estos
    # campos declarados, response_model=ExtractResponse los FILTRA de la respuesta
    # y el dashboard nunca los recibe.
    comparaciones: dict = Field(
        default_factory=dict,
        description="Pares período-a-período: {esf:[[actual,anterior],...], eri:[...]}.",
    )
    periodos_esf: list[dict] = Field(
        default_factory=list,
        description="Períodos del ESF: [{label, tipo, meses, anio}, ...].",
    )
    periodos_eri: list[dict] = Field(
        default_factory=list,
        description="Períodos del ERI: [{label, tipo, meses, anio}, ...].",
    )


class CtrlYear(BaseModel):
    g: float = 0.0
    div: float = 0.0
    cap: float = 0.0


class ExportRequest(BaseModel):
    """Modelo actual del frontend para exportar a Excel con fórmulas nativas."""

    data: dict[str, list[float | None]]
    ctrl: list[CtrlYear] = Field(default_factory=list)
    params: dict[str, str | float] = Field(default_factory=dict)


class DashboardXlsxRequest(BaseModel):
    """Genera un .xlsx con gráficos NATIVOS de Excel (openpyxl) ligados a las
    celdas de datos. Al editar los datos en Excel, los gráficos se actualizan
    solos. El frontend arma el modelo D; el backend solo arma el libro."""

    data: dict[str, list[float | None]]
    labels: list[str] = Field(default_factory=list)
    meses: list[int] = Field(default_factory=list)
    empresa: str = "Empresa"
    chart_style: str = Field(
        default="combo", description="barras | lineas | area | combo"
    )


class SriRucResponse(BaseModel):
    """Datos del contribuyente devueltos por el SRI (consulta por RUC)."""

    ruc: str | None = None
    razon_social: str | None = None
    actividad: str | None = None
    estado: str | None = None
    tipo: str | None = None
    regimen: str | None = None
    ciiu: str | None = None
    fuente: str | None = None


class PresentacionRequest(BaseModel):
    """Genera una presentación ejecutiva (Canva via MCP) para gerencia/accionistas.

    El contenido (cifras, narrativa, matriz de escenarios) lo arma el frontend,
    que es donde vive el motor de cálculo. El backend solo orquesta Canva.
    """

    content: dict = Field(description="Contenido ejecutivo estructurado del deck.")
    audience: str = Field(default="Gerencia General y Accionistas")
    brand_kit_id: str | None = Field(default=None, description="ID del Brand Kit de Canva.")
    style: str | None = Field(default=None, description="Directrices visuales si no hay brand kit.")
    export_formats: list[str] = Field(default_factory=lambda: ["pdf", "pptx"])
    slides: int = Field(default=11, ge=6, le=20)


class RecomendacionRequest(BaseModel):
    """Cifras deterministas (del frontend) para que la IA redacte la recomendación."""

    empresa: str = ""
    recomendado: str = Field(description="clave del escenario óptimo: sin|div|mix|cap")
    comparacion: dict = Field(description="resultado de compareScenarios (4 escenarios)")


class RecomendacionResponse(BaseModel):
    """Narrativa del agente con los controles de IA obligatorios."""

    narrativa: str
    confianza_modelo: str = Field(default="media", description="alta|media|baja")
    requiere_revision_humana: bool = True


class PresentacionResponse(BaseModel):
    status: str
    design_id: str | None = None
    edit_url: str | None = None
    view_url: str | None = None
    title: str | None = None
    page_count: int | None = None
    exports: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
