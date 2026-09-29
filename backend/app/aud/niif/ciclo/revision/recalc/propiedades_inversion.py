"""Recálculo independiente del resultado principal de «Propiedades de inversión».

Re-deriva el **ajuste propuesto** (``totals["ajuste"] = propiedades de inversión
auditadas − saldo del mayor``) volviendo a agregar los datos crudos del
``run["detalle"]`` con una suma escrita aparte del procesador, y lo coteja contra
lo que declaró el motor. Es la segunda implementación de la identidad central de
la prueba (``saldo del mayor + ajuste = auditado``, NIC 40.33-35 y 40.56):

- **Propiedades de inversión auditadas** = suma inmueble por inmueble de la
  medición auditada (``item["aud"]`` de ``detalle["items"]``: valor razonable al
  corte o valor neto según costo, por la parte que es propiedad de inversión). Es
  la cifra más cruda que el motor expone por partida y aquí se re-suma aparte, sin
  reutilizar el acumulado ``totals["piAuditado"]``.
- **Saldo según el mayor** = el saldo que ingresó el auditor
  (``detalle["parametros"]["saldoMayor"]``, dato crudo del encargo) o, si no lo
  informó, la suma del importe en libros del detalle (``item["libros"]``), tal
  como decide el procesador.
- **Ajuste propuesto** = auditado − mayor, re-derivado aquí (NO se copia
  ``totals["ajuste"]``).

Si la agregación del motor se desvía (una partida que no suma, un signo, el mayor
mal tomado), el cotejo lo marca. Es robusto ante operandos faltantes: devuelve
``None`` en vez de reventar.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _comp(concepto, dec, rec):
    dc = _dif(dec, rec)
    return {"concepto": concepto, "declarado": dec, "recalculado": rec,
            "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO}


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    par = d.get("parametros") or {}
    items = d.get("items") or []

    # 1 · Re-agrega, partida por partida, la medición auditada de cada inmueble
    #     (independiente del acumulado del motor). Es la cifra más cruda que el
    #     detalle expone por inmueble: VR al corte o valor neto según costo, por
    #     la parte que es propiedad de inversión.
    pi_auditado = round(sum(_num(i.get("aud")) or 0.0 for i in items), 2)
    # ... y el importe en libros según el detalle (para el mayor cuando no se informó).
    libros_detalle = round(sum(_num(i.get("libros")) or 0.0 for i in items), 2)

    # 2 · Saldo del mayor: el dato del auditor o, si falta, la suma del detalle
    #     (misma regla que el procesador: mayor = saldoMayor o libros del detalle).
    saldo_mayor = _num(par.get("saldoMayor"))
    mayor = saldo_mayor if saldo_mayor is not None else libros_detalle

    # 3 · Ajuste propuesto = auditado − mayor (re-derivado aquí, no copiado).
    ajuste = round(pi_auditado - mayor, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = [
        _comp("Propiedades de inversión auditadas", _num(tot.get("piAuditado")), pi_auditado),
        _comp("Saldo según el mayor", _num(tot.get("saldoMayor")), mayor),
        _comp("Ajuste propuesto (auditado − mayor)", declarado, ajuste),
    ]

    return {
        "etiqueta": "Ajuste propuesto (auditado − saldo del mayor)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
