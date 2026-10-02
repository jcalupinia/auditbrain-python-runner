"""Recálculo independiente del resultado principal de «Cobertura de seguros de activos».

El resultado principal de esta prueba es el **ajuste propuesto en resultados por la
prima pagada por anticipado** (``totals["ajustePrima"]``, ``run["primary"]``). El
procesador lo arma como ``ajustePrima = -difPrima`` donde ``difPrima = Σ(registrada −
recalculada)`` por póliza; equivale entonces a la identidad::

    ajustePrima = primaRecalculada − primaRegistrada = Σ recalculada − Σ registrada

Este módulo la re-deriva desde los campos **más crudos** de ``run["detalle"]["polizas"]``
—sin reutilizar los acumulados ``calc``/``dif``/``restantes`` que ya dejó el procesador—:

- **prima anticipada recalculada** por póliza = ``prima_total × días_por_transcurrir ÷
  días_de_vigencia``, con ``días_de_vigencia = (hasta − desde)`` y
  ``días_por_transcurrir = max(min((hasta − corte), días_de_vigencia), 0)``, recalculando
  aquí ambos plazos a partir de las fechas crudas ``desde``/``hasta`` de la póliza y del
  ``corte`` del encargo (devengo: NIC 1.27–28; PYMES 2.36/3.16A);
- **prima anticipada registrada** por póliza = el saldo anticipado que informó el cliente
  (campo crudo ``reg``).

El ajuste re-derivado es ``Σ recalculada − Σ registrada`` y se coteja contra
``totals["ajustePrima"]``. Es la segunda implementación de la identidad central de la
prueba: si la agregación del procesador se desvía (un plazo mal contado, una póliza que
no suma, un signo cambiado), el cotejo lo marca. Robusto ante operandos faltantes:
cualquier fecha/importe ausente o inválido colapsa a ``None`` en vez de reventar.
"""
from __future__ import annotations

import datetime

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fecha(v):
    """Fecha desde un ``date`` o un ISO (``YYYY-MM-DD...``); ``None`` si no se puede."""
    if isinstance(v, datetime.date):
        return v
    if not v:
        return None
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _ok(diff):
    return diff is not None and diff <= TOL_RECALCULO


def _recalculada(pol, corte):
    """Prima anticipada al corte de una póliza, re-derivada desde datos crudos.

    ``None`` si falta la prima o no se pueden reconstruir los plazos de vigencia.
    """
    prima = _num(pol.get("prima"))
    desde, hasta = _fecha(pol.get("desde")), _fecha(pol.get("hasta"))
    if prima is None or desde is None or hasta is None or corte is None:
        return None
    dias = (hasta - desde).days
    if dias <= 0:
        return None
    restantes = max(min((hasta - corte).days, dias), 0)
    return prima * restantes / dias


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    polizas = d.get("polizas") or []
    corte = _fecha(d.get("corte"))

    # Re-agrega recalculada y registrada póliza por póliza (independiente del motor).
    recalculada = round(sum(_recalculada(p, corte) or 0.0 for p in polizas), 2)
    registrada = round(sum(_num(p.get("reg")) or 0.0 for p in polizas), 2)
    ajuste = round(recalculada - registrada, 2)

    declarado = _num(tot.get(run.get("primary")))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Prima pagada por anticipado recalculada (Σ prima × días por transcurrir ÷ días de vigencia)",
         recalculada, "primaRecalculada"),
        ("Prima pagada por anticipado registrada (Σ saldo anticipado del cliente)",
         registrada, "primaRegistrada"),
        ("Ajuste propuesto en resultados (recalculada − registrada)", ajuste, run.get("primary")),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": _ok(dc)})

    return {
        "etiqueta": (run.get("labels") or {}).get(run.get("primary")) or "Ajuste propuesto (prima anticipada)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": _ok(diff),
        "componentes": comps,
    }
