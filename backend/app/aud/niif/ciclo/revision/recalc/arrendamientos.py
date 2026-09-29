"""Recálculo independiente del resultado principal de «Arrendamientos» (NIIF 16 / Sección 20).

Re-deriva el **ajuste propuesto al pasivo** (``totals["ajuste"] = pasivo − registrado``,
el ``primary`` de la prueba) volviendo a agregar el detalle **contrato por contrato** de
``run["detalle"]["contratos"]`` con una suma escrita aparte del procesador, y lo coteja
contra lo que declaró el motor. Es la segunda implementación de la identidad central del
rubro: **pasivo por arrendamiento registrado + ajuste = pasivo recalculado (auditado)**.

De dónde se parte (campos más crudos disponibles en el detalle):
- ``c["pasivo"]``     → pasivo por arrendamiento recalculado al corte de cada contrato
                        (0 en los contratos exentos / operativos que no se reconocen).
- ``c["pasivo_reg"]`` → pasivo por arrendamiento registrado en el mayor (dato del cliente).

El procesador arma el total como ``T("pasivo") − T("pasivo_reg")`` (suma y luego resta a
nivel de rubro). Aquí se re-agrega por separado el pasivo recalculado y el registrado y se
vuelve a restar; si la agregación del motor se desviara (un contrato que no suma, un signo,
un total mal armado), el cotejo lo marca. No se copia ``totals["ajuste"]``: se re-deriva.

Si el detalle no trae contratos, se cae a ``run["rows"]`` (las mismas cifras por contrato
que ve el auditor en la consola). Es robusto ante operandos faltantes: devuelve ``None`` en
lugar de reventar.
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


def _contratos(run: dict) -> list:
    """Filas por contrato desde el detalle; si falta, desde ``rows`` (la consola)."""
    d = run.get("detalle") or {}
    cs = d.get("contratos")
    if cs:
        return cs
    return run.get("rows") or []


def recalcular(run: dict) -> dict:
    tot = run.get("totals") or {}
    cs = _contratos(run)

    # Re-agrega pasivo recalculado y registrado contrato por contrato, independiente
    # del acumulado del motor (que suma primero y resta el total).
    pasivo = round(sum(_num(c.get("pasivo")) or 0.0 for c in cs), 2)
    registrado = round(sum(_num(c.get("pasivo_reg")) or 0.0 for c in cs), 2)
    ajuste = round(pasivo - registrado, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = []
    for concepto, rec, clave in (
        ("Pasivo por arrendamiento recalculado", pasivo, "pasivo"),
        ("Pasivo por arrendamiento registrado (mayor)", registrado, "pasivoRegistrado"),
        ("Ajuste propuesto al pasivo (recalculado − registrado)", ajuste, "ajuste"),
    ):
        dec = _num(tot.get(clave))
        dc = _dif(dec, rec)
        comps.append({"concepto": concepto, "declarado": dec, "recalculado": rec,
                      "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})

    return {
        "etiqueta": "Ajuste propuesto al pasivo (recalculado − registrado)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
