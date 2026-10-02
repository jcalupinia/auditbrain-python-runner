"""Recálculo independiente del resultado principal de «Préstamos y obligaciones financieras».

Re-deriva el **ajuste propuesto al pasivo** (``totals["ajuste"]``, que es
``run["primary"]``) volviendo a agregar el detalle préstamo por préstamo de
``run["detalle"]["prestamos"]`` con una suma escrita aparte del procesador. Es la
segunda implementación de la identidad central de la prueba:

    pasivo registrado + ajuste = pasivo auditado

donde el pasivo auditado del rubro se reparte en corriente + no corriente
(NIC 1 69–76). El ajuste se re-arma como::

    ajuste = (corriente + no corriente) − registrado

Campos crudos de cada préstamo (``detalle["prestamos"][i]``) desde los que parte:

- ``saldo_reg``  → capital registrado por el cliente.
- ``int_reg``    → intereses por pagar registrados (puede ser ``None``).
  El **pasivo registrado** se re-suma como ``saldo_reg + (int_reg or 0)``, sin
  reutilizar el ``reg_tot`` que ya calculó el procesador.
- ``cp``         → porción corriente auditada del préstamo (costo amortizado que
  vence en 12 meses, o todo el saldo si un covenant exigible reclasifica).
- ``lp``         → porción no corriente auditada del préstamo.
  El **pasivo auditado** se re-suma como ``cp + lp`` (que reconstruye el costo
  amortizado ``ca_tot`` desde su reparto corriente/no corriente), sin leer el
  ``ca_tot`` ni el ``ajuste`` ya calculados.

Si la agregación del procesador se desvía (un signo, un préstamo que no suma, un
reparto corriente/no corriente que no cierra contra el auditado), el cotejo lo marca.
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
    prestamos = d.get("prestamos") or []

    # Re-agrega préstamo por préstamo desde los campos más crudos, sin redondear
    # cada parcial (para no arrastrar ruido de centavos al restar los agregados).
    registrado = auditado = corriente = nocorriente = 0.0
    for c in prestamos:
        saldo = _num(c.get("saldo_reg")) or 0.0
        interes = _num(c.get("int_reg")) or 0.0
        cp = _num(c.get("cp")) or 0.0
        lp = _num(c.get("lp")) or 0.0
        registrado += saldo + interes
        corriente += cp
        nocorriente += lp
        auditado += cp + lp                       # = costo amortizado re-armado

    registrado_r = round(registrado, 2)
    corriente_r = round(corriente, 2)
    nocorriente_r = round(nocorriente, 2)
    auditado_r = round(auditado, 2)
    # El ajuste sale de los agregados sin redondear, redondeado una sola vez.
    ajuste_r = round(auditado - registrado, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste_r)

    comps = [
        _comp("Pasivo registrado (capital + intereses)", _num(tot.get("pasivoRegistrado")), registrado_r),
        _comp("Pasivo corriente auditado", _num(tot.get("corriente")), corriente_r),
        _comp("Pasivo no corriente auditado", _num(tot.get("noCorriente")), nocorriente_r),
        _comp("Pasivo auditado (corriente + no corriente)", _num(tot.get("pasivo")), auditado_r),
        _comp("Ajuste propuesto (auditado − registrado)", declarado, ajuste_r),
    ]

    return {
        "etiqueta": "Ajuste propuesto al pasivo (auditado − registrado)",
        "declarado": declarado,
        "recalculado": ajuste_r,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
