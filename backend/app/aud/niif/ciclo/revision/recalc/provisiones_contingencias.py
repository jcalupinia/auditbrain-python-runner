"""Recálculo independiente del resultado principal de «Provisiones y contingencias».

Re-deriva el **ajuste propuesto** (``totals["ajusteProvisiones"] = requerida − libros``)
volviendo a agregar el detalle por partida de ``run["detalle"]["provisiones"]`` con una
segunda implementación, escrita aparte del procesador, de la identidad central de la
prueba:

    provisiones en libros + ajuste = provisiones auditadas (requeridas)

y de su regla de reconocimiento (NIC 37.14, 23): **una provisión solo se reconoce si la
salida de recursos es probable**; el pasivo contingente (posible) o la salida remota se
revelan pero no se provisionan, así que su provisión requerida es cero.

Parte de los campos más crudos que el procesador deja por partida en el ``detalle``:
``naturaleza`` (pasivo/activo), ``clasif`` (la clasificación de obligación y
probabilidad de la hoja 05/13), ``vp`` (valor presente de la mejor estimación, hoja 07)
y ``saldo_libros`` (lo registrado). Por cada **partida de pasivo** re-deriva su provisión
requerida —``vp`` si se reconoce, ``0`` si es contingente o remota, ``None`` si quedó sin
evaluación— y su ajuste ``requerida − libros``; luego los suma. Si la agregación del motor
se desvía (un signo, una partida que no suma, un reconocimiento mal clasificado), el cotejo
lo marca.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO

# Clasificaciones de la hoja 13 que llevan a reconocer la provisión (usar el valor presente).
_RECONOCE = ("Reconocer provisión", "Activo reconocible")


def _num(v):
    if isinstance(v, dict):
        v = v.get("v")
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _requerida(clasif: str, vp):
    """Provisión requerida re-derivada (NIC 37.14, 23): valor presente si se reconoce,
    0 si es contingente o remota, None si la partida quedó sin evaluación."""
    if clasif == "Sin evaluación":
        return None
    if clasif in _RECONOCE:
        return vp
    return 0.0


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    labels = run.get("labels") or {}
    primary = run.get("primary") or "ajusteProvisiones"
    provisiones = d.get("provisiones") or []

    # Solo los pasivos entran en el ajuste principal (los activos contingentes van aparte).
    pas = [r for r in provisiones if (r or {}).get("naturaleza") == "Pasivo"]

    libros = 0.0
    requerida = 0.0
    ajuste = 0.0
    for r in pas:
        lib = _num(r.get("saldo_libros"))
        req = _requerida(r.get("clasif"), _num(r.get("vp")))
        libros += lib or 0.0
        requerida += req or 0.0
        # Ajuste por partida = requerida − libros (se omite si la partida quedó sin evaluar,
        # igual que el motor, que no suma las diferencias None).
        if req is not None and lib is not None:
            ajuste += req - lib
    libros = round(libros, 2)
    requerida = round(requerida, 2)
    ajuste = round(ajuste, 2)

    declarado = _num(tot.get(primary))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Provisiones registradas en libros", libros, "librosProvisiones"),
        ("Provisión requerida (NIC 37 · Secc. 21)", requerida, "provisionRequerida"),
        ("Ajuste propuesto (requerida − libros)", ajuste, primary),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": labels.get(primary) or "Ajuste propuesto (requerida − libros)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
