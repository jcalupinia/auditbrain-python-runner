"""Recálculo independiente del resultado principal de «Intangibles y goodwill».

Re-deriva el **ajuste propuesto** (``totals["ajuste"] = neto auditado − neto según el
mayor``) volviendo a agregar el detalle por partida de ``run["detalle"]["items"]`` con
una aritmética escrita aparte del procesador, y lo coteja contra lo que declaró el
motor. Es la segunda implementación de la identidad central de la prueba
(neto auditado vs saldo mayor = ajuste): si la agregación del procesador se desvía
(un signo, una partida que no suma, un total mal armado, el saldo del mayor mal
tomado), el cotejo lo marca.

Desde qué campos CRUDOS se parte (por partida, en ``items``):

* **Neto según el auxiliar del cliente** (``netoAuxiliar``): se re-arma partida por
  partida desde los importes tal como los registró el cliente —
  ``libros = costo − amort. acum. inicial (aai) − amort. registrada (areg)
  − deterioro acum. (det) − deterioro registrado (dreg) + reversión registrada (rreg)`` —
  y se suman. Es la derivación más cruda (solo entradas del auxiliar).
* **Neto auditado** (``netoAuditado``): se re-arma el valor neto auditado de cada
  partida desde sus componentes auditados —
  ``aud = 0`` si la partida no es capitalizable (``cap == "No"``); si no,
  ``aud = costo auditado (costoAud) − amort. acumulada auditada (aai + amortAud)
  − deterioro acum. (det) − deterioro del año auditado (detAud)
  + reversión auditada (revAud)`` — con la acumulación ``aai + amortAud`` re-hecha
  aquí, sin reutilizar el campo ``aud`` del procesador — y se suman.
* **Neto según el mayor** (``saldoMayor``): el parámetro del auditor
  (``detalle["parametros"]["saldoMayor"]``); si está en blanco, el neto del auxiliar
  re-derivado arriba (misma regla del procesador).
* **Ajuste propuesto** (``ajuste``, resultado principal): ``netoAuditado − saldoMayor``.

No se copia ``totals["ajuste"]``: se re-deriva desde el detalle. Robusto ante
operandos faltantes (un componente sin dato → ``diff = None`` y la fila queda no
conforme, sin reventar).
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    """Número o ``None`` (no revienta ante texto/vacío/None)."""
    if isinstance(v, dict):
        v = v.get("v")
    if isinstance(v, bool) or v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _n0(v) -> float:
    """Operando aritmético: dato ausente → 0.0 (igual que ``x or 0`` en el procesador)."""
    n = _num(v)
    return n if n is not None else 0.0


def _dif(dec, rec):
    if dec is None or rec is None:
        return None
    return round(abs(dec - rec), 2)


def _es_no(cap) -> bool:
    """La partida NO es capitalizable (``cap == "No"``): su neto auditado es cero."""
    return str(cap if cap is not None else "").strip().lower().startswith("n")


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    items = d.get("items") or []
    par = d.get("parametros") or {}

    # --- neto según el auxiliar del cliente: desde los importes crudos del auxiliar ---
    # libros = costo − aai − areg − det − dreg + rreg  (misma regla, aritmética aparte).
    neto_auxiliar = round(
        sum(_n0(x.get("costo")) - _n0(x.get("aai")) - _n0(x.get("areg"))
            - _n0(x.get("det")) - _n0(x.get("dreg")) + _n0(x.get("rreg"))
            for x in items),
        2,
    )

    # --- neto auditado: re-armado por partida desde sus componentes auditados ---
    # aud = 0 si no es capitalizable; si no, costoAud − (aai + amortAud) − det − detAud + revAud.
    neto_auditado = round(
        sum(0.0 if _es_no(x.get("cap")) else
            _n0(x.get("costoAud"))
            - (_n0(x.get("aai")) + _n0(x.get("amortAud")))
            - _n0(x.get("det")) - _n0(x.get("detAud")) + _n0(x.get("revAud"))
            for x in items),
        2,
    )

    # --- neto según el mayor: parámetro del auditor, o el auxiliar si viene en blanco ---
    saldo_mayor_param = _num(par.get("saldoMayor"))
    saldo_mayor = saldo_mayor_param if saldo_mayor_param is not None else neto_auxiliar

    # --- ajuste propuesto (resultado principal) ---
    ajuste = round(neto_auditado - saldo_mayor, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Neto según el auxiliar (Σ costo − amort − deterioro + reversión por partida)", neto_auxiliar, "netoAuxiliar"),
        ("Intangibles netos auditados (Σ neto auditado por partida)", neto_auditado, "netoAuditado"),
        ("Intangibles netos según el mayor (parámetro del auditor)", saldo_mayor, "saldoMayor"),
        ("Ajuste propuesto (neto auditado − mayor)", ajuste, "ajuste"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste propuesto (neto auditado − mayor)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
