"""Recálculo independiente del resultado principal de «Patrimonio».

Re-deriva el **ajuste neto propuesto al patrimonio** (``totals["ajusteNeto"]``) volviendo
a agregar los datos crudos de ``run["detalle"]`` con una aritmética escrita aparte del
procesador, y lo coteja contra lo que declaró el motor. Es la segunda implementación de la
identidad central de la prueba:

    patrimonioAuditado = patrimonioCliente + ajusteNeto

donde el ajuste es la suma con signo de las reclasificaciones patrimoniales que el
procesador detecta al recorrer las actas y transacciones (``run["detalle"]["txs"]``):

    ajusteNeto = − aportesPasivo − instrumentosPasivo + dividendosPosterioresPasivo

Cada componente se re-arma aquí desde los campos MÁS crudos de cada transacción, sin
reutilizar los importes ya enrutados por el procesador (``aportePasivo``, ``instrPasivo``,
``divPostPasivo``):

- ``aportesPasivo``  — aportes con obligación de devolución: se toma el ``importe`` de toda
  transacción de ``tipo == "Aporte"`` con ``devolucion == "Sí"`` (NIC 32 11, 15–16, 18 a);
  van a pasivo financiero, no a patrimonio.
- ``instrumentosPasivo`` — instrumentos con obligación contractual de entregar efectivo:
  ``importe`` de toda transacción con ``obligacion == "Sí"`` que no sea ya un aporte a pasivo
  (p. ej. acciones preferentes rescatables); reclasificar a pasivo.
- ``dividendosPosterioresPasivo`` — dividendos declarados después del cierre registrados como
  pasivo al corte: ``importe`` de todo ``tipo == "Dividendo declarado"`` cuya fecha efectiva
  (acta o, en su defecto, la fecha de la transacción) es posterior al corte y con
  ``pasivoCorte == "Sí"``; no existía obligación al cierre, se revierte contra el patrimonio
  (NIC 10 12–13). Por eso suma (+) al ajuste, mientras las dos primeras restan (−).

El patrimonio según cliente se re-agrega como la suma del ``final`` de cada cuenta patrimonial
(``run["detalle"]["cuentas"]``). Todos los operandos se toman con tolerancia a datos faltantes:
un campo ausente no revienta, aporta 0 a su suma.
"""
from __future__ import annotations

import datetime

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


def _fecha(v):
    """Fecha ISO (``YYYY-MM-DD``) → ``date``; cualquier otra cosa → ``None``."""
    if isinstance(v, datetime.date):
        return v
    if not v:
        return None
    try:
        return datetime.date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _es_si(v):
    return str(v or "").strip().lower() in {"sí", "si", "s", "x", "yes", "y", "1", "true", "verdadero"}


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    cuentas = d.get("cuentas") or []
    txs = d.get("txs") or []
    corte = _fecha(((d.get("cortes") or {}).get("actual")))

    # Patrimonio según cliente: re-agrega el saldo final de cada cuenta patrimonial.
    cliente = round(sum(_num(c.get("final")) or 0.0 for c in cuentas), 2)

    # Componentes del ajuste re-armados desde los campos crudos de cada transacción.
    aportes_pasivo = 0.0
    instr_pasivo = 0.0
    div_post_pasivo = 0.0
    for t in txs:
        imp = _num(t.get("importe")) or 0.0
        tipo = str(t.get("tipo") or "").strip()
        es_aporte_pasivo = tipo == "Aporte" and _es_si(t.get("devolucion"))
        if es_aporte_pasivo:
            aportes_pasivo += imp
        # Instrumento con obligación contractual (que no sea ya un aporte a pasivo).
        elif _es_si(t.get("obligacion")):
            instr_pasivo += imp
        # Dividendo declarado después del cierre registrado como pasivo al corte.
        if tipo == "Dividendo declarado" and _es_si(t.get("pasivoCorte")):
            efectiva = _fecha(t.get("fechaActa")) or _fecha(t.get("fecha"))
            posterior = bool(corte and efectiva and efectiva > corte)
            if posterior:
                div_post_pasivo += imp

    aportes_pasivo = round(aportes_pasivo, 2)
    instr_pasivo = round(instr_pasivo, 2)
    div_post_pasivo = round(div_post_pasivo, 2)

    ajuste = round(-aportes_pasivo - instr_pasivo + div_post_pasivo, 2)
    auditado = round(cliente + ajuste, 2)

    declarado = _num(tot.get("ajusteNeto"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Patrimonio según cliente", cliente, "patrimonioCliente"),
        ("Aportes con obligación de devolución (a pasivo)", aportes_pasivo, "aportesPasivo"),
        ("Instrumentos con obligación contractual (a pasivo)", instr_pasivo, "instrumentosPasivo"),
        ("Dividendos posteriores registrados como pasivo (revertir)", div_post_pasivo, "dividendosPosterioresPasivo"),
        ("Patrimonio auditado", auditado, "patrimonioAuditado"),
        ("Ajuste neto propuesto al patrimonio", ajuste, "ajusteNeto"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste neto propuesto al patrimonio",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
