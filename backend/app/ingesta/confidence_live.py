"""Confidence Engine en vivo (Fase 5).

Consolida en un solo veredicto las señales de confianza que producen las etapas
anteriores (clasificación en Fase 2, extracción/adaptadores en Fase 2/4,
normalización en Fase 3) y arma la **cola de revisión**: qué campos y qué
datasets requieren intervención humana (o, en Fase 6, el AI Semantic Resolver).

No oculta la incertidumbre: si una proporción de campos queda dudosa
(`LOW`/`REVIEW_REQUIRED`) por encima del umbral, el dataset se marca
`review_required` aunque su calidad declarada fuera alta.

Es aditivo: no toca ningún flujo existente; se apoya solo en el contrato y en el
motor de confianza ya mergeados.
"""
from __future__ import annotations

from typing import Iterable, Optional

from pydantic import BaseModel, Field

from backend.app.ingesta.confidence import (
    NivelConfianza,
    clasificar_confianza,
    requiere_revision,
)
from backend.app.ingesta.contract import (
    CampoExtraido,
    DatasetNormalizado,
    ResultadoValidacion,
)

# Proporción de campos POR DEBAJO de HIGH (MEDIUM/LOW/REVIEW) a partir de la cual
# el dataset entero va a revisión. Nota: un solo campo LOW/REVIEW ya fuerza la
# revisión por el contrato (Fase 1); este umbral captura la señal que ESO no ve:
# un dataset mayormente MEDIUM (p. ej. muchos valores de OCR) que, campo a campo,
# no dispararía revisión pero en conjunto sí la amerita.
UMBRAL_PCT_DUDOSOS = 0.20

# Severidad de cada nivel (mayor = más revisión); para elegir el peor.
_ORDEN = {
    NivelConfianza.HIGH: 0,
    NivelConfianza.MEDIUM: 1,
    NivelConfianza.LOW: 2,
    NivelConfianza.REVIEW_REQUIRED: 3,
}


class ResumenConfianza(BaseModel):
    """Distribución y veredicto de confianza de un dataset."""

    total_campos: int = Field(ge=0)
    por_nivel: dict[NivelConfianza, int] = Field(default_factory=dict)
    dudosos: int = Field(ge=0)              # LOW + REVIEW_REQUIRED
    pct_dudosos: float = Field(ge=0.0, le=1.0)
    no_altos: int = Field(ge=0)             # todos los que NO son HIGH
    pct_no_altos: float = Field(ge=0.0, le=1.0)
    peor_nivel: NivelConfianza
    veredicto: NivelConfianza
    review_required: bool


class ItemRevision(BaseModel):
    """Una entrada de la cola de revisión (campo o dataset completo)."""

    dataset_id: str
    document_type: str
    field: Optional[str] = None            # None ⇒ el dataset completo
    confidence: NivelConfianza
    extraction_method: Optional[str] = None
    motivo: str
    source_file: Optional[str] = None


def _peor(niveles: Iterable[NivelConfianza], *, defecto: NivelConfianza) -> NivelConfianza:
    niveles = list(niveles)
    if not niveles:
        return defecto
    return max(niveles, key=lambda n: _ORDEN[n])


def resumen_confianza(
    ds: DatasetNormalizado,
    *,
    umbral_pct_dudosos: float = UMBRAL_PCT_DUDOSOS,
) -> ResumenConfianza:
    """Calcula la distribución de confianza y el veredicto del dataset.

    - Sin campos: el veredicto se deriva de ``quality_score``.
    - Con campos: el veredicto es el nivel MÁS severo presente (conservador);
      además, si la proporción de dudosos supera el umbral, exige revisión.
    """
    campos = ds.campos
    por_nivel: dict[NivelConfianza, int] = {}
    for c in campos:
        por_nivel[c.confidence] = por_nivel.get(c.confidence, 0) + 1

    total = len(campos)
    dudosos = por_nivel.get(NivelConfianza.LOW, 0) + por_nivel.get(
        NivelConfianza.REVIEW_REQUIRED, 0
    )
    pct = (dudosos / total) if total else 0.0
    no_altos = total - por_nivel.get(NivelConfianza.HIGH, 0)
    pct_no_altos = (no_altos / total) if total else 0.0

    nivel_calidad = clasificar_confianza(ds.quality_score)
    if total:
        peor = _peor((c.confidence for c in campos), defecto=nivel_calidad)
    else:
        peor = nivel_calidad

    review = (
        ds.review_required
        or requiere_revision(peor)
        or pct_no_altos > umbral_pct_dudosos
        or requiere_revision(nivel_calidad)
    )
    # El veredicto no puede ser mejor que lo que exige la revisión.
    veredicto = peor
    if review and not requiere_revision(veredicto):
        veredicto = NivelConfianza.LOW

    return ResumenConfianza(
        total_campos=total,
        por_nivel=por_nivel,
        dudosos=dudosos,
        pct_dudosos=round(pct, 4),
        no_altos=no_altos,
        pct_no_altos=round(pct_no_altos, 4),
        peor_nivel=peor,
        veredicto=veredicto,
        review_required=review,
    )


