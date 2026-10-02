"""Recálculo independiente del resultado principal de «Impuesto corriente y diferido».

Re-deriva el **ajuste neto al gasto por impuesto en resultados**
(``totals[run["primary"]]`` = ``totals["ajusteResultados"]``) sumando sus tres
componentes, cada uno re-armado aquí con aritmética propia desde los campos
CRUDOS de ``run["detalle"]`` —sin reutilizar el ``ajusteResultados`` que calculó
el procesador—. Es una segunda implementación de la identidad central de la
prueba: si el procesador desvía un signo, una tarifa o un saldo, el cotejo lo marca.

Identidad re-derivada (procesador ``impuesto_corriente_diferido``)::

    impuesto corriente auditado  = base imponible auditada × tarifa           (NIC 12; LRTI art. 37)
    ajuste corriente             = impuesto corriente auditado − impuesto corriente registrado
    ajuste diferido a resultados = Σ (requerido − registrado) de las partidas del
                                   movimiento del diferido que van a resultados (no ORI)  (NIC 12.58)
    gasto por variación de saldos = − Σ (cierre − inicio) de esas mismas partidas
    reclasificación a ORI        = gasto diferido registrado − gasto por variación de saldos
    ajuste neto a resultados     = ajuste corriente − ajuste diferido a resultados − reclasificación a ORI

Campos crudos usados de ``detalle``: ``au["base"]`` (base imponible auditada) y
``tarifa`` (tarifa general + recargo del año de reversión, NIC 12.47) para
recalcular el impuesto corriente auditado; ``irEf`` (impuesto corriente
registrado); ``mov`` (movimiento del diferido por bloque: ``req``, ``cie``,
``ini`` y la marca ``ori``); y ``num["gastoDiferidoRegistrado"]``. La aritmética
es propia: multiplicación base × tarifa y agregación de las partidas, sin leer el
``ajusteResultados`` del motor.
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


def _comp(concepto, dec, rec):
    dc = _dif(dec, rec)
    return {"concepto": concepto, "declarado": dec, "recalculado": rec,
            "diff": dc, "ok": dc is not None and dc <= TOL_RECALCULO}


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    au = d.get("au") or {}
    num = d.get("num") or {}
    mov = d.get("mov") or []
    primary = run.get("primary") or "ajusteResultados"

    tarifa = _num(d.get("tarifa"))
    base_aud = _num(au.get("base"))
    ir_reg = _num(d.get("irEf"))                        # impuesto corriente registrado
    gdr = _num(num.get("gastoDiferidoRegistrado"))      # gasto diferido registrado en resultados

    # 1 · Impuesto corriente auditado = base imponible auditada × tarifa (aritmética propia).
    ir_aud = None
    if base_aud is not None and tarifa is not None:
        ir_aud = round(max(base_aud, 0.0) * tarifa / 100.0, 2)

    # 2 · Ajuste corriente = auditado − registrado.
    aj_corr = None
    if ir_aud is not None and ir_reg is not None:
        aj_corr = round(ir_aud - ir_reg, 2)

    # 3 · Movimiento del diferido: solo los bloques que van a resultados (no ORI).
    no_ori = [x for x in mov if not x.get("ori")]
    # Ajuste diferido a resultados = Σ (requerido − registrado) de esas partidas.
    aj_dif_res = round(sum((_num(x.get("req")) or 0.0) - (_num(x.get("cie")) or 0.0) for x in no_ori), 2)
    # Gasto por la variación de los saldos registrados sin ORI = − Σ (cierre − inicio).
    gasto_dif_saldos = round(-sum((_num(x.get("cie")) or 0.0) - (_num(x.get("ini")) or 0.0) for x in no_ori), 2)

    # 4 · Reclasificación a ORI = gasto diferido registrado − gasto por variación de saldos.
    #     Sin gasto diferido registrado no hay reclasificación (como en el procesador).
    reclas = 0.0 if gdr is None else round(gdr - gasto_dif_saldos, 2)

    # 5 · Ajuste neto a resultados = corriente − diferido a resultados − reclasificación a ORI.
    aj_res = None
    if aj_corr is not None:
        aj_res = round(aj_corr - aj_dif_res - reclas, 2)

    declarado = _num(tot.get(primary))
    diff = _dif(declarado, aj_res)

    comps = [
        _comp("Impuesto corriente auditado (base imponible auditada × tarifa)",
              _num(tot.get("impuestoCorrienteAuditado")), ir_aud),
        _comp("Ajuste corriente (auditado − registrado)",
              _num(tot.get("ajusteCorriente")), aj_corr),
        _comp("Ajuste diferido a resultados (requerido − registrado)",
              _num(tot.get("ajusteDiferidoResultados")), aj_dif_res),
        _comp("Reclasificación a ORI del diferido",
              _num(tot.get("reclasificacionORI")), reclas),
        _comp("Ajuste neto al gasto por impuesto en resultados",
              declarado, aj_res),
    ]

    etiqueta = (run.get("labels") or {}).get(primary) or "Ajuste neto al gasto por impuesto en resultados"
    return {
        "etiqueta": etiqueta,
        "declarado": declarado,
        "recalculado": aj_res,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
