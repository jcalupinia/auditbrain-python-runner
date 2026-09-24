"""Detección de anomalías explicable: estadística (stdlib) + ML opcional.

- ``anomalias_estadisticas``: z-score robusto por MAD sobre cada variable
  numérica; marca los registros con |z| > umbral y explica QUÉ variable lo
  disparó (ML-001, ML-007/008). Sin dependencias externas: siempre corre.
- ``anomalias_isolation_forest``: Isolation Forest multivariado (sklearn); si
  la librería no está, degrada al camino estadístico (ML-002). No bloqueante.
- ``score_ensemble``: combina el score estadístico/ML con los factores de
  reglas deterministas (del motor) en un score 0..100 explicable (ML-005).

Nada de esto sustituye una prueba normativa: es una CAPA DE PRIORIZACIÓN. El
auditor revisa las marcas; el score ordena la cola de revisión.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence

Registro = dict[str, Any]

# --- Umbrales gobernables (ver registry para versionarlos por modelo) -------
UMBRAL_Z = 3.5          # |z robusto| por encima de esto = variable atípica
UMBRAL_ALTO = 66.0      # score >= => nivel "alto"
UMBRAL_MEDIO = 33.0     # score >= => nivel "medio"
_ESCALA_MAD = 0.6745    # constante que hace el z robusto comparable al z normal


@dataclass(frozen=True)
class FactorRiesgo:
    """Una variable que contribuye al score, con su porqué (explicabilidad)."""

    variable: str
    valor: float
    z: float
    contribucion: float   # aporte 0..100 al score del registro
    motivo: str = ""


@dataclass
class RiesgoRegistro:
    """Score de riesgo de UN registro, con su desglose por variable."""

    indice: int
    score: float                       # 0..100
    nivel: str                         # "alto" | "medio" | "bajo"
    metodo: str                        # "estadistico" | "isolation_forest" | "ensemble"
    factores: list[FactorRiesgo] = field(default_factory=list)
    registro: Registro | None = None

    def a_dict(self) -> dict:
        return {
            "indice": self.indice,
            "score": round(self.score, 2),
            "nivel": self.nivel,
            "metodo": self.metodo,
            "factores": [
                {"variable": f.variable, "valor": f.valor, "z": round(f.z, 3),
                 "contribucion": round(f.contribucion, 2), "motivo": f.motivo}
                for f in self.factores
            ],
        }


def nivel_de(score: float) -> str:
    if score >= UMBRAL_ALTO:
        return "alto"
    if score >= UMBRAL_MEDIO:
        return "medio"
    return "bajo"


def mediana_mad(valores: Sequence[float]) -> tuple[float, float]:
    """Mediana y desviación absoluta mediana (MAD), robustas a extremos."""
    vals = [float(v) for v in valores]
    if not vals:
        return 0.0, 0.0
    med = statistics.median(vals)
    mad = statistics.median([abs(v - med) for v in vals])
    return med, mad


def z_robusto(valores: Sequence[float]) -> list[float]:
    """z robusto por variable: ``0.6745*(x-mediana)/MAD``.

    Si MAD=0 (variable casi constante) cae a la desviación estándar; si esa
    también es 0, todos los z son 0 (no hay dispersión → nada atípico).
    """
    vals = [float(v) for v in valores]
    if not vals:
        return []
    med, mad = mediana_mad(vals)
    if mad > 0:
        return [_ESCALA_MAD * (v - med) / mad for v in vals]
    # MAD nulo: respaldo por desviación estándar clásica.
    if len(vals) > 1:
        sd = statistics.pstdev(vals)
        if sd > 0:
            media = statistics.fmean(vals)
            return [(v - media) / sd for v in vals]
    return [0.0 for _ in vals]


def _matriz(registros: Sequence[Registro], campos: Sequence[str]) -> dict[str, list[float]]:
    """Extrae columnas numéricas; valores no numéricos → 0.0 (documentado)."""
    cols: dict[str, list[float]] = {c: [] for c in campos}
    for r in registros:
        for c in campos:
            try:
                cols[c].append(float(r.get(c, 0) or 0))
            except (TypeError, ValueError):
                cols[c].append(0.0)
    return cols


def _score_desde_zmax(zmax: float) -> float:
    """Mapea |z| máximo a 0..100: z=umbral → 50, z=2·umbral → 100 (saturado)."""
    return max(0.0, min(100.0, (zmax / UMBRAL_Z) * 50.0))


def anomalias_estadisticas(
    registros: Sequence[Registro],
    campos: Sequence[str],
    *,
    umbral_z: float = UMBRAL_Z,
) -> list[RiesgoRegistro]:
    """z-score robusto por variable; marca y EXPLICA los registros atípicos.

    Devuelve un ``RiesgoRegistro`` por registro, ordenados por score desc. Cada
    uno lleva sus ``factores`` (una por variable con |z| relevante), de modo que
    el auditor vea por qué se marcó (ML-007/008).
    """
    campos = list(campos)
    cols = _matriz(registros, campos)
    zcols = {c: z_robusto(cols[c]) for c in campos}

    salida: list[RiesgoRegistro] = []
    for i in range(len(registros)):
        factores: list[FactorRiesgo] = []
        zmax = 0.0
        for c in campos:
            z = zcols[c][i]
            zmax = max(zmax, abs(z))
            if abs(z) >= umbral_z:
                factores.append(FactorRiesgo(
                    variable=c, valor=cols[c][i], z=z,
                    contribucion=_score_desde_zmax(abs(z)),
                    motivo=f"{c}={cols[c][i]:.2f} está a {abs(z):.1f} desviaciones robustas de la mediana",
                ))
        score = _score_desde_zmax(zmax)
        salida.append(RiesgoRegistro(
            indice=i, score=score, nivel=nivel_de(score), metodo="estadistico",
            factores=sorted(factores, key=lambda f: -abs(f.z)),
            registro=dict(registros[i]),
        ))
    salida.sort(key=lambda r: -r.score)
    return salida


def hay_ml() -> bool:
    """True si scikit-learn está disponible para la capa ML (no bloqueante)."""
    try:
        import sklearn  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def anomalias_isolation_forest(
    registros: Sequence[Registro],
    campos: Sequence[str],
    *,
    contaminacion: float = 0.05,
    semilla: int = 42,
) -> list[RiesgoRegistro]:
    """Isolation Forest multivariado (sklearn), con explicación por variable.

    Si scikit-learn NO está instalado, degrada a ``anomalias_estadisticas``
    (marca ``metodo="estadistico_fallback"``): la capacidad nunca bloquea el
    flujo por falta de una dependencia opcional.
    """
    campos = list(campos)
    if not hay_ml():
        base = anomalias_estadisticas(registros, campos)
        for r in base:
            r.metodo = "estadistico_fallback"
        return base

    from sklearn.ensemble import IsolationForest

    cols = _matriz(registros, campos)
    X = [[cols[c][i] for c in campos] for i in range(len(registros))]
    if len(X) < 2:
        return anomalias_estadisticas(registros, campos)

    modelo = IsolationForest(contamination=contaminacion, random_state=semilla)
    modelo.fit(X)
    # score_samples: mayor = más normal. Invertimos y normalizamos a 0..100.
    crudos = modelo.score_samples(X)
    lo, hi = min(crudos), max(crudos)
    rango = (hi - lo) or 1.0
    # z robusto por variable para EXPLICAR (IF no da atribución nativa).
    zcols = {c: z_robusto(cols[c]) for c in campos}

    salida: list[RiesgoRegistro] = []
    for i in range(len(registros)):
        score = 100.0 * (hi - crudos[i]) / rango  # más aislado → más score
        factores = [
            FactorRiesgo(
                variable=c, valor=cols[c][i], z=zcols[c][i],
                contribucion=abs(zcols[c][i]),
                motivo=f"{c} contribuye al aislamiento (z robusto {zcols[c][i]:.1f})",
            )
            for c in campos if abs(zcols[c][i]) >= 1.0
        ]
        salida.append(RiesgoRegistro(
            indice=i, score=score, nivel=nivel_de(score), metodo="isolation_forest",
            factores=sorted(factores, key=lambda f: -abs(f.z)),
            registro=dict(registros[i]),
        ))
    salida.sort(key=lambda r: -r.score)
    return salida


def score_ensemble(
    registros: Sequence[Registro],
    campos: Sequence[str],
    *,
    reglas_por_indice: dict[int, list[FactorRiesgo]] | None = None,
    usar_ml: bool = False,
    peso_estadistico: float = 0.5,
    peso_reglas: float = 0.5,
) -> list[RiesgoRegistro]:
    """Ensemble explicable: capa de datos (estadística o ML) + factores de reglas.

    - ``usar_ml=True`` usa Isolation Forest si está disponible (si no, degrada).
    - ``reglas_por_indice`` inyecta los factores deterministas que ya produjo el
      motor (regla que señaló ese registro), cada uno con su contribución.
    El score final combina ambas capas y CONSERVA todos los factores para que la
    marca sea explicable (nunca un "número mágico", benchmark §8.2).
    """
    reglas_por_indice = reglas_por_indice or {}
    base = (
        anomalias_isolation_forest(registros, campos)
        if usar_ml else anomalias_estadisticas(registros, campos)
    )
    por_indice = {r.indice: r for r in base}

    salida: list[RiesgoRegistro] = []
    for i in range(len(registros)):
        datos = por_indice.get(i)
        score_datos = datos.score if datos else 0.0
        factores = list(datos.factores) if datos else []

        factores_regla = reglas_por_indice.get(i, [])
        score_reglas = min(100.0, sum(f.contribucion for f in factores_regla))
        factores = factores + list(factores_regla)

        score = min(100.0, peso_estadistico * score_datos + peso_reglas * score_reglas)
        # La concurrencia de ambas capas nunca reduce el riesgo por debajo de la
        # capa más fuerte: un asiento que la regla marca P0 no se "diluye".
        score = max(score, score_reglas, score_datos * 0.6)
        salida.append(RiesgoRegistro(
            indice=i, score=score, nivel=nivel_de(score), metodo="ensemble",
            factores=sorted(factores, key=lambda f: -f.contribucion),
            registro=dict(registros[i]),
        ))
    salida.sort(key=lambda r: -r.score)
    return salida
