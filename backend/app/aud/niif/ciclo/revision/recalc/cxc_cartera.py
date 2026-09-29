"""Recálculo independiente del resultado principal de «Cuentas por cobrar: cartera y deterioro».

Re-deriva el **ajuste de deterioro propuesto** —el ``primary`` de la prueba—
volviendo a agregar el detalle por factura de ``run["detalle"]["filas"]`` con una
suma escrita aparte del procesador. La identidad central del rubro es::

    ajuste = deterioro requerido − deterioro registrado (mayor)

donde el **deterioro requerido** es la pérdida esperada/incurrida sumada factura
por factura: por cada factura, ``max(costo amortizado × tasa, 0)`` (cero cuando el
tramo no tiene tasa). El procesador la agrega en una sola pasada
(``requerido = sum(x["det"] or 0 for x in filas)`` con ``det = max(ca·tasa, 0)``);
aquí se vuelve a estimar factura por factura desde los campos crudos ``ca``
(costo amortizado) y ``tasa`` (tasa aplicada) del detalle, sin reutilizar el
campo ``det`` ni el acumulado del motor. El **deterioro registrado** es un dato
de entrada del auditor (``detalle["provisionRegistrada"]``, no una cifra
calculada), así que se toma como declarado.

Es la segunda implementación de la identidad de la prueba: si la agregación del
procesador se desvía (un tramo que no suma, una tasa mal aplicada, un signo del
ajuste), el cotejo lo marca.
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


def _comp(concepto, dec, rec):
    dc = _dif(dec, rec)
    return {"concepto": concepto, "declarado": dec, "recalculado": rec,
            "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO}


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    filas = d.get("filas") or []

    # Deterioro requerido re-derivado factura por factura: max(costo amortizado · tasa, 0),
    # cero cuando el tramo no tiene tasa. Independiente del acumulado y del campo ``det`` del motor.
    requerido = 0.0
    for x in filas:
        ca = _num(x.get("ca"))
        tasa = _num(x.get("tasa"))
        if ca is None or tasa is None:
            continue
        requerido += max(ca * tasa, 0.0)
    requerido = round(requerido, 2)

    # Deterioro registrado: dato de entrada del auditor (no calculado), tomado del detalle.
    registrado = _num(d.get("provisionRegistrada")) or 0.0
    registrado = round(registrado, 2)

    ajuste = round(requerido - registrado, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = [
        _comp("Deterioro requerido (Σ máx(costo amortizado × tasa, 0) por factura)",
              _num(tot.get("deterioroRequerido")), requerido),
        _comp("Deterioro registrado (mayor)", _num(tot.get("provisionRegistrada")), registrado),
        _comp("Ajuste de deterioro propuesto (requerido − registrado)", declarado, ajuste),
    ]

    return {
        "etiqueta": "Ajuste de deterioro propuesto (requerido − registrado)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
