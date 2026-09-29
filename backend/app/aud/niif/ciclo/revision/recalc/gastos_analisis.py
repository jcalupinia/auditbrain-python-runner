"""Recálculo independiente del resultado principal de «Gastos: análisis».

Re-deriva el **ajuste propuesto al gasto (neto)** (``totals["ajusteGasto"]``,
``run["primary"]``) volviendo a agregar los comprobantes crudos de la muestra en
``run["detalle"]["trans"]`` con aritmética escrita aparte del procesador. Es la
segunda implementación de la identidad central de la prueba (M09):

    ajuste = gastos del ejercicio no registrados al corte
             + gastos devengados no registrados
             − gastos de otro período registrados al corte
             − gastos anticipados llevados a resultados

Partiendo de los campos MÁS crudos de cada transacción —importe, fecha de
documento (``fdoc``), fecha de registro (``freg``), período del servicio
(``desde``/``hasta``) y la fecha de corte del encargo
(``detalle["cortes"]["actual"]``)— se vuelve a decidir, comprobante a
comprobante, si su importe (o su porción devengada por días) alimenta cada uno
de los cuatro componentes, sin reutilizar los campos ya calculados por el motor
(``noRegistrado``, ``otroPeriodo``, ``anticipado``, ``devNoReg``). Si la
agregación del procesador se desvía (un signo, una fecha mal comparada, un
prorrateo por días erróneo, un comprobante que no suma), el cotejo lo marca.

Corte (comprobantes sin período de servicio; NIC 1 27–28):
- documento del ejercicio (``fdoc`` ≤ corte) registrado después del corte
  (``freg`` > corte) → gasto del ejercicio no registrado;
- documento posterior al corte (``fdoc`` > corte) registrado en el ejercicio
  (``freg`` ≤ corte) → gasto de otro período.

Devengo (comprobantes con período de servicio; NIC 1 27–28, PYMES 2.36):
- días del servicio = (hasta − desde) + 1; días hasta el corte prorratean el
  importe. Registrado en el ejercicio → la porción posterior al corte es gasto
  anticipado; registrado después → la porción del período es devengado no
  registrado.
"""
from __future__ import annotations

import datetime

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fecha(v):
    """Fecha ISO (o ``date``) → ``datetime.date``; ``None`` si falta o no parsea."""
    if v is None or v == "":
        return None
    if isinstance(v, datetime.date):
        return v
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    trans = d.get("trans") or []
    corte = _fecha((d.get("cortes") or {}).get("actual"))

    no_reg = otro = antic = dev_nr = 0.0
    for t in trans:
        imp = _num(t.get("importe"))
        if imp is None:
            continue
        desde, hasta = _fecha(t.get("desde")), _fecha(t.get("hasta"))
        freg = _fecha(t.get("freg"))
        # «Registrado en el ejercicio»: la fecha de registro cae hasta el corte.
        en_periodo = corte is not None and freg is not None and freg <= corte

        if desde is None or hasta is None:
            # Sin período de servicio → prueba de corte por fecha de documento.
            fdoc = _fecha(t.get("fdoc"))
            doc_en_periodo = corte is not None and fdoc is not None and fdoc <= corte
            if doc_en_periodo and not en_periodo:
                no_reg += imp          # documento del ejercicio registrado tras el corte
            elif (not doc_en_periodo) and en_periodo and fdoc is not None:
                otro += imp            # documento posterior registrado en el ejercicio
        else:
            # Con período de servicio → devengo por días.
            if corte is None or hasta < desde:
                continue
            dias = (hasta - desde).days + 1
            if dias <= 0:
                continue
            dias_periodo = max(0, (min(hasta, corte) - desde).days + 1)
            dias_post = dias - dias_periodo
            gasto_periodo = imp * dias_periodo / dias
            if en_periodo:
                antic += imp * dias_post / dias   # porción posterior al corte
            else:
                dev_nr += gasto_periodo           # porción del período no registrada

    no_reg = round(no_reg, 2)
    otro = round(otro, 2)
    antic = round(antic, 2)
    dev_nr = round(dev_nr, 2)
    ajuste = round(no_reg + dev_nr - otro - antic, 2)

    declarado = _num(tot.get("ajusteGasto"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Gastos del ejercicio no registrados (corte)", no_reg, "noRegistradoCorte"),
        ("Gastos devengados no registrados", dev_nr, "devengadoNoRegistrado"),
        ("Gastos de otro período registrados (corte)", otro, "otroPeriodo"),
        ("Gastos anticipados llevados a resultados", antic, "anticipado"),
        ("Ajuste propuesto al gasto (neto)", ajuste, "ajusteGasto"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste propuesto al gasto (neto)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
