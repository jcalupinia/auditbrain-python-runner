"""Motor de riesgo explicable (capa 6 de la arquitectura de convergencia).

Enriquecimiento de riesgo NO bloqueante y SIEMPRE explicable sobre la
población completa, complementario al ensemble determinista de reglas del
motor (`motor-auditoria-analitica/motor/riesgo.py`).

Dos capas:
  - **estadística** (stdlib puro, siempre disponible): z-score robusto por
    MAD, con la contribución por variable que disparó la marca (ML-001).
  - **machine learning OPCIONAL** (Isolation Forest de scikit-learn): se activa
    solo si la librería está instalada; si no, degrada al camino estadístico
    sin romper nada (ML-002). NUNCA sustituye a las conciliaciones, fórmulas o
    pruebas normativas deterministas (regla del benchmark §19).

Gobierno del modelo (ML-009/010/011) en ``registry.py``: cada corrida ML
registra algoritmo, versión, features, parámetros, umbral y hash de config
para reproducibilidad.

Principio no negociable: toda marca de riesgo explica su factor (ML-007/008);
un score sin explicación no se muestra.
"""

from __future__ import annotations

from backend.app.risk.anomaly import (  # noqa: F401
    FactorRiesgo,
    RiesgoRegistro,
    anomalias_estadisticas,
    anomalias_isolation_forest,
    hay_ml,
    mediana_mad,
    nivel_de,
    score_ensemble,
    z_robusto,
)
from backend.app.risk.registry import (  # noqa: F401
    ModeloRiesgo,
    RegistroModelos,
    hash_config,
)

__all__ = [
    "FactorRiesgo",
    "RiesgoRegistro",
    "anomalias_estadisticas",
    "anomalias_isolation_forest",
    "hay_ml",
    "mediana_mad",
    "nivel_de",
    "score_ensemble",
    "z_robusto",
    "ModeloRiesgo",
    "RegistroModelos",
    "hash_config",
]
