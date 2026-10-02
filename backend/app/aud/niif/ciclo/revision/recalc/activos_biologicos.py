"""Recálculo independiente del resultado principal de «Activos biológicos» (NIC 41 · Secc. 34).

Re-deriva el **ajuste propuesto** (``totals["ajuste"] = valorAuditado − valorLibros``)
volviendo a agregar, lote por lote, los datos CRUDOS de ``run["detalle"]["items"]`` con
una aritmética escrita aparte del procesador. Es la segunda implementación de la
identidad central de la prueba (``valor auditado = valor en libros + ajuste``): si la
agregación del motor se desvía (un signo, un lote que no suma, un total mal armado o un
valor auditado mal medido), el cotejo lo marca.

Campos crudos de partida (los que entrega el cliente, ya coaccionados a número por el
procesador, no cifras calculadas del motor):

* ``vl``  = valor en libros al corte del lote (``valor_libros``).
* Valor razonable (``ruta == VR``):     ``aud = q · (vc − cv)`` con ``q`` = cantidad
  contada (``cc``) o, sin conteo, la de registros (``cf``); ``vc`` = VR unitario al
  corte (``vr_corte``); ``cv`` = costo de venta unitario (``costo_venta``) o 0. Si no
  hay VR al corte el lote no se midió → ``aud`` queda ``None`` (no entra al ajuste, igual
  que en el motor).
* Modelo del costo (``ruta == COSTO``):  ``neto = ca − dep − det`` (costo, depreciación y
  deterioro acumulados); ``deterioro adicional = max(0, neto − rec)`` contra el importe
  recuperable; ``aud = neto − deterioro adicional``.
* Fuera de NIC 41 / Sección 34 (plantas productoras, ``ruta`` = NIC 16 / Sección 17):
  se acepta el valor en libros → ``aud = vl`` (ajuste 0).

La **ruta** (clasificación categórica por marco) se lee del detalle; lo que se
re-implementa aquí es la ARITMÉTICA de cada valor auditado y su agregación, no la
decisión de marco. ``VR`` y ``COSTO`` se importan como etiquetas del procesador (no es
reutilizar su cálculo, solo el nombre del modelo).
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO
from backend.app.aud.niif.procesadores.activos_biologicos import COSTO, VR


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _aud_lote(it: dict):
    """Valor auditado del lote re-derivado desde campos crudos; ``None`` si no se pudo medir."""
    vl = _num(it.get("vl"))
    ruta = it.get("ruta")
    if ruta == VR:
        cf = _num(it.get("cf"))
        cc = _num(it.get("cc"))
        q = cc if cc is not None else cf
        vc = _num(it.get("vc"))
        cv = _num(it.get("cvRaw")) or 0.0
        if q is None or vc is None:
            return None
        return q * (vc - cv)
    if ruta == COSTO:
        ca = _num(it.get("ca"))
        if ca is None:
            return None
        neto = ca - (_num(it.get("dep")) or 0.0) - (_num(it.get("det")) or 0.0)
        rec = _num(it.get("rec"))
        det_ad = max(0.0, neto - rec) if rec is not None else 0.0
        return neto - det_ad
    # Fuera de NIC 41 / Sección 34 (plantas productoras a NIC 16 / Secc. 17): se deja al valor en libros.
    return vl


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    items = d.get("items") or []

    # Re-agrega lote por lote, independiente del acumulado del motor.
    libros = round(sum(_num(it.get("vl")) or 0.0 for it in items), 2)
    auds = [(_aud_lote(it), _num(it.get("vl"))) for it in items]
    auditado = round(sum(a for a, _ in auds if a is not None), 2)
    # ajuste = Σ(auditado − libros) solo de los lotes efectivamente medidos (mismo criterio del motor).
    ajuste = round(sum((a - (vl or 0.0)) for a, vl in auds if a is not None), 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Activos biológicos según el anexo (libros)", libros, "valorLibros"),
        ("Activos biológicos auditados (VR − costos de venta / costo)", auditado, "valorAuditado"),
        ("Ajuste propuesto (auditado − libros)", ajuste, "ajuste"),
    ):
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
