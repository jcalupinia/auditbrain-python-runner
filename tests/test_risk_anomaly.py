"""Motor de riesgo explicable: estadística + ML opcional + ensemble (P1)."""
import pytest

from backend.app.risk import anomaly as A
from backend.app.risk.anomaly import (
    FactorRiesgo,
    anomalias_estadisticas,
    anomalias_isolation_forest,
    hay_ml,
    mediana_mad,
    nivel_de,
    score_ensemble,
    z_robusto,
)

NORMALES = [100, 102, 98, 101, 99, 103, 97, 100]
POBLACION = [{"monto": v} for v in NORMALES] + [{"monto": 5000}]  # último = atípico


def test_mediana_mad_y_z():
    med, mad = mediana_mad([1, 2, 3, 4, 5])
    assert med == 3 and mad == 1
    z = z_robusto([10, 10, 10, 10, 100])
    assert z[-1] > z[0]  # el 100 es el más atípico


def test_nivel_de():
    assert nivel_de(90) == "alto" and nivel_de(50) == "medio" and nivel_de(10) == "bajo"


def test_anomalias_estadisticas_marca_y_explica():
    res = anomalias_estadisticas(POBLACION, ["monto"])
    top = res[0]
    assert top.registro["monto"] == 5000  # el atípico queda primero
    assert top.nivel == "alto" and top.metodo == "estadistico"
    assert top.factores and top.factores[0].variable == "monto"
    assert "desviaciones" in top.factores[0].motivo
    # un registro normal no tiene factores (no superó el umbral)
    normales = [r for r in res if r.registro["monto"] != 5000]
    assert all(not r.factores for r in normales)


def test_hay_ml_y_isolation_forest():
    pytest.importorskip("sklearn")
    assert hay_ml() is True
    pob = [{"m": v, "f": v} for v in NORMALES] + [{"m": 5000, "f": 9000}]
    res = anomalias_isolation_forest(pob, ["m", "f"], semilla=42)
    top = res[0]
    assert top.metodo == "isolation_forest"
    assert top.registro["m"] == 5000
    assert top.factores  # explicación por variable presente


def test_isolation_forest_degrada_sin_sklearn(monkeypatch):
    monkeypatch.setattr(A, "hay_ml", lambda: False)
    res = anomalias_isolation_forest(POBLACION, ["monto"])
    assert res[0].metodo == "estadistico_fallback"
    assert res[0].registro["monto"] == 5000  # sigue marcando el atípico


def test_score_ensemble_combina_reglas_y_datos():
    # La regla determinista marca el registro índice 0 (no el atípico estadístico).
    reglas = {0: [FactorRiesgo(variable="AST-006", valor=0, z=0, contribucion=80.0,
                               motivo="cuenta poco usada")]}
    res = score_ensemble(POBLACION, ["monto"], reglas_por_indice=reglas)
    por_indice = {r.indice: r for r in res}
    # el marcado por regla tiene score alto y conserva el factor de la regla
    r0 = por_indice[0]
    assert r0.score >= 80.0 and any(f.variable == "AST-006" for f in r0.factores)
    # el atípico estadístico (sin regla que lo corrobore) surge como "medio":
    # conservador, se revisa pero no es "alto" sin corroboración de una regla.
    assert por_indice[8].score >= 50.0 and por_indice[8].nivel in ("medio", "alto")
    assert por_indice[8].metodo == "ensemble"
