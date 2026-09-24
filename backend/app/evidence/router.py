"""Rutas HTTP del motor de evidencia (DQ/ANA · conciliación asistida).

Expone el ``matcher`` (conciliación registro-a-registro con tolerancias
exacto/normalizado/fuzzy/numérico/fecha) y el ``confidence`` (confianza de dos
ejes) como endpoints stateless: reciben los registros en el cuerpo y devuelven
el resultado, sin tocar la BD. Es la conciliación asistida del benchmark
(skill ``auditbrain-assisted-reconciliation``) disponible por API.

Permisos: ``require_staff``. El cálculo es determinista; el LLM no interviene.
El emparejamiento SEMÁNTICO (embeddings) queda fuera de este endpoint por ahora:
requiere un proveedor de embeddings, que se inyecta en el servidor.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session  # noqa: F401  (consistencia con el resto de routers)

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User

from .confidence import confianza_extraccion, confianza_interpretacion, nivel_de
from .matcher import (
    CampoEmparejamiento,
    CriterioEmparejamiento,
    EstadoEmparejamiento,
    ModoEmparejamiento,
    TipoCampo,
    emparejar_lotes,
)

router = APIRouter(prefix="/evidence", tags=["evidence"])


class CampoIn(BaseModel):
    nombre: str
    tipo: str = "texto"          # texto | numero | fecha
    modo: str = "normalizado"    # exacto | normalizado | fuzzy
    peso: float = 1.0
    umbral_fuzzy: float = 0.85
    tolerancia_absoluta: str = "0.00"
    tolerancia_relativa: float = 0.0
    tolerancia_dias: int = 0
    obligatorio: bool = False


class CriterioIn(BaseModel):
    umbral: float = 0.80
    campos: list[CampoIn] = Field(default_factory=list)


class ConciliarIn(BaseModel):
    izquierda: list[dict] = Field(..., description="Registros a conciliar (consultas).")
    derecha: list[dict] = Field(..., description="Registros candidatos (contraparte).")
    criterio: CriterioIn
    uno_a_uno: bool = True


def _campo(c: CampoIn) -> CampoEmparejamiento:
    try:
        tipo = TipoCampo(c.tipo)
        modo = ModoEmparejamiento(c.modo)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if modo is ModoEmparejamiento.SEMANTICO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="modo 'semantico' requiere embeddings (no disponible en este endpoint)")
    try:
        tol_abs = Decimal(str(c.tolerancia_absoluta))
    except (InvalidOperation, ValueError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="tolerancia_absoluta inválida")
    return CampoEmparejamiento(
        nombre=c.nombre, tipo=tipo, modo=modo, peso=c.peso, umbral_fuzzy=c.umbral_fuzzy,
        tolerancia_absoluta=tol_abs, tolerancia_relativa=c.tolerancia_relativa,
        tolerancia_dias=c.tolerancia_dias, obligatorio=c.obligatorio,
    )


@router.post("/conciliar")
def conciliar(body: ConciliarIn, user: User = Depends(require_staff)) -> dict:
    """Concilia dos conjuntos de registros y devuelve el emparejamiento.

    Cada consulta sale con su mejor candidato (índice, score, aporte por campo)
    o como no conciliada. El resumen cuenta conciliadas vs. pendientes de cada
    lado, que es lo que alimenta el papel de conciliación.
    """
    if not body.criterio.campos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Defina al menos un campo de comparación.")
    if len(body.izquierda) > 5000 or len(body.derecha) > 5000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Máximo 5000 registros por lado.")
    criterio = CriterioEmparejamiento(
        campos=tuple(_campo(c) for c in body.criterio.campos), umbral=body.criterio.umbral,
    )
    resultados = emparejar_lotes(body.izquierda, body.derecha, criterio, uno_a_uno=body.uno_a_uno)

    filas = []
    derecha_tomada: set[int] = set()
    for i, res in enumerate(resultados):
        mejor = res.mejor
        if mejor is not None:
            derecha_tomada.add(mejor.indice_candidato)
        filas.append({
            "indice_izquierda": i,
            "estado": res.estado.value,
            "indice_derecha": mejor.indice_candidato if mejor else None,
            "score": round(mejor.score, 4) if mejor else None,
            "por_campo": {k: round(v, 4) for k, v in mejor.por_campo.items()} if mejor else {},
        })
    conciliadas = sum(1 for f in filas if f["estado"] == EstadoEmparejamiento.UNICA.value)
    return {
        "filas": filas,
        "resumen": {
            "izquierda_total": len(body.izquierda),
            "derecha_total": len(body.derecha),
            "conciliadas": conciliadas,
            "izquierda_sin_conciliar": len(body.izquierda) - conciliadas,
            "derecha_sin_conciliar": len(body.derecha) - len(derecha_tomada),
        },
    }


class ConfianzaIn(BaseModel):
    tipo: str = Field(..., description="'extraccion' o 'interpretacion'.")
    # Eje extracción (escalares JSON-friendly):
    metodo: str = "manual"                      # manual|excel|csv|pdfplumber|ocr
    ocr_word_confidence: float | None = None
    parseo_limpio: bool = True
    # Eje interpretación:
    mapeo_conocido: bool = True


@router.post("/confianza")
def confianza(body: ConfianzaIn, user: User = Depends(require_staff)) -> dict:
    """Calcula la confianza (0..1) y su nivel para una extracción o interpretación.

    El eje de interpretación aquí se evalúa sin un emparejamiento contra otra
    fuente (base + ``mapeo_conocido``); el eje con ``ResultadoEmparejamiento`` se
    calcula server-side dentro del pipeline, no por este endpoint stateless.
    """
    if body.tipo == "extraccion":
        score, aportes = confianza_extraccion(
            body.metodo, ocr_word_confidence=body.ocr_word_confidence,
            parseo_limpio=body.parseo_limpio,
        )
    elif body.tipo == "interpretacion":
        score, aportes = confianza_interpretacion(mapeo_conocido=body.mapeo_conocido)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="tipo debe ser 'extraccion' o 'interpretacion'.")
    return {
        "score": round(score, 4),
        "nivel": nivel_de(score).value,
        "aportes": [{"factor": a.factor, "delta": round(a.delta, 4), "motivo": a.motivo} for a in aportes],
    }