def consolidar_confianza(
    ds: DatasetNormalizado,
    *,
    umbral_pct_dudosos: float = UMBRAL_PCT_DUDOSOS,
) -> DatasetNormalizado:
    """Aplica el veredicto de confianza al dataset (en vivo).

    Marca ``review_required`` según el resumen, y deja constancia en
    ``validation_results`` y ``warnings`` de la distribución de confianza.
    Idempotente: no duplica el resultado de validación "confianza".
    """
    resumen = resumen_confianza(ds, umbral_pct_dudosos=umbral_pct_dudosos)
    if resumen.review_required:
        ds.review_required = True

    detalle = (
        f"veredicto={resumen.veredicto.value}; dudosos={resumen.dudosos}/"
        f"{resumen.total_campos} ({resumen.pct_dudosos:.0%}); "
        + ", ".join(f"{n.value}:{c}" for n, c in sorted(
            resumen.por_nivel.items(), key=lambda kv: _ORDEN[kv[0]]
        ))
    ) if resumen.total_campos else f"veredicto={resumen.veredicto.value}; sin campos"

    ds.validation_results = [
        r for r in ds.validation_results if r.regla != "confianza"
    ]
    ds.validation_results.append(
        ResultadoValidacion(
            regla="confianza", ok=not resumen.review_required, detalle=detalle
        )
    )
    return ds


def cola_de_revision(datasets: Iterable[DatasetNormalizado]) -> list[ItemRevision]:
    """Arma la cola de revisión a partir de uno o varios datasets.

    Incluye cada campo dudoso (`LOW`/`REVIEW_REQUIRED`) como ítem propio, y el
    dataset completo cuando queda en revisión pero no tiene campos dudosos
    puntuales (p. ej. por calidad baja o clasificación dudosa).
    """
    cola: list[ItemRevision] = []
    for ds in datasets:
        campos_dudosos = [c for c in ds.campos if requiere_revision(c.confidence)]
        for c in campos_dudosos:
            cola.append(_item_de_campo(ds, c))
        if ds.review_required and not campos_dudosos:
            cola.append(
                ItemRevision(
                    dataset_id=ds.dataset_id,
                    document_type=ds.document_type.value,
                    field=None,
                    confidence=resumen_confianza(ds).veredicto,
                    extraction_method=ds.extraction_method.value,
                    motivo="dataset marcado para revisión (calidad/clasificación)",
                    source_file=ds.source_file,
                )
            )
    return cola


def _item_de_campo(ds: DatasetNormalizado, c: CampoExtraido) -> ItemRevision:
    motivos = []
    if c.confidence is NivelConfianza.REVIEW_REQUIRED:
        motivos.append("confianza REVIEW_REQUIRED")
    elif c.confidence is NivelConfianza.LOW:
        motivos.append("confianza LOW")
    if c.warnings:
        motivos.append("; ".join(c.warnings))
    return ItemRevision(
        dataset_id=ds.dataset_id,
        document_type=ds.document_type.value,
        field=c.field,
        confidence=c.confidence,
        extraction_method=c.extraction_method.value,
        motivo="; ".join(motivos) or "requiere revisión",
        source_file=(c.evidence.source_file if c.evidence else ds.source_file),
    )
