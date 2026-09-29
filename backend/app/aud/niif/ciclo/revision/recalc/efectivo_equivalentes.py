"""Recálculo independiente del resultado principal de «Efectivo y equivalentes».

Re-deriva el **ajuste propuesto** (``totals["ajuste"] = auditado − libros``) volviendo
a agregar el detalle por cuenta de ``run["detalle"]["cuentas"]`` con una suma escrita
aparte del procesador, y lo coteja contra lo que declaró el motor. Es la segunda
implementación de la identidad de la prueba: si la agregación del procesador se
desvía (un signo, una cuenta que no suma, un total mal armado), el cotejo lo marca.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    cuentas = d.get("cuentas") or []

    # Re-agrega libros y auditado cuenta por cuenta (independiente del acumulado del motor).
    libros = round(sum(_num(c.get("libros")) or 0.0 for c in cuentas), 2)
    auditado = round(sum(_num(c.get("auditado")) or 0.0 for c in cuentas), 2)
    ajuste = round(auditado - libros, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (("Efectivo según libros", libros, "saldoLibros"),
                                 ("Efectivo y equivalentes auditado", auditado, "auditado"),
                                 ("Ajuste propuesto (auditado − libros)", ajuste, "ajuste")):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste propuesto (auditado − libros)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
