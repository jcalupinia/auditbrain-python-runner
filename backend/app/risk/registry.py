"""Gobierno del modelo de riesgo (ML-009/010/011).

Registra QUÉ modelo produjo cada score: algoritmo, versión, features,
parámetros, umbral, métricas y un hash de configuración para reproducibilidad
(dos corridas "iguales" deben compartir ``config_hash``). Es el análogo del
snapshot de ejecución (Agente D) para la capa de riesgo/ML: sin esto, un score
de anomalía no es auditable.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


def hash_config(algoritmo: str, features: tuple[str, ...], parametros: dict, umbral: float) -> str:
    """sha256 canónico de la configuración de un modelo (DATA-012 análogo)."""
    material = {
        "algoritmo": algoritmo,
        "features": sorted(features),
        "parametros": parametros,
        "umbral": umbral,
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ModeloRiesgo:
    """Ficha inmutable de un modelo de riesgo y su configuración."""

    model_id: str
    version: str
    algoritmo: str                       # "mad_zscore" | "isolation_forest" | ...
    features: tuple[str, ...]
    parametros: dict = field(default_factory=dict)
    umbral: float = 3.5
    entrenado_en: str | None = None      # ISO; None para modelos no entrenados (estadísticos)
    metricas: dict = field(default_factory=dict)
    limitaciones: str = ""
    owner: str = "AuditConsulting"

    @property
    def config_hash(self) -> str:
        return hash_config(self.algoritmo, self.features, self.parametros, self.umbral)

    def a_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "algoritmo": self.algoritmo,
            "features": list(self.features),
            "parametros": self.parametros,
            "umbral": self.umbral,
            "entrenado_en": self.entrenado_en,
            "metricas": self.metricas,
            "limitaciones": self.limitaciones,
            "owner": self.owner,
            "config_hash": self.config_hash,
        }


class ConflictoDeVersion(Exception):
    """Se intentó registrar la MISMA versión con distinta configuración."""


class RegistroModelos:
    """Registro versionado en memoria de modelos de riesgo (ML-009/010)."""

    def __init__(self) -> None:
        self._modelos: dict[tuple[str, str], ModeloRiesgo] = {}

    def registrar(self, modelo: ModeloRiesgo) -> ModeloRiesgo:
        """Alta idempotente por (model_id, version).

        Re-registrar la misma versión con IDÉNTICA config es un no-op (devuelve
        la existente); con config distinta es un ``ConflictoDeVersion`` (una
        versión publicada no se muta: se sube una nueva).
        """
        clave = (modelo.model_id, modelo.version)
        previo = self._modelos.get(clave)
        if previo is not None:
            if previo.config_hash != modelo.config_hash:
                raise ConflictoDeVersion(
                    f"{modelo.model_id} v{modelo.version} ya existe con otra configuración"
                )
            return previo
        self._modelos[clave] = modelo
        return modelo

    def obtener(self, model_id: str, version: str | None = None) -> ModeloRiesgo | None:
        """Devuelve una versión concreta o, si no se pide, la más reciente."""
        if version is not None:
            return self._modelos.get((model_id, version))
        versiones = self.versiones(model_id)
        return versiones[-1] if versiones else None

    def versiones(self, model_id: str) -> list[ModeloRiesgo]:
        """Versiones de un modelo, ordenadas ascendente por versión."""
        ms = [m for (mid, _), m in self._modelos.items() if mid == model_id]
        return sorted(ms, key=lambda m: _clave_version(m.version))

    def listar(self) -> list[ModeloRiesgo]:
        return list(self._modelos.values())


def _clave_version(v: str) -> tuple:
    """Ordena versiones numéricas ('1.2.0') y textuales de forma estable."""
    partes = []
    for p in str(v).replace("-", ".").split("."):
        partes.append((0, int(p)) if p.isdigit() else (1, p))
    return tuple(partes)


def modelo_estadistico(features: tuple[str, ...], *, umbral: float = 3.5,
                       version: str = "1.0.0") -> ModeloRiesgo:
    """Ficha del modelo estadístico por defecto (sin entrenamiento)."""
    return ModeloRiesgo(
        model_id="riesgo_mad_zscore",
        version=version,
        algoritmo="mad_zscore",
        features=tuple(features),
        parametros={"escala_mad": 0.6745},
        umbral=umbral,
        limitaciones="Univariado por variable; asume dispersión no nula (respaldo por desviación estándar).",
    )


def modelo_isolation_forest(features: tuple[str, ...], *, contaminacion: float = 0.05,
                            semilla: int = 42, version: str = "1.0.0") -> ModeloRiesgo:
    """Ficha del modelo Isolation Forest (ML opcional)."""
    return ModeloRiesgo(
        model_id="riesgo_isolation_forest",
        version=version,
        algoritmo="isolation_forest",
        features=tuple(features),
        parametros={"contamination": contaminacion, "random_state": semilla},
        umbral=0.0,
        entrenado_en=datetime.datetime.utcnow().isoformat(),
        limitaciones="No supervisado; requiere revisión humana. Explicación aproximada por z robusto, no SHAP nativo.",
    )
