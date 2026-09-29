"""Recálculo independiente del resultado principal de «Inventarios, producción y costo de ventas».

Re-deriva el **ajuste propuesto** (``totals["ajuste"]``) volviendo a agregar los datos
más crudos de ``run["detalle"]["items"]`` (kardex, conteo, costo, soportes, precio de venta,
fecha de último movimiento…) con una aritmética escrita aparte del procesador, y lo coteja
contra lo que declaró el motor. Es la segunda implementación de la identidad central de la
prueba (NIC 2 · NIIF para las PYMES 13 y 27):

    ajuste = inventario neto auditado − inventario neto en libros
           = (costo auditado − provisión estimada) − (saldo del mayor − provisión registrada)

Partimos de los campos CRUDOS de cada ítem, sin reutilizar los importes ya calculados por el
procesador (``it["costo"]``, ``it["prov"]``, ``it["provBase"]``…):

- **Costo auditado** de cada ítem = cantidad × costo unitario auditado, donde
  cantidad = conteo físico si se contó, si no el kardex (``cc``/``kx``), y costo unitario =
  el soportado por el auditor si existe, si no el registrado (``sop``/``cu``).
- **Provisión estimada** de cada ítem (menor entre costo y VNR; NIC 2.9 / PYMES 13.4):
  se re-arma el VNR desde el precio de venta menos costos de terminación y venta
  (``pv``, ``ct``, ``cv``); la rebaja se limita al costo de la partida; cuando no hay precio
  de venta se estima por antigüedad con los tramos de obsolescencia (días sin movimiento
  re-calculados desde ``fum`` y la fecha de corte con los parámetros ``obsDias``/``obsPct``);
  y se aplica la excepción de NIC 2.32 para materias primas (no se rebajan por debajo del costo
  si el producto terminado asociado se vendería con margen ≥ 0), que en NIIF para las PYMES
  nunca aplica.
- **Saldo del mayor** y **provisión registrada** son entradas del auditor (``parametros``);
  se cotejan como componentes para cubrir también el lado de libros de la identidad.

Cada componente se expone en ``componentes`` con su declarado, recalculado, diff y ok.
Robusto ante operandos faltantes: un campo ausente devuelve ``None`` sin reventar.
"""
from __future__ import annotations

from datetime import date

from backend.app.aud.niif.ciclo.revision.recalc import TOL_RECALCULO


def _num(v):
    if isinstance(v, bool):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fecha(v):
    if isinstance(v, date):
        return v
    if not v:
        return None
    try:
        return date.fromisoformat(str(v)[:10])
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


def _pct_obs(dias, p):
    """% de provisión por antigüedad según el tramo de días sin movimiento (mismos umbrales que el motor)."""
    if dias is None:
        return None
    d1, d2, d3 = _num(p.get("obsDias1")), _num(p.get("obsDias2")), _num(p.get("obsDias3"))
    q1, q2, q3 = _num(p.get("obsPct1")) or 0.0, _num(p.get("obsPct2")) or 0.0, _num(p.get("obsPct3")) or 0.0
    if d3 is not None and dias > d3:
        return q3 / 100
    if d2 is not None and dias > d2:
        return q2 / 100
    if d1 is not None and dias > d1:
        return q1 / 100
    return 0.0


def _costo_y_prov(it, p, corte_a, pymes):
    """Re-deriva (costo auditado, provisión estimada) de un ítem desde sus campos crudos.

    Devuelve ``(None, None)`` si faltan los operandos mínimos (cantidad/costo), para no reventar.
    """
    kx, cc, cu, sop = _num(it.get("kx")), _num(it.get("cc")), _num(it.get("cu")), _num(it.get("sop"))
    cant = cc if cc is not None else kx
    cua = sop if sop is not None else cu
    if cant is None or cua is None:
        return None, None
    costo = cant * cua

    pv = _num(it.get("pv"))
    ct = _num(it.get("ct")) or 0.0
    cv = _num(it.get("cv")) or 0.0

    # Días sin movimiento re-calculados desde la fecha del último movimiento y el corte.
    fum = _fecha(it.get("fum"))
    dias = None if (fum is None or corte_a is None) else (corte_a - fum).days

    # VNR (menor entre costo y VNR); si no hay precio de venta, se estima por antigüedad (tramos).
    if pv is not None:
        vnr = pv - ct - cv
        rebaja_bruta = max(0.0, cua - vnr) * cant
        prov_base = min(costo, rebaja_bruta)
    else:
        pct = _pct_obs(dias, p)
        prov_base = None if pct is None else costo * pct

    # Excepción de NIC 2.32 (materias primas): no se rebajan si el PT asociado se vende con margen ≥ 0.
    pt_c, pt_p = _num(it.get("ptC")), _num(it.get("ptP"))
    pt_margen = None if (pt_c is None or pt_p is None) else pt_p - pt_c
    es_mp = bool(it.get("esMp"))
    excepcion = bool(es_mp and not pymes and pt_margen is not None and pt_margen >= 0)

    prov = 0.0 if excepcion else (prov_base if prov_base is not None else 0.0)
    return costo, prov


def recalcular(run: dict) -> dict:
    d = run.get("detalle") or {}
    tot = run.get("totals") or {}
    p = d.get("parametros") or {}
    items = d.get("items") or []
    pymes = bool(d.get("pymes"))
    corte_a = _fecha(d.get("corte"))

    # Re-agrega el inventario al costo auditado y la provisión estimada, ítem por ítem, desde lo crudo.
    costo_aud = 0.0
    prov_est = 0.0
    vk_t = 0.0
    for it in items:
        vk = _num(it.get("vk"))
        if vk is not None:
            vk_t += vk
        costo, prov = _costo_y_prov(it, p, corte_a, pymes)
        if costo is not None:
            costo_aud += costo
        if prov is not None:
            prov_est += prov
    costo_aud = round(costo_aud, 2)
    prov_est = round(prov_est, 2)

    # Lado de libros: entradas del auditor (mayor y provisión registrada; con sus caídas por defecto).
    saldo_mayor_p = _num(p.get("saldoMayor"))
    mayor = saldo_mayor_p if saldo_mayor_p is not None else round(vk_t, 2)
    prov_reg = _num(p.get("provisionRegistrada")) or 0.0

    inv_neto = round(costo_aud - prov_est, 2)
    libro_neto = round(mayor - prov_reg, 2)
    ajuste = round(inv_neto - libro_neto, 2)

    declarado = _num(tot.get("ajuste"))
    diff = _dif(declarado, ajuste)

    comps = [
        _comp("Inventario al costo auditado (Σ cantidad × costo unitario auditado)",
              _num(tot.get("costoAuditado")), costo_aud),
        _comp("Provisión estimada (rebaja a VNR / obsolescencia, neta de la excepción NIC 2.32)",
              _num(tot.get("provisionEstimada")), prov_est),
        _comp("Inventario neto auditado (costo auditado − provisión estimada)",
              _num(tot.get("inventarioNeto")), inv_neto),
        _comp("Inventario según el mayor", _num(tot.get("saldoMayor")), round(mayor, 2)),
        _comp("Provisión registrada", _num(tot.get("provisionRegistrada")), round(prov_reg, 2)),
        _comp("Inventario neto en libros (mayor − provisión registrada)",
              _num(tot.get("libroNeto")), libro_neto),
    ]

    return {
        "etiqueta": "Ajuste propuesto (inventario neto auditado − neto en libros)",
        "declarado": declarado,
        "recalculado": ajuste,
        "diff": diff,
        "ok": diff is not None and diff <= TOL_RECALCULO,
        "componentes": comps,
    }
