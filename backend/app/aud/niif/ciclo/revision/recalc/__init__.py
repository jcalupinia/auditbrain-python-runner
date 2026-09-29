"""Registro de los recálculos independientes a medida por rubro.

Cada herramienta del catálogo tiene (o puede tener) su módulo
``revision/recalc/<processor>.py`` con una función::

    def recalcular(run: dict) -> dict

que re-deriva el **resultado principal** de la prueba (normalmente el ajuste
propuesto, ``auditado = registrado + ajuste``) desde los datos crudos del
``run["detalle"]``, sin reutilizar el cálculo del procesador. Devuelve::

    {
      "etiqueta": str,          # qué cifra se re-deriva
      "declarado": float|None,  # totals[primary] tal como lo calculó el procesador
      "recalculado": float|None,# el mismo importe re-derivado aquí
      "diff": float|None,       # |declarado - recalculado| (None si falta un operando)
      "ok": bool,               # diff <= TOL_RECALculo
      "componentes": [ {"concepto": str, "declarado": float, "recalculado": float,
                        "diff": float, "ok": bool}, ... ],   # desglose opcional
    }

El registro se resuelve por importación perezosa del módulo del rubro, así que
agregar un rubro es solo crear su archivo (no hay lista que mantener).
"""
from __future__ import annotations

import importlib

# Tolerancia del recálculo: los importes se declaran redondeados a 2 decimales
# (``r2``), así que una diferencia por debajo de un centavo es ruido de redondeo.
TOL_RECALCULO = 0.01


def recalculo_de(processor: str):
    """Función ``recalcular`` del rubro, o ``None`` si el rubro no tiene módulo."""
    if not processor:
        return None
    try:
        mod = importlib.import_module(f"backend.app.aud.niif.ciclo.revision.recalc.{processor}")
    except ModuleNotFoundError:
        return None
    return getattr(mod, "recalcular", None)
