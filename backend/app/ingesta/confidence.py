"""Confidence Engine — clasificación de confianza de una extracción.

Cada dato extraído recibe un nivel de confianza. La regla de oro es **no
ocultar la incertidumbre**: un dato dudoso se marca para revisión humana o
para el AI Semantic Resolver (fase posterior), nunca se da por bueno en
silencio.

Niveles (del prompt maestro §19):

- ``HIGH``            — extracción nativa/determinista inequívoca.
- ``MEDIUM``          — extraída con alguna heurística tolerante.
- ``LOW``             — dudosa; se envía a revisión.
- ``REVIEW_REQUIRED`` — no se pudo resolver con confianza; exige revisión
                        humana o resolución semántica.

Los umbrales son constantes de módulo para poder ajustarlos sin tocar la
lógica. El puntaje es un ``float`` en ``[0, 1]``.
"""
from __future__ import annotations

from enum import Enum


class NivelConfianza(str, Enum):
    """Nivel de confianza de un dato extraído."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


# Umbrales de clasificación (puntaje en [0, 1]). Ajustables sin tocar lógica.
UMBRAL_ALTA = 0.90   # score >= 0.90           -> HIGH
UMBRAL_MEDIA = 0.70  # 0.70 <= score < 0.90    -> MEDIUM
UMBRAL_BAJA = 0.50   # 0.50 <= score < 0.70    -> LOW
#                      score < 0.50            -> REVIEW_REQUIRED

# Niveles que obligan a revisión humana / resolución semántica.
_NIVELES_REVISION = frozenset({NivelConfianza.LOW, NivelConfianza.REVIEW_REQUIRED})


def clasificar_confianza(score: float) -> NivelConfianza:
    """Traduce un puntaje en ``[0, 1]`` al nivel de confianza.

    Un puntaje fuera de rango se acota a ``[0, 1]`` (nunca lanza): un valor
    inválido debe degradar a revisión, no romper la ingesta.
    """
    if score != score:  # NaN
        return NivelConfianza.REVIEW_REQUIRED
    score = max(0.0, min(1.0, float(score)))
    if score >= UMBRAL_ALTA:
        return NivelConfianza.HIGH
    if score >= UMBRAL_MEDIA:
        return NivelConfianza.MEDIUM
    if score >= UMBRAL_BAJA:
        return NivelConfianza.LOW
    return NivelConfianza.REVIEW_REQUIRED


def requiere_revision(nivel: NivelConfianza) -> bool:
    """¿Este nivel exige revisión humana o resolución semántica?

    ``LOW`` y ``REVIEW_REQUIRED`` sí; ``HIGH`` y ``MEDIUM`` no.
    """
    return nivel in _NIVELES_REVISION
