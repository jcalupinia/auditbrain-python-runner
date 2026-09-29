"""Consola de revisión genérica para las herramientas NIIF del catálogo.

A diferencia de la planificación (``ciclo.consola_revision``, que recalcula
índices desde ``est9``), las 20 pruebas del catálogo son heterogéneas pero
comparten el mismo contrato del procesador (``docs/niif/CONTRATO_PROCESADOR.md``):
``totals``/``primary``, ``labels``, ``rows``, ``exceptions``, ``PANEL`` y
``REF_PROBLEMAS``. Sobre ese contrato se arma:

- un **revisor genérico** (``base.revisar``) con los controles que valen para
  cualquier herramienta conforme: el panel resuelve, las cédulas declaradas
  están presentes, todo problema con importe está enlazado a su celda y el
  resultado principal existe; y
- un **recálculo a medida por rubro** (``recalc.recalculo_de``): si existe el
  módulo ``revision/recalc/<processor>.py``, su ``recalcular(run)`` re-deriva el
  resultado principal (``auditado = registrado + ajuste``) desde los datos crudos
  del ``detalle``, con una segunda implementación independiente del cálculo del
  procesador. Si diverge, el veredicto baja a NO APTO.

El veredicto sigue siendo el mismo de la planificación: APTO PARA REVISIÓN DEL
SOCIO / OBSERVADO / NO APTO, y la aprobación final es humana (compuerta del socio).
"""
from backend.app.aud.niif.ciclo.revision.base import revisar  # noqa: F401
from backend.app.aud.niif.ciclo.revision.recalc import recalculo_de  # noqa: F401
