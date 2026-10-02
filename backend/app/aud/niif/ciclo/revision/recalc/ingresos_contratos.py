"""Recálculo independiente del resultado principal de «Ingresos de contratos con clientes».

Re-deriva el **ajuste propuesto a ingresos** (``totals["ajuste"]``, el ``primary`` del
rubro) volviendo a agregar el detalle por obligación de desempeño de
``run["detalle"]["lineas"]`` con una aritmética escrita aparte del procesador, y lo
coteja contra lo que declaró el motor. Es la segunda implementación de la identidad
central de la prueba (NIIF 15 · Sección 23):

    ingreso registrado  +  ajuste  =  ingreso auditado (reconocible del año)

Parte de los campos MÁS crudos que el procesador dejó por línea/obligación:

* ``vp``          — valor presente reconocible acumulado de la obligación (NIIF 15 60-65),
* ``anterior``    — ingreso reconocido en años anteriores (``anteriorEf = anterior or 0``),
* ``registrado``  — ingreso registrado en el año por el cliente.

y re-arma, con sus propias sumas, cada componente y el total:

* Reconocible del año por línea =  ``vp − anterior``  (identidad ``recAnio``); se suma
  sobre las líneas medidas (``vp`` no vacío) → ``ingresoReconocible``.
* Registrado del año            =  suma de ``registrado`` de todas las líneas → ``ingresoRegistrado``.
* Ajuste propuesto por línea    =  ``(vp − anterior) − registrado``; se suma sobre las
  líneas medidas → ``ajuste`` (el resultado principal).

Si la agregación del procesador se desvía (un signo, una línea que no suma, un total mal
armado o una línea sin medir contada mal), el cotejo lo marca. No copia ``totals["ajuste"]``:
lo re-deriva desde el detalle.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, dict):
        v = v.get("v")
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
    lineas = d.get("lineas") or []

    # Re-agrega obligación por obligación (independiente del acumulado del motor).
    reconocible = 0.0   # ingreso reconocible del año (líneas medidas)
    registrado = 0.0    # ingreso registrado del año (todas las líneas del anexo)
    ajuste = 0.0        # ajuste = reconocible − registrado (líneas medidas)
    for x in lineas:
        reg = _num(x.get("registrado"))
        if reg is not None:
            registrado += reg
        vp = _num(x.get("vp"))
        if vp is None:            # línea sin medir: no entra en reconocible ni en el ajuste
            continue
        rec_linea = vp - (_num(x.get("anterior")) or 0.0)
        reconocible += rec_linea
        ajuste += rec_linea - (reg or 0.0)

    reconocible = round(reconocible, 2)
    registrado = round(registrado, 2)
    ajuste = round(ajuste, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Ingreso reconocible del año (VP − reconocido anterior)", reconocible, "ingresoReconocible"),
        ("Ingreso registrado del año (anexo)", registrado, "ingresoRegistrado"),
        ("Ajuste propuesto a ingresos (reconocible − registrado)", ajuste, "ajuste"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste propuesto a ingresos (reconocible − registrado)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
