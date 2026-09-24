"""Rutas HTTP del motor de riesgo (ML/ANA · detección de anomalías).

Expone el detector de anomalías (z-score robusto MAD, Isolation Forest opcional,
ensemble explicable) como endpoint stateless. Cada registro marcado sale con su
score 0..100, su nivel (alto/medio/bajo) y el desglose de factores que lo
explican (benchmark §8.2: nunca un "número mágico"). Determinista salvo el modo
ML, que degrada con elegancia si scikit-learn no está disponible.

Permisos: ``require_staff``.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.auth.deps import require_staff
from backend.app.auth.models import User

from .anomaly import (
    anomalias_estadisticas,
    anomalias_isolation_forest,
    hay_ml,
    score_ensemble,
)

router = APIRouter(prefix="/risk", tags=["risk"])


class AnomaliasIn(BaseModel):
    registros: list[dict] = Field(..., description="Filas a analizar (misma forma).")
    campos: list[str] = Field(..., description="Variables numéricas a evaluar.")
    metodo: str = Field("estadistico", description="estadistico | isolation_forest | ensemble")
    umbral_z: float = 3.5
    contaminacion: float = 0.05
    usar_ml: bool = False
    solo_marcados: bool = Field(True, description="Si True, omite los de nivel 'bajo'.")


@router.get("/ml")
def ml_disponible(user: User = Depends(require_staff)) -> dict:
    """¿Está disponible Isolation Forest (scikit-learn) en este entorno?"""
    return {"disponible": hay_ml()}


@router.post("/anomalias")
def anomalias(body: AnomaliasIn, user: User = Depends(require_staff)) -> dict:
    """Detecta y EXPLICA registros atípicos según el método elegido."""
    if not body.campos:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Indique al menos una variable en 'campos'.")
    if len(body.registros) > 20000:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Máximo 20000 registros.")

    if body.metodo == "estadistico":
        resultados = anomalias_estadisticas(body.registros, body.campos, umbral_z=body.umbral_z)
    elif body.metodo == "isolation_forest":
        resultados = anomalias_isolation_forest(body.registros, body.campos, contaminacion=body.contaminacion)
    elif body.metodo == "ensemble":
        resultados = score_ensemble(body.registros, body.campos, usar_ml=body.usar_ml)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="metodo debe ser 'estadistico', 'isolation_forest' o 'ensemble'.")

    filas = [r for r in resultados if not body.solo_marcados or r.nivel != "bajo"]
    resumen = {
        "total": len(resultados),
        "alto": sum(1 for r in resultados if r.nivel == "alto"),
        "medio": sum(1 for r in resultados if r.nivel == "medio"),
        "bajo": sum(1 for r in resultados if r.nivel == "bajo"),
    }
    return {
        "metodo": body.metodo,
        "ml_disponible": hay_ml(),
        "resumen": resumen,
        "anomalias": [r.a_dict() for r in sorted(filas, key=lambda r: r.score, reverse=True)],
    }
