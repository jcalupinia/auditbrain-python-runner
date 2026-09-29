"""Recálculo independiente del resultado principal de «Inversiones e instrumentos financieros».

Re-deriva el **ajuste propuesto al importe neto** (``totals["ajuste"]``, el resultado
``primary`` de la prueba) volviendo a agregar el detalle por instrumento de
``run["detalle"]["instrumentos"]`` con una aritmética escrita aparte del procesador,
y lo coteja contra lo que declaró el motor. Es la segunda implementación de la
identidad central de la prueba.

Identidad re-derivada, instrumento por instrumento:

    ajuste = (medición según la norma − saldo en libros) − ajuste de deterioro
           =  difMed                                      −  ajDet

donde el **ajuste de deterioro** solo se reconoce en resultados para las categorías
medidas a costo (``esperada`` ∈ {CA = costo amortizado, COSTO = costo menos deterioro});
en VR con cambios en resultados/ORI la corrección no forma parte de este ajuste
(``ajDet = 0``). El importe neto de la prueba es la suma de los ajustes de cada
instrumento que tiene medición completa.

Campos crudos de los que se parte (por instrumento, en ``detalle["instrumentos"]``):
``medicion`` (medición según la norma), ``libros`` (saldo en libros bruto),
``detCalc`` (deterioro recalculado), ``detReg`` (deterioro registrado) y ``esperada``
(categoría de medición NIIF 9 que enruta si el deterioro entra al ajuste). No se baja
por debajo de la medición por instrumento (reconstruir la TIE, el valor razonable o el
deterioro de cada título sería re-implementar el procesador entero); se re-agrega y se
re-arma la identidad ``difMed − ajDet`` de forma independiente al acumulado del motor.

Componentes expuestos (cada uno cotejado contra lo que publican los ``totals``):
1. Diferencia de medición  →  ``totals["difMedicion"]``.
2. Ajuste de deterioro reconocido (costo amortizado y costo)  →  implícito en los
   totales como ``difMedicion − ajuste``.
3. Ajuste propuesto neto (diferencia de medición − ajuste de deterioro)  →  ``totals["ajuste"]``.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO

# Categorías medidas a costo cuyo movimiento de deterioro entra al ajuste propuesto
# (costo amortizado y costo menos deterioro). En VR (resultados/ORI) no se reconoce aquí.
_CON_DETERIORO = ("CA", "COSTO")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _ok(diff):
    return diff is not None and diff <= TOL_RECALCULO


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    instrumentos = d.get("instrumentos") or []

    # Re-agrega instrumento por instrumento, independiente del acumulado del motor.
    sum_difmed = 0.0   # Σ (medición − saldo en libros)
    sum_ajdet = 0.0    # Σ ajuste de deterioro (solo costo amortizado y costo)
    sum_ajuste = 0.0   # Σ ajuste propuesto (difMed − ajDet) de los que tienen medición completa
    hay_difmed = hay_ajdet = hay_ajuste = False

    for x in instrumentos:
        med = _num(x.get("medicion"))
        lib = _num(x.get("libros"))
        difmed = None if med is None or lib is None else med - lib

        esperada = x.get("esperada")
        if esperada in _CON_DETERIORO:
            det_calc = _num(x.get("detCalc"))
            det_reg = _num(x.get("detReg")) or 0.0
            ajdet = None if det_calc is None else det_calc - det_reg
        else:
            ajdet = 0.0

        ajuste = None if difmed is None or ajdet is None else difmed - ajdet

        if difmed is not None:
            sum_difmed += difmed
            hay_difmed = True
        if ajdet is not None:
            sum_ajdet += ajdet
            hay_ajdet = True
        if ajuste is not None:
            sum_ajuste += ajuste
            hay_ajuste = True

    difmed_rec = round(sum_difmed, 2) if hay_difmed else None
    ajdet_rec = round(sum_ajdet, 2) if hay_ajdet else None
    ajuste_rec = round(sum_ajuste, 2) if hay_ajuste else None

    # Declarados por el motor.
    difmed_dec = _num(tot.get("difMedicion"))
    ajuste_dec = _num(tot.get("ajuste"))
    # El ajuste de deterioro reconocido no tiene un total propio: los totales lo
    # implican como (diferencia de medición − ajuste propuesto neto).
    ajdet_dec = None if difmed_dec is None or ajuste_dec is None else round(difmed_dec - ajuste_dec, 2)

    diff = _dif(ajuste_dec, ajuste_rec)

    comps = []
    for concepto, dec, rec in (
        ("Diferencia de medición (medición − saldo en libros)", difmed_dec, difmed_rec),
        ("Ajuste de deterioro reconocido (costo amortizado y costo)", ajdet_dec, ajdet_rec),
        ("Ajuste propuesto neto (diferencia de medición − ajuste de deterioro)", ajuste_dec, ajuste_rec),
    ):
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": _ok(dc)})

    return {
        "etiqueta": "Ajuste propuesto (importe neto)",
        "declarado": ajuste_dec,
        "recalculado": ajuste_rec,
        "diff": diff,
        "ok": _ok(diff),
        "componentes": comps,
    }
