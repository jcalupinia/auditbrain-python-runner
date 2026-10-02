"""Recálculo independiente del resultado principal de «Pérdida crediticia
esperada — enfoque simplificado NIIF 9».

El resultado principal (``totals["ajuste"]``) es el **ajuste propuesto**:

    ajuste = pérdida crediticia esperada − provisión registrada (mayor)

Este módulo re-deriva ese ajuste con una segunda implementación, aparte del
procesador, partiendo de los datos MÁS crudos que expone el ``run``:

- **Pérdida crediticia esperada**: se vuelve a agregar sumando la pérdida
  esperada factura por factura (columna ``pce`` de ``run["rows"]`` — la hoja
  «09_Detalle por factura», el importe por ítem más granular del run). El
  procesador la acumula en ``totals["pce"]``; aquí se re-suma de forma
  independiente, cada factura por su cuenta.
- **Provisión registrada**: es un dato de entrada del auditor (el saldo del
  mayor), tomado de ``run["detalle"]["provisionRegistrada"]`` (o, en su
  defecto, de ``parametros["provisionRegistrada"]``). No es un cálculo; se
  coteja contra ``totals["provisionRegistrada"]``. Si el auditor no lo cargó
  el procesador lo trata como cero (``prov_reg or 0``), así que aquí se hace
  lo mismo para reproducir fielmente la identidad declarada.

Es la segunda implementación de la identidad central de la prueba: si la
agregación del procesador se desvía (una factura que no suma, un signo, la
provisión mal restada), el cotejo lo marca.
"""
from __future__ import annotations

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, dict):
        v = v.get("v")
    if isinstance(v, bool) or v in (None, ""):
        return None
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
    rows = run.get("rows") or []

    # 1 · Pérdida crediticia esperada: re-suma factura por factura (independiente
    #     del acumulado del motor). Una factura sin tasa deja la columna en blanco
    #     y no aporta (igual que ``f["pce"] or 0`` en el procesador).
    if rows:
        pce = round(sum(_num(f.get("pce")) or 0.0 for f in rows), 2)
    else:
        pce = None

    # 2 · Provisión registrada (dato del mayor). None → 0.0 para reproducir la
    #     identidad declarada (``prov_reg or 0``), que es como el motor arma el ajuste.
    prov_reg_raw = d.get("provisionRegistrada")
    if prov_reg_raw is None:
        prov_reg_raw = (d.get("parametros") or {}).get("provisionRegistrada")
    prov_reg = _num(prov_reg_raw)
    prov_reg = prov_reg if prov_reg is not None else 0.0

    # 3 · Ajuste propuesto = pérdida esperada − provisión registrada.
    ajuste = None if pce is None else round(pce - prov_reg, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = [
        _comp("Pérdida crediticia esperada (Σ por factura)", _num(tot.get("pce")), pce),
        _comp("Provisión registrada (mayor)", _num(tot.get("provisionRegistrada")), prov_reg),
        _comp("Ajuste propuesto (PCE − provisión registrada)", _num(tot.get("ajuste")), ajuste),
    ]

    return {
        "etiqueta": "Ajuste propuesto (PCE − provisión registrada)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
