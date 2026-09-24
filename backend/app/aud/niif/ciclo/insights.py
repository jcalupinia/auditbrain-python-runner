"""Enriquecimiento analítico del ciclo con los motores evidence y risk.

Dos aportes **aditivos** que el ciclo calcula y guarda en el registro, sin tocar
la máquina de estados ni las reglas del espejo:

- ``scoring_riesgo`` (paso ``analyze``): detección de anomalías explicable
  (``backend/app/risk``) sobre la población validada — marca las filas atípicas
  por sus campos numéricos, con score 0-100 y su desglose.
- ``matriz_evidencia`` (paso ``validate``): matriz de evidencia
  (``backend/app/evidence``) que cruza requerimientos ↔ archivos recibidos —
  cobertura, corroboración (≥2 fuentes) y qué requerimiento quedó sin evidencia.

Ambas funciones son **defensivas**: cualquier error devuelve ``{}`` y el ciclo
sigue igual (nunca rompen la acción). Deterministas; el LLM no interviene.
"""
from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def scoring_riesgo(definicion: dict, rows: list[dict]) -> dict:
    """Score de riesgo por fila sobre los campos numéricos de la definición.

    Solo aplica a definiciones declarativas (con ``fields``); para procesadores
    especializados devuelve ``{}`` (tienen su propia lógica). Marca las filas de
    nivel alto/medio y deja el resumen para el panel del auditor.
    """
    try:
        campos = [f["key"] for f in (definicion.get("fields") or [])
                  if isinstance(f, dict) and f.get("type") == "number" and f.get("key")]
        if not campos or not isinstance(rows, list) or not rows:
            return {}
        from backend.app.risk.anomaly import anomalias_estadisticas

        resultados = anomalias_estadisticas(rows, campos)
        marcados = [r for r in resultados if r.nivel != "bajo"]
        return {
            "campos": campos,
            "resumen": {
                "total": len(resultados),
                "alto": sum(1 for r in resultados if r.nivel == "alto"),
                "medio": sum(1 for r in resultados if r.nivel == "medio"),
                "bajo": sum(1 for r in resultados if r.nivel == "bajo"),
            },
            # top 50 más riesgosas, cada una con su desglose explicable.
            "anomalias": [r.a_dict() for r in
                          sorted(marcados, key=lambda r: r.score, reverse=True)[:50]],
        }
    except Exception:  # nunca romper el ciclo por el enriquecimiento
        log.exception("scoring_riesgo falló; se omite el enriquecimiento de riesgo")
        return {}


def matriz_evidencia(requests: list[dict], archivos: Any) -> dict:
    """Matriz de evidencia: requerimientos ↔ archivos recibidos (no rechazados).

    ``archivos`` es la lista de ``PruebaArchivo`` de la prueba. Cada requerimiento
    queda con sus fuentes (archivos que lo cubren), si está corroborado (≥2) y su
    estado de revisión. Base para el panel de cobertura de evidencia del auditor.
    """
    try:
        if not requests:
            return {}
        from backend.app.evidence.citation import SourceReference, source_id_de
        from backend.app.evidence.crossref import MatrizEvidencia

        m = MatrizEvidencia()
        for r in requests:
            rid = str(r.get("id") or "").strip()
            if not rid:
                continue
            etiqueta = str(r.get("document") or r.get("purpose") or rid)
            refs = []
            for a in archivos:
                if getattr(a, "requerimiento", None) == rid and getattr(a, "estado", "") != "rechazado":
                    refs.append(SourceReference(
                        source_id=source_id_de(a.sha256, rid),
                        file_hash=a.sha256, filename=a.nombre, metodo="upload",
                    ))
            m.agregar(rid, etiqueta, None, refs)

        entradas = m.entradas
        return {
            "resumen": {
                "requerimientos": len(entradas),
                "con_evidencia": sum(1 for e in entradas if e.num_fuentes > 0),
                "sin_evidencia": sum(1 for e in entradas if e.num_fuentes == 0),
                "corroborados": sum(1 for e in entradas if e.es_corroborado),
            },
            "entradas": [
                {"requerimiento": e.dato_id, "documento": e.etiqueta,
                 "fuentes": e.num_fuentes, "corroborado": e.es_corroborado,
                 "estado": e.estado_validacion.value}
                for e in entradas
            ],
        }
    except Exception:
        log.exception("matriz_evidencia falló; se omite el enriquecimiento de evidencia")
        return {}
