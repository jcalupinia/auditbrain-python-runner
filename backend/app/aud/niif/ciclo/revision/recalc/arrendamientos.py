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


def _dep_acum(t: float, roi: float, md: float, ev) -> float:
    """Depreciación acumulada a ``t`` meses (lineal). Segunda implementación, independiente del procesador."""
    if not md:
        return 0.0
    if not ev:
        return roi * min(t, md) / md
    me, aj, md2 = ev.get("me") or 0, ev.get("ajuste") or 0, ev.get("md2") or md
    if t <= me:
        return roi * min(t, md) / md
    return roi * min(me, md) / md + (roi * (1 - min(me, md) / md) + aj) * min(t - me, md2 - me) / (md2 - me)


def _idiferido_cross(cs: list) -> list:
    """Re-deriva la generación y la reversión del impuesto diferido (en bruto, sobre la vida del contrato)
    a partir de la tabla de amortización (interés y canon) y una depreciación lineal recalculada aparte, y
    la coteja contra lo que declaró el procesador en ``c["idiferido"]``. Si el detalle no trae idiferido o
    tabla, no agrega componentes (robusto)."""
    gen_rec = rev_rec = gen_dec = rev_dec = 0.0
    hay = False
    for c in cs:
        if not isinstance(c, dict):
            continue
        idf = c.get("idiferido")
        tabla = c.get("tabla") or []
        if not idf or not tabla:
            continue
        hay = True
        roi = _num(c.get("activo_ini")) or 0.0
        md = _num(c.get("md")) or 0.0
        m = _num(c.get("m")) or 1.0
        ev = c.get("ev")
        for x in tabla:
            j = _num(x.get("j")) or 0
            dep = _dep_acum(j * m, roi, md, ev) - _dep_acum((j - 1) * m, roi, md, ev)
            dif = dep + (_num(x.get("interes")) or 0.0) - (_num(x.get("pago")) or 0.0)
            if dif > 0:
                gen_rec += dif
            else:
                rev_rec += dif
        gen_dec += _num(idf.get("gen")) or 0.0
        rev_dec += _num(idf.get("rev")) or 0.0
    if not hay:
        return []
    out = []
    for concepto, dec, rec in (("Generación de diferencias temporarias (bruto, vida del contrato)", gen_dec, round(gen_rec, 2)),
                               ("Reversión de diferencias temporarias (bruto, vida del contrato)", rev_dec, round(rev_rec, 2))):
        dc = _dif(dec, rec)
        out.append({"concepto": concepto, "declarado": round(dec, 2) if dec is not None else None,
                    "recalculado": rec, "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO})
    return out


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

    comps += _idiferido_cross(cs)  # cruce independiente del impuesto diferido (NIC 12)

    return {
        "etiqueta": "Ajuste propuesto al pasivo (recalculado − registrado)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
