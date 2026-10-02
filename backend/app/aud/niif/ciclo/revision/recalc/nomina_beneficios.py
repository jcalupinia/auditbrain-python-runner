"""Recálculo independiente del resultado principal de «Beneficios sociales y nómina».

Re-deriva el **ajuste propuesto a pasivos laborales** (``totals["ajustePasivos"]``,
el ``run["primary"]``) volviendo a agregar el detalle por empleado y por plan
actuarial de ``run["detalle"]`` con una suma escrita aparte del procesador.

Es la segunda implementación de la identidad central de la prueba:

    pasivos por beneficios REGISTRADOS + ajuste = pasivos AUDITADOS (recalculados)

El ajuste de cada pasivo es ``recalculado − registrado`` sumado **solo sobre los
empleados/planes con valor registrado informado** (si el cliente no informó el
registrado de una fila, esa fila no genera ajuste — igual criterio que el motor,
que deja su diferencia en blanco). Los pasivos re-derivados y sus campos crudos:

- Décimo tercero por pagar   ← empleados: ``d13`` (recalc) vs ``d13_reg`` (registrado)
- Décimo cuarto por pagar    ← empleados: ``d14`` vs ``d14_reg``
- Provisión de vacaciones    ← empleados: ``vac`` vs ``vac_reg``
- Fondo de reserva           ← empleados: ``fr``  vs ``fr_reg``
- Aporte patronal IESS       ← empleados: ``pat`` vs ``pat_reg``
- Jubilación patronal y desahucio ← actuarial: ``inf`` (DBO del informe) vs ``prov`` (provisión registrada)

La suma de los seis ajustes por componente es el ``ajustePasivos`` declarado. El
importe declarado de cada componente se toma de ``detalle["ajustes"]`` (lo que el
motor propone ajustar) y se coteja contra el re-derivado aquí; si la agregación
del procesador se desvía (un signo, un componente que no suma, un total mal
armado), el cotejo lo marca.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO

# (concepto, dataset del detalle, campo recalculado, campo registrado, clave para
#  casar el importe declarado en detalle["ajustes"]).
_COMPONENTES = (
    ("Décimo tercero por pagar", "empleados", "d13", "d13_reg", "décimo tercero"),
    ("Décimo cuarto por pagar", "empleados", "d14", "d14_reg", "décimo cuarto"),
    ("Provisión de vacaciones", "empleados", "vac", "vac_reg", "vacaciones"),
    ("Fondo de reserva", "empleados", "fr", "fr_reg", "fondo de reserva"),
    ("Aporte patronal IESS", "empleados", "pat", "pat_reg", "aporte patronal"),
    ("Jubilación patronal y desahucio", "actuarial", "inf", "prov", "jubila"),
)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _ajuste_componente(filas, campo_rec, campo_reg):
    """Ajuste re-derivado = Σ (recalculado − registrado) sobre las filas con
    registrado informado. Devuelve ``None`` si ninguna fila lo informó."""
    total = None
    for f in filas or []:
        reg = _num(f.get(campo_reg))
        if reg is None:                      # sin registrado informado → no genera ajuste
            continue
        rec = _num(f.get(campo_rec))
        if rec is None:
            continue
        total = (total or 0.0) + (rec - reg)
    return total


def _declarado_ajuste(ajustes, clave):
    """Importe que el motor propone ajustar para ese pasivo (detalle["ajustes"])."""
    for a in ajustes or []:
        try:
            nombre, importe = a[0], a[1]
        except (TypeError, IndexError, KeyError):
            continue
        if clave in str(nombre).lower():
            return _num(importe)
    return None


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    primary = run.get("primary") or "ajustePasivos"
    ajustes = d.get("ajustes") or []
    datos = {"empleados": d.get("empleados") or [], "actuarial": d.get("actuarial") or []}

    comps = []
    total_rec = None
    for concepto, dataset, campo_rec, campo_reg, clave in _COMPONENTES:
        rec = _ajuste_componente(datos.get(dataset), campo_rec, campo_reg)
        if rec is not None:
            total_rec = (total_rec or 0.0) + rec
            rec = round(rec, 2)
        dec = _declarado_ajuste(ajustes, clave)
        if dec is not None:
            dec = round(dec, 2)
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    recalculado = None if total_rec is None else round(total_rec, 2)
    declarado = _num(tot.get(primary))
    diff = _dif(declarado, recalculado)

    return {
        "etiqueta": run.get("labels", {}).get(primary, "Ajuste propuesto a pasivos laborales"),
        "declarado": declarado,
        "recalculado": recalculado,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
